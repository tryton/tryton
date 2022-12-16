# This file is part of Tryton.  The COPYRIGHT file at the toplevel of this
# repository contains the full copyright notices and license terms.
from trytond.model import fields

__all__ = ['Monetary']


class Monetary(fields.Numeric):
    """
    Define a numeric field with currency (``decimal``).
    """
    def __init__(self, string='', currency=None, digits=None, help='',
            required=False, readonly=False, domain=None, states=None,
            select=False, on_change=None, on_change_with=None, depends=None,
            context=None, loading='eager'):
        '''
        :param currency: the name of the Many2One field which stores
            the currency
        '''
        if currency:
            if depends is None:
                depends = [currency]
            elif currency not in depends:
                depends = depends.copy()
                depends.append(currency)
        super().__init__(string=string, digits=digits, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            select=select, on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)
        self.currency = currency

    def definition(self, model, language):
        definition = super().definition(model, language)
        definition['symbol'] = self.currency
        definition['monetary'] = True
        return definition
