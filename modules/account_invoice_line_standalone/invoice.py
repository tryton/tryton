#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import PoolMeta

__all__ = ['Invoice', 'InvoiceLine']
__metaclass__ = PoolMeta


class Invoice:
    __name__ = 'account.invoice'

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        add_remove = [
            ('invoice_type', '=', Eval('type')),
            ('party', '=', Eval('party')),
            ('currency', '=', Eval('currency')),
            ('company', '=', Eval('company')),
            ('invoice', '=', None),
        ]

        if not cls.lines.add_remove:
            cls.lines.add_remove = add_remove
        else:
            cls.lines.add_remove = [
                add_remove,
                cls.lines.add_remove,
                ]


class InvoiceLine:
    __name__ = 'account.invoice.line'

    @classmethod
    def _view_look_dom_arch(cls, tree, type, field_children=None):
        if type == 'form' and Transaction().context.get('standalone'):
            tree_root = tree.getroottree().getroot()
            if tree_root.get('cursor') == 'product':
                tree_root.set('cursor', 'party')
        return super(InvoiceLine, cls)._view_look_dom_arch(tree, type,
            field_children=field_children)
