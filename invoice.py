#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.osv import OSV
import copy


class Invoice(OSV):
    _name = 'account.invoice'

    def __init__(self):
        super(Invoice, self).__init__()
        self.lines = copy.copy(self.lines)
        if not hasattr(self.lines, 'add_remove') or not self.lines.add_remove:
            self.lines.add_remove="[" \
                    "('invoice_type', '=', type)," \
                    "('party', '=', party)," \
                    "('currency', '=', currency)," \
                    "('company', '=', company)," \
                    "('invoice', '=', False)," \
                    "]"
        else:
            for clause in (
                    "('invoice_type', '=', type)",
                    "('party', '=', party)",
                    "('currency', '=', currency)",
                    "('company', '=', company)",
                    "('invoice', '=', False)",
                    ):
                if clause not in self.lines.add_remove:
                    sep = ''
                    if self.lines.add_remove[-2] != ',':
                        sep = ','
                    self.lines.add_remove = self.lines.add_remove[:-1] + \
                            sep + clause + self.lines.add_remove[-1:]
        self._reset_columns()

Invoice()

class InvoiceLine(OSV):
    _name = 'account.invoice.line'

    def _view_look_dom_arch(self, cursor, user, tree, type, context=None):
        if context is None:
            context = {}
        if type == 'form' and context.get('standalone'):
            tree_root = tree.getroottree().getroot()
            if tree_root.get('cursor') == 'product':
                tree_root.set('cursor', 'party')
        return super(InvoiceLine, self)._view_look_dom_arch(cursor, user, tree,
                type, context=context)

InvoiceLine()
