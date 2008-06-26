#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Purchase"

from trytond.osv import fields, OSV


class PurchaseLine(OSV):
    _name = 'purchase.line'

    analytic_accounts = fields.Many2One('analytic_account.account.selection',
            'Analytic Accounts', required=True,
            states={
                'invisible': "type != 'line'",
            })

    def _view_look_dom_arch(self, cursor, user, tree, type, context=None):
        analytic_account_obj = self.pool.get('analytic_account.account')
        analytic_account_obj.convert_view(cursor, user, tree, context=context)
        arch, fields = super(PurchaseLine, self)._view_look_dom_arch(cursor,
                user, tree, type, context=context)
        return arch, fields

    def fields_get(self, cursor, user, fields_names=None, context=None):
        analytic_account_obj = self.pool.get('analytic_account.account')

        res = super(PurchaseLine, self).fields_get(cursor, user, fields_names,
                context=context)

        analytic_accounts_field = super(PurchaseLine, self).fields_get(cursor,
                user, ['analytic_accounts'],
                context=context)['analytic_accounts']

        res.update(analytic_account_obj.analytic_accounts_fields_get(cursor,
            user, analytic_accounts_field, fields_names, context=context))
        return res

    def _read_flat(self, cursor, user, ids, fields_names, context=None,
            load='_classic_read'):
        selection_obj = self.pool.get('analytic_account.account.selection')
        res = super(PurchaseLine, self)._read_flat(cursor, user, ids,
                fields_names, context=context, load=load)

        root_ids = []
        for field in fields_names:
            if field.startswith('analytic_account_'):
                root_ids.append(int(field[len('analytic_account_'):]))
        if root_ids:
            id2record = {}
            for record in res:
                id2record[record['id']] = record
            lines = self.browse(cursor, user, ids, context=context)
            for line in lines:
                for account in line.analytic_accounts.accounts:
                    if account.root.id in root_ids:
                        id2record[line.id]['analytic_account_' \
                                + str(account.root.id)] = account.id
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
        if 'analytic_accounts' in vals:
            selection_obj.write(cursor, user, vals['analytic_accounts'],
                    selection_vals, context=context)
        else:
            selection_id = selection_obj.create(cursor, user, selection_vals,
                    context=context)
            vals['analytic_accounts'] = selection_id
        return super(PurchaseLine, self).create(cursor, user, vals,
                context=context)

    def write(self, cursor, user, ids, vals, context=None):
        selection_obj = self.pool.get('analytic_account.account.selection')
        vals = vals.copy()
        selection_vals = {}
        for field in vals.keys():
            if field.startswith('analytic_account_'):
                root_id = int(field[len('analytic_account_'):])
                selection_vals[root_id] = vals[field]
                del vals[field]
        if selection_vals:
            lines = self.browse(cursor, user, ids, context=context)
            for line in lines:
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
        return super(PurchaseLine, self).write(cursor, user, ids, vals,
                context=context)

    def unlink(self, cursor, user, ids, context=None):
        selection_obj = self.pool.get('analytic_account.account.selection')

        selection_ids = []
        lines = self.browse(cursor, user, ids, context=context)
        for line in lines:
            selection_ids.append(line.analytic_accounts.id)

        res = super(PurchaseLine, self).unlink(cursor, user, ids,
                context=context)
        selection_obj.unlink(cursor, user, selection_ids, context=context)
        return res

    def copy(self, cursor, user, line_id, default=None, context=None):
        selection_obj = self.pool.get('analytic_account.account.selection')

        if default is None:
            default = {}
        default = default.copy()
        line = self.browse(cursor, user, line_id, context=context)
        default['analytic_accounts'] = selection_obj.copy(cursor, user,
                line.analytic_accounts.id, context=context)
        return super(PurchaseLine, self).copy(cursor, user, line_id,
                default=default, context=context)

    def get_invoice_line(self, cursor, user, line, context=None):
        account_selection_obj = self.pool.get('analytic_account.account.selection')

        res = super(PurchaseLine, self).get_invoice_line(cursor, user, line,
                context=context)

        selection_id = account_selection_obj.copy(cursor, user,
                line.analytic_accounts.id, context=context)
        res['analytic_accounts'] = selection_id
        return res

PurchaseLine()


class Account(OSV):
    _name = 'analytic_account.account'

    def unlink(self, cursor, user, ids, context=None):
        invoice_line_obj = self.pool.get('purchase.line')
        try:
            invoice_line_obj.fields_view_get(cursor.dbname)
        except:
            pass
        return super(Account, self).unlink(cursor, user, ids, context=context)

    def create(self, cursor, user, vals, context=None):
        invoice_line_obj = self.pool.get('purchase.line')
        try:
            invoice_line_obj.fields_view_get(cursor.dbname)
        except:
            pass
        return super(Account, self).create(cursor, user, vals, context=context)

    def write(self, cursor, user, ids, vals, context=None):
        invoice_line_obj = self.pool.get('purchase.line')
        try:
            invoice_line_obj.fields_view_get(cursor.dbname)
        except:
            pass
        return super(Account, self).write(cursor, user, ids, vals,
                context=context)

Account()
