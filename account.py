"Account"

from trytond.osv import fields, OSV
from trytond.osv.orm import ID_MAX, exclude
from trytond.wizard import Wizard, WizardOSV
from trytond.report import Report
from decimal import Decimal


class Type(OSV):
    'Account Type'
    _name = 'account.account.type'
    _order = 'code'
    _description = __doc__
    name = fields.Char('Name', size=None, required=True, translate=True)
    code = fields.Char('Code', size=None, required=True)
    partner_account = fields.Boolean('Partner account')

    def __init__(self):
        super(Type, self).__init__()
        self._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'Code must be unique!'),
        ]

    def default_partner_account(self, cursor, user, context=None):
        return False

Type()


class Account(OSV):
    'Account'
    _name = 'account.account'
    _description = __doc__
    _order = 'code, id'
    _parent_name = 'parents'

    name = fields.Char('Name', size=None, required=True, translate=True,
            select=1)
    code = fields.Char('Code', size=None, select=1)
    active = fields.Boolean('Active', select=2)
    company = fields.Many2One('company.company', 'Company', required=True)
    currency = fields.Function('get_currency', type='many2one',
            relation='account.currency', string='Currency')
    second_currency = fields.Many2One('account.currency', 'Secondary currency',
            help='Force all moves for this account \n' \
                    'to have this secondary currency.')
    type = fields.Selection('get_types', 'Type', required=True)
    parents = fields.Many2Many('account.account', 'account_account_rel',
            'child', 'parent', 'Parents')
    childs = fields.Many2Many('account.account', 'account_account_rel',
            'parent', 'child', 'Childs')
    #TODO fix digits depend of the currency
    balance = fields.Function('get_balance', digits=(16, 2), string='Balance')
    credit = fields.Function('get_credit_debit', digits=(16, 2), string='Credit')
    debit = fields.Function('get_credit_debit', digits=(16, 2), string='Debit')
    reconcile = fields.Boolean('Reconcile',
            help='Check if the account can be used \n' \
                    'for reconciliation.')
    close_method = fields.Selection([
        ('none', 'None'),
        ('balance', 'Balance'),
        ('detail', 'Detail'),
        ('unreconciled', 'Unreconciled'),
        ], 'Deferral method', required=True,
        help='How to process the lines of this account ' \
                'when closing the fiscal year\n' \
                '- None: to start with an empty account\n'
                '- Balance: to create one entry to keep the balance\n'
                '- Detail: to keep all entries\n'
                '- Unreconciled: to keep all unreconciled entries')
    note = fields.Text('Note')

    def __init__(self):
        super(Account, self).__init__()
        self._constraints += [
            ('check_recursion_parents',
                'Error! You can not create recursive accounts.', ['parents']),
        ]

    def default_active(self, cursor, user, context=None):
        return True

    def default_company(self, cursor, user, context=None):
        if context is None:
            context = {}
        return context.get('company', False)

    def default_type(self, cursor, user, context=None):
        return 'view'

    def default_reconcile(self, cursor, user, context=None):
        return False

    def default_close_method(self, cursor, user, context=None):
        return 'balance'

    def check_recursion_parents(self, cursor, user, ids):
        ids_parent = ids[:]
        while len(ids_parent):
            ids_parent2 = []
            for i in range((len(ids) / ID_MAX) + \
                    ((len(ids) % ID_MAX) and 1 or 0)):
                sub_ids_parent = ids_parent[ID_MAX * i:ID_MAX * (i + 1)]
                cursor.execute('SELECT distinct parent ' \
                        'FROM account_account_rel ' \
                        'WHERE child IN ' \
                            '(' + ','.join([str(x) for x in sub_ids_parent]) + ')')
                ids_parent2.extend(filter(None,
                    [x[0] for x in cursor.fetchall()]))
            ids_parent = ids_parent2
            for i in ids_parent:
                if i in ids:
                    return False
        return True

    def get_currency(self, cursor, user, ids, name, arg, context=None):
        currency_obj = self.pool.get('account.currency')
        res = {}
        for account in self.browse(cursor,user, ids, context=context):
            res[account.id] = account.company.currency.id
        currency_names = {}
        for currency_id, currency_name in currency_obj.name_get(cursor, user,
                [x for x in res.values() if x], context=context):
            currency_names[currency_id] = currency_name

        for i in res.keys():
            if res[i] and res[i] in currency_names:
                res[i] = (res[i], currency_names[res[i]])
            else:
                res[i] = False
        return res

    def get_types(self, cursor, user, context=None):
        type_obj = self.pool.get('account.account.type')
        type_ids = type_obj.search(cursor, user, [], context=context)
        types = type_obj.browse(cursor, user, type_ids, context=context)
        return [(x.code, x.name) for x in types]

    def get_balance(self, cursor, user, ids, name, arg, context=None):
        res = {}
        company_obj = self.pool.get('company.company')
        currency_obj = self.pool.get('account.currency')
        move_line_obj = self.pool.get('account.move.line')

        child_ids = self.search(cursor, user, [('parents', 'child_of', ids)],
                context=context)
        all_ids = {}.fromkeys(ids + child_ids).keys()
        line_query = move_line_obj.query_get(cursor, user, context=context)
        cursor.execute('SELECT a.id, ' \
                    'SUM((COALESCE(l.debit, 0) - COALESCE(l.credit, 0))) ' \
                'FROM account_account a ' \
                    'LEFT JOIN account_move_line l ' \
                    'ON (a.id = l.account) ' \
                'WHERE a.type != \'view\' ' \
                    'AND a.id IN (' + \
                        ','.join(['%s' for x in all_ids]) + ') ' \
                    'AND ' + line_query + ' ' \
                    'AND a.active ' \
                'GROUP BY a.id', all_ids)
        account_sum = {}
        for account_id, sum in cursor.fetchall():
            account_sum[account_id] = sum

        account2company = {}
        id2company = {}
        accounts = self.browse(cursor, user, all_ids, context=context)
        for account in accounts:
            account2company[account.id] = account.company.id
            id2company[account.company.id] = account.company

        for account_id in ids:
            res.setdefault(account_id, Decimal('0.0'))
            child_ids = self.search(cursor, user, [
                ('parents', 'child_of', [account_id]),
                ], context=context)
            company_id = account2company[account_id]
            to_currency = id2company[company_id].currency
            for child_id in child_ids:
                child_company_id = account2company[child_id]
                from_currency = id2company[child_company_id].currency
                res[account_id] += currency_obj.compute(cursor, user,
                        from_currency, account_sum.get(child_id, Decimal('0.0')),
                        to_currency, round=True, context=context)
            res[account_id] = currency_obj.round(cursor, user, to_currency,
                    res[account_id])
        return res

    def get_credit_debit(self, cursor, user, ids, name, arg, context=None):
        res = {}
        move_line_obj = self.pool.get('account.move.line')
        company_obj = self.pool.get('company.company')
        currency_obj = self.pool.get('account.currency')

        if name not in ('credit', 'debit'):
            raise Exception('Bad argument')

        line_query = move_line_obj.query_get(cursor, user, context=context)
        cursor.execute('SELECT a.id, ' \
                    'SUM(COALESCE(l.' + name + ', 0)) ' \
                'FROM account_account a ' \
                    'LEFT JOIN account_move_line l ' \
                    'ON (a.id = l.account) ' \
                'WHERE a.type != \'view\' ' \
                    'AND a.id IN (' + \
                        ','.join(['%s' for x in ids]) + ') ' \
                    'AND ' + line_query + ' ' \
                    'AND a.active ' \
                'GROUP BY a.id', ids)
        for account_id, sum in cursor.fetchall():
            res[account_id] = sum

        account2company = {}
        id2company = {}
        accounts = self.browse(cursor, user, ids, context=context)
        for account in accounts:
            account2company[account.id] = account.company.id
            id2company[account.company.id] = account.company

        for account_id in ids:
            res.setdefault(account_id, Decimal('0.0'))
            company_id = account2company[account_id]
            currency = id2company[company_id].currency
            res[account_id] = currency_obj.round(cursor, user, currency,
                    res[account_id])
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

    def copy(self, cursor, user, object_id, default=None, context=None):
        account = self.browse(cursor, user, object_id, context=context)
        default['parents'] = False
        if account:
            #Also duplicate all childs
            new_child_ids = []
            for child in account.childs:
                new_child_ids.append(
                        self.copy(cursor, user, child.id, default,
                            context=context))
            default['childs'] = [('set', new_child_ids)]
        else:
            default['childs'] = False
        return super(Account, self).copy(cursor, user, object_id, default,
                context=context)

    def write(self, cursor, user, ids, vals, context=None):
        if not vals.get('active', True):
            move_line_obj = self.pool.get('account.move.line')
            account_ids = self.search(cursor, user, [
                ('parents', 'child_of', ids),
                ], context=context)
            if move_line_obj.search(cursor, user, [
                ('account', 'in', account_ids),
                ], context=context):
                vals = vals.copy()
                del vals['active']
        return super(Account, self).write(cursor, user, ids, vals,
                context=context)

Account()


class OpenChartAccountInit(WizardOSV):
    _name = 'account.account.open_chart_account.init'
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            help='Keep empty for all open fiscal year')

OpenChartAccountInit()


class OpenChartAccount(Wizard):
    'Open Chart Of Account'
    _name = 'account.account.open_chart_account'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'account.account.open_chart_account.init',
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
            ('fs_id', '=', 'act_account_tree2'),
            ('module', '=', 'account'),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)
        res['context'] = str({'fiscalyear': data['form']['fiscalyear']})
        return res

OpenChartAccount()


class Partner(OSV):
    _name = 'partner.partner'
    account_payable = fields.Property('account.account', type='many2one',
            relation='account.account', string='Account Payable',
            group_name='Accounting Properties', view_load=True,
            domain="[('type', '=', 'payable'), ('company', '=', company)]",
            states={
                'required': "company",
                'invisible': "not company",
            })
    account_receivable = fields.Property('account.account', type='many2one',
            relation='account.account', string='Account Receivable',
            group_name='Accounting Properties', view_load=True,
            domain="[('type', '=', 'receivable'), ('company', '=', company)]",
            states={
                'required': "company",
                'invisible': "not company",
            })

Partner()


class PrintGeneralLegderInit(WizardOSV):
    _name = 'account.account.open_general_ledger.init'
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            required=True)
    #TODO add domain for start_period <= end_period
    start_period = fields.Many2One('account.period', 'Start Period',
            domain="[('fiscalyear', '=', fiscalyear)]")
    end_period = fields.Many2One('account.period', 'End Period',
            domain="[('fiscalyear', '=', fiscalyear)]")
    company = fields.Many2One('company.company', 'Company', required=True)
    posted = fields.Boolean('Posted Move', help='Only posted move')

    def default_fiscalyear(self, cursor, user, context=None):
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        fiscalyear_id = fiscalyear_obj.find(cursor, user, exception=False,
                context=context)
        if fiscalyear_id:
            return fiscalyear_obj.name_get(cursor, user, fiscalyear_id,
                    context=context)[0]
        return False

    def default_company(self, cursor, user, context=None):
        if context is None:
            context = {}
        company_obj = self.pool.get('company.company')
        if context.get('company'):
            return company_obj.name_get(cursor, user, context['company'],
                    context=context)[0]
        return False

    def default_posted(self, cursor, user, context=None):
        return False

PrintGeneralLegderInit()


class PrintGeneralLegder(Wizard):
    'Print General Legder'
    _name = 'account.account.print_general_ledger'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'account.account.open_general_ledger.init',
                'state': [
                    ('end', 'Cancel', 'gtk-cancel'),
                    ('print', 'Print', 'gtk-print', True),
                ],
            },
        },
        'print': {
            'result': {
                'type': 'print',
                'report': 'account.account.general_ledger',
                'state': 'end',
            },
        },
    }

PrintGeneralLegder()


class GeneralLegder(Report):
    _name = 'account.account.general_ledger'

    def _get_objects(self, cursor, user, ids, model, context):
        #Don't browse false account
        return None

    def parse(self, cursor, user, content, objects, datas, context):
        if context is None:
            context = {}
        context = context.copy()
        account_obj = self.pool.get('account.account')
        period_obj = self.pool.get('account.period')
        company_obj = self.pool.get('company.company')

        company = company_obj.browse(cursor, user,
                datas['form']['company'], context=context)

        account_ids = account_obj.search(cursor, user, [
            ('company', '=', datas['form']['company']),
            ], order='code, id', context=context)

        start_period_ids = []
        if datas['form']['start_period']:
            start_period = period_obj.browse(cursor, user,
                    datas['form']['start_period'], context=context)
            start_period_ids = period_obj.search(cursor, user, [
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ('end_date', '<=', start_period.start_date),
                ], context=context)
        if not start_period_ids:
            start_period_ids = [0]

        start_context = context.copy()
        start_context['fiscalyear'] = datas['form']['fiscalyear']
        start_context['periods'] = start_period_ids
        start_context['posted'] = datas['form']['posted']
        start_accounts = account_obj.browse(cursor, user, account_ids,
                context=start_context)
        id2start_account = {}
        for account in start_accounts:
            id2start_account[account.id] = account

        end_period_ids = []
        if datas['form']['end_period']:
            end_period = period_obj.browse(cursor, user,
                    datas['form']['end_period'], context=context)
            end_period_ids = period_obj.search(cursor, user, [
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ('end_date', '<=', end_period.start_date),
                ], context=context)
            end_period_ids = exclude(end_period_ids, start_period_ids)
            if datas['form']['end_period'] not in end_period_ids:
                end_period_ids.append(datas['form']['end_period'])
        else:
            end_period_ids = period_obj.search(cursor, user, [
                ('fiscalyear', '=', datas['form']['fiscalyear']),
                ], context=context)
            end_period_ids = exclude(end_period_ids, start_period_ids)

        end_context = context.copy()
        end_context['fiscalyear'] = datas['form']['fiscalyear']
        end_context['periods'] = end_period_ids
        end_context['posted'] = datas['form']['posted']
        end_accounts = account_obj.browse(cursor, user, account_ids,
                context=end_context)
        id2end_account = {}
        for account in end_accounts:
            id2end_account[account.id] = account

        periods = period_obj.browse(cursor, user, end_period_ids,
                context=context)
        periods.sort(lambda x, y: cmp(x.start_date, y.start_date))
        context['start_period'] = periods[0]
        periods.sort(lambda x, y: cmp(x.end_date, y.end_date))
        context['end_period'] = periods[-1]

        context['accounts'] = account_obj.browse(cursor, user, account_ids,
                context=context)
        context['id2start_account'] = id2start_account
        context['id2end_account'] = id2end_account
        context['digits'] = company.currency.digits
        context['lines'] = lambda account_id: self.lines(cursor, user,
                account_id, end_period_ids, datas['form']['posted'], context)
        context['company'] = company

        return super(GeneralLegder, self).parse(cursor, user, content, objects,
                datas, context)

    def lines(self, cursor, user, account_id, period_ids, posted, context):
        move_line_obj = self.pool.get('account.move.line')
        period_obj = self.pool.get('account.period')
        res = []

        clause = [
            ('account', '=', account_id),
            ('period', 'in', period_ids),
            ('state', '!=', 'draft'),
            ]
        if posted:
            clause.append(('move.state', '=', 'posted'))
        move_line_ids = move_line_obj.search(cursor, user, clause,
                context=context)
        move_lines = move_line_obj.browse(cursor, user, move_line_ids,
                context=context)
        move_lines.sort(lambda x, y: cmp(x.date, y.date))

        balance = Decimal('0.0')
        for line in move_lines:
            balance += line.debit - line.credit
            res.append({
                'date': line.date,
                'debit': line.debit,
                'credit': line.credit,
                'balance': balance,
                'name': line.name,
                'state': line.move.state,
                })
        return res

GeneralLegder()
