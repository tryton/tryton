#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Get, Eval, And, Bool, Not, Or
from decimal import Decimal


class Party(ModelSQL, ModelView):
    _name = 'party.party'
    account_payable = fields.Property(fields.Many2One('account.account',
        'Account Payable', domain=[
            ('kind', '=', 'payable'),
            ('company', '=', Eval('company')),
        ],
        states={
            'required': Bool(Eval('company')),
            'invisible': Not(Bool(Eval('company'))),
        }))
    account_receivable = fields.Property(fields.Many2One('account.account',
        'Account Receivable', domain=[
            ('kind', '=', 'receivable'),
            ('company', '=', Eval('company')),
        ],
        states={
            'required': Bool(Eval('company')),
            'invisible': Not(Bool(Eval('company'))),
        }))
    customer_tax_rule = fields.Property(fields.Many2One('account.tax.rule',
        'Customer Tax Rule', domain=[('company', '=', Eval('company'))],
        states={
            'invisible': Not(Bool(Eval('company'))),
        }, help='Apply this rule on taxes when party is customer.'))
    supplier_tax_rule = fields.Property(fields.Many2One('account.tax.rule',
        'Supplier Tax Rule', domain=[('company', '=', Eval('company'))],
        states={
            'invisible': Not(Bool(Eval('company'))),
        }, help='Apply this rule on taxes when party is supplier.'))
    receivable = fields.Function(fields.Numeric('Receivable'),
            'get_receivable_payable', searcher='search_receivable_payable')
    payable = fields.Function(fields.Numeric('Payable'),
            'get_receivable_payable', searcher='search_receivable_payable')
    receivable_today = fields.Function(fields.Numeric('Receivable Today'),
            'get_receivable_payable', searcher='search_receivable_payable')
    payable_today = fields.Function(fields.Numeric('Payable Today'),
            'get_receivable_payable', searcher='search_receivable_payable')

    def get_receivable_payable(self, cursor, user_id, ids, names,
            context=None):
        '''
        Function to compute receivable, payable (today or not) for party ids.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: the ids of the party
        :param names: the list of field name to compute
        :param arg: optional argument
        :param context: the context
        :return: a dictionary with all field names as key and
            a dictionary as value with id as key
        '''
        res = {}
        move_line_obj = self.pool.get('account.move.line')
        company_obj = self.pool.get('company.company')
        user_obj = self.pool.get('res.user')
        date_obj = self.pool.get('ir.date')

        if context is None:
            context = {}

        for name in names:
            if name not in ('receivable', 'payable',
                    'receivable_today', 'payable_today'):
                raise Exception('Bad argument')
            res[name] = dict((x, Decimal('0.0')) for x in ids)

        if not ids:
            return {}

        company_id = None
        user = user_obj.browse(cursor, user_id, user_id, context=context)
        if context.get('company'):
            child_company_ids = company_obj.search(cursor, user_id, [
                ('parent', 'child_of', [user.main_company.id]),
                ], order=[], context=context)
            if context['company'] in child_company_ids:
                company_id = context['company']

        if not company_id:
            company_id = user.company.id or user.main_company.id

        if not company_id:
            return res

        line_query, _ = move_line_obj.query_get(cursor, user_id, context=context)

        for name in names:
            code = name
            today_query = ''
            today_value = []
            if name in ('receivable_today', 'payable_today'):
                code = name[:-6]
                today_query = 'AND (l.maturity_date <= %s ' \
                        'OR l.maturity_date IS NULL) '
                today_value = [date_obj.today(cursor, user, context=context)]

            cursor.execute('SELECT l.party, ' \
                        'SUM((COALESCE(l.debit, 0) - COALESCE(l.credit, 0))) ' \
                    'FROM account_move_line AS l, ' \
                        'account_account AS a ' \
                    'WHERE a.id = l.account ' \
                        'AND a.active ' \
                        'AND a.kind = %s ' \
                        'AND l.party IN ' \
                            '(' + ','.join(('%s',) * len(ids)) + ') ' \
                        'AND l.reconciliation IS NULL ' \
                        'AND ' + line_query + ' ' \
                        + today_query + \
                        'AND a.company = %s ' \
                    'GROUP BY l.party',
                    [code,] + ids + today_value + [company_id])
            for party_id, sum in cursor.fetchall():
                # SQLite uses float for SUM
                if not isinstance(sum, Decimal):
                    sum = Decimal(str(sum))
                res[name][party_id] = sum
        return res

    def search_receivable_payable(self, cursor, user_id, name, clause,
            context=None):
        move_line_obj = self.pool.get('account.move.line')
        company_obj = self.pool.get('company.company')
        user_obj = self.pool.get('res.user')
        date_obj = self.pool.get('ir.date')

        if context is None:
            context = {}

        if name not in ('receivable', 'payable',
                'receivable_today', 'payable_today'):
            raise Exception('Bad argument')

        company_id = None
        user = user_obj.browse(cursor, user_id, user_id, context=context)
        if context.get('company'):
            child_company_ids = company_obj.search(cursor, user_id, [
                ('parent', 'child_of', [user.main_company.id]),
                ], context=context)
            if context['company'] in child_company_ids:
                company_id = context['company']

        if not company_id:
            company_id = user.company.id or user.main_company.id

        if not company_id:
            return []

        code = name
        today_query = ''
        today_value = []
        if name in ('receivable_today', 'payable_today'):
            code = name[:-6]
            today_query = 'AND (l.maturity_date <= %s ' \
                    'OR l.maturity_date IS NULL) '
            today_value = [date_obj.today(cursor, user, context=context)]

        line_query, _ = move_line_obj.query_get(cursor, user_id, context=context)

        cursor.execute('SELECT l.party '
                'FROM account_move_line AS l, '
                    'account_account AS a '
                'WHERE a.id = l.account '
                    'AND a.active '
                    'AND a.kind = %s '
                    'AND l.party IS NOT NULL '
                    'AND l.reconciliation IS NULL '
                    'AND ' + line_query + ' ' \
                    + today_query + \
                    'AND a.company = %s '
                'GROUP BY l.party '
                'HAVING (SUM((COALESCE(l.debit, 0) - COALESCE(l.credit, 0))) ' \
                        + clause[1] + ' %s)',
                    [code] + today_value + [company_id] + [clause[2]])
        return [('id', 'in', [x[0] for x in cursor.fetchall()])]

Party()
