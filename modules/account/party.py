#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from decimal import Decimal


class Party(ModelSQL, ModelView):
    _name = 'party.party'
    account_payable = fields.Property(type='many2one',
            relation='account.account', string='Account Payable',
            domain="[('kind', '=', 'payable'), " \
                    "('company', '=', globals().get('company', 0))]",
            states={
                'required': "globals().get('company') and bool(company)",
                'invisible': "not globals().get('company') or not bool(company)",
            })
    account_receivable = fields.Property(type='many2one',
            relation='account.account', string='Account Receivable',
            domain="[('kind', '=', 'receivable'), " \
                    "('company', '=', globals().get('company', 0))]",
            states={
                'required': "globals().get('company') and bool(company)",
                'invisible': "not globals().get('company') or not bool(company)",
            })
    customer_tax_rule = fields.Property(type='many2one',
            relation='account.tax.rule', string='Customer Tax Rule',
            domain="[('company', '=', globals().get('company', 0))]",
            states={
                'invisible': "not globals().get('company') or not bool(company)",
            }, help='Apply this rule on taxes when party is customer.')
    supplier_tax_rule = fields.Property(type='many2one',
            relation='account.tax.rule', string='Supplier Tax Rule',
            domain="[('company', '=', globals().get('company', 0))]",
            states={
                'invisible': "not globals().get('company') or not bool(company)",
            }, help='Apply this rule on taxes when party is supplier.')
    receivable = fields.Function('get_receivable_payable',
            fnct_search='search_receivable_payable', string='Receivable')
    payable = fields.Function('get_receivable_payable',
            fnct_search='search_receivable_payable', string='Payable')
    receivable_today = fields.Function('get_receivable_payable',
            fnct_search='search_receivable_payable', string='Receivable Today')
    payable_today = fields.Function('get_receivable_payable',
            fnct_search='search_receivable_payable', string='Payable Today')

    def get_receivable_payable(self, cursor, user_id, ids, name, arg,
            context=None):
        res = {}
        move_line_obj = self.pool.get('account.move.line')
        company_obj = self.pool.get('company.company')
        user_obj = self.pool.get('res.user')
        date_obj = self.pool.get('ir.date')

        if context is None:
            context = {}

        if name not in ('receivable', 'payable',
                'receivable_today', 'payable_today'):
            raise Exception('Bad argument')

        if not ids:
            return {}

        for i in ids:
            res[i] = Decimal('0.0')

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
            return res

        code = name
        today_query = ''
        today_value = []
        if name in ('receivable_today', 'payable_today'):
            code = name[:-6]
            today_query = 'AND (l.maturity_date <= %s ' \
                    'OR l.maturity_date IS NULL) '
            today_value = [date_obj.today(cursor, user, context=context)]

        line_query, _ = move_line_obj.query_get(cursor, user_id, context=context)

        cursor.execute('SELECT l.party, ' \
                    'SUM((COALESCE(l.debit, 0) - COALESCE(l.credit, 0))) ' \
                'FROM account_move_line AS l, ' \
                    'account_account AS a ' \
                'WHERE a.id = l.account ' \
                    'AND a.active ' \
                    'AND a.kind = %s ' \
                    'AND l.party IN ' \
                        '(' + ','.join(['%s' for x in ids]) + ') ' \
                    'AND l.reconciliation IS NULL ' \
                    'AND ' + line_query + ' ' \
                    + today_query + \
                    'AND a.company = %s ' \
                'GROUP BY l.party',
                [code,] + ids + today_value + [company_id])
        for party_id, sum in cursor.fetchall():
            res[party_id] = sum
        return res

    def search_receivable_payable(self, cursor, user_id, name, args,
            context=None):
        if not len(args):
            return []
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

        cursor.execute('SELECT l.party ' \
                'FROM account_move_line AS l, ' \
                    'account_account AS a ' \
                'WHERE a.id = l.account ' \
                    'AND a.active ' \
                    'AND a.kind = %s ' \
                    'AND l.party IS NOT NULL ' \
                    'AND l.reconciliation IS NULL ' \
                    'AND ' + line_query + ' ' \
                    + today_query + \
                    'AND a.company = %s ' \
                'GROUP BY l.party ' \
                'HAVING ' + \
                    'AND'.join(['(SUM((COALESCE(l.debit, 0) - COALESCE(l.credit, 0))) ' \
                        + ' ' + x[1] + ' %s) ' for x in args]),
                    [code] + today_value + [company_id] + [x[2] for x in args])
        if not cursor.rowcount:
            return [('id', '=', 0)]
        return [('id', 'in', [x[0] for x in cursor.fetchall()])]

Party()
