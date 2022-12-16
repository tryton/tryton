# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval


class BraintreeCustomerMethodMixin:
    __slots__ = ()

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
            'readonly': (
                ~Eval('party') | (Eval('party', -1) < 0)
                | ~Eval('braintree_account')
                | (Eval('braintree_account', -1) < 0)),
            })
    braintree_customer_method = fields.Char(
        "Braintree Customer Method",
        states={
            'invisible': (
                (Eval('process_method') != 'braintree')
                | ~Eval('braintree_customer')),
            })
    # Use Function field with selection
    # to avoid querying Braintree on validation
    braintree_customer_method_selection = fields.Function(fields.Selection(
            'get_braintree_customer_methods', "Braintree Customer Method",
            states={
                'invisible': (
                    (Eval('process_method') != 'braintree')
                    | ~Eval('braintree_customer')),
                }),
        'get_braintree_customer_method',
        setter='set_braintree_customer_method')

    def on_change_party(self):
        try:
            super().on_change_party()
        except AttributeError:
            pass
        self.braintree_customer = None

    @fields.depends('journal')
    def on_change_with_braintree_account(self, name=None):
        if self.journal and self.journal.process_method == 'braintree':
            return self.journal.braintree_account.id

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
