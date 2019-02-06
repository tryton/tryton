# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import uuid
import logging

import stripe

from trytond.model import ModelSQL, ModelView, Workflow, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.report import Report
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

    stripe_checkout_needed = fields.Function(
        fields.Boolean("Stripe Checkout Needed"), 'get_stripe_checkout_needed')
    stripe_checkout_id = fields.Char("Stripe Checkout ID", readonly=True)
    stripe_charge_id = fields.Char("Stripe Charge ID", readonly=True)
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
    stripe_customer = fields.Many2One(
        'account.payment.stripe.customer', "Stripe Customer", readonly=True,
        domain=[
            ('party', '=', Eval('party', -1)),
            ('stripe_account', '=', Eval('stripe_account', -1)),
            ],
        depends=['party', 'stripe_account'])
    stripe_account = fields.Function(fields.Many2One(
            'account.payment.stripe.account', "Stripe Account"),
        'on_change_with_stripe_account')
    stripe_amount = fields.Function(
        fields.Integer("Stripe Amount"), 'get_stripe_amount')

    @classmethod
    def __setup__(cls):
        super(Payment, cls).__setup__()
        cls._error_messages.update({
                'stripe_receivable': ('Stripe journal "%(journal)s" '
                    'can only be used for receivable payment "%(payment)s".'),
                })
        cls._buttons.update({
                'stripe_checkout': {
                    'invisible': (~Eval('state', 'draft').in_(
                            ['approved', 'processing'])
                        | ~Eval('stripe_checkout_needed', False)),
                    },
                })

    def get_stripe_checkout_needed(self, name):
        return (self.journal.process_method == 'stripe'
            and not self.stripe_token
            and not self.stripe_customer)

    @fields.depends('journal')
    def on_change_with_stripe_account(self, name=None):
        if self.journal and self.journal.process_method == 'stripe':
            return self.journal.stripe_account.id

    def get_stripe_amount(self, name):
        return int(self.amount * 10**self.currency_digits)

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
    def copy(cls, payments, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default['stripe_checkout_id'] = None
        default['stripe_charge_id'] = None
        default['stripe_token'] = None
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
                        ('stripe_token', '!=', None),
                        ('stripe_customer', '!=', None),
                        ],
                    ('stripe_charge_id', '=', None),
                    ])
        for payment in payments:
            cls.__lock([payment])
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
                payment.save()
                if charge.status == 'succeeded':
                    cls.succeed([payment])
                elif charge.status == 'failed':
                    cls.fail([payment])
            Transaction().commit()

    def _charge_parameters(self):
        source, customer = None, None
        if self.stripe_token:
            source = self.stripe_token
        elif self.stripe_customer:
            customer = self.stripe_customer.stripe_customer_id
        return {
            'api_key': self.journal.stripe_account.secret_key,
            'amount': self.stripe_amount,
            'currency': self.currency.code,
            'description': self.description,
            'customer': customer,
            'source': source,
            'idempotency_key': self.stripe_checkout_id,
            }

    @classmethod
    def __lock(cls, records):
        from trytond.tools import grouped_slice, reduce_ids
        from sql import Literal, For
        transaction = Transaction()
        database = transaction.database
        connection = transaction.connection
        table = cls.__table__()

        if database.has_select_for():
            for sub_records in grouped_slice(records):
                where = reduce_ids(table.id, sub_records)
                query = table.select(
                    Literal(1), where=where, for_=For('UPDATE', nowait=True))
                with connection.cursor() as cursor:
                    cursor.execute(*query)
        else:
            database.lock(connection, cls._table)


class Account(ModelSQL, ModelView):
    "Stripe Account"
    __name__ = 'account.payment.stripe.account'

    name = fields.Char("Name", required=True)
    secret_key = fields.Char("Secret Key", required=True)
    publishable_key = fields.Char("Publishable Key", required=True)
    zip_code = fields.Boolean("Zip Code", help="Verification on checkout")

    @classmethod
    def default_zip_code(cls):
        return True


class Customer(ModelSQL, ModelView):
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
    stripe_customer_id = fields.Char("Stripe Customer ID", readonly=True)
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
    active = fields.Boolean("Active")

    @classmethod
    def __setup__(cls):
        super(Customer, cls).__setup__()
        cls._buttons.update({
                'stripe_checkout': {
                    'invisible': ~Eval('stripe_checkout_needed', False),
                    },
                })

    @classmethod
    def default_active(cls):
        return True

    def get_stripe_checkout_needed(self, name):
        return not self.stripe_token

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
