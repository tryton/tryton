# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval


class StripeCustomerMethodMixin:
    __slots__ = ()

    stripe_account = fields.Function(fields.Many2One(
            'account.payment.stripe.account', "Stripe Account"),
        'on_change_with_stripe_account')

    stripe_customer = fields.Many2One(
        'account.payment.stripe.customer', "Stripe Customer",
        domain=[
            ('party', '=', Eval('party', -1)),
            ('stripe_account', '=', Eval('stripe_account', -1)),
            ],
        states={
            'invisible': Eval('process_method') != 'stripe',
            'readonly': (
                ~Eval('party') | (Eval('party', -1) < 0)
                | ~Eval('stripe_account') | (Eval('stripe_account', -1) < 0)),
            })

    stripe_customer_source = fields.Char(
        "Stripe Customer Source",
        states={
            'invisible': (
                (Eval('process_method') != 'stripe')
                | ~Eval('stripe_customer')
                | Eval('stripe_customer_payment_method')),
            })
    # Use Function field with selection to avoid to query Stripe
    # to validate the value
    stripe_customer_source_selection = fields.Function(fields.Selection(
            'get_stripe_customer_sources', "Stripe Customer Source",
            states={
                'invisible': (
                    (Eval('process_method') != 'stripe')
                    | ~Eval('stripe_customer')
                    | Eval('stripe_customer_payment_method')),
                }),
        'get_stripe_customer_source', setter='set_stripe_customer_source')

    stripe_customer_payment_method = fields.Char(
        "Stripe Payment Method",
        states={
            'invisible': (
                (Eval('process_method') != 'stripe')
                | ~Eval('stripe_customer')
                | Eval('stripe_customer_source')),
            })
    # Use Function field with selection to avoid to query Stripe
    # to validate the value
    stripe_customer_payment_method_selection = fields.Function(
        fields.Selection(
            'get_stripe_customer_payment_methods',
            "Stripe Customer Payment Method",
            states={
                'invisible': (
                    (Eval('process_method') != 'stripe')
                    | ~Eval('stripe_customer')
                    | Eval('stripe_customer_source')),
                }),
        'get_stripe_customer_payment_method',
        setter='set_stripe_customer_payment_method')

    def on_change_party(self):
        try:
            super().on_change_party()
        except AttributeError:
            pass
        self.stripe_customer = None
        self.stripe_customer_source = None
        self.stripe_customer_source_selection = None

    @fields.depends('journal')
    def on_change_with_stripe_account(self, name=None):
        if self.journal and self.journal.process_method == 'stripe':
            return self.journal.stripe_account

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

    @classmethod
    def set_stripe_customer_source(cls, payments, name, value):
        pass

    @fields.depends('stripe_customer', 'stripe_customer_payment_method')
    def get_stripe_customer_payment_methods(self):
        methods = [('', '')]
        if self.stripe_customer:
            methods.extend(self.stripe_customer.payment_methods())
        if (self.stripe_customer_payment_method
                and self.stripe_customer_payment_method not in dict(methods)):
            methods.append(
                (self.stripe_customer_payment_method,
                    self.stripe_customer_payment_method))
        return methods

    @fields.depends(
        'stripe_customer_payment_method_selection',
        'stripe_customer_payment_method')
    def on_change_stripe_customer_payment_method_selection(self):
        self.stripe_customer_payment_method = (
            self.stripe_customer_payment_method_selection)

    def get_stripe_customer_payment_method(self, name):
        return self.stripe_customer_payment_method

    @classmethod
    def set_stripe_customer_payment_method(cls, payments, name, value):
        pass
