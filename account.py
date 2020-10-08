# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import urllib
import uuid

import braintree
from braintree.exceptions import TooManyRequestsError, GatewayTimeoutError
from braintree.exceptions.braintree_error import BraintreeError

from trytond.cache import Cache
from trytond.config import config
from trytond.i18n import gettext
from trytond.model import (
    ModelSQL, ModelView, DeactivableMixin, Workflow, fields)
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool
from trytond.report import Report
from trytond.transaction import Transaction
from trytond.url import http_host
from trytond.wizard import (
    Wizard, StateAction, StateView, StateTransition, Button)

from trytond.modules.account_payment.exceptions import (
    ProcessError, PaymentValidationError)

logger = logging.getLogger(__name__)

SUCCEEDED_STATUSES = {braintree.Transaction.Status.Settled}
FAILED_STATUSES = {
    braintree.Transaction.Status.AuthorizationExpired,
    braintree.Transaction.Status.SettlementDeclined,
    braintree.Transaction.Status.Failed,
    braintree.Transaction.Status.GatewayRejected,
    braintree.Transaction.Status.ProcessorDeclined,
    braintree.Transaction.Status.Voided,
    }
DISPUTE_FINAL_STATUSES = {
    braintree.Dispute.Status.Expired,
    braintree.Dispute.Status.Won,
    braintree.Dispute.Status.Lost,
    }


class PaymentJournal(metaclass=PoolMeta):
    __name__ = 'account.payment.journal'

    braintree_account = fields.Many2One(
        'account.payment.braintree.account', "Account", ondelete='RESTRICT',
        domain=[
            ('currency', '=', Eval('currency')),
            ],
        states={
            'required': Eval('process_method') == 'braintree',
            'invisible': Eval('process_method') != 'braintree',
            },
        depends=['currency', 'process_method'])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        braintree_method = ('braintree', "Braintree")
        if braintree_method not in cls.process_method.selection:
            cls.process_method.selection.append(braintree_method)


class PaymentGroup(metaclass=PoolMeta):
    __name__ = 'account.payment.group'

    def process_braintree(self):
        pool = Pool()
        Payment = pool.get('account.payment')
        for payment in self.payments:
            if not payment.braintree_nonce and not payment.braintree_customer:
                account = payment.journal.braintree_account
                for customer in payment.party.braintree_customers:
                    if (customer.braintree_account == account
                            and customer.braintree_customer_id):
                        payment.braintree_customer = customer
                        break
                else:
                    raise ProcessError(
                        gettext(
                            'account_payment_braintree.msg_no_braintree_nonce',
                            payment=payment.rec_name))
        Payment.save(self.payments)
        Payment.__queue__.braintree_transact(self.payments)


class CheckoutMixin:
    braintree_checkout_id = fields.Char("Braintree Checkout ID", readonly=True)
    braintree_client_token = fields.Char(
        "Braintree Client Token", readonly=True)
    braintree_nonce = fields.Char(
        "Braintree Nonce", readonly=True,
        states={
            'invisible': ~Eval('braintree_nonce'),
            })
    braintree_device_data = fields.Char(
        "Braintree Device Data", readonly=True,
        states={
            'invisible': ~Eval('device_data'),
            })

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('braintree_checkout_id')
        default.setdefault('braintree_client_token', None)
        default.setdefault('braintree_nonce', None)
        default.setdefault('braintree_device_data', None)
        return super().copy(records, default=default)

    @classmethod
    @ModelView.button_action('account_payment_braintree.wizard_checkout')
    def braintree_checkout(cls, records):
        for record in records:
            record.braintree_checkout_id = uuid.uuid4().hex
        cls.save(records)

    @property
    def braintree_checkout_url(self):
        pool = Pool()
        database = Transaction().database.name
        Checkout = pool.get(
            'account.payment.braintree.checkout', type='wizard')
        action = Checkout.checkout.get_action()
        return action['url'] % {
            'http_host': http_host(),
            'database': database,
            'model': self.__class__.__name__,
            'id': self.braintree_checkout_id,
            }

    def braintree_set_nonce(self, nonce, device_data=None):
        self.braintree_nonce = nonce
        self.device_data = device_data
        self.save()


class Payment(CheckoutMixin, metaclass=PoolMeta):
    __name__ = 'account.payment'

    braintree_account = fields.Function(fields.Many2One(
            'account.payment.braintree.account', "Braintree Account"),
        'on_change_with_braintree_account')

    braintree_customer = fields.Many2One(
        'account.payment.braintree.customer', "Braintree Customer",
        domain=[
            ('party', '=', Eval('party', -1)),
            ('braintree_account', '=', Eval('braintree_account', -1)),
            ],
        states={
            'invisible': Eval('process_method') != 'braintree',
            'readonly': (~Eval('state').in_(['draft', 'approved'])
                | Eval('braintree_nonce')),
            },
        depends=['party', 'braintree_account', 'process_method',
            'braintree_nonce', 'state'])
    braintree_customer_method = fields.Char(
        "Braintree Customer Method",
        states={
            'invisible': ((Eval('process_method') != 'braintree')
                | Eval('braintree_nonce')
                | ~Eval('braintree_customer')),
            'readonly': ~Eval('state').in_(['draft', 'approved']),
            },
        depends=[
            'process_method',
            'braintree_nonce',
            'braintree_customer',
            'state'])
    # Use Function field with selection
    # to avoid querying Braintree on validation
    braintree_customer_method_selection = fields.Function(fields.Selection(
            'get_braintree_customer_methods', "Braintree Customer Method",
            states={
                'invisible': ((Eval('process_method') != 'braintree')
                    | Eval('braintree_nonce')
                    | ~Eval('braintree_customer')),
                'readonly': ~Eval('state').in_(['draft', 'approved']),
                },
            depends=[
                'process_method',
                'braintree_nonce',
                'braintree_customer',
                'state']),
        'get_braintree_customer_method',
        setter='set_braintree_customer_method')

    braintree_transaction_id = fields.Char(
        "Braintree Transaction ID", readonly=True,
        states={
            'invisible': ((Eval('process_method') != 'braintree')
                | ~Eval('braintree_transaction_id')),
            },
        depends=['process_method'])
    braintree_settle_payment = fields.Boolean(
        "Braintree Settle Payment",
        states={
            'invisible': Eval('process_method') != 'braintree',
            'readonly': Eval('state') != 'draft',
            },
        depends=['process_method', 'state'])
    braintree_payment_settled = fields.Boolean(
        "Braintree Payment Settled", readonly=True)
    braintree_settlement_needed = fields.Function(
        fields.Boolean("Braintree Settlement Needed"),
        'get_braintree_settlement_needed')

    braintree_refunds = fields.One2Many(
        'account.payment.braintree.refund', 'payment', "Refunds",
        states={
            'invisible': ((Eval('process_method') != 'braintree')
                | ~Eval('braintree_transaction_id')),
            },
        depends=['process_method', 'braintree_transaction_id'])

    braintree_dispute_reason = fields.Char(
        "Braintree Dispute Reason", readonly=True,
        states={
            'invisible': ~Eval('braintree_dispute_reason'),
            })
    braintree_dispute_status = fields.Char(
        "Braintree Dispute Status", readonly=True,
        states={
            'invisible': ~Eval('braintree_dispute_status'),
            })

    braintree_error_message = fields.Text(
        "Braintree Error Message", readonly=True,
        states={
            'invisible': ~Eval('braintree_error_message'),
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.amount.states['readonly'] &= ~Eval('braintree_settlement_needed')
        cls.amount.depends.append('braintree_settlement_needed')
        cls._buttons.update({
                'braintree_checkout': {
                    'invisible': (~Eval('state', 'draft').in_(
                            ['approved', 'processing'])
                        | (Eval('process_method') != 'braintree')
                        | Eval('braintree_nonce')
                        | Eval('braintree_customer_method')),
                    'depends': [
                        'state',
                        'process_method',
                        'braintree_nonce',
                        'braintree_customer_method',
                        ],
                    },
                'braintree_do_settle_payment': {
                    'invisible': ((Eval('state', 'draft') != 'processing')
                        | ~Eval('braintree_settlement_needed')),
                    'depends': ['state', 'braintree_settlement_needed'],
                    },
                'braintree_do_pull': {
                    'invisible': ~Eval('braintree_transaction_id'),
                    'depends': ['braintree_transaction_id'],
                    },
                })

    @fields.depends('journal')
    def on_change_with_braintree_account(self, name=None):
        if self.journal and self.journal.process_method == 'braintree':
            return self.journal.braintree_account.id

    def on_change_party(self):
        super().on_change_party()
        self.braintree_customer = None

    @fields.depends('braintree_customer', 'braintree_customer_method')
    def get_braintree_customer_methods(self):
        methods = [('', '')]
        if self.braintree_customer:
            methods.extend(self.braintree_customer.payment_methods())
        if (self.braintree_customer_method
                and self.braintree_customer_method not in dict(methods)):
            methods.append((
                    self.braintree_customer_method,
                    self.braintree_customer_method))
        return methods

    @fields.depends(
        'braintree_customer_method_selection', 'braintree_customer_method')
    def on_change_braintree_customer_method_selection(self):
        self.braintree_customer_method = (
            self.braintree_customer_method_selection)

    def get_braintree_customer_method(self, name):
        return self.braintree_customer_method

    @classmethod
    def set_braintree_customer_method(cls, payments, name, value):
        pass

    @classmethod
    def default_braintree_settle_payment(cls):
        return True

    @classmethod
    def default_braintree_payment_settled(cls):
        return False

    def get_braintree_settlement_needed(self, name):
        return (self.journal.process_method == 'braintree'
            and self.braintree_transaction_id
            and not self.braintree_settle_payment
            and not self.braintree_payment_settled)

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//group[@id="braintree"]', 'states', {
                    'invisible': Eval('process_method') != 'braintree',
                    }),
            ]

    @classmethod
    def validate(cls, payments):
        super(Payment, cls).validate(payments)
        for payment in payments:
            payment.check_braintree_journal()

    def check_braintree_journal(self):
        if (self.kind != 'receivable'
                and self.journal.process_method == 'braintree'):
            raise PaymentValidationError(
                gettext('account_payment_braintree.msg_braintree_receivable',
                    journal=self.journal.rec_name,
                    payment=self.rec_name))

    @classmethod
    def copy(cls, payments, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('braintree_transaction_id', None)
        default.setdefault('braintree_payment_settled', False)
        default.setdefault('braintree_error_message')
        return super().copy(payments, default=default)

    @classmethod
    def braintree_checkout(cls, payments):
        for payment in payments:
            if payment.braintree_client_token:
                continue
            gateway = payment.braintree_account.gateway()
            client_token = gateway.client_token.generate()
            payment.braintree_client_token = client_token
        return super().braintree_checkout(payments)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, payments):
        super(Payment, cls).draft(payments)
        for payment in payments:
            if payment.braintree_nonce:
                payment.braintree_nonce = None
                payment.braintree_device_data = None
        cls.save(payments)

    @classmethod
    def braintree_transact(cls, payments=None):
        """Create transactions for braintree payments

        The transaction is committed after each payment sale."""
        if payments is None:
            payments = cls.search([
                    ('state', '=', 'processing'),
                    ('journal.process_method', '=', 'braintree'),
                    ['OR',
                        ('braintree_nonce', '!=', None),
                        ('braintree_customer_method', '!=', None),
                        ('braintree_customer', '!=', None),
                        ],
                    ('braintree_transaction_id', '=', None),
                    ('company', '=', Transaction().context.get('company')),
                    ])

        for payment in payments:
            # Use clear cache after a commit
            payment = cls(payment.id)
            if (payment.braintree_transaction_id
                    or payment.journal.process_method != 'braintree'
                    or payment.state != 'processing'):
                continue
            payment.lock()
            gateway = payment.braintree_account.gateway()
            try:
                result = gateway.transaction.sale(
                    payment._braintree_transaction_parameters())
            except TooManyRequestsError as e:
                logger.warning(str(e))
                continue
            except BraintreeError as e:
                payment.braintree_error_message = str(e)
                payment.save()
                cls.fail([payment])
            except Exception:
                logger.error(
                    "Error when processing payment %d", payment.id,
                    exc_info=True)
                continue
            else:
                if result.is_success:
                    payment.braintree_transaction_id = result.transaction.id
                    payment.braintree_payment_settled = (
                        payment.braintree_settle_payment)
                    payment.braintree_update(result.transaction)
                    if (payment.braintree_account.environment == 'sandbox'
                            and (payment.braintree_account
                                .sandbox_settle_transaction)
                            and payment.braintree_settle_payment):
                        gateway.testing.settle_transaction(
                            result.transaction.id)
                else:
                    payment.braintree_error_message = result.message
                    payment.save()
                    cls.fail([payment])
            Transaction().commit()

    def _braintree_transaction_parameters(self):
        params = {
            'amount': self.amount,
            'options': {
                'submit_for_settlement': self.braintree_settle_payment,
                },
            }
        if self.braintree_nonce:
            params['payment_method_nonce'] = self.braintree_nonce
        elif self.braintree_customer_method:
            params['payment_method_token'] = self.braintree_customer_method
        elif self.braintree_customer:
            params['customer_id'] = (
                self.braintree_customer.braintree_customer_id)
        if self.braintree_device_data:
            params['device_data'] = self.braintree_device_data
        return params

    @classmethod
    @ModelView.button
    def braintree_do_settle_payment(cls, payments):
        cls.write(payments, {
                'braintree_settle_payment': True,
                })
        cls.__queue__.braintree_settle_payment_(payments)

    @classmethod
    def braintree_settle_payment_(cls, payments=None):
        """Settle braintree payments

        The transaction is committed after each payment settlement."""
        if payments is None:
            payments = cls.search([
                    ('state', '=', 'processing'),
                    ('journal.process_method', '=', 'braintree'),
                    ('braintree_transaction_id', '!=', None),
                    ('braintree_payment_settled', '=', False),
                    ('braintree_settle_payment', '=', True),
                    ('company', '=', Transaction().context.get('company')),
                    ])

        for payment in payments:
            # Use clear cache after a commit
            payment = cls(payment.id)
            if (payment.journal.process_method != 'braintree'
                    or payment.braintree_payment_settled
                    or payment.state != 'processing'):
                continue
            payment.lock()
            braintree_account = payment.braintree_account
            gateway = braintree_account.gateway()
            try:
                result = gateway.transaction.submit_for_settlement(
                    payment.braintree_transaction_id,
                    payment.amount,
                    payment._braintree_settlement_parameters())
            except TooManyRequestsError as e:
                logger.warning(str(e))
                continue
            except BraintreeError as e:
                payment.braintree_error_message = str(e)
                payment.save()
                cls.fail([payment])
            except Exception:
                logger.error(
                    "Error when processing payment %d", payment.id,
                    exc_info=True)
                continue
            else:
                if result.is_success:
                    payment.braintree_payment_settled = True
                    payment.braintree_update(result.transaction)
                    if (braintree_account.environment == 'sandbox'
                            and (braintree_account
                                .sandbox_settle_transaction)):
                        gateway.testing.settle_transaction(
                            result.transaction.id)
                else:
                    payment.braintree_error_message = result.message
                    payment.save()
                    cls.fail([payment])
            Transaction().commit()

    def _braintree_settlement_parameters(self):
        return {}

    @classmethod
    @ModelView.button
    def braintree_do_pull(cls, payments):
        cls.braintree_pull(payments)

    @classmethod
    def braintree_pull(cls, payments=None):
        "Update payments with braintree transactions"
        if payments is None:
            payments = cls.search([
                    ('state', '=', 'processing'),
                    ('journal.process_method', '=', 'braintree'),
                    ('braintree_transaction_id', '!=', None),
                    ('company', '=', Transaction().context.get('company')),
                    ])

        for payment in payments:
            gateway = payment.braintree_account.gateway()
            try:
                transaction = gateway.transaction.find(
                    payment.braintree_transaction_id)
            except TooManyRequestsError as e:
                logger.warning(str(e))
                continue
            except Exception:
                logger.error(
                    "Error when pulling payment %d", payment.id,
                    exc_info=True)
                continue
            else:
                payment.braintree_update(transaction)
        cls.save(payments)

    def braintree_update(self, transaction):
        "Update payment with braintree transaction"
        if self.state == 'succeeded':
            self.__class__.proceed([self])
        gateway = transaction.gateway
        amount = transaction.amount
        for id_ in transaction.refund_ids:
            refund = gateway.transaction.find(id_)
            if refund.status in SUCCEEDED_STATUSES:
                amount -= refund.amount
        for dispute in transaction.disputes:
            if dispute.status in DISPUTE_FINAL_STATUSES:
                amount -= dispute.amount_disputed - dispute.amount_won
        self.amount = amount
        self.save()
        if transaction.status in SUCCEEDED_STATUSES:
            if amount:
                self.__class__.succeed([self])
            else:
                self.__class__.fail([self])
        elif transaction.status in FAILED_STATUSES:
            self.__class__.fail([self])


class PaymentBraintreeRefund(Workflow, ModelSQL, ModelView):
    "Braintree Payment Refund"
    __name__ = 'account.payment.braintree.refund'

    payment = fields.Many2One(
        'account.payment', "Payment", required=True,
        domain=[
            ('process_method', '=', 'braintree'),
            ('braintree_transaction_id', '!=', None),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])
    amount = fields.Numeric(
        "Amount", required=True, digits=(16, Eval('currency_digits', 2)),
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['currency_digits', 'state'])

    state = fields.Selection([
            ('draft', "Draft"),
            ('approved', "Approved"),
            ('processing', "Processing"),
            ('succeeded', "Succeeded"),
            ('failed', "Failed"),
            ], "State", readonly=True)

    braintree_transaction_id = fields.Char(
        "Braintree Transaction ID", readonly=True)

    braintree_error_message = fields.Text(
        "Braintree Error Message", readonly=True,
        states={
            'invisible': ~Eval('braintree_error_message'),
            })

    currency_digits = fields.Function(
        fields.Integer("Currency Digits"), 'on_change_with_currency_digits')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._transitions |= set((
                ('draft', 'approved'),
                ('approved', 'processing'),
                ('processing', 'succeeded'),
                ('processing', 'failed'),
                ('approved', 'draft'),
                ))
        cls._buttons.update({
                'draft': {
                    'invisible': Eval('state') != 'approved',
                    'icon': 'tryton-back',
                    'depends': ['state'],
                    },
                'approve': {
                    'invisible': Eval('state') != 'draft',
                    'icon': 'tryton-forward',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def default_state(cls):
        return 'draft'

    @fields.depends('payment', '_parent_payment.currency_digits')
    def on_change_with_currency_digits(self, name=None):
        if self.payment:
            return self.payment.currency_digits

    @classmethod
    def copy(cls, refunds, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('braintree_transaction_id')
        default.setdefault('braintree_error_message')
        return super().copy(refunds, default=default)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, refunds):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('approved')
    def approve(cls, refunds):
        pass

    @classmethod
    @Workflow.transition('processing')
    def process(cls, refunds):
        pass

    @classmethod
    @Workflow.transition('succeeded')
    def succeed(cls, refunds):
        pass

    @classmethod
    @Workflow.transition('failed')
    def fail(cls, refunds):
        pass

    @classmethod
    def braintree_refund(cls, refunds=None):
        """Refund braintree transaction

        The transaction is committed after each refund."""
        if refunds is None:
            refunds = cls.search([('state', '=', 'approved')])

        for refund in refunds:
            # User clear cache after a commit
            refund = cls(refund.id)
            if refund.braintree_transaction_id:
                continue
            refund.lock()
            braintree_account = refund.payment.braintree_account
            gateway = braintree_account.gateway()
            try:
                result = gateway.transaction.refund(
                    refund.payment.braintree_transaction_id,
                    refund._refund_parameters())
            except TooManyRequestsError as e:
                logger.warning(str(e))
                continue
            except BraintreeError as e:
                refund.braintree_error_message = str(e)
                refund.save()
                cls.process([refund])
                cls.fail([refund])
            except Exception:
                logger.error(
                    "Error when refund %d", refund.id,
                    exc_info=True)
                continue
            else:
                cls.process([refund])
                if result.is_success:
                    refund.braintree_transaction_id = result.transaction.id
                    refund.braintree_update(result.transaction)
                    if (braintree_account.environment == 'sandbox'
                            and (braintree_account
                                .sandbox_settle_transaction)):
                        gateway.testing.settle_transaction(
                            result.transaction.id)
                else:
                    refund.braintree_error_message = result.message
                    refund.save()
                    cls.fail([refund])
            Transaction().commit()

    def _refund_parameters(self):
        return {
            'amount': self.amount,
            }

    @classmethod
    def braintree_pull(cls, refunds=None):
        "Update refund with braintree transactions"
        if refunds is None:
            refunds = cls.search([
                    ('state', '=', 'processing'),
                    ('braintree_transaction_id', '!=', None),
                    ('payment.company',
                        '=', Transaction().context.get('company')),
                    ])

        for refund in refunds:
            gateway = refund.payment.braintree_account.gateway()
            try:
                transaction = gateway.transaction.find(
                    refund.braintree_transaction_id)
            except TooManyRequestsError as e:
                logger.warning(str(e))
                continue
            except Exception:
                logger.error(
                    "Error when pulling refund %d", refund.id,
                    exc_info=True)
                continue
            else:
                refund.braintree_update(transaction)
        cls.save(refunds)
        for refund in refunds:
            if refund.state in {'succeeded', 'failed'}:
                payment = refund.payment
                gateway = payment.braintree_account.gateway()
                transaction = gateway.transaction.find(
                    payment.braintree_transaction_id)
                payment.braintree_update(transaction)

    def braintree_update(self, transaction):
        "Update refund with braintree transaction"
        self.amount = transaction.amount
        self.save()
        if transaction.status in SUCCEEDED_STATUSES:
            self.__class__.succeed([self])
        elif transaction.status in FAILED_STATUSES:
            self.__class__.fail([self])


class PaymentBraintreeAccount(ModelSQL, ModelView):
    "Braintree Account"
    __name__ = 'account.payment.braintree.account'

    name = fields.Char("Name", required=True)
    currency = fields.Many2One('currency.currency', "Currency", required=True)
    environment = fields.Selection([
            ('sandbox', "Sandbox"),
            ('production', "Production"),
            ], "Environment", required=True)
    merchant_id = fields.Char("Merchant ID", required=True)
    public_key = fields.Char("Public Key", required=True)
    private_key = fields.Char("Private Key", required=True)
    webhook_identifier = fields.Char("Webhook Identifier", readonly=True)
    webhook_endpoint = fields.Function(
        fields.Char(
            "Webhook Endpoint",
            help="The URL to be called by Braintree."),
        'on_change_with_webhook_endpoint')
    sandbox_settle_transaction = fields.Boolean(
        "Automatic Settlement",
        states={
            'invisible': Eval('environment') != 'sandbox',
            },
        depends=['environment'])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'new_identifier': {
                    'icon': 'tryton-refresh',
                    },
                })

    @classmethod
    def default_environment(cls):
        return 'sandbox'

    @classmethod
    def default_sandbox_settle_transaction(cls):
        return False

    @fields.depends('webhook_identifier')
    def on_change_with_webhook_endpoint(self, name=None):
        if not self.webhook_identifier:
            return
        url_part = {
            'identifier': self.webhook_identifier,
            'database_name': Transaction().database.name,
            }
        return http_host() + (
            urllib.parse.quote(
                '/%(database_name)s/account_payment_braintree'
                '/webhook/%(identifier)s' % url_part))

    @property
    def configuration(self):
        return braintree.Configuration(
            environment=braintree.Environment.All[self.environment],
            merchant_id=self.merchant_id,
            public_key=self.public_key,
            private_key=self.private_key,
            )

    def gateway(self):
        return braintree.BraintreeGateway(self.configuration)

    @classmethod
    @ModelView.button
    def new_identifier(cls, accounts):
        for account in accounts:
            if account.webhook_identifier:
                account.webhook_identifier = None
            else:
                account.webhook_identifier = uuid.uuid4().hex
        cls.save(accounts)

    def webhook(self, notification):
        """Handles Braintree webhook notification

        The return values must be:
            - None if the method could not handle the notification kind
            - True if the notification has been handled
            - False if the notification should be retried by Braintree
        """
        if notification.kind in {
                braintree.WebhookNotification.Kind.DisputeOpened,
                braintree.WebhookNotification.Kind.DisputeLost,
                braintree.WebhookNotification.Kind.DisputeWon,
                braintree.WebhookNotification.Kind.DisputeAccepted,
                braintree.WebhookNotification.Kind.DisputeExpired,
                braintree.WebhookNotification.Kind.DisputeDisputed}:
            return self.webhook_dispute(notification.dispute)
        elif notification.kind in {
                braintree.WebhookNotification.Kind.
                TransactionSettlementDeclined,
                braintree.WebhookNotification.Kind.TransactionSettled}:
            return self.webhook_transaction(notification.transaction)
        return None

    def webhook_dispute(self, dispute):
        pool = Pool()
        Payment = pool.get('account.payment')

        payments = Payment.search([
                ('braintree_transaction_id', '=', dispute.transaction.id),
                ])
        if not payments:
            logger.error(
                "webhook dispute: No payment '%s'", dispute.transaction.id)
        for payment in payments:
            # TODO remove when https://bugs.tryton.org/issue4080
            with Transaction().set_context(company=payment.company.id):
                payment = Payment(payment.id)
                payment.braintree_dispute_reason = dispute.reason
                payment.braintree_dispute_status = dispute.status
                payment.save()
                gateway = payment.braintree_account.gateway()
                transaction = gateway.transaction.find(
                    payment.braintree_transaction_id)
                payment.braintree_update(transaction)
        return bool(payments)

    def webhook_transaction(self, transaction):
        pool = Pool()
        Payment = pool.get('account.payment')

        payments = Payment.search([
                ('braintree_transaction_id', '=', transaction.id),
                ])
        if not payments:
            logger.error(
                "webhook transaction: No payment '%s'", transaction.id)
        for payment in payments:
            # TODO remove when https://bugs.tryton.org/issue4080
            with Transaction().set_context(company=payment.company.id):
                payment = Payment(payment.id)
                payment.braintree_update(transaction)
        return bool(payments)


class PaymentBraintreeCustomer(
        CheckoutMixin, DeactivableMixin, ModelSQL, ModelView):
    "Braintree Customer"
    __name__ = 'account.payment.braintree.customer'
    _history = True
    party = fields.Many2One(
        'party.party', "Party", required=True, select=True,
        states={
            'readonly': (
                Eval('braintree_customer_id') | Eval('braintree_nonce')),
            },
        depends=['braintree_customer_id', 'braintree_nonce'])
    braintree_account = fields.Many2One(
        'account.payment.braintree.account', "Account", required=True,
        states={
            'readonly': (
                Eval('braintree_customer_id') | Eval('braintree_nonce')),
            },
        depends=['braintree_customer_id', 'braintree_nonce'])
    braintree_customer_id = fields.Char(
        "Braintree Customer ID",
        states={
            'readonly': Eval('braintree_customer_id') & (Eval('id', -1) >= 0),
            })
    braintree_error_message = fields.Text(
        "Braintree Error Message", readonly=True,
        states={
            'invisible': ~Eval('braintree_error_message'),
            })

    _payment_methods_cache = Cache(
        'account_payment_braintree_customer.payment_methods',
        duration=config.getint(
            'account_payment_braintree', 'payment_methods_cache',
            default=15 * 60))

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'braintree_checkout': {
                    'invisible': Bool(Eval('braintree_nonce')),
                    'depends': ['braintree_nonce'],
                    },
                'delete_payment_method': {
                    'invisible': ~Eval('braintree_customer_id'),
                    'depends': ['braintree_customer_id'],
                    },
                })

    def get_rec_name(self, name):
        name = super().get_rec_name(name)
        return (
            self.braintree_customer_id if self.braintree_customer_id else name)

    @classmethod
    def delete(cls, customers):
        cls.write(customers, {
                'active': False,
                })

    @classmethod
    def copy(cls, customers, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('braintree_customer_id', None)
        return super().copy(customers, default=default)

    @classmethod
    def braintree_checkout(cls, customers):
        for customer in customers:
            if customer.braintree_client_token:
                continue
            gateway = customer.braintree_account.gateway()
            client_token = gateway.client_token.generate(
                customer._client_token_parameters())
            customer.braintree_client_token = client_token
        return super().braintree_checkout(customers)

    def _client_token_parameters(self):
        params = {}
        if self.braintree_customer_id:
            params['customer_id'] = self.braintree_customer_id
        return params

    def braintree_set_nonce(self, nonce, device_data=None):
        super().braintree_set_nonce(nonce, device_data=device_data)
        self.braintree_create(customers=[self])

    @classmethod
    def braintree_create(cls, customers=None):
        """Creates braintree customers

        The transaction is committed after each customer."""
        if not customers:
            customers = cls.search([
                    ('braintree_nonce', '!=', None),
                    ])
        for customer in customers:
            # Use clear cache after commit
            customer = cls(customer.id)
            if not customer.braintree_nonce:
                continue
            customer.lock()
            gateway = customer.braintree_account.gateway()
            try:
                if not customer.braintree_customer_id:
                    result = gateway.customer.create({
                            'email': customer.party.email,
                            'phone': customer.party.phone,
                            'payment_method_nonce': customer.braintree_nonce,
                            })
                else:
                    result = gateway.payment_method.create({
                            'customer_id': customer.braintree_customer_id,
                            'payment_method_nonce': customer.braintree_nonce,
                            })
            except TooManyRequestsError as e:
                logger.warning(str(e))
                continue
            except BraintreeError as e:
                customer.braintree_error_message = str(e)
            except Exception:
                logger.error(
                    "Error when creating customer %d", customer.id,
                    exc_info=True)
                continue
            else:
                if result.is_success:
                    if not customer.braintree_customer_id:
                        customer.braintree_customer_id = result.customer.id
                    customer.braintree_error_message = None
                else:
                    customer.braintree_error_message = result.message
            customer.braintree_client_token = None
            customer.braintree_nonce = None
            customer.save()
            cls._payment_methods_cache.clear()
            Transaction().commit()

    @classmethod
    def braintree_delete(cls, customers=None):
        """Deletes braintree customers

        The transaction is committed after each customer."""
        if not customers:
            customers = cls.search([
                    ('active', '=', False),
                    ('braintree_customer_id', '!=', None),
                    ])
        for customer in customers:
            # Use clear cache after commit
            customer = cls(customer.id)
            assert not customer.active
            customer.lock()
            gateway = customer.braintree_account.gateway()
            try:
                result = gateway.customer.delete(
                    customer.braintree_customer_id)
            except TooManyRequestsError as e:
                logger.warning(str(e))
                continue
            except Exception:
                logger.error(
                    "Error when deleting customer %d", customer.id,
                    exc_info=True)
                continue
            if result.is_success:
                customer.braintree_customer_id = None
            customer.save()
            Transaction().commit()

    def find(self):
        if not self.braintree_customer_id:
            return
        gateway = self.braintree_account.gateway()
        try:
            return gateway.customer.find(self.braintree_customer_id)
        except (TooManyRequestsError,
                GatewayTimeoutError) as e:
            logger.warning(str(e))

    def payment_methods(self):
        methods = self._payment_methods_cache.get(self.id)
        if methods is not None:
            return methods
        methods = []
        customer = self.find()
        if customer:
            for payment_method in customer.payment_methods:
                name = self._payment_method_name(payment_method)
                methods.append((payment_method.token, name))
            self._payment_methods_cache.set(self.id, methods)
        return methods

    def _payment_method_name(cls, payment_method):
        name = payment_method.token
        if hasattr(payment_method, 'card_type'):
            name = payment_method.card_type
            if payment_method.last_4:
                name += ' ****' + payment_method.last_4
            if (payment_method.expiration_month
                    and payment_method.expiration_year):
                name += ' %s/%s' % (
                    payment_method.expiration_month,
                    payment_method.expiration_year)
        elif isinstance(payment_method, braintree.PayPalAccount):
            name = "Paypal %s" % payment_method.email
        elif isinstance(payment_method, braintree.VenmoAccount):
            name = "Venmo %s" % payment_method.source_description
        elif isinstance(payment_method, braintree.UsBankAccount):
            name = "****" + payment_method.last_4
        return name

    @classmethod
    @ModelView.button_action(
        'account_payment_braintree.wizard_customer_payment_method_delete')
    def delete_payment_method(cls, customers):
        pass

    def delete_payment_method_(self, payment_method):
        gateway = self.braintree_account.gateway()
        try:
            result = gateway.payment_method.delete(payment_method)
        except (TooManyRequestsError,
                GatewayTimeoutError) as e:
            logger.warning(str(e))
        else:
            if not result.is_success:
                logger.error(result.message)
        self._payment_methods_cache.clear()


class PaymentBraintreeCustomerPaymentMethodDelete(Wizard):
    "Delete Customer Payment Method"
    __name__ = 'account.payment.braintree.customer.payment_method.delete'
    start_state = 'ask'
    ask = StateView(
        'account.payment.braintree.customer.payment_method.delete.ask',
        'account_payment_braintree.'
        'customer_payment_method_delete_ask_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Delete", 'delete_', 'tryton-ok', default=True),
            ])
    delete_ = StateTransition()

    def default_ask(self, fields):
        default = {}
        if 'customer' in fields:
            default['customer'] = self.record.id
        return default

    def transition_delete_(self):
        self.record.delete_payment_method_(self.ask.payment_method)
        return 'end'


class PaymentBraintreeCustomerPaymentMethodDeleteAsk(ModelView):
    "Delete Customer Payment Method"
    __name__ = 'account.payment.braintree.customer.payment_method.delete.ask'

    customer = fields.Many2One(
        'account.payment.braintree.customer', "Customer", readonly=True)
    payment_method = fields.Selection(
        'get_payment_methods', "Payment Method", required=True)

    @fields.depends('customer')
    def get_payment_methods(self):
        methods = [('', '')]
        if self.customer:
            methods.extend(self.customer.payment_methods())
        return methods


class PaymentBraintreeCheckout(Wizard):
    "Braintree Checkout"
    __name__ = 'account.payment.braintree.checkout'
    start_state = 'checkout'
    checkout = StateAction('account_payment_braintree.url_checkout')

    def do_checkout(self, action):
        action['url'] = self.record.braintree_checkout_url
        return action, {}


class PaymentBraintreeCheckoutPage(Report):
    "Braintree Checkout"
    __name__ = 'account.payment.braintree.checkout'
