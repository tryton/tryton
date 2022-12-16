#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import fields
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['Party']
__metaclass__ = PoolMeta


class Party:
    __name__ = 'party.party'
    account_payable = fields.Property(fields.Many2One('account.account',
            'Account Payable', domain=[
                ('kind', '=', 'payable'),
                ('company', '=', Eval('context', {}).get('company')),
                ],
            states={
                'required': Bool(Eval('context', {}).get('company')),
                'invisible': ~Eval('context', {}).get('company'),
                }))
    account_receivable = fields.Property(fields.Many2One('account.account',
            'Account Receivable', domain=[
                ('kind', '=', 'receivable'),
                ('company', '=', Eval('context', {}).get('company', 0)),
                ],
            states={
                'required': Bool(Eval('context', {}).get('company')),
                'invisible': ~Eval('context', {}).get('company'),
                }))
    customer_tax_rule = fields.Property(fields.Many2One('account.tax.rule',
            'Customer Tax Rule',
            domain=[
                ('company', '=', Eval('context', {}).get('company', 0)),
                ('kind', 'in', ['sale', 'both']),
                ],
            states={
                'invisible': ~Eval('context', {}).get('company'),
                }, help='Apply this rule on taxes when party is customer.'))
    supplier_tax_rule = fields.Property(fields.Many2One('account.tax.rule',
            'Supplier Tax Rule',
            domain=[
                ('company', '=', Eval('context', {}).get('company', 0)),
                ('kind', 'in', ['purchase', 'both']),
                ],
            states={
                'invisible': ~Eval('context', {}).get('company'),
                }, help='Apply this rule on taxes when party is supplier.'))
    receivable = fields.Function(fields.Numeric('Receivable'),
            'get_receivable_payable', searcher='search_receivable_payable')
    payable = fields.Function(fields.Numeric('Payable'),
            'get_receivable_payable', searcher='search_receivable_payable')
    receivable_today = fields.Function(fields.Numeric('Receivable Today'),
            'get_receivable_payable', searcher='search_receivable_payable')
    payable_today = fields.Function(fields.Numeric('Payable Today'),
            'get_receivable_payable', searcher='search_receivable_payable')

    @classmethod
    def get_receivable_payable(cls, parties, names):
        '''
        Function to compute receivable, payable (today or not) for party ids.
        '''
        res = {}
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        User = pool.get('res.user')
        Date = pool.get('ir.date')
        cursor = Transaction().cursor

        for name in names:
            if name not in ('receivable', 'payable',
                    'receivable_today', 'payable_today'):
                raise Exception('Bad argument')
            res[name] = dict((p.id, Decimal('0.0')) for p in parties)

        user_id = Transaction().user
        if user_id == 0 and 'user' in Transaction().context:
            user_id = Transaction().context['user']
        user = User(user_id)
        if not user.company:
            return res
        company_id = user.company.id

        line_query, _ = MoveLine.query_get()

        for name in names:
            code = name
            today_query = ''
            today_value = []
            if name in ('receivable_today', 'payable_today'):
                code = name[:-6]
                today_query = 'AND (l.maturity_date <= %s ' \
                    'OR l.maturity_date IS NULL) '
                today_value = [Date.today()]

            cursor.execute('SELECT l.party, '
                    'SUM((COALESCE(l.debit, 0) - COALESCE(l.credit, 0))) '
                'FROM account_move_line AS l, account_account AS a '
                'WHERE a.id = l.account '
                    'AND a.active '
                    'AND a.kind = %s '
                    'AND l.party IN '
                        '(' + ','.join(('%s',) * len(parties)) + ') '
                    'AND l.reconciliation IS NULL '
                    'AND ' + line_query + ' '
                    + today_query +
                    'AND a.company = %s '
                'GROUP BY l.party',
                [code] + [p.id for p in parties] + today_value + [company_id])
            for party_id, sum in cursor.fetchall():
                # SQLite uses float for SUM
                if not isinstance(sum, Decimal):
                    sum = Decimal(str(sum))
                res[name][party_id] = sum
        return res

    @classmethod
    def search_receivable_payable(cls, name, clause):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Company = pool.get('company.company')
        User = pool.get('res.user')
        Date = pool.get('ir.date')
        cursor = Transaction().cursor

        if name not in ('receivable', 'payable',
                'receivable_today', 'payable_today'):
            raise Exception('Bad argument')

        company_id = None
        user_id = Transaction().user
        if user_id == 0 and 'user' in Transaction().context:
            user_id = Transaction().context['user']
        user = User(user_id)
        if Transaction().context.get('company'):
            child_companies = Company.search([
                    ('parent', 'child_of', [user.main_company.id]),
                    ])
            if Transaction().context['company'] in child_companies:
                company_id = Transaction().context['company']

        if not company_id:
            if user.company:
                company_id = user.company.id
            elif user.main_company:
                company_id = user.main_company.id

        if not company_id:
            return []

        code = name
        today_query = ''
        today_value = []
        if name in ('receivable_today', 'payable_today'):
            code = name[:-6]
            today_query = 'AND (l.maturity_date <= %s ' \
                'OR l.maturity_date IS NULL) '
            today_value = [Date.today()]

        line_query, _ = MoveLine.query_get()

        cursor.execute('SELECT l.party '
            'FROM account_move_line AS l, account_account AS a '
            'WHERE a.id = l.account '
                'AND a.active '
                'AND a.kind = %s '
                'AND l.party IS NOT NULL '
                'AND l.reconciliation IS NULL '
                'AND ' + line_query + ' '
                + today_query +
                'AND a.company = %s '
            'GROUP BY l.party '
            'HAVING (SUM((COALESCE(l.debit, 0) - COALESCE(l.credit, 0))) '
                + clause[1] + ' %s)',
            [code] + today_value + [company_id] + [Decimal(clause[2] or 0)])
        return [('id', 'in', [x[0] for x in cursor.fetchall()])]
