#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import copy
from trytond.model import ModelView, ModelSQL
from trytond.pyson import Eval
from trytond.transaction import Transaction


class Invoice(ModelSQL, ModelView):
    _name = 'account.invoice'

    def __init__(self):
        super(Invoice, self).__init__()
        self.lines = copy.copy(self.lines)
        add_remove = [
            ('invoice_type', '=', Eval('type')),
            ('party', '=', Eval('party')),
            ('currency', '=', Eval('currency')),
            ('company', '=', Eval('company')),
            ('invoice', '=', None),
        ]

        if not self.lines.add_remove:
            self.lines.add_remove = add_remove
        else:
            self.lines.add_remove = copy.copy(self.lines.add_remove)
            self.lines.add_remove = [
                add_remove,
                self.lines.add_remove,
            ]
        self._reset_columns()

Invoice()


class InvoiceLine(ModelSQL, ModelView):
    _name = 'account.invoice.line'

    def _view_look_dom_arch(self, tree, type, field_children=None):
        if type == 'form' and Transaction().context.get('standalone'):
            tree_root = tree.getroottree().getroot()
            if tree_root.get('cursor') == 'product':
                tree_root.set('cursor', 'party')
        return super(InvoiceLine, self)._view_look_dom_arch(tree, type,
            field_children=field_children)

InvoiceLine()
