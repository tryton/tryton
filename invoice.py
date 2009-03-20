#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Invoice"
from trytond.model import ModelView, ModelSQL, fields


class InvoiceLine(ModelSQL, ModelView):
    _name = 'account.invoice.line'

    analytic_accounts = fields.Many2One('analytic_account.account.selection',
            'Analytic Accounts',
            states={
                'invisible': "type != 'line'",
            })

    def _view_look_dom_arch(self, cursor, user, tree, type, context=None):
        analytic_account_obj = self.pool.get('analytic_account.account')
        analytic_account_obj.convert_view(cursor, user, tree, context=context)
        arch, fields = super(InvoiceLine, self)._view_look_dom_arch(cursor,
                user, tree, type, context=context)
        return arch, fields

    def fields_get(self, cursor, user, fields_names=None, context=None):
        analytic_account_obj = self.pool.get('analytic_account.account')

        res = super(InvoiceLine, self).fields_get(cursor, user, fields_names,
                context=context)

        analytic_accounts_field = super(InvoiceLine, self).fields_get(cursor,
                user, ['analytic_accounts'],
                context=context)['analytic_accounts']

        res.update(analytic_account_obj.analytic_accounts_fields_get(cursor,
            user, analytic_accounts_field, fields_names, context=context))
        return res

    def read(self, cursor, user, ids, fields_names=None, context=None):
        selection_obj = self.pool.get('analytic_account.account.selection')

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]

        if fields_names:
            fields_names2 = [x for x in fields_names
                    if not x.startswith('analytic_account_')]
        else:
            fields_names2 = fields_names

        res = super(InvoiceLine, self).read(cursor, user, ids,
                fields_names=fields_names2, context=context)

        if not fields_names:
            fields_names = list(set(self._columns.keys() \
                    + self._inherit_fields.keys()))

        root_ids = []
        for field in fields_names:
            if field.startswith('analytic_account_') and '.' not in field:
                root_ids.append(int(field[len('analytic_account_'):]))
        if root_ids:
            id2record = {}
            for record in res:
                id2record[record['id']] = record
            lines = self.browse(cursor, user, ids, context=context)
            for line in lines:
                if line.type != 'line':
                    continue
                for account in line.analytic_accounts.accounts:
                    if account.root.id in root_ids:
                        id2record[line.id]['analytic_account_' \
                                + str(account.root.id)] = account.id
                        for field in fields_names:
                            if field.startswith('analytic_account_' + \
                                    str(account.root.id) + '.'):
                                ham, field2 = field.split('.', 1)
                                id2record[line.id][field] = account[field2]
        if int_id:
            return res[0]
        return res

    def create(self, cursor, user, vals, context=None):
        selection_obj = self.pool.get('analytic_account.account.selection')
        vals = vals.copy()
        selection_vals = {}
        for field in vals.keys():
            if field.startswith('analytic_account_'):
                if vals[field]:
                    selection_vals.setdefault('accounts', [])
                    selection_vals['accounts'].append(('add', vals[field]))
                del vals[field]
        if vals.get('analytic_accounts'):
            selection_obj.write(cursor, user, vals['analytic_accounts'],
                    selection_vals, context=context)
        elif vals.get('type', 'line') == 'line':
            selection_id = selection_obj.create(cursor, user, selection_vals,
                    context=context)
            vals['analytic_accounts'] = selection_id
        return super(InvoiceLine, self).create(cursor, user, vals,
                context=context)

    def write(self, cursor, user, ids, vals, context=None):
        selection_obj = self.pool.get('analytic_account.account.selection')
        vals = vals.copy()
        if isinstance(ids, (int, long)):
            ids = [ids]
        selection_vals = {}
        for field in vals.keys():
            if field.startswith('analytic_account_'):
                root_id = int(field[len('analytic_account_'):])
                selection_vals[root_id] = vals[field]
                del vals[field]
        if selection_vals:
            lines = self.browse(cursor, user, ids, context=context)
            for line in lines:
                if line.type != 'line':
                    continue
                accounts = []
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
                selection_obj.write(cursor, user, line.analytic_accounts.id, {
                    'accounts': [('set', accounts)],
                    }, context=context)
        return super(InvoiceLine, self).write(cursor, user, ids, vals,
                context=context)

    def delete(self, cursor, user, ids, context=None):
        selection_obj = self.pool.get('analytic_account.account.selection')

        if isinstance(ids, (int, long)):
            ids = [ids]
        selection_ids = []
        lines = self.browse(cursor, user, ids, context=context)
        for line in lines:
            if line.analytic_accounts:
                selection_ids.append(line.analytic_accounts.id)

        res = super(InvoiceLine, self).delete(cursor, user, ids,
                context=context)
        selection_obj.delete(cursor, user, selection_ids, context=context)
        return res

    def copy(self, cursor, user, ids, default=None, context=None):
        selection_obj = self.pool.get('analytic_account.account.selection')

        new_ids = super(InvoiceLine, self).copy(cursor, user, ids,
                default=default, context=context)

        int_id = False
        if isinstance(new_ids, (int, long)):
            int_id = True
            new_ids = [new_ids]

        for line in self.browse(cursor, user, new_ids, context=context):
            if line.analytic_accounts:
                selection_id = selection_obj.copy(cursor, user,
                        line.analytic_accounts.id, context=context)
                self.write(cursor, user, line.id, {
                    'analytic_accounts': selection_id,
                    }, context=context)

        if int_id:
            return new_ids[0]
        return new_ids

    def get_move_line(self, cursor, user, line, context=None):
        res = super(InvoiceLine, self).get_move_line(cursor, user, line,
                context=context)
        if line.analytic_accounts and line.analytic_accounts.accounts:
            res['analytic_lines'] = []
            for account in line.analytic_accounts.accounts:
                vals = {}
                vals['name'] = line.description
                vals['debit'] = res['debit']
                vals['credit'] = res['credit']
                vals['currency'] = line.invoice.currency.id
                vals['account'] = account.id
                vals['journal'] = line.invoice.journal.id
                vals['date'] = line.invoice.invoice_date
                vals['reference'] = line.invoice.reference
                vals['party'] = line.invoice.party.id
                res['analytic_lines'].append(('create', vals))
        return res

InvoiceLine()


class Account(ModelSQL, ModelView):
    _name = 'analytic_account.account'

    def delete(self, cursor, user, ids, context=None):
        account_invoice_line_obj = self.pool.get('account.invoice.line')
        res = super(Account, self).delete(cursor, user, ids, context=context)
        # Restart the cache on the fields_view_get method of account.invoice.line
        account_invoice_line_obj.fields_view_get(cursor.dbname)
        return res

    def create(self, cursor, user, vals, context=None):
        account_invoice_line_obj = self.pool.get('account.invoice.line')
        res = super(Account, self).create(cursor, user, vals, context=context)
        # Restart the cache on the fields_view_get method of account.invoice.line
        account_invoice_line_obj.fields_view_get(cursor.dbname)
        return res

    def write(self, cursor, user, ids, vals, context=None):
        account_invoice_line_obj = self.pool.get('account.invoice.line')
        res = super(Account, self).write(cursor, user, ids, vals,
                context=context)
        # Restart the cache on the fields_view_get method of account.invoice.line
        account_invoice_line_obj.fields_view_get(cursor.dbname)
        return res

Account()
