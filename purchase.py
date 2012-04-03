#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool


class Purchase(ModelSQL, ModelView):
    _name = "purchase.purchase"

    def __init__(self):
        super(Purchase, self).__init__()
        self._error_messages.update({
            'analytic_account_required': 'Analytic account is required ' \
                    'on line "%s" (%d)!',
            })

    def check_for_quotation(self, purchase_id):
        account_selection_obj = Pool().get(
                'analytic_account.account.selection')

        res = super(Purchase, self).check_for_quotation(purchase_id)

        purchase = self.browse(purchase_id)
        if not account_selection_obj.check_root(
                [x.analytic_accounts.id for x in purchase.lines
                    if x.analytic_accounts.id]):
            for line in purchase.lines:
                if line.type != 'line':
                    continue
                if not account_selection_obj.check_root(
                        [line.analytic_accounts.id]):
                    self.raise_user_error('analytic_account_required',
                            (line.rec_name, line.id))
        return res

Purchase()


class PurchaseLine(ModelSQL, ModelView):
    _name = 'purchase.line'

    analytic_accounts = fields.Many2One('analytic_account.account.selection',
        'Analytic Accounts',
        states={
            'invisible': Eval('type') != 'line',
            }, depends=['type'])

    def _view_look_dom_arch(self, tree, type, field_children=None):
        analytic_account_obj = Pool().get('analytic_account.account')
        analytic_account_obj.convert_view(tree)
        arch, fields = super(PurchaseLine, self)._view_look_dom_arch(tree,
            type, field_children=field_children)
        return arch, fields

    def fields_get(self, fields_names=None):
        analytic_account_obj = Pool().get('analytic_account.account')

        res = super(PurchaseLine, self).fields_get(fields_names)

        analytic_accounts_field = super(PurchaseLine, self).fields_get(
                ['analytic_accounts'])['analytic_accounts']

        res.update(analytic_account_obj.analytic_accounts_fields_get(
            analytic_accounts_field, fields_names))
        return res

    def default_get(self, fields, with_rec_name=True):
        fields = [x for x in fields if not x.startswith('analytic_account_')]
        return super(PurchaseLine, self).default_get(fields,
            with_rec_name=with_rec_name)

    def read(self, ids, fields_names=None):
        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]

        if fields_names:
            fields_names2 = [x for x in fields_names
                    if not x.startswith('analytic_account_')]
        else:
            fields_names2 = fields_names

        res = super(PurchaseLine, self).read(ids, fields_names=fields_names2)

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
            lines = self.browse(ids)
            for line in lines:
                for root_id in root_ids:
                    id2record[line.id]['analytic_account_' \
                            + str(root_id)] = None
                if line.type != 'line':
                    continue
                if not line.analytic_accounts:
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

    def create(self, vals):
        selection_obj = Pool().get('analytic_account.account.selection')
        vals = vals.copy()
        selection_vals = {}
        for field in vals.keys():
            if field.startswith('analytic_account_'):
                if vals[field]:
                    selection_vals.setdefault('accounts', [])
                    selection_vals['accounts'].append(('add', vals[field]))
                del vals[field]
        if vals.get('analytic_accounts'):
            selection_obj.write(vals['analytic_accounts'], selection_vals)
        elif vals.get('type', 'line') == 'line':
            selection_id = selection_obj.create(selection_vals)
            vals['analytic_accounts'] = selection_id
        return super(PurchaseLine, self).create(vals)

    def write(self, ids, vals):
        selection_obj = Pool().get('analytic_account.account.selection')
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
            lines = self.browse(ids)
            for line in lines:
                if line.type != 'line':
                    continue
                accounts = []
                if not line.analytic_accounts:
                    # Create missing selection
                    with Transaction().set_user(0):
                        selection_id = selection_obj.create({})
                    self.write(line.id, {
                        'analytic_accounts': selection_id,
                        })
                    line = self.browse(line.id)
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
                selection_obj.write(line.analytic_accounts.id, {
                    'accounts': [('set', accounts)],
                    })
        return super(PurchaseLine, self).write(ids, vals)

    def delete(self, ids):
        selection_obj = Pool().get('analytic_account.account.selection')

        if isinstance(ids, (int, long)):
            ids = [ids]
        selection_ids = []
        lines = self.browse(ids)
        for line in lines:
            if line.analytic_accounts:
                selection_ids.append(line.analytic_accounts.id)

        res = super(PurchaseLine, self).delete(ids)
        selection_obj.delete(selection_ids)
        return res

    def copy(self, ids, default=None):
        selection_obj = Pool().get('analytic_account.account.selection')

        new_ids = super(PurchaseLine, self).copy(ids, default=default)

        int_id = False
        if isinstance(new_ids, (int, long)):
            int_id = True
            new_ids = [new_ids]

        for line in self.browse(new_ids):
            if line.analytic_accounts:
                selection_id = selection_obj.copy(line.analytic_accounts.id)
                self.write(line.id, {
                    'analytic_accounts': selection_id,
                    })

        if int_id:
            return new_ids[0]
        return new_ids

    def get_invoice_line(self, line):
        pool = Pool()
        account_selection_obj = pool.get('analytic_account.account.selection')

        res = super(PurchaseLine, self).get_invoice_line(line)
        if not res:
            return res

        selection_id = False
        if line.analytic_accounts:
            selection_id = account_selection_obj.copy(
                line.analytic_accounts.id)
        for vals in res:
            vals['analytic_accounts'] = selection_id
        return res

PurchaseLine()


class Account(ModelSQL, ModelView):
    _name = 'analytic_account.account'

    def delete(self, ids):
        purchase_line_obj = Pool().get('purchase.line')
        res = super(Account, self).delete(ids)
        # Restart the cache on the fields_view_get method of purchase.line
        purchase_line_obj.fields_view_get.reset()
        return res

    def create(self, vals):
        purchase_line_obj = Pool().get('purchase.line')
        res = super(Account, self).create(vals)
        # Restart the cache on the fields_view_get method of purchase.line
        purchase_line_obj.fields_view_get.reset()
        return res

    def write(self, ids, vals):
        purchase_line_obj = Pool().get('purchase.line')
        res = super(Account, self).write(ids, vals)
        # Restart the cache on the fields_view_get method of purchase.line
        purchase_line_obj.fields_view_get.reset()
        return res

Account()
