# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
import logging
import urllib.parse
import uuid
from decimal import Decimal
from email.header import Header
from itertools import groupby
from operator import attrgetter

import stripe
from sql import Literal

from trytond.cache import Cache
from trytond.config import config
from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, Index, ModelSQL, ModelView, Unique, Workflow, dualmethod,
    fields)
from trytond.modules.account_payment.exceptions import (
    PaymentValidationError, ProcessError)
from trytond.modules.company.model import (
    employee_field, reset_employee, set_employee)
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, TimeDelta
from trytond.report import Report, get_email
from trytond.rpc import RPC
from trytond.sendmail import sendmail_transactional
from trytond.tools import sql_pairing
from trytond.tools.email_ import set_from_header
from trytond.transaction import Transaction
from trytond.url import http_host
from trytond.wizard import (
    Button, StateAction, StateTransition, StateView, Wizard)

from .common import StripeCustomerMethodMixin

logger = logging.getLogger(__name__)
stripe.max_network_retries = config.getint(
    'account_payment_stripe', 'max_network_retries', default=3)

RETRY_CODES = {'lock_timeout', 'token_in_use'}
STRIPE_VERSION = '2023-08-16'


class Journal(metaclass=PoolMeta):
    __name__ = 'account.payment.journal'

    stripe_account = fields.Many2One(
        'account.payment.stripe.account', "Account", ondelete='RESTRICT',
        states={
            'required': Eval('process_method') == 'stripe',
            'invisible': Eval('process_method') != 'stripe',
            })

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        stripe_method = ('stripe', 'Stripe')
        if stripe_method not in cls.process_method.selection:
            cls.process_method.selection.append(stripe_method)


class Group(metaclass=PoolMeta):
    __name__ = 'account.payment.group'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons['succeed']['invisible'] |= (
            Eval('process_method') == 'stripe')

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
                    raise ProcessError(
                        gettext('account_payment_stripe.msg_no_stripe_token',
                            payment=payment.rec_name))
        Payment.save(self.payments)
        Payment.__queue__.stripe_charge(self.payments)


class CheckoutMixin:
    __slots__ = ()
    stripe_checkout_id = fields.Char(
        "Stripe Checkout ID", readonly=True, strip=False)

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('stripe_checkout_id')
        return super().copy(records, default=default)

    @classmethod
    @ModelView.button_action('account_payment_stripe.wizard_checkout')
    def stripe_checkout(cls, records):
        for record in records:
            record.stripe_checkout_id = uuid.uuid4().hex
        cls.save(records)

    @property
    def stripe_checkout_url(self):
        pool = Pool()
        database = Transaction().database.name
        Checkout = pool.get('account.payment.stripe.checkout', type='wizard')
        action = Checkout.checkout.get_action()
        return action['url'] % {
            'http_host': http_host(),
            'database': database,
            'model': self.__class__.__name__,
            'id': self.stripe_checkout_id,
            }


class Payment(StripeCustomerMethodMixin, CheckoutMixin, metaclass=PoolMeta):
    __name__ = 'account.payment'

    stripe_checkout_needed = fields.Function(
        fields.Boolean("Stripe Checkout Needed"),
        'on_change_with_stripe_checkout_needed')
    stripe_charge_id = fields.Char(
        "Stripe Charge ID", readonly=True, strip=False,
        states={
            'invisible': ((Eval('process_method') != 'stripe')
                | ~Eval('stripe_charge_id')),
            })
    stripe_capture = fields.Boolean(
        "Stripe Capture",
        states={
            'invisible': Eval('process_method') != 'stripe',
            'readonly': Eval('state') != 'draft',
            })
    stripe_captured = fields.Boolean(
        "Stripe Captured", readonly=True)
    stripe_capture_needed = fields.Function(
        fields.Boolean("Stripe Capture Needed"),
        'get_stripe_capture_needed')
    stripe_token = fields.Char(
        "Stripe Token", readonly=True, strip=False,
        states={
            'invisible': ~Eval('stripe_token'),
            })
    stripe_payment_intent_id = fields.Char(
        "Stripe Payment Intent", readonly=True, strip=False,
        states={
            'invisible': ~Eval('stripe_payment_intent_id'),
            })
    stripe_chargeable = fields.Boolean(
        "Stripe Chargeable",
        states={
            'invisible': ((Eval('process_method') != 'stripe')
                | ~Eval('stripe_token')),
            })
    stripe_capturable = fields.Boolean(
        "Stripe Capturable",
        states={
            'invisible': ((Eval('process_method') != 'stripe')
                | ~Eval('stripe_payment_intent_id')
                | ~Eval('stripe_capture_needed')),
            })
    stripe_idempotency_key = fields.Char(
        "Stripe Idempotency Key", readonly=True, strip=False)
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
    stripe_amount = fields.Function(
        fields.Integer("Stripe Amount"),
        'get_stripe_amount', setter='set_stripe_amount')
    stripe_refunds = fields.One2Many(
        'account.payment.stripe.refund', 'payment', "Refunds",
        states={
            'invisible': ((Eval('process_method') != 'stripe')
                | (~Eval('stripe_charge_id')
                    & ~Eval('stripe_payment_intent_id'))),
            })

    @classmethod
    def __setup__(cls):
        super(Payment, cls).__setup__()

        cls.stripe_customer.states['readonly'] = (
            ~Eval('state').in_(['draft', 'submitted', 'approved'])
            | Eval('stripe_token')
            | Eval('stripe_payment_intent_id'))

        cls.stripe_customer_source.states['invisible'] |= (
            Eval('stripe_token') | Eval('stripe_payment_intent_id'))
        cls.stripe_customer_source.states['readonly'] = (
            ~Eval('state').in_(['draft', 'submitted', 'approved']))

        cls.stripe_customer_source_selection.states['invisible'] |= (
            Eval('stripe_token') | Eval('stripe_payment_intent_id'))
        cls.stripe_customer_source_selection.states['readonly'] = (
            ~Eval('state').in_(['draft', 'submitted', 'approved']))

        cls.stripe_customer_payment_method.states['invisible'] |= (
            Eval('stripe_token'))
        cls.stripe_customer_payment_method.states['readonly'] = (
            ~Eval('state').in_(['draft', 'submitted', 'approved'])
            | Eval('stripe_payment_intent_id'))

        cls.stripe_customer_payment_method_selection.states['invisible'] |= (
            Eval('stripe_token'))
        cls.stripe_customer_payment_method_selection.states['readonly'] = (
            ~Eval('state').in_(['draft', 'submitted', 'approved'])
            | Eval('stripe_payment_intent_id'))

        cls.amount.states['readonly'] &= ~Eval('stripe_capture_needed')
        cls.stripe_amount.states.update(cls.amount.states)
        cls._buttons.update({
                'stripe_checkout': {
                    'invisible': (~Eval('state', 'draft').in_(
                            ['submitted', 'approved', 'processing'])
                        | ~Eval('stripe_checkout_needed', False)),
                    'depends': ['state', 'stripe_checkout_needed'],
                    },
                'stripe_do_capture': {
                    'invisible': ((Eval('state', 'draft') != 'processing')
                        | ~Eval('stripe_capture_needed')),
                    'depends': ['state', 'stripe_capture_needed'],
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()
        table = cls.__table_handler__(module_name)
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
    def default_stripe_capturable(cls):
        return False

    @classmethod
    def default_stripe_idempotency_key(cls):
        return uuid.uuid4().hex

    @fields.depends('process_method',
        'stripe_token', 'stripe_payment_intent_id',
        'stripe_customer_source', 'stripe_customer_source_selection',
        'stripe_customer_payment_method',
        'stripe_customer_payment_method_selection')
    def on_change_with_stripe_checkout_needed(self, name=None):
        return (self.process_method == 'stripe'
            and not self.stripe_token
            and not self.stripe_payment_intent_id
            and not self.stripe_customer_source
            and not self.stripe_customer_payment_method)

    def get_stripe_capture_needed(self, name):
        return (self.journal.process_method == 'stripe'
            and (self.stripe_charge_id
                or self.stripe_payment_intent_id)
            and not self.stripe_capture
            and not self.stripe_captured)

    def get_stripe_amount(self, name):
        return int(self.amount * 10 ** self.currency.digits)

    @classmethod
    def set_stripe_amount(cls, payments, name, value):
        keyfunc = attrgetter('currency')
        payments = sorted(payments, key=keyfunc)
        value = Decimal(value)
        for currency, payments in groupby(payments, keyfunc):
            cls.write(list(payments), {
                    'amount': value * 10 ** -Decimal(currency.digits),
                    })

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//group[@id="stripe"]', 'states', {
                    'invisible': Eval('process_method') != 'stripe',
                    }),
            ]

    @classmethod
    def validate_fields(cls, payments, field_names):
        super().validate_fields(payments, field_names)
        cls.check_stripe_journal(payments, field_names)

    @classmethod
    def check_stripe_journal(cls, payments, field_names=None):
        if field_names and not (field_names & {'kind', 'journal'}):
            return
        for payment in payments:
            if (payment.kind != 'receivable'
                    and payment.journal.process_method == 'stripe'):
                raise PaymentValidationError(
                    gettext('account_payment_stripe.msg_stripe_receivable',
                        journal=payment.journal.rec_name,
                        payment=payment.rec_name))

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
        default.setdefault('stripe_charge_id', None)
        default.setdefault('stripe_token', None)
        default.setdefault('stripe_payment_intent_id', None)
        default.setdefault('stripe_idempotency_key', None)
        default.setdefault('stripe_error_message', None)
        default.setdefault('stripe_error_code', None)
        default.setdefault('stripe_error_param', None)
        default.setdefault('stripe_captured', False)
        default.setdefault('stripe_chargeable', False)
        default.setdefault('stripe_capturable', False)
        return super(Payment, cls).copy(payments, default=default)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, payments):
        super(Payment, cls).draft(payments)
        for payment in payments:
            if payment.stripe_token:
                payment.stripe_token = None
                payment.stripe_payment_intent_id = None
        cls.save(payments)

    @classmethod
    def stripe_checkout(cls, payments):
        for payment in payments:
            if not payment.stripe_payment_intent_id:
                payment_intent = stripe.PaymentIntent.create(
                    **payment._payment_intent_parameters(off_session=False))
                payment.stripe_payment_intent_id = payment_intent.id
        return super().stripe_checkout(payments)

    def _send_email_checkout(self, from_=None):
        pool = Pool()
        Language = pool.get('ir.lang')
        from_cfg = config.get('email', 'from')
        self.stripe_checkout([self])
        emails = self._emails_checkout()
        if not emails:
            logger.warning("Could not send checkout email for %d", self.id)
            return
        languages = [self.party.lang or Language.get()]
        msg, title = get_email(
            'account.payment.stripe.email_checkout', self, languages)
        set_from_header(msg, from_cfg, from_ or from_cfg)
        msg['To'] = ','.join(emails)
        msg['Subject'] = Header(title, 'utf-8')
        sendmail_transactional(from_cfg, emails, msg)

    def _emails_checkout(self):
        emails = []
        if self.party.email:
            emails.append(self.party.email)
        return emails

    def _payment_intent_parameters(self, off_session=False):
        idempotency_key = None
        if self.stripe_idempotency_key:
            idempotency_key = 'payment_intent-%s' % self.stripe_idempotency_key
        params = {
            'api_key': self.journal.stripe_account.secret_key,
            'stripe_version': STRIPE_VERSION,
            'amount': self.stripe_amount,
            'currency': self.currency.code,
            'capture_method': 'automatic' if self.stripe_capture else 'manual',
            'customer': (self.stripe_customer.stripe_customer_id
                if self.stripe_customer else None),
            'description': self.description,
            'off_session': off_session,
            'payment_method_types': ['card'],
            'idempotency_key': idempotency_key,
            }
        if self.stripe_customer_payment_method:
            params['payment_method'] = self.stripe_customer_payment_method
            params['confirm'] = True
        return params

    @classmethod
    def stripe_charge(cls, payments=None, off_session=True):
        """Charge stripe payments

        The transaction is committed after each payment charge.
        """
        pool = Pool()
        Customer = pool.get('account.payment.stripe.customer')
        if payments is None:
            payments = cls.search([
                    ('state', '=', 'processing'),
                    ('journal.process_method', '=', 'stripe'),
                    ['OR',
                        [
                            ('stripe_token', '!=', None),
                            ('stripe_chargeable', '=', True),
                            ],
                        ('stripe_customer_source', '!=', None),
                        ('stripe_customer_payment_method', '!=', None),
                        ],
                    ('stripe_charge_id', '=', None),
                    ('stripe_payment_intent_id', '=', None),
                    ('company', '=', Transaction().context.get('company')),
                    ])

        def create_charge(payment):
            charge = stripe.Charge.create(**payment._charge_parameters())
            payment.stripe_charge_id = charge.id
            payment.stripe_captured = charge.captured
            payment.save()

        def create_payment_intent(payment):
            try:
                payment_intent = stripe.PaymentIntent.create(
                    **payment._payment_intent_parameters(
                        off_session=off_session))
            except stripe.error.CardError as e:
                error = e.json_body.get('error', {})
                payment_intent = error.get('payment_intent')
                if not payment_intent:
                    raise
            payment.stripe_payment_intent_id = payment_intent['id']
            payment.save()

        for payment in payments:
            # Use clear cache after a commit
            payment = cls(payment.id)
            if (payment.stripe_charge_id
                    or payment.stripe_payment_intent_id
                    or payment.journal.process_method != 'stripe'
                    or payment.state != 'processing'):
                continue
            payment.lock()
            try:
                if ((payment.stripe_token and payment.stripe_chargeable)
                        or payment.stripe_customer_source):
                    create_charge(payment)
                elif payment.stripe_customer_payment_method:
                    create_payment_intent(payment)
            except (stripe.error.RateLimitError,
                    stripe.error.APIConnectionError) as e:
                logger.warning(str(e))
                continue
            except stripe.error.StripeError as e:
                if e.code in RETRY_CODES:
                    logger.warning(str(e))
                    continue
                payment.stripe_error_message = str(e)
                payment.stripe_error_code = e.code
                if isinstance(e, stripe.error.StripeErrorWithParamCode):
                    payment.stripe_error_param = e.param
                payment.save()
                cls.fail([payment])
            except Exception:
                logger.error(
                    "Error when processing payment %d", payment.id,
                    exc_info=True)
                continue
            Transaction().commit()

        customers = [p.stripe_customer for p in payments if p.stripe_customer]
        if customers:
            Customer.__queue__.find_identical(customers)

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
            'stripe_version': STRIPE_VERSION,
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
    def stripe_do_capture(cls, payments):
        cls.write(payments, {
                'stripe_capture': True,
                })
        cls.__queue__.stripe_capture_(payments)

    @classmethod
    def stripe_capture_(cls, payments=None):
        """Capture stripe payments

        The transaction is committed after each payment capture.
        """
        if payments is None:
            payments = cls.search([
                    ('state', '=', 'processing'),
                    ('journal.process_method', '=', 'stripe'),
                    ['OR',
                        ('stripe_charge_id', '!=', None),
                        [
                            ('stripe_payment_intent_id', '!=', None),
                            ('stripe_capturable', '=', True),
                            ],
                        ],
                    ('stripe_captured', '=', False),
                    ('stripe_capture', '=', True),
                    ('company', '=', Transaction().context.get('company')),
                    ])

        def capture_charge(payment):
            charge = stripe.Charge.retrieve(
                payment.stripe_charge_id,
                api_key=payment.journal.stripe_account.secret_key,
                stripe_version=STRIPE_VERSION)
            charge.capture(**payment._capture_parameters())
            payment.stripe_captured = charge.captured
            payment.save()

        def capture_intent(payment):
            params = payment._capture_parameters()
            params['amount_to_capture'] = params.pop('amount')
            stripe.PaymentIntent.capture(
                payment.stripe_payment_intent_id,
                api_key=payment.journal.stripe_account.secret_key,
                stripe_version=STRIPE_VERSION,
                **params)
            payment.stripe_captured = True
            payment.save()

        for payment in payments:
            # Use clear cache after a commit
            payment = cls(payment.id)
            if (payment.journal.process_method != 'stripe'
                    or payment.stripe_captured
                    or payment.state != 'processing'):
                continue
            payment.lock()
            try:
                if payment.stripe_charge_id:
                    capture_charge(payment)
                elif payment.stripe_payment_intent_id:
                    capture_intent(payment)
            except (stripe.error.RateLimitError,
                    stripe.error.APIConnectionError) as e:
                logger.warning(str(e))
                continue
            except stripe.error.StripeError as e:
                if e.code in RETRY_CODES:
                    logger.warning(str(e))
                    continue
                payment.stripe_error_message = str(e)
                payment.save()
                cls.fail([payment])
            except Exception:
                logger.error(
                    "Error when capturing payment %d", payment.id,
                    exc_info=True)
                continue
            Transaction().commit()

    def _capture_parameters(self):
        idempotency_key = None
        if self.stripe_idempotency_key:
            idempotency_key = 'capture-%s' % self.stripe_idempotency_key
        return {
            'amount': self.stripe_amount,
            'idempotency_key': idempotency_key,
            }

    @property
    def stripe_payment_intent(self):
        if not self.stripe_payment_intent_id:
            return
        try:
            return stripe.PaymentIntent.retrieve(
                self.stripe_payment_intent_id,
                api_key=self.journal.stripe_account.secret_key,
                stripe_version=STRIPE_VERSION)
        except (stripe.error.RateLimitError,
                stripe.error.APIConnectionError) as e:
            logger.warning(str(e))

    stripe_intent = stripe_payment_intent

    @dualmethod
    def stripe_intent_update(cls, payments=None):
        pass


class Refund(Workflow, ModelSQL, ModelView):
    "Stripe Payment Refund"
    __name__ = 'account.payment.stripe.refund'

    payment = fields.Many2One(
        'account.payment', "Payment", required=True,
        domain=[
            ('process_method', '=', 'stripe'),
            ['OR',
                ('stripe_charge_id', '!=', None),
                ('stripe_payment_intent_id', '!=', None),
                ],
            ],
        states={
            'readonly': Eval('state') != 'draft',
            })
    amount = Monetary(
        "Amount", currency='currency', digits='currency', required=True,
        states={
            'readonly': Eval('state') != 'draft',
            })
    stripe_amount = fields.Function(
        fields.Integer("Stripe Amount"), 'get_stripe_amount')
    reason = fields.Selection([
            (None, ""),
            ('duplicate', "Duplicate"),
            ('fraudulent', "Fraudulent"),
            ('requested_by_customer', "Requested by Customer"),
            ], "Reason",
        states={
            'readonly': Eval('state') != 'draft',
            })
    submitted_by = employee_field(
        "Submitted by",
        states=['submitted', 'approved', 'processing', 'succeeded', 'failed'])
    approved_by = employee_field(
        "Approved by",
        states=['approved', 'processing', 'succeeded', 'failed'])

    state = fields.Selection([
            ('draft', "Draft"),
            ('submitted', "Submitted"),
            ('approved', "Approved"),
            ('processing', "Processing"),
            ('succeeded', "Succeeded"),
            ('failed', "Failed"),
            ], "State", readonly=True, sort=False)

    stripe_idempotency_key = fields.Char(
        "Stripe Idempotency Key", readonly=True, strip=False)
    stripe_refund_id = fields.Char(
        "Stripe Refund ID", readonly=True, strip=False)
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

    currency = fields.Function(
        fields.Many2One('currency.currency', "Currency"),
        'on_change_with_currency')
    company = fields.Function(
        fields.Many2One('company.company', "Company"),
        'on_change_with_company')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_indexes.add(
            Index(
                t,
                (t.state, Index.Equality()),
                where=t.state.in_([
                        'draft', 'submitted', 'approved', 'processing'])))
        cls.__access__.add('payment')
        cls._transitions |= set((
                ('draft', 'submitted'),
                ('submitted', 'approved'),
                ('approved', 'processing'),
                ('processing', 'succeeded'),
                ('processing', 'failed'),
                ('approved', 'draft'),
                ))
        cls._buttons.update({
                'draft': {
                    'invisible': ~Eval('state').in_(['approved', 'submitted']),
                    'icon': 'tryton-back',
                    'depends': ['state'],
                    },
                'submit': {
                    'invisible': Eval('state') != 'draft',
                    'icon': 'tryton-forward',
                    'depends': ['state'],
                    },
                'approve': {
                    'invisible': Eval('state') != 'draft',
                    'icon': 'tryton-forward',
                    'depends': ['state'],
                    },
                })

    def get_stripe_amount(self, name):
        return int(self.amount * 10 ** self.currency.digits)

    @classmethod
    def default_stripe_idempotency_key(cls):
        return uuid.uuid4().hex

    @fields.depends('payment', '_parent_payment.currency')
    def on_change_with_currency(self, name=None):
        return self.payment.currency if self.payment else None

    @fields.depends('payment', '_parent_payment.company')
    def on_change_with_company(self, name=None):
        return self.payment.company if self.payment else None

    @classmethod
    def default_state(cls):
        return 'draft'

    @classmethod
    def create(cls, vlist):
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            values.setdefault(
                'stripe_idempotency_key',
                cls.default_stripe_idempotency_key())
        return super().create(vlist)

    @classmethod
    def copy(cls, refunds, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('stripe_refund_id')
        default.setdefault('stripe_idempotency_key')
        default.setdefault('stripe_error_message')
        default.setdefault('stripe_error_code')
        default.setdefault('stripe_error_param')
        return super().copy(refunds, default=default)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    @reset_employee('submitted_by', 'approved_by')
    def draft(cls, refunds):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('submitted')
    @set_employee('submitted_by')
    def submit(cls, refunds):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('approved')
    @set_employee('approved_by')
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
    def stripe_create(cls, refunds=None):
        """Create stripe refund

        The transaction is committed after each refund.
        """
        if not refunds:
            refunds = cls.search([('state', '=', 'approved')])
        for refund in refunds:
            # Use clear cache after a commit
            refund = cls(refund.id)
            if refund.stripe_refund_id:
                continue
            refund.lock()
            try:
                rf = stripe.Refund.create(
                    api_key=refund.payment.journal.stripe_account.secret_key,
                    stripe_version=STRIPE_VERSION,
                    **refund._refund_parameters())
            except (stripe.error.RateLimitError,
                    stripe.error.APIConnectionError) as e:
                logger.warning(str(e))
                continue
            except stripe.error.StripeError as e:
                if e.code in RETRY_CODES:
                    logger.warning(str(e))
                    continue
                refund.stripe_error_message = str(e)
                refund.stripe_error_code = e.code
                if isinstance(e, stripe.error.StripeErrorWithParamCode):
                    refund.stripe_error_param = e.param
                cls.process([refund])
                cls.fail([refund])
            except Exception:
                logger.error(
                    "Error when creating refund %d", refund.id,
                    exc_info=True)
                continue
            else:
                refund.stripe_refund_id = rf.id
                cls.process([refund])
                if rf.status == 'succeeded':
                    cls.succeed([refund])
                elif rf.status in {'failed', 'canceled'}:
                    refund.stripe_error_code = rf['failure_reason']
                    cls.fail([refund])
            refund.save()
            Transaction().commit()

    def _refund_parameters(self):
        idempotency_key = None
        if self.stripe_idempotency_key:
            idempotency_key = 'refund-%s' % self.stripe_idempotency_key
        params = {
            'amount': self.stripe_amount,
            'reason': self.reason,
            'idempotency_key': idempotency_key,
            }
        payment = self.payment
        if payment.stripe_charge_id:
            params['charge'] = payment.stripe_charge_id
        elif payment.stripe_payment_intent_id:
            params['payment_intent'] = payment.stripe_payment_intent_id
        return params


class Account(ModelSQL, ModelView):
    "Stripe Account"
    __name__ = 'account.payment.stripe.account'

    name = fields.Char("Name", required=True)
    secret_key = fields.Char("Secret Key", required=True, strip=False)
    publishable_key = fields.Char(
        "Publishable Key", required=True, strip=False)
    webhook_identifier = fields.Char("Webhook Identifier", readonly=True)
    webhook_endpoint = fields.Function(
        fields.Char(
            "Webhook Endpoint",
            help="The URL to be called by Stripe."),
        'on_change_with_webhook_endpoint')
    webhook_signing_secret = fields.Char(
        "Webhook Signing Secret", strip=False,
        states={
            'invisible': ~Eval('webhook_identifier'),
            },
        help="The Stripe's signing secret of the webhook.")
    last_event = fields.Char("Last Event", readonly=True, strip=False)
    setup_intent_delay = fields.TimeDelta(
        "Setup Intent Delay", required=True,
        domain=[
            ('setup_intent_delay', '>=', TimeDelta()),
            ],
        help="The delay before cancelling setup intent not succeeded.")

    @classmethod
    def __setup__(cls):
        super(Account, cls).__setup__()
        cls._buttons.update({
                'new_identifier': {
                    'icon': 'tryton-refresh',
                    },
                })
        if Pool().test:
            cls.__rpc__['webhook'] = RPC(
                readonly=False, instantiate=0, check_access=False)

    @fields.depends('webhook_identifier')
    def on_change_with_webhook_endpoint(self, name=None):
        if not self.webhook_identifier:
            return ''
        # TODO add basic authentication support
        url_part = {
            'identifier': self.webhook_identifier,
            'database_name': Transaction().database.name,
            }
        return http_host() + (
            urllib.parse.quote(
                '/%(database_name)s/account_payment_stripe'
                '/webhook/%(identifier)s'
                % url_part))

    @classmethod
    def default_setup_intent_delay(cls):
        return dt.timedelta(days=30)

    @classmethod
    def fetch_events(cls):
        """Fetch last events of each account without webhook and process them

        The transaction is committed after each event.
        """
        accounts = cls.search([
                ('webhook_identifier', '=', None),
                ])
        for account in accounts:
            while True:
                events = stripe.Event.list(
                    api_key=account.secret_key,
                    stripe_version=STRIPE_VERSION,
                    ending_before=account.last_event,
                    limit=100)
                if not events:
                    break
                for event in reversed(list(events)):
                    account.webhook(event)
                    account.last_event = event.id
                    account.save()
                    Transaction().commit()

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
        elif type_ == 'charge.expired':
            return self.webhook_charge_expired(data)
        elif type_ == 'charge.failed':
            return self.webhook_charge_failed(data)
        elif type_ == 'charge.pending':
            return self.webhook_charge_pending(data)
        elif type_ == 'charge.refunded':
            return self.webhook_charge_refunded(data)
        elif type_ == 'charge.refund.updated':
            return self.webhook_charge_refund_updated(data)
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
        elif type_ == 'payment_intent.succeeded':
            return self.webhook_payment_intent_succeeded(data)
        elif type_ == 'payment_intent.amount_capturable_updated':
            return self.webhook_payment_intent_amount_capturable_updated(data)
        elif type_ == 'payment_intent.payment_failed':
            return self.webhook_payment_intent_payment_failed(data)
        elif type_ == 'payment_intent.canceled':
            return self.webhook_payment_intent_canceled(data)
        return None

    def webhook_charge_succeeded(self, payload, _event='charge.succeeded'):
        pool = Pool()
        Payment = pool.get('account.payment')

        charge = payload['object']
        payments = Payment.search([
                ('stripe_charge_id', '=', charge['id']),
                ])
        if not payments:
            payment_intent_id = charge.get('payment_intent')
            if payment_intent_id:
                found = Payment.search([
                        ('stripe_payment_intent_id', '=', payment_intent_id),
                        ])
                # Once payment intent has succeeded or failed,
                # only charge events are sent.
                payments = [p for p in found
                    if p.state in {'succeeded', 'failed'}]
                if found and not payments:
                    return True
            if not payments:
                logger.error("%s: No payment '%s'", _event, charge['id'])
        for payment in payments:
            if payment.state == 'succeeded':
                Payment.proceed([payment])
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

    def webhook_charge_expired(self, payload):
        return self.webhook_source_failed(payload)

    def webhook_charge_pending(self, payload):
        return self.webhook_charge_succeeded(payload, _event='charge.pending')

    def webhook_charge_refunded(self, payload):
        return self.webhook_charge_succeeded(payload, _event='charge.refunded')

    def webhook_charge_refund_updated(self, payload):
        pool = Pool()
        Refund = pool.get('account.payment.stripe.refund')

        rf = payload['object']
        refunds = Refund.search([
                ('stripe_refund_id', '=', rf['id']),
                ])
        if not refunds:
            logger.error("charge.refund.updated: No refund '%s'", rf['id'])
        for refund in refunds:
            if rf['status'] == 'pending':
                Refund.processing([refund])
            elif rf['status'] == 'succeeded':
                Refund.succeed([refund])
            elif rf['status'] in {'failed', 'canceled'}:
                refund.stripe_error_code = rf['failure_reason']
                Refund.fail([refund])
            refund.save()
        return bool(refunds)

    def webhook_charge_failed(self, payload, _event='charge.failed'):
        pool = Pool()
        Payment = pool.get('account.payment')

        charge = payload['object']
        payments = Payment.search([
                ('stripe_charge_id', '=', charge['id']),
                ])
        if not payments:
            payment_intent_id = charge.get('payment_intent')
            if payment_intent_id:
                found = Payment.search([
                        ('stripe_payment_intent_id', '=', payment_intent_id),
                        ])
                # Once payment intent has succeeded or failed,
                # only charge events are sent.
                payments = [p for p in found
                    if p.state in {'succeeded', 'failed'}]
                if found and not payments:
                    return True
            if not payments:
                logger.error("%s: No payment '%s'", _event, charge['id'])
        for payment in payments:
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
            charge = stripe.Charge.retrieve(
                source['charge'],
                api_key=self.secret_key,
                stripe_version=STRIPE_VERSION)
            if charge.payment_intent:
                payments = Payment.search([
                        ('stripe_payment_intent_id', '=',
                            charge.payment_intent),
                        ])
        if not payments:
            logger.error(
                "charge.dispute.created: No payment '%s'", source['charge'])
        for payment in payments:
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
            charge = stripe.Charge.retrieve(
                source['charge'],
                api_key=self.secret_key,
                stripe_version=STRIPE_VERSION)
            if charge.payment_intent:
                payments = Payment.search([
                        ('stripe_payment_intent_id', '=',
                            charge.payment_intent),
                        ])
        if not payments:
            logger.error(
                "charge.dispute.closed: No payment '%s'", source['charge'])
        for payment in payments:
            payment.stripe_dispute_reason = source['reason']
            payment.stripe_dispute_status = source['status']
            payment.save()
            if source['status'] == 'lost':
                Payment.fail([payment])
                if payment.stripe_amount > source['amount']:
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
            Payment.fail([payment])
        return True

    def webhook_payment_intent_succeeded(self, payload):
        pool = Pool()
        Payment = pool.get('account.payment')

        payment_intent = payload['object']
        payments = Payment.search([
                ('stripe_payment_intent_id', '=', payment_intent['id']),
                ])
        if not payments:
            logger.error(
                "payment_intent.succeeded: No payment '%s'",
                payment_intent['id'])
        for payment in payments:
            if payment.state == 'succeeded':
                Payment.proceed([payment])
            payment.stripe_captured = bool(
                payment_intent['amount_received'])
            payment.stripe_amount = payment_intent['amount_received']
            payment.save()
            if payment.amount:
                Payment.succeed([payment])
            else:
                Payment.fail([payment])
        return bool(payments)

    def webhook_payment_intent_amount_capturable_updated(self, payload):
        pool = Pool()
        Payment = pool.get('account.payment')

        payment_intent = payload['object']
        payments = Payment.search([
                ('stripe_payment_intent_id', '=', payment_intent['id']),
                ])
        if not payments:
            logger.error(
                "payment_intent.amount_capturable_updated: No payment '%s'",
                payment_intent['id'])
        for payment in payments:
            payment = Payment(payment.id)
            if payment.state == 'succeeded':
                Payment.proceed([payment])
            payment.stripe_capturable = bool(
                payment_intent['amount_capturable'])
            if payment.stripe_amount > payment_intent['amount_capturable']:
                payment.stripe_amount = payment_intent['amount_capturable']
            payment.save()
        return bool(payments)

    def webhook_payment_intent_payment_failed(self, payload):
        pool = Pool()
        Payment = pool.get('account.payment')

        payment_intent = payload['object']
        payments = Payment.search([
                ('stripe_payment_intent_id', '=', payment_intent['id']),
                ])
        if not payments:
            logger.error(
                "payment_intent.payment_failed: No payment '%s'",
                payment_intent['id'])
        for payment in payments:
            error = payment_intent['last_payment_error']
            if error:
                payment.stripe_error_message = error['message']
                payment.stripe_error_code = error['code']
                payment.stripe_error_param = None
                payment.save()
            if payment_intent['status'] in [
                    'requires_payment_method', 'requires_source']:
                payment._send_email_checkout()
            else:
                Payment.fail([payment])
        return bool(payments)

    def webhook_payment_intent_canceled(self, payload):
        pool = Pool()
        Payment = pool.get('account.payment')

        payment_intent = payload['object']
        payments = Payment.search([
                ('stripe_payment_intent_id', '=', payment_intent['id']),
                ])
        if not payments:
            logger.error(
                "payment_intent.canceled: No payment '%s'",
                payment_intent['id'])
        for payment in payments:
            payment = Payment(payment.id)
            Payment.fail([payment])
        return bool(payments)

    @classmethod
    @ModelView.button
    def new_identifier(cls, accounts):
        for account in accounts:
            if account.webhook_identifier:
                account.webhook_identifier = None
            else:
                account.webhook_identifier = uuid.uuid4().hex
        cls.save(accounts)


class Customer(CheckoutMixin, DeactivableMixin, ModelSQL, ModelView):
    "Stripe Customer"
    __name__ = 'account.payment.stripe.customer'
    _history = True
    party = fields.Many2One('party.party', "Party", required=True,
        states={
            'readonly': Eval('stripe_customer_id') | Eval('stripe_token'),
            })
    stripe_account = fields.Many2One(
        'account.payment.stripe.account', "Account", required=True,
        states={
            'readonly': Eval('stripe_customer_id') | Eval('stripe_token'),
            })
    stripe_checkout_needed = fields.Function(
        fields.Boolean("Stripe Checkout Needed"), 'get_stripe_checkout_needed')
    stripe_customer_id = fields.Char(
        "Stripe Customer ID", strip=False,
        states={
            'readonly': ((Eval('stripe_customer_id') | Eval('stripe_token'))
                & (Eval('id', -1) >= 0)),
            })
    stripe_token = fields.Char("Stripe Token", readonly=True, strip=False)
    stripe_setup_intent_id = fields.Char(
        "Stripe SetupIntent ID", readonly=True, strip=False)
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

    identical_customers = fields.Many2Many(
        'account.payment.stripe.customer.identical',
        'source', 'target', "Identical Customers", readonly=True,
        states={
            'invisible': ~Eval('identical_customers'),
            })
    fingerprints = fields.One2Many(
        'account.payment.stripe.customer.fingerprint', 'customer',
        "Fingerprints", readonly=True)

    _sources_cache = Cache(
        'account_payment_stripe_customer.sources',
        duration=config.getint(
            'account_payment_stripe', 'sources_cache', default=15 * 60),
        context=False)
    _payment_methods_cache = Cache(
        'account_payment_stripe_customer.payment_methods',
        duration=config.getint(
            'account_payment_stripe', 'payment_methods', default=15 * 60),
        context=False)

    @classmethod
    def __setup__(cls):
        super(Customer, cls).__setup__()
        cls._buttons.update({
                'stripe_checkout': {
                    'invisible': ~Eval('stripe_checkout_needed', False),
                    'depends': ['stripe_checkout_needed'],
                    },
                'detach_source': {
                    'invisible': ~Eval('stripe_customer_id'),
                    'depends': ['stripe_customer_id'],
                    },
                'find_identical': {
                    'invisible': ~Eval('stripe_customer_id'),
                    'depends': ['stripe_customer_id'],
                    },
                })

    def get_stripe_checkout_needed(self, name):
        return (not self.stripe_customer_id
            or not self.stripe_token
            or not self.stripe_setup_intent_id)

    def get_rec_name(self, name):
        name = super(Customer, self).get_rec_name(name)
        return self.stripe_customer_id if self.stripe_customer_id else name

    @classmethod
    def write(cls, *args, **kwargs):
        super().write(*args, **kwargs)
        cls._sources_cache.clear()
        cls._payment_methods_cache.clear()

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
        default.setdefault('stripe_token', None)
        default.setdefault('stripe_customer_id', None)
        return super(Customer, cls).copy(customers, default=default)

    @classmethod
    def stripe_checkout(cls, customers):
        for customer in customers:
            if customer.stripe_setup_intent_id:
                continue
            setup_intent = stripe.SetupIntent.create(
                api_key=customer.stripe_account.secret_key,
                stripe_version=STRIPE_VERSION)
            customer.stripe_setup_intent_id = setup_intent.id
        return super().stripe_checkout(customers)

    @classmethod
    def stripe_create(cls, customers=None):
        """Create stripe customer with token

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
            # Use clear cache after a commit
            customer = cls(customer.id)
            if customer.stripe_customer_id:
                continue
            customer.lock()
            try:
                cu = stripe.Customer.create(
                    api_key=customer.stripe_account.secret_key,
                    stripe_version=STRIPE_VERSION,
                    source=customer.stripe_token,
                    **customer._customer_parameters())
            except (stripe.error.RateLimitError,
                    stripe.error.APIConnectionError) as e:
                logger.warning(str(e))
                continue
            except stripe.error.StripeError as e:
                if e.code in RETRY_CODES:
                    logger.warning(str(e))
                    continue
                customer.stripe_error_message = str(e)
                customer.stripe_error_code = e.code
                if isinstance(e, stripe.error.StripeErrorWithParamCode):
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
        cls.__queue__.find_identical(customers)

    def _customer_parameters(self):
        locales = [pl.lang.code for pl in self.party.langs if pl.lang]
        return {
            'email': self.party.email,
            'name': self.party.name,
            'phone': self.party.phone,
            'preferred_locales': locales,
            }

    @classmethod
    def stripe_update(cls, customers):
        for customer in customers:
            try:
                stripe.Customer.modify(
                    customer.stripe_customer_id,
                    api_key=customer.stripe_account.secret_key,
                    stripe_version=STRIPE_VERSION,
                    **customer._customer_parameters()
                    )
            except (stripe.error.RateLimitError,
                    stripe.error.APIConnectionError) as e:
                logger.warning(str(e))
            except Exception as e:
                if (isinstance(e, stripe.error.StripeError)
                        and e.code in RETRY_CODES):
                    logger.warning(str(e))
                else:
                    logger.error(
                        "Error when updating customer %d", customer.id,
                        exc_info=True)

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
            # Use clear cache after a commit
            customer = cls(customer.id)
            assert not customer.active
            customer.lock()
            try:
                cu = stripe.Customer.retrieve(
                    api_key=customer.stripe_account.secret_key,
                    stripe_version=STRIPE_VERSION,
                    id=customer.stripe_customer_id)
                cu.delete()
            except (stripe.error.RateLimitError,
                    stripe.error.APIConnectionError) as e:
                logger.warning(str(e))
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

    def retrieve(self, **params):
        if not self.stripe_customer_id:
            return
        try:
            return stripe.Customer.retrieve(
                api_key=self.stripe_account.secret_key,
                stripe_version=STRIPE_VERSION,
                id=self.stripe_customer_id,
                **params)
        except (stripe.error.RateLimitError,
                stripe.error.APIConnectionError) as e:
            logger.warning(str(e))

    def sources(self):
        sources = self._sources_cache.get(self.id)
        if sources is not None:
            return sources
        sources = []
        customer = self.retrieve(expand=['sources'])
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
            self._sources_cache.set(self.id, sources)
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

    @classmethod
    @ModelView.button_action(
        'account_payment_stripe.wizard_customer_source_detach')
    def detach_source(cls, customers):
        pass

    def delete_source(self, source):
        try:
            if source in dict(self.payment_methods()):
                stripe.PaymentMethod.detach(
                    source,
                    api_key=self.stripe_account.secret_key,
                    stripe_version=STRIPE_VERSION)
            else:
                stripe.Customer.delete_source(
                    self.stripe_customer_id,
                    source,
                    api_key=self.stripe_account.secret_key,
                    stripe_version=STRIPE_VERSION)
        except (stripe.error.RateLimitError,
                stripe.error.APIConnectionError) as e:
            logger.warning(str(e))
            raise
        self._sources_cache.clear()
        self._payment_methods_cache.clear()

    def payment_methods(self):
        methods = self._payment_methods_cache.get(self.id)
        if methods is not None:
            return methods
        methods = []
        if self.stripe_customer_id:
            try:
                payment_methods = stripe.PaymentMethod.list(
                    api_key=self.stripe_account.secret_key,
                    stripe_version=STRIPE_VERSION,
                    customer=self.stripe_customer_id)
            except (stripe.error.RateLimitError,
                    stripe.error.APIConnectionError) as e:
                logger.warning(str(e))
                return []
            for payment_method in payment_methods:
                name = self._payment_method_name(payment_method)
                methods.append((payment_method.id, name))
        self._payment_methods_cache.set(self.id, methods)
        return methods

    def _payment_method_name(cls, payment_method):
        name = payment_method.id
        if payment_method.type == 'card':
            card = payment_method.card
            name = card.brand
            if card.last4:
                name += ' ****' + card.last4
            if card.exp_month and card.exp_year:
                name += ' %s/%s' % (card.exp_month, card.exp_year)
        elif payment_method.type == 'sepa_debit':
            name = '****' + payment_method.sepa_debit.last4
        return name

    @property
    def stripe_setup_intent(self):
        if not self.stripe_setup_intent_id:
            return
        try:
            return stripe.SetupIntent.retrieve(
                self.stripe_setup_intent_id,
                api_key=self.stripe_account.secret_key,
                stripe_version=STRIPE_VERSION)
        except (stripe.error.RateLimitError,
                stripe.error.APIConnectionError) as e:
            logger.warning(str(e))

    stripe_intent = stripe_setup_intent

    @dualmethod
    def stripe_intent_update(cls, customers=None):
        """Update stripe customers with intent

        The transaction is committed after each customer."""
        if customers is None:
            customers = cls.search([
                    ('stripe_setup_intent_id', '!=', None),
                    ])

        for customer in customers:
            # Use clear cache after commit
            customer = cls(customer.id)
            setup_intent = customer.stripe_setup_intent
            if not setup_intent:
                continue
            if setup_intent.status not in {'succeeded', 'canceled'}:
                delay = customer.stripe_account.setup_intent_delay
                expiration = dt.datetime.now() - delay
                created = dt.datetime.fromtimestamp(setup_intent.created)
                if created < expiration:
                    setup_intent.cancel()
                continue
            customer.lock()
            try:
                if setup_intent.status == 'succeeded':
                    if customer.stripe_customer_id:
                        stripe.PaymentMethod.attach(
                            setup_intent.payment_method,
                            customer=customer.stripe_customer_id,
                            api_key=customer.stripe_account.secret_key,
                            stripe_version=STRIPE_VERSION)
                    else:
                        cu = stripe.Customer.create(
                            api_key=customer.stripe_account.secret_key,
                            stripe_version=STRIPE_VERSION,
                            payment_method=setup_intent.payment_method,
                            **customer._customer_parameters())
                        customer.stripe_customer_id = cu.id
            except (stripe.error.RateLimitError,
                    stripe.error.APIConnectionError) as e:
                logger.warning(str(e))
                continue
            except stripe.error.StripeError as e:
                if e.code in RETRY_CODES:
                    logger.warning(str(e))
                    continue
                customer.stripe_error_message = str(e)
            except Exception:
                logger.error(
                    "Error when updating customer %d", customer.id,
                    exc_info=True)
                continue
            else:
                customer.stripe_error_message = None
                customer.stripe_error_code = None
                customer.stripe_error_param = None
            customer.stripe_setup_intent_id = None
            customer.save()
            cls._payment_methods_cache.clear()
            Transaction().commit()

    def fetch_fingeprints(self):
        customer = self.retrieve(expand=['sources'])
        if customer:
            for source in customer.sources:
                if hasattr(source, 'fingerprint'):
                    yield source.fingerprint
            try:
                payment_methods = stripe.PaymentMethod.list(
                    api_key=self.stripe_account.secret_key,
                    stripe_version=STRIPE_VERSION,
                    customer=customer.id,
                    type='card')
            except (stripe.error.RateLimitError,
                    stripe.error.APIConnectionError) as e:
                logger.warning(str(e))
                payment_methods = []
            for payment_method in payment_methods:
                yield payment_method.card.fingerprint

    @classmethod
    @ModelView.button
    def find_identical(cls, customers):
        pool = Pool()
        Fingerprint = pool.get('account.payment.stripe.customer.fingerprint')
        new = []
        for customer in customers:
            fingerprints = set(customer.fetch_fingeprints())
            fingerprints -= {f.fingerprint for f in customer.fingerprints}
            for fingerprint in fingerprints:
                new.append(Fingerprint(
                        customer=customer,
                        fingerprint=fingerprint))
        Fingerprint.save(new)


class CustomerFingerprint(ModelSQL):
    "Stripe Customer Fingerprint"
    __name__ = 'account.payment.stripe.customer.fingerprint'
    customer = fields.Many2One(
        'account.payment.stripe.customer', "Customer",
        required=True, ondelete='CASCADE')
    fingerprint = fields.Char("Fingerprint", required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('customer_fingerprint_unique',
                Unique(t, t.customer, t.fingerprint),
                'account_payment_stripe.msg_customer_fingerprint_unique'),
            ]


class CustomerIdentical(ModelSQL):
    "Stripe Customer Identical"
    __name__ = 'account.payment.stripe.customer.identical'
    source = fields.Many2One('account.payment.stripe.customer', "Source")
    target = fields.Many2One('account.payment.stripe.customer', "Target")

    @classmethod
    def table_query(cls):
        pool = Pool()
        Fingerprint = pool.get('account.payment.stripe.customer.fingerprint')
        source = Fingerprint.__table__()
        target = Fingerprint.__table__()
        return (
            source
            .join(target, condition=source.fingerprint == target.fingerprint)
            .select(
                Literal(0).as_('create_uid'),
                source.create_date.as_('create_date'),
                Literal(None).as_('write_uid'),
                Literal(None).as_('write_date'),
                sql_pairing(source.id, target.id).as_('id'),
                source.customer.as_('source'),
                target.customer.as_('target'),
                where=source.customer != target.customer))


class Checkout(Wizard):
    "Stripe Checkout"
    __name__ = 'account.payment.stripe.checkout'
    start_state = 'checkout'
    checkout = StateAction('account_payment_stripe.url_checkout')

    def do_checkout(self, action):
        action['url'] = self.record.stripe_checkout_url
        return action, {}


class CheckoutPage(Report):
    "Stripe Checkout"
    __name__ = 'account.payment.stripe.checkout'


class CustomerSourceDetach(Wizard):
    "Detach Customer Source"
    __name__ = 'account.payment.stripe.customer.source.detach'
    start_state = 'ask'
    ask = StateView(
        'account.payment.stripe.customer.source.detach.ask',
        'account_payment_stripe.customer_source_detach_ask_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Detach", 'detach', 'tryton-ok', default=True),
            ])
    detach = StateTransition()

    def default_ask(self, fields):
        default = {}
        if 'customer' in fields:
            default['customer'] = self.record.id
        return default

    def transition_detach(self):
        self.record.delete_source(self.ask.source)
        return 'end'


class CustomerSourceDetachAsk(ModelView):
    "Detach Customer Source"
    __name__ = 'account.payment.stripe.customer.source.detach.ask'

    customer = fields.Many2One(
        'account.payment.stripe.customer', "Customer", readonly=True)
    source = fields.Selection('get_sources', "Source", required=True)

    @fields.depends('customer')
    def get_sources(self):
        sources = [('', '')]
        if self.customer:
            sources.extend(
                dict(set(self.customer.sources())
                    | set(self.customer.payment_methods())).items())
        return sources
