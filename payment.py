# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import uuid
import logging
import urllib
from decimal import Decimal
from itertools import groupby
from operator import attrgetter

import stripe

from trytond import backend
from trytond.model import (
    ModelSQL, ModelView, Workflow, DeactivableMixin, fields)
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool
from trytond.report import Report
from trytond.rpc import RPC
from trytond.transaction import Transaction
from trytond.url import HOSTNAME
from trytond.wizard import Wizard, StateAction

__all__ = ['Journal', 'Group', 'Payment', 'Account', 'Customer',
    'Checkout', 'CheckoutPage']
logger = logging.getLogger(__name__)


class Journal:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment.journal'

    stripe_account = fields.Many2One(
        'account.payment.stripe.account', "Account", ondelete='RESTRICT',
        states={
            'required': Eval('process_method') == 'stripe',
            'invisible': Eval('process_method') != 'stripe',
            },
        depends=['process_method'])

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        stripe_method = ('stripe', 'Stripe')
        if stripe_method not in cls.process_method.selection:
            cls.process_method.selection.append(stripe_method)


class Group:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment.group'

    @classmethod
    def __setup__(cls):
        super(Group, cls).__setup__()
        cls._error_messages.update({
                'no_stripe_token': ('No Stripe token found '
                    'for payment "%(payment)s".'),
                })

    def process_stripe(self):
        pool = Pool()
        Payment = pool.get('account.payment')
        for payment in self.payments:
            if not payment.stripe_token and not payment.stripe_customer:
                account = payment.journal.stripe_account
                for customer in payment.party.stripe_customers:
                    if (customer.stripe_account == account
                            and customer.stripe_customer_id):
                        payment.stripe_customer = customer
                        break
                else:
                    self.raise_user_error('no_stripe_token', {
                            'payment': payment.rec_name,
                            })
        Payment.save(self.payments)


class Payment:
    __metaclass__ = PoolMeta
    __name__ = 'account.payment'

    stripe_journal = fields.Function(
        fields.Boolean("Stripe Journal"), 'on_change_with_stripe_journal')
    stripe_checkout_needed = fields.Function(
        fields.Boolean("Stripe Checkout Needed"), 'get_stripe_checkout_needed')
    stripe_checkout_id = fields.Char("Stripe Checkout ID", readonly=True)
    stripe_charge_id = fields.Char(
        "Stripe Charge ID", readonly=True,
        states={
            'invisible': ~Eval('stripe_journal') & ~Eval('stripe_charge_id'),
            },
        depends=['stripe_journal'])
    stripe_capture = fields.Boolean(
        "Stripe Capture",
        states={
            'invisible': ~Eval('stripe_journal'),
            'readonly': Eval('state') != 'draft',
            },
        depends=['stripe_journal', 'state'])
    stripe_captured = fields.Boolean(
        "Stripe Captured", readonly=True)
    stripe_capture_needed = fields.Function(
        fields.Boolean("Stripe Capture Needed"),
        'get_stripe_capture_needed')
    stripe_token = fields.Char("Stripe Token",
        states={
            'invisible': (~Eval('stripe_journal')
                | Eval('stripe_customer_source')),
            'readonly': ~Eval('state').in_(['draft', 'approved']),
            },
        depends=['stripe_journal', 'stripe_customer_source', 'state'])
    stripe_chargeable = fields.Boolean(
        "Stripe Chargeable",
        states={
            'invisible': ~Eval('stripe_journal') | ~Eval('stripe_token'),
            },
        depends=['stripe_journal', 'stripe_token'])
    stripe_idempotency_key = fields.Char(
        "Stripe Idempotency Key", readonly=True)
    stripe_error_message = fields.Char("Stripe Error Message", readonly=True,
        states={
            'invisible': ~Eval('stripe_error_message'),
            })
    stripe_error_code = fields.Char("Stripe Error Code", readonly=True,
        states={
            'invisible': ~Eval('stripe_error_code'),
            })
    stripe_error_param = fields.Char("Stripe Error Param", readonly=True,
        states={
            'invisible': ~Eval('stripe_error_param'),
            })
    stripe_dispute_reason = fields.Char("Stripe Dispute Reason", readonly=True,
        states={
            'invisible': ~Eval('stripe_dispute_reason'),
            })
    stripe_dispute_status = fields.Char("Stripe Dispute Status", readonly=True,
        states={
            'invisible': ~Eval('stripe_dispute_status'),
            })
    stripe_customer = fields.Many2One(
        'account.payment.stripe.customer', "Stripe Customer",
        domain=[
            ('party', '=', Eval('party', -1)),
            ('stripe_account', '=', Eval('stripe_account', -1)),
            ],
        states={
            'invisible': ~Eval('stripe_journal'),
            'required': Bool(Eval('stripe_customer_source')),
            'readonly': ~Eval('state').in_(['draft', 'approved']),
            },
        depends=['party', 'stripe_account', 'stripe_journal',
            'stripe_customer_source', 'state'])
    stripe_customer_source = fields.Char(
        "Stripe Customer Source",
        states={
            'invisible': (~Eval('stripe_journal') | Eval('stripe_token')
                | ~Eval('stripe_customer')),
            'readonly': ~Eval('state').in_(['draft', 'approved']),
            },
        depends=['stripe_account', 'stripe_token', 'stripe_customer', 'state'])
    # Use Function field with selection to avoid to query Stripe
    # to validate the value
    stripe_customer_source_selection = fields.Function(fields.Selection(
            'get_stripe_customer_sources', "Stripe Customer Source",
            states={
                'invisible': (~Eval('stripe_journal') | Eval('stripe_token')
                    | ~Eval('stripe_customer')),
                'readonly': ~Eval('state').in_(['draft', 'approved']),
                },
            depends=[
                'stripe_account', 'stripe_token', 'stripe_customer', 'state']),
        'get_stripe_customer_source')
    stripe_account = fields.Function(fields.Many2One(
            'account.payment.stripe.account', "Stripe Account"),
        'on_change_with_stripe_account')
    stripe_amount = fields.Function(
        fields.Integer("Stripe Amount"),
        'get_stripe_amount', setter='set_stripe_amount')

    @classmethod
    def __setup__(cls):
        super(Payment, cls).__setup__()
        cls.amount.states['readonly'] &= ~Eval('stripe_capture_needed')
        cls.amount.depends.append('stripe_capture_needed')
        cls.stripe_amount.states.update(cls.amount.states)
        cls.stripe_amount.depends.extend(cls.amount.depends)
        cls._error_messages.update({
                'stripe_receivable': ('Stripe journal "%(journal)s" '
                    'can only be used for receivable payment "%(payment)s".'),
                })
        cls._buttons.update({
                'stripe_checkout': {
                    'invisible': (~Eval('state', 'draft').in_(
                            ['approved', 'processing'])
                        | ~Eval('stripe_checkout_needed', False)),
                    'depends': ['state', 'stripe_checkout_needed'],
                    },
                'stripe_capture_': {
                    'invisible': ((Eval('state', 'draft') != 'processing')
                        | ~Eval('stripe_capture_needed')),
                    'depends': ['state', 'stripe_capture_needed'],
                    },
                })
        # As there is not setter to avoid the cost of validation,
        # the readonly attribute must be unset.
        cls.stripe_customer_source_selection._field.readonly = False

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()
        table = TableHandler(cls, module_name)
        idempotency_key_exist = table.column_exist('stripe_idempotency_key')

        super(Payment, cls).__register__(module_name)

        # Migration from 4.6: do not set the same key to all existing payments
        if not idempotency_key_exist:
            cursor.execute(*sql_table.update(
                    [sql_table.stripe_idempotency_key], [None]))

    @classmethod
    def default_stripe_capture(cls):
        return True

    @classmethod
    def default_stripe_captured(cls):
        return False

    @classmethod
    def default_stripe_chargeable(cls):
        return False

    @classmethod
    def default_stripe_idempotency_key(cls):
        return uuid.uuid4().hex

    @fields.depends('journal')
    def on_change_with_stripe_journal(self, name=None):
        if self.journal:
            return self.journal.process_method == 'stripe'
        else:
            return False

    @fields.depends('party')
    def on_change_party(self):
        super(Payment, self).on_change_party()
        self.stripe_customer = None
        self.stripe_customer_source = None
        self.stripe_customer_source_selection = None

    @fields.depends('stripe_customer', 'stripe_customer_source')
    def get_stripe_customer_sources(self):
        sources = [('', '')]
        if self.stripe_customer:
            sources.extend(self.stripe_customer.sources())
        if (self.stripe_customer_source
                and self.stripe_customer_source not in dict(sources)):
            sources.append(
                (self.stripe_customer_source, self.stripe_customer_source))
        return sources

    @fields.depends(
        'stripe_customer_source_selection',
        'stripe_customer_source')
    def on_change_stripe_customer_source_selection(self):
        self.stripe_customer_source = self.stripe_customer_source_selection

    def get_stripe_customer_source(self, name):
        return self.stripe_customer_source

    def get_stripe_checkout_needed(self, name):
        return (self.journal.process_method == 'stripe'
            and not self.stripe_token
            and not self.stripe_customer)

    def get_stripe_capture_needed(self, name):
        return (self.journal.process_method == 'stripe'
            and self.stripe_charge_id
            and not self.stripe_captured)

    @fields.depends('journal')
    def on_change_with_stripe_account(self, name=None):
        if self.journal and self.journal.process_method == 'stripe':
            return self.journal.stripe_account.id

    def get_stripe_amount(self, name):
        return int(self.amount * 10 ** self.currency_digits)

    @classmethod
    def set_stripe_amount(cls, payments, name, value):
        keyfunc = attrgetter('currency_digits')
        payments = sorted(payments, key=keyfunc)
        value = Decimal(value)
        for digits, payments in groupby(payments, keyfunc):
            digits = Decimal(digits)
            cls.write(list(payments), {
                    'amount': value * 10 ** -digits,
                    })

    @classmethod
    def validate(cls, payments):
        super(Payment, cls).validate(payments)
        for payment in payments:
            payment.check_stripe_journal()

    def check_stripe_journal(self):
        if (self.kind != 'receivable'
                and self.journal.process_method == 'stripe'):
            self.raise_user_error('stripe_receivable', {
                    'journal': self.journal.rec_name,
                    'payment': self.rec_name,
                    })

    @classmethod
    def create(cls, vlist):
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            # Ensure to get a different key for each record
            # default methods are called only once
            values.setdefault('stripe_idempotency_key',
                cls.default_stripe_idempotency_key())
        return super(Payment, cls).create(vlist)

    @classmethod
    def copy(cls, payments, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default['stripe_checkout_id'] = None
        default['stripe_charge_id'] = None
        default['stripe_token'] = None
        default.setdefault('stripe_idempotency_key')
        default.setdefault('stripe_error_message')
        default.setdefault('stripe_error_code')
        default.setdefault('stripe_error_param')
        return super(Payment, cls).copy(payments, default=default)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, payments):
        super(Payment, cls).draft(payments)
        for payment in payments:
            if payment.stripe_token:
                payment.stripe_token = None
        cls.save(payments)

    @classmethod
    @ModelView.button_action('account_payment_stripe.wizard_checkout')
    def stripe_checkout(cls, payments):
        for payment in payments:
            payment.stripe_checkout_id = uuid.uuid4().hex
        cls.save(payments)

    @classmethod
    def stripe_charge(cls, payments=None):
        """Charge stripe payments

        The transaction is committed after each payment charge.
        """
        if not payments:
            payments = cls.search([
                    ('state', '=', 'processing'),
                    ('journal.process_method', '=', 'stripe'),
                    ['OR',
                        [
                            ('stripe_token', '!=', None),
                            ('stripe_chargeable', '=', True),
                            ],
                        ('stripe_customer.stripe_customer_id', '!=', None),
                        ],
                    ('stripe_charge_id', '=', None),
                    ])
        for payment in payments:
            try:
                charge = stripe.Charge.create(**payment._charge_parameters())
            except (stripe.error.RateLimitError,
                    stripe.error.APIConnectionError) as e:
                logger.warning(str(e))
                continue
            except stripe.error.StripeError as e:
                payment.stripe_error_message = unicode(e)
                if isinstance(e, stripe.error.CardError):
                    payment.stripe_error_code = e.code
                    payment.stripe_error_param = e.param
                payment.save()
                cls.fail([payment])
            except Exception:
                logger.error(
                    "Error when processing payment %d", payment.id,
                    exc_info=True)
                continue
            else:
                payment.stripe_charge_id = charge.id
                payment.stripe_captured = charge.captured
                payment.save()
                if charge.status == 'succeeded' and charge.captured:
                    cls.succeed([payment])
                elif charge.status == 'failed':
                    cls.fail([payment])
            Transaction().commit()

    def _charge_parameters(self):
        source, customer = None, None
        if self.stripe_token:
            source = self.stripe_token
        elif self.stripe_customer_source:
            source = self.stripe_customer_source
        if self.stripe_customer:
            customer = self.stripe_customer.stripe_customer_id
        idempotency_key = None
        if self.stripe_idempotency_key:
            idempotency_key = 'charge-%s' % self.stripe_idempotency_key
        return {
            'api_key': self.journal.stripe_account.secret_key,
            'amount': self.stripe_amount,
            'currency': self.currency.code,
            'capture': bool(self.stripe_capture),
            'description': self.description,
            'customer': customer,
            'source': source,
            'idempotency_key': idempotency_key,
            }

    @classmethod
    @ModelView.button
    def stripe_capture_(cls, payments):
        """Capture stripe payments

        The transaction is committed after each payment capture.
        """
        for payment in payments:
            if (not payment.stripe_charge_id
                    or payment.stripe_captured
                    or payment.state != 'processing'):
                continue
            try:
                charge = stripe.Charge.retrieve(
                    payment.stripe_charge_id,
                    api_key=payment.journal.stripe_account.secret_key)
                charge.capture(**payment._capture_parameters())
            except (stripe.error.RateLimitError,
                    stripe.error.APIConnectionError) as e:
                logger.warning(str(e))
                continue
            except stripe.error.StripeError as e:
                payment.stripe_error_message = unicode(e)
                payment.save()
                cls.fail([payment])
            except Exception:
                logger.error(
                    "Error when capturing payment %d", payment.id,
                    exc_info=True)
                continue
            else:
                payment.stripe_charge_id = charge.id
                payment.stripe_captured = charge.captured
                payment.save()
                if charge.status == 'succeeded' and charge.captured:
                    cls.succeed([payment])
                elif charge.status == 'failed':
                    cls.fail([payment])
            Transaction().commit()

    def _capture_parameters(self):
        idempotency_key = None
        if self.stripe_idempotency_key:
            idempotency_key = 'capture-%s' % self.stripe_idempotency_key
        return {
            'amount': self.stripe_amount,
            'idempotency_key': idempotency_key,
            }


class Account(ModelSQL, ModelView):
    "Stripe Account"
    __name__ = 'account.payment.stripe.account'

    name = fields.Char("Name", required=True)
    secret_key = fields.Char("Secret Key", required=True)
    publishable_key = fields.Char("Publishable Key", required=True)
    webhook_identifier = fields.Char("Webhook Identifier", readonly=True)
    webhook_endpoint = fields.Function(
        fields.Char(
            "Webhook Endpoint",
            help="The URL to be called by Stripe."),
        'on_change_with_webhook_endpoint')
    webhook_signing_secret = fields.Char(
        "Webhook Signing Secret",
        states={
            'invisible': ~Eval('webhook_identifier'),
            },
        depends=['webhook_identifier'],
        help="The Stripe's signing secret of the webhook.")
    zip_code = fields.Boolean("Zip Code", help="Verification on checkout")

    @classmethod
    def __setup__(cls):
        super(Account, cls).__setup__()
        cls._buttons.update({
                'new_identifier': {
                    'icon': 'tryton-refresh',
                    },
                })
        if Pool().test:
            cls.__rpc__['webhook'] = RPC(readonly=False, instantiate=0)

    @classmethod
    def default_zip_code(cls):
        return True

    @fields.depends('webhook_identifier')
    def on_change_with_webhook_endpoint(self, name=None):
        if not self.webhook_identifier:
            return ''
        # TODO add basic authentication support
        url_part = {
            'identifier': self.webhook_identifier,
            'database_name': Transaction().database.name,
            }
        return 'https://' + HOSTNAME + (
            urllib.quote(
                '/%(database_name)s/account_payment_stripe'
                '/webhook/%(identifier)s'
                % url_part))

    def webhook(self, payload):
        """This method handles stripe webhook callbacks

        The return values are:
            - None if the method could not handle payload['type']
            - True if the payload has been handled
            - False if the webhook should be retried by Stripe
        """
        data = payload['data']
        type_ = payload['type']
        if type_ == 'charge.succeeded':
            return self.webhook_charge_succeeded(data)
        if type_ == 'charge.captured':
            return self.webhook_charge_captured(data)
        elif type_ == 'charge.failed':
            return self.webhook_charge_failed(data)
        elif type_ == 'charge.pending':
            return self.webhook_charge_pending(data)
        elif type_ == 'charge.refunded':
            return self.webhook_charge_refunded(data)
        elif type_ == 'charge.dispute.created':
            return self.webhook_charge_dispute_created(data)
        elif type_ == 'charge.dispute.closed':
            return self.webhook_charge_dispute_closed(data)
        elif type_ == 'source.chargeable':
            return self.webhook_source_chargeable(data)
        elif type_ == 'source.failed':
            return self.webhook_source_failed(data)
        elif type_ == 'source.canceled':
            return self.webhook_source_canceled(data)
        return None

    def webhook_charge_succeeded(self, payload, _event='charge.succeeded'):
        pool = Pool()
        Payment = pool.get('account.payment')

        charge = payload['object']
        payments = Payment.search([
                ('stripe_charge_id', '=', charge['id']),
                ])
        if not payments:
            logger.error("%s: No payment '%s'", _event, charge['id'])
        for payment in payments:
            # TODO: remove when https://bugs.tryton.org/issue4080
            with Transaction().set_context(company=payment.company.id):
                if payment.state == 'succeeded':
                    Payment.fail([payment])
                payment.stripe_captured = charge['captured']
                payment.stripe_amount = (
                    charge['amount'] - charge['amount_refunded'])
                payment.save()
                if payment.amount:
                    if charge['status'] == 'succeeded' and charge['captured']:
                        Payment.succeed([payment])
                else:
                    Payment.fail([payment])
        return bool(payments)

    def webhook_charge_captured(self, payload):
        return self.webhook_charge_succeeded(payload, _event='charge.captured')

    def webhook_charge_pending(self, payload):
        return self.webhook_charge_succeeded(payload, _event='charge.pending')

    def webhook_charge_refunded(self, payload):
        return self.webhook_charge_succeeded(payload, _event='charge.pending')

    def webhook_charge_failed(self, payload):
        pool = Pool()
        Payment = pool.get('account.payment')

        charge = payload['object']
        payments = Payment.search([
                ('stripe_charge_id', '=', charge['id']),
                ])
        if not payments:
            logger.error("charge.failed: No payment '%s'", charge['id'])
        for payment in payments:
            # TODO: remove when https://bugs.tryton.org/issue4080
            with Transaction().set_context(company=payment.company.id):
                payment.stripe_error_message = charge['failure_message']
                payment.stripe_error_code = charge['failure_code']
                payment.stripe_error_param = None
                payment.save()
                if charge['status'] == 'failed':
                    Payment.fail([payment])
        return bool(payments)

    def webhook_charge_dispute_created(self, payload):
        pool = Pool()
        Payment = pool.get('account.payment')

        source = payload['object']
        payments = Payment.search([
                ('stripe_charge_id', '=', source['charge']),
                ])
        if not payments:
            logger.error(
                "charge.dispute.created: No payment '%s'", source['charge'])
        for payment in payments:
            # TODO: remove when https://bugs.tryton.org/issue4080
            with Transaction().set_context(company=payment.company.id):
                payment.stripe_dispute_reason = source['reason']
                payment.stripe_dispute_status = source['status']
                payment.save()
        return bool(payments)

    def webhook_charge_dispute_closed(self, payload):
        pool = Pool()
        Payment = pool.get('account.payment')

        source = payload['object']
        payments = Payment.search([
                ('stripe_charge_id', '=', source['charge']),
                ])
        if not payments:
            logger.error(
                "charge.dispute.closed: No payment '%s'", source['charge'])
        for payment in payments:
            # TODO: remove when https://bugs.tryton.org/issue4080
            with Transaction().set_context(company=payment.company.id):
                payment.stripe_dispute_reason = source['reason']
                payment.stripe_dispute_status = source['status']
                payment.save()
                if source['status'] == 'lost':
                    Payment.fail([payment])
                    if payment.stripe_amount != source['amount']:
                        payment.stripe_amount -= source['amount']
                        payment.save()
                        Payment.succeed([payment])
        return bool(payments)

    def webhook_source_chargeable(self, payload):
        pool = Pool()
        Payment = pool.get('account.payment')

        source = payload['object']
        payments = Payment.search([
                ('stripe_token', '=', source['id']),
                ])
        if payments:
            Payment.write(payments, {'stripe_chargeable': True})
        return True

    def webhook_source_failed(self, payload):
        pool = Pool()
        Payment = pool.get('account.payment')

        source = payload['object']
        payments = Payment.search([
                ('stripe_token', '=', source['id']),
                ])
        for payment in payments:
            # TODO: remove when https://bugs.tryton.org/issue4080
            with Transaction().set_context(company=payment.company.id):
                payment.stripe_error_message = source['failure_message']
                payment.stripe_error_code = source['failure_code']
                payment.stripe_error_param = None
                payment.save()
                Payment.fail([payment])
        return True

    def webhook_source_canceled(self, payload):
        pool = Pool()
        Payment = pool.get('account.payment')

        source = payload['object']
        payments = Payment.search([
                ('stripe_token', '=', source['id']),
                ])
        for payment in payments:
            # TODO: remove when https://bugs.tryton.org/issue4080
            with Transaction().set_context(company=payment.company.id):
                Payment.fail([payment])
        return True

    @classmethod
    @ModelView.button
    def new_identifier(cls, accounts):
        for account in accounts:
            account.webhook_identifier = uuid.uuid4().hex
        cls.save(accounts)


class Customer(DeactivableMixin, ModelSQL, ModelView):
    "Stripe Customer"
    __name__ = 'account.payment.stripe.customer'
    _history = True
    party = fields.Many2One('party.party', "Party", required=True, select=True,
        states={
            'readonly': Eval('stripe_customer_id') | Eval('stripe_token'),
            },
        depends=['stripe_customer_id', 'stripe_token'])
    stripe_account = fields.Many2One(
        'account.payment.stripe.account', "Account", required=True,
        states={
            'readonly': Eval('stripe_customer_id') | Eval('stripe_token'),
            },
        depends=['stripe_customer_id', 'stripe_token'])
    stripe_checkout_needed = fields.Function(
        fields.Boolean("Stripe Checkout Needed"), 'get_stripe_checkout_needed')
    stripe_checkout_id = fields.Char("Stripe Checkout ID", readonly=True)
    stripe_customer_id = fields.Char(
        "Stripe Customer ID",
        states={
            'readonly': ((Eval('stripe_customer_id') | Eval('stripe_token'))
                & (Eval('id', -1) >= 0)),
            },
        depends=['stripe_token'])
    stripe_token = fields.Char("Stripe Token", readonly=True)
    stripe_error_message = fields.Char("Stripe Error Message", readonly=True,
        states={
            'invisible': ~Eval('stripe_error_message'),
            })
    stripe_error_code = fields.Char("Stripe Error Code", readonly=True,
        states={
            'invisible': ~Eval('stripe_error_code'),
            })
    stripe_error_param = fields.Char("Stripe Error Param", readonly=True,
        states={
            'invisible': ~Eval('stripe_error_param'),
            })

    @classmethod
    def __setup__(cls):
        super(Customer, cls).__setup__()
        cls._buttons.update({
                'stripe_checkout': {
                    'invisible': ~Eval('stripe_checkout_needed', False),
                    'depends': ['stripe_checkout_needed'],
                    },
                })

    def get_stripe_checkout_needed(self, name):
        return not self.stripe_customer_id and not self.stripe_token

    def get_rec_name(self, name):
        name = super(Customer, self).get_rec_name(name)
        return self.stripe_customer_id if self.stripe_customer_id else name

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
        default['stripe_checkout_id'] = None
        default['stripe_token'] = None
        default['stripe_customer_id'] = None
        return super(Customer, cls).copy(customers, default=default)

    @classmethod
    @ModelView.button_action('account_payment_stripe.wizard_checkout')
    def stripe_checkout(cls, customers):
        for customer in customers:
            customer.stripe_checkout_id = uuid.uuid4().hex
        cls.save(customers)

    @classmethod
    def stripe_create(cls, customers=None):
        """Create stripe customer

        The transaction is committed after each customer.
        """
        if not customers:
            customers = cls.search([
                    ('stripe_token', '!=', None),
                    ['OR',
                        ('stripe_customer_id', '=', None),
                        ('stripe_customer_id', '=', ''),
                        ],
                    ])
        for customer in customers:
            assert not customer.stripe_customer_id
            try:
                cu = stripe.Customer.create(
                    api_key=customer.stripe_account.secret_key,
                    description=customer.rec_name,
                    email=customer.party.email,
                    source=customer.stripe_token)
            except stripe.error.RateLimitError:
                logger.warning("Rate limit error")
                continue
            except stripe.error.StripeError as e:
                customer.stripe_error_message = unicode(e)
                if isinstance(e, stripe.error.CardError):
                    customer.stripe_error_code = e.code
                    customer.stripe_error_param = e.param
                customer.stripe_token = None
            except Exception:
                logger.error(
                    "Error when creating customer %d", customer.id,
                    exc_info=True)
                continue
            else:
                customer.stripe_customer_id = cu.id
                # TODO add card
            customer.save()
            Transaction().commit()

    @classmethod
    def stripe_delete(cls, customers=None):
        """Delete customer

        The transaction is committed after each customer.
        """
        if not customers:
            customers = cls.search([
                    ('active', '=', False),
                    ('stripe_customer_id', '!=', None),
                    ])
        for customer in customers:
            assert not customer.active
            try:
                cu = stripe.Customer.retrieve(
                    api_key=customer.stripe_account.secret_key,
                    id=customer.stripe_customer_id)
                cu.delete()
            except stripe.error.RateLimitError:
                logger.warning("Rate limit error")
                continue
            except Exception:
                logger.error(
                    "Error when deleting customer %d", customer.id,
                    exc_info=True)
                continue
            customer.stripe_token = None
            customer.stripe_customer_id = None
            customer.save()
            Transaction().commit()

    def retrieve(self):
        if not self.stripe_customer_id:
            return
        try:
            return stripe.Customer.retrieve(
                api_key=self.stripe_account.secret_key,
                id=self.stripe_customer_id)
        except (stripe.error.RateLimitError,
                stripe.error.APIConnectionError) as e:
            logger.warning(str(e))

    def sources(self):
        sources = []
        customer = self.retrieve()
        if customer:
            for source in customer.sources:
                name = source.id
                if source.object == 'card':
                    name = self._source_name(source)
                elif source.object == 'source':
                    if source.usage != 'reusable':
                        continue
                    name = self._source_name(source)
                else:
                    continue
                sources.append((source.id, name))
        return sources

    def _source_name(cls, source):
        def card_name(card):
            name = card.brand
            if card.last4 or card.dynamic_last4:
                name += ' ****' + (card.last4 or card.dynamic_last4)
            if card.exp_month and card.exp_year:
                name += ' %s/%s' % (card.exp_month, card.exp_year)
            return name

        name = source.id
        if source.object == 'card':
            name = card_name(source)
        elif source.object == 'source':
            if source.type == 'card':
                name = card_name(source.card)
            elif source.type == 'sepa_debit':
                name = '****' + source.sepa_debit.last4
        return name


class Checkout(Wizard):
    "Stripe Checkout"
    __name__ = 'account.payment.stripe.checkout'
    start_state = 'checkout'
    checkout = StateAction('account_payment_stripe.url_checkout')

    def do_checkout(self, action):
        pool = Pool()
        Payment = pool.get('account.payment')
        Customer = pool.get('account.payment.stripe.customer')
        context = Transaction().context
        active_model = context['active_model']
        active_id = context['active_id']
        if active_model == Payment.__name__:
            Model = Payment
        elif active_model == Customer.__name__:
            Model = Customer
        else:
            raise ValueError("Invalid active_model: %s" % active_model)
        record = Model(active_id)
        database = Transaction().database.name
        action['url'] = action['url'] % {
            'hostname': HOSTNAME,
            'database': database,
            'model': active_model,
            'id': record.stripe_checkout_id,
            }
        return action, {}


class CheckoutPage(Report):
    "Stripe Checkout"
    __name__ = 'account.payment.stripe.checkout'
