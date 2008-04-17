"Tax"

from trytond.osv import fields, OSV
from trytond.wizard import Wizard, WizardOSV
from decimal import Decimal


class Group(OSV):
    'Tax Group'
    _name = 'account.tax.group'
    _description = __doc__

    name = fields.Char('Name', size=None, required=True, translate=True)
    code = fields.Char('Code', size=None, required=True)

    def __init__(self):
        super(Group, self).__init__()
        self._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'Code must be unique!'),
        ]

Group()


class Code(OSV):
    'Tax Code'
    _name = 'account.tax.code'
    _description = __doc__
    _order = 'code, id'

    name = fields.Char('Name', size=None, required=True, select=1)
    code = fields.Char('Code', size=None, select=1)
    active = fields.Boolean('Active', select=2)
    company = fields.Many2One('company.company', 'Company', required=True)
    parent = fields.Many2One('account.tax.code', 'Parent', select=1,
            domain="[('company', '=', company)]")
    childs = fields.One2Many('account.tax.code', 'parent', 'Childs',
            domain="[('company', '=', company)]")
    sum = fields.Function('get_sum', digits=(16, 2), string='Sum')

    def __init__(self):
        super(Code, self).__init__()
        self._constraints += [
            ('check_recursion',
                'Error! You can not create recursive tax code!', ['parent']),
        ]

    def default_active(self, cursor, user, context=None):
        return True

    def default_company(self, cursor, user, context=None):
        if context is None:
            context = {}
        return context.get('company', False)

    def get_sum(self, cursor, user, ids, name, arg, context=None):
        res = {}
        move_line_obj = self.pool.get('account.move.line')
        currency_obj = self.pool.get('account.currency')

        child_ids = self.search(cursor, user, [('parent', 'child_of', ids)],
                context=context)
        all_ids = {}.fromkeys(ids + child_ids).keys()
        line_query = move_line_obj.query_get(cursor, user, context=context)
        cursor.execute('SELECT c.id, ' \
                    'SUM(tl.amount) ' \
                'FROM account_tax_code c, ' \
                    'account_tax_line tl, ' \
                    'account_move_line l ' \
                'WHERE c.id = tl.code ' \
                    'AND tl.move_line = l.id ' \
                    'AND c.id IN (' + \
                        ','.join(['%s' for x in all_ids])+ ') ' \
                    'AND ' + line_query + ' ' \
                    'AND c.active ' \
                'GROUP BY c.id', all_ids)
        code_sum = {}
        for code_id, sum in cursor.fetchall():
            code_sum[code_id] = sum

        for code in self.browse(cursor, user, ids, context=context):
            res.setdefault(code.id, Decimal('0.0'))
            child_ids = self.search(cursor, user, [
                ('parent', 'child_of', [code.id]),
                ], context=context)
            for child_id in child_ids:
                res[code.id] += currency_obj.round(cursor, user,
                        code.company.currency,
                        code_sum.get(child_id, Decimal('0.0')))
            res[code.id] = currency_obj.round(cursor, user,
                    code.company.currency, res[code.id])
        return res

    def name_search(self, cursor, user, name='', args=None, operator='ilike',
            context=None, limit=None):
        if name:
            ids = self.search(cursor, user,
                    [('code', 'like', name + '%')] + args,
                    limit=limit, context=context)
            if not ids:
                ids = self.search(cursor, user,
                        [(self._rec_name, operator, name)] + args,
                        limit=limit, context=context)
        else:
            ids = self.search(cursor, user, args, limit=limit, context=context)
        res = self.name_get(cursor, user, ids, context=context)
        return res

    def name_get(self, cursor, user, ids, context=None):
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        return [(r['id'], r['code'] and r['code'] + ' - ' + str(r[self._rec_name]) \
                or str(r[self._rec_name])) for r in self.read(cursor, user, ids,
                    [self._rec_name, 'code'], context=context, load='_classic_write')]

Code()


class OpenChartCodeInit(WizardOSV):
    _name = 'account.tax.open_chart_code.init'
    method = fields.Selection([
        ('fiscalyear', 'By Fiscal Year'),
        ('periods', 'By Periods'),
        ], 'Method', required=True)
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            help='Keep empty for all open fiscal year',
            states={
                'invisible': "method != 'fiscalyear'",
            })
    periods = fields.Many2Many('account.period', None, None, None, 'Periods',
            help='Keep empty for all periods of all open fiscal year',
            states={
                'invisible': "method != 'periods'",
            })

    def default_method(self, cursor, user, context=None):
        return 'periods'

OpenChartCodeInit()


class OpenChartCode(Wizard):
    'Open Chart Of Tax Code by Fiscal Year'
    _name = 'account.tax.open_chart_code'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'account.tax.open_chart_code.init',
                'state': [
                    ('end', 'Cancel', 'gtk-cancel'),
                    ('open', 'Open', 'gtk-ok', True),
                ],
            },
        },
        'open': {
            'result': {
                'type': 'action',
                'action': '_action_open_chart',
                'state': 'end',
            },
        },
    }

    def _action_open_chart(self, cursor, user, data, context=None):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_tax_code_tree2'),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id,
                context=context)
        if data['form']['method'] == 'fiscalyear':
            res['context'] = str({'fiscalyear': data['form']['fiscalyear']})
        else:
            res['context'] = str({'periods': data['form']['periods'][0][1]})
        return res

OpenChartCode()


class Tax(OSV):
    '''
    Account Tax

    Type:
        percentage: tax = price * amount
        fixed: tax = amount
        none: tax = none
    '''
    _name = 'account.tax'
    _description = 'Account Tax'
    _order = 'sequence, id'

    name = fields.Char('Name', size=None, required=True, translate=True)
    group = fields.Many2One('account.tax.group', 'Group', required=True,
            states={
                'invisible': "locals().get('parent', True)",
            })
    active = fields.Boolean('Active')
    sequence = fields.Integer('Sequence', required=True,
            help='Use to order the taxes')
    amount = fields.Numeric('Amount', digits=(16, 2),
            states={
                'invisible': "type != 'fixed'",
            }, invisible=True)
    percentage = fields.Numeric('Percentage', digits=(16, 8),
            states={
                'invisible': "type != 'percentage'",
            })
    type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed'),
        ('none', 'None'),
        ], 'Type', required=True)
    parent = fields.Many2One('account.tax', 'Parent')
    childs = fields.One2Many('account.tax', 'parent', 'Childs')

    company = fields.Many2One('company.company', 'Company', required=True)
    invoice_account = fields.Many2One('account.account', 'Invoice Account',
            domain="[('company', '=', company)]",
            help='Keep empty to use the default invoice account',
            states={
                'readonly': "type == 'none'",
            })
    refund_account = fields.Many2One('account.account', 'Refund Account',
            domain="[('company', '=', company)]",
            help='Keep empty to use the default refund account',
            states={
                'readonly': "type == 'none'",
            })

    invoice_base_code = fields.Many2One('account.tax.code',
            'Invoice Base Code',
            states={
                'readonly': "type == 'none'",
            })
    invoice_base_sign = fields.Numeric('Invoice Base Sign', digits=(2, 0),
            help='Usualy 1 or -1',
            states={
                'readonly': "type == 'none'",
            })
    invoice_tax_code = fields.Many2One('account.tax.code',
            'Invoice Tax Code',
            states={
                'readonly': "type == 'none'",
            })
    invoice_tax_sign = fields.Numeric('Invoice Tax Sign', digits=(2, 0),
            help='Usualy 1 or -1',
            states={
                'readonly': "type == 'none'",
            })
    refund_base_code = fields.Many2One('account.tax.code',
            'Refund Base Code',
            states={
                'readonly': "type == 'none'",
            })
    refund_base_sign = fields.Numeric('Refund Base Sign', digits=(2, 0),
            help='Usualy 1 or -1',
            states={
                'readonly': "type == 'none'",
            })
    refund_tax_code = fields.Many2One('account.tax.code',
            'Refund Tax Code',
            states={
                'readonly': "type == 'none'",
            })
    refund_tax_sign = fields.Numeric('Refund Tax Sign', digits=(2, 0),
            help='Usualy 1 or -1',
            states={
                'readonly': "type == 'none'",
            })

    def default_active(self, cursor, user, context=None):
        return True

    def default_group(self, cursor, user, context=None):
        group_obj = self.pool.get('account.tax.group')
        group_ids = group_obj.search(cursor, user, [
            ('code', '=', 'none'),
            ], limit=1, context=context)
        return group_obj.name_get(cursor, user, group_ids[0],
                context=context)

    def default_type(self, cursor, user, context=None):
        return 'percentage'

    def default_include_base_amount(self, cursor, user, context=None):
        return False

    def default_invoice_base_sign(self, cursor, user, context=None):
        return 1

    def default_invoice_tax_sign(self, cursor, user, context=None):
        return 1

    def default_refund_base_sign(self, cursor, user, context=None):
        return 1

    def default_refund_tax_sign(self, cursor, user, context=None):
        return 1

    def default_company(self, cursor, user, context=None):
        if context is None:
            context = {}
        return context.get('company', False)

    def _process_tax(self, cursor, user, tax, price_unit, context=None):
        if tax.type == 'percentage':
            amount = price_unit * tax.percentage
            return {
                'base': price_unit,
                'amount': amount,
                'tax': tax,
            }
        if tax.type == 'fixed':
            amount = tax.amount
            return {
                'base': price_unit,
                'amount': amount,
                'tax': tax,
            }

    def _unit_compute(self, cursor, user, taxes, price_unit, context=None):
        res = []
        for tax in taxes:
            if tax.type != 'none':
                res.append(self._process_tax(cursor, user, tax, price_unit,
                    context=context))
            if len(tax.childs):
                res.extend(self._unit_compute(cursor, user, tax.childs,
                    price_unit, context=context))
        return res

    def compute(self, cursor, user, ids, price_unit, quantity, context=None):
        '''
        Compute taxes for price_unit and quantity.
        Return list of dict for each taxes and their childs with:
            base
            amount
            tax
        '''
        ids = self.search(cursor, user, [
            ('id', 'in', ids),
            ], order='sequence, id', context=context)
        taxes = self.browse(cursor, user, ids, context=context)
        res = self._unit_compute(cursor, user, taxes, price_unit,
                context=context)
        for row in res:
            row['base'] *= Decimal(str(quantity))
            row['amount'] *= Decimal(str(quantity))
        return res

    def _process_tax_inv(self, cursor, user, tax, price_unit, context=None):
        # base will be calculate when all taxes will be compute
        if tax.type == 'percentage':
            amount = price_unit - (price_unit / (1 + tax.percentage))
            return {
                'base': price_unit,
                'amount': amount,
                'tax': tax,
            }
        if tax.type == 'fixed':
            amount = tax.amount
            return {
                'base': price_unit,
                'amount': amount,
                'tax': tax,
            }

    def _unit_compute_inv(self, cursor, user, taxes, price_unit, context=None):
        res = []
        total_amount = Decimal('0.0')
        for tax in taxes:
            if tax.type != 'none':
                res.append(self._process_tax_inv(cursor, user, tax, price_unit,
                    context=context))
                total_amount += res[-1]['amount']
            if len(tax.childs):
                tax.childs.reverse()
                res_childs = self._unit_compute_inv(cursor, user, tax.childs,
                    price_unit, context=context)
                for res_child in res_childs:
                    total_amount += res_child['amount']
                res.extend(res_childs)
        for row in res:
            res['base'] -= total_amount
        return res

    def compute_inv(self, cursor, user, ids, price_unit, quantity,
            context=None):
        '''
        Compute the inverse taxes for price_unit and quantity.
        Return list of dict for each taxes and their childs with:
            base
            amount
            tax
        '''
        ids = self.search(cursor, user, [
            ('id', 'in', ids),
            ], order='sequence, id', context=context)
        taxes = self.browse(cursor, user, ids, context=context)
        taxes.reverse()
        res = self._unit_compute_inv(cursor, user, taxes, price_unit,
                context=context)
        res.reverse()
        for row in res:
            row['amount'] *= quantity
        return res

Tax()


class Line(OSV):
    'Tax Line'
    _name = 'account.tax.line'
    _description = __doc__
    _rec_name = 'amount'

    amount = fields.Numeric('Amount', digits=(16, 2))
    code = fields.Many2One('account.tax.code', 'Code', select=1, required=True)
    move_line = fields.Many2One('account.move.line', 'Move Line',
            required=True, select=1, ondelete='CASCADE')

Line()


class OpenCode(Wizard):
    'Open Code'
    _name = 'account.tax.open_code'
    states = {
        'init': {
            'result': {
                'type': 'action',
                'action': '_action_open_code',
                'state': 'end',
            },
        },
    }

    def _action_open_code(self, cursor, user, data, context=None):
        if context is None:
            context = {}
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        period_obj = self.pool.get('account.period')

        if not context.get('fiscalyear'):
            fiscalyear_ids = fiscalyear_obj.search(cursor, user, [
                ('state', '=', 'open'),
                ], context=context)
        else:
            fiscalyear_ids = [context['fiscalyear']]

        period_ids = []
        if not context.get('periods'):
            period_ids = period_obj.search(cursor, user, [
                ('fiscalyear', 'in', fiscalyear_ids),
                ], context=context)
        else:
            period_ids = context['periods']

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_tax_line_form'),
            ('module', '=', 'account'),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id,
                context=context)
        res['domain'] = str([
            ('move_line.period', 'in', period_ids),
            ('code', '=', data['id']),
            ])
        if context.get('fiscalyear'):
            res['context'] = str({'fiscalyear': context['fiscalyear']})
        else:
            res['context'] = str({'periods': period_ids})
        return res

OpenCode()


class AccountTemplate(OSV):
    _name = 'account.account.template'
    taxes = fields.Many2Many('account.tax', 'account_account_template_tax_rel',
            'account', 'tax', 'Default Taxes',
            domain="[('parent', '=', False)]")

AccountTemplate()


class Account(OSV):
    _name = 'account.account'
    taxes = fields.Many2Many('account.tax', 'account_account_tax_rel',
            'account', 'tax', 'Default Taxes',
            domain="[('company', '=', company), ('parent', '=', False)]",
            help='Default tax for manual encoding move lines \n' \
                    'for journal type: "expense" and "revenue"')

Account()

class Partner(OSV):
    _name = 'partner.partner'
    tax_vat = fields.Property(type='many2one',
            relation='account.tax', string='VAT',
            group_name='Accounting Properties', view_load=True,
            domain="[('group.code', '=', 'vat'), ('company', '=', company)]",
            help='This tax will be used, instead of the default VAT.')

Partner()
