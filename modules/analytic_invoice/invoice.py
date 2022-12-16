#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['InvoiceLine', 'Account']
__metaclass__ = PoolMeta


class InvoiceLine:
    __name__ = 'account.invoice.line'
    analytic_accounts = fields.Many2One('analytic_account.account.selection',
        'Analytic Accounts',
        states={
            'invisible': Eval('type') != 'line',
            },
        depends=['type'])

    @classmethod
    def _view_look_dom_arch(cls, tree, type, field_children=None):
        AnalyticAccount = Pool().get('analytic_account.account')
        AnalyticAccount.convert_view(tree)
        return super(InvoiceLine, cls)._view_look_dom_arch(tree, type,
            field_children=field_children)

    @classmethod
    def fields_get(cls, fields_names=None):
        AnalyticAccount = Pool().get('analytic_account.account')

        fields = super(InvoiceLine, cls).fields_get(fields_names)

        analytic_accounts_field = super(InvoiceLine, cls).fields_get(
                ['analytic_accounts'])['analytic_accounts']

        fields.update(AnalyticAccount.analytic_accounts_fields_get(
                analytic_accounts_field, fields_names))
        return fields

    @classmethod
    def default_get(cls, fields, with_rec_name=True):
        fields = [x for x in fields if not x.startswith('analytic_account_')]
        return super(InvoiceLine, cls).default_get(fields,
            with_rec_name=with_rec_name)

    @classmethod
    def read(cls, ids, fields_names=None):
        if fields_names:
            fields_names2 = [x for x in fields_names
                    if not x.startswith('analytic_account_')]
        else:
            fields_names2 = fields_names

        res = super(InvoiceLine, cls).read(ids, fields_names=fields_names2)

        if not fields_names:
            fields_names = cls._fields.keys()

        root_ids = []
        for field in fields_names:
            if field.startswith('analytic_account_') and '.' not in field:
                root_ids.append(int(field[len('analytic_account_'):]))
        if root_ids:
            id2record = {}
            for record in res:
                id2record[record['id']] = record
            lines = cls.browse(ids)
            for line in lines:
                for root_id in root_ids:
                    id2record[line.id]['analytic_account_'
                        + str(root_id)] = None
                if line.type != 'line':
                    continue
                if not line.analytic_accounts:
                    continue
                for account in line.analytic_accounts.accounts:
                    if account.root.id in root_ids:
                        id2record[line.id]['analytic_account_'
                            + str(account.root.id)] = account.id
                        for field in fields_names:
                            if field.startswith('analytic_account_'
                                    + str(account.root.id) + '.'):
                                ham, field2 = field.split('.', 1)
                                id2record[line.id][field] = account[field2]
        return res

    @classmethod
    def create(cls, vlist):
        Selection = Pool().get('analytic_account.account.selection')
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            selection_vals = {}
            for field in vals.keys():
                if field.startswith('analytic_account_'):
                    if vals[field]:
                        selection_vals.setdefault('accounts', [])
                        selection_vals['accounts'].append(('add',
                                [vals[field]]))
                    del vals[field]
            if vals.get('analytic_accounts'):
                Selection.write([Selection(vals['analytic_accounts'])],
                    selection_vals)
            elif vals.get('type', 'line') == 'line':
                selection, = Selection.create([selection_vals])
                vals['analytic_accounts'] = selection.id
        return super(InvoiceLine, cls).create(vlist)

    @classmethod
    def write(cls, lines, vals):
        Selection = Pool().get('analytic_account.account.selection')
        vals = vals.copy()
        selection_vals = {}
        for field in vals.keys():
            if field.startswith('analytic_account_'):
                root_id = int(field[len('analytic_account_'):])
                selection_vals[root_id] = vals[field]
                del vals[field]
        if selection_vals:
            for line in lines:
                if line.type != 'line':
                    continue
                accounts = []
                if not line.analytic_accounts:
                    # Create missing selection
                    with Transaction().set_user(0):
                            selection, = Selection.create([{}])
                    cls.write([line], {
                            'analytic_accounts': selection.id,
                            })
                for account in line.analytic_accounts.accounts:
                    if account.root.id in selection_vals:
                        value = selection_vals[account.root.id]
                        if value:
                            accounts.append(value)
                    else:
                        accounts.append(account.id)
                for account_id in selection_vals.values():
                    if account_id \
                            and account_id not in accounts:
                        accounts.append(account_id)
                Selection.write([line.analytic_accounts], {
                        'accounts': [('set', accounts)],
                        })
        super(InvoiceLine, cls).write(lines, vals)

    @classmethod
    def delete(cls, lines):
        Selection = Pool().get('analytic_account.account.selection')

        selection_ids = []
        for line in lines:
            if line.analytic_accounts:
                selection_ids.append(line.analytic_accounts.id)

        super(InvoiceLine, cls).delete(lines)
        Selection.delete(Selection.browse(selection_ids))

    @classmethod
    def copy(cls, lines, default=None):
        Selection = Pool().get('analytic_account.account.selection')

        new_lines = super(InvoiceLine, cls).copy(lines, default=default)

        for line in new_lines:
            if line.analytic_accounts:
                selection, = Selection.copy([line.analytic_accounts])
                cls.write([line], {
                        'analytic_accounts': selection.id,
                        })
        return new_lines

    def _credit(self):
        Selection = Pool().get('analytic_account.account.selection')

        result = super(InvoiceLine, self)._credit()

        if self.analytic_accounts:
            selection, = Selection.copy([self.analytic_accounts])
            result['analytic_accounts'] = selection.id
        return result

    def get_move_line(self):
        values = super(InvoiceLine, self).get_move_line()
        if self.analytic_accounts and self.analytic_accounts.accounts:
            for value in values:
                value['analytic_lines'] = []
                to_create = []
                for account in self.analytic_accounts.accounts:
                    vals = {}
                    vals['name'] = self.description
                    vals['debit'] = value['debit']
                    vals['credit'] = value['credit']
                    vals['account'] = account.id
                    vals['journal'] = self.invoice.journal.id
                    vals['date'] = (self.invoice.accounting_date 
                        or self.invoice.invoice_date)
                    vals['reference'] = self.invoice.reference
                    vals['party'] = self.invoice.party.id
                    to_create.append(vals)
                if to_create:
                    value['analytic_lines'] = [('create', to_create)]
        return values


class Account(ModelSQL, ModelView):
    __name__ = 'analytic_account.account'

    @classmethod
    def delete(cls, accounts):
        InvoiceLine = Pool().get('account.invoice.line')
        super(Account, cls).delete(accounts)
        # Restart the cache on the fields_view_get method of
        # account.invoice.line
        InvoiceLine._fields_view_get_cache.clear()

    @classmethod
    def create(cls, vlist):
        InvoiceLine = Pool().get('account.invoice.line')
        accounts = super(Account, cls).create(vlist)
        # Restart the cache on the fields_view_get method of
        # account.invoice.line
        InvoiceLine._fields_view_get_cache.clear()
        return accounts

    @classmethod
    def write(cls, accounts, vals):
        InvoiceLine = Pool().get('account.invoice.line')
        super(Account, cls).write(accounts, vals)
        # Restart the cache on the fields_view_get method of
        # account.invoice.line
        InvoiceLine._fields_view_get_cache.clear()
