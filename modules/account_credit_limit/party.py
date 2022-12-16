# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.pyson import Eval

__all__ = ['Party']


class Party:
    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    credit_amount = fields.Function(fields.Numeric('Credit Amount',
            digits=(16, Eval('credit_limit_digits', 2)),
            depends=['credit_limit_digits']),
        'get_credit_amount')
    credit_limit_amount = fields.Property(fields.Numeric(
            'Credit Limit Amount',
            digits=(16, Eval('credit_limit_digits', 2)),
            depends=['credit_limit_digits']))
    credit_limit_digits = fields.Function(fields.Integer('Currency Digits'),
        'get_credit_limit_digits')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._error_messages.update({
                'credit_limit_amount': (
                    '"%s" has reached the credit limit amount (%s)'),
                'credit_limit_dunning': (
                    '"%s" has reached the dunning credit limit (%s)'),
                })

    @classmethod
    def get_credit_amount(cls, parties, name):
        return {p.id: p.receivable for p in parties}

    @staticmethod
    def _credit_limit_to_lock():
        'Return models to lock when checking credit limit'
        return ['account.move.line']

    def check_credit_limit(self, amount, origin=None):
        '''
        Check if amount will not reach credit limit for party
        If origin is set and user is in group credit_limit then a warning will
        be raised
        '''
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            Dunning = pool.get('account.dunning')
        except KeyError:
            Dunning = None
        User = pool.get('res.user')
        Group = pool.get('res.group')

        if self.credit_limit_amount is None:
            return

        def in_group():
            group = Group(ModelData.get_id('account_credit_limit',
                    'group_credit_limit'))
            transaction = Transaction()
            user_id = transaction.user
            if user_id == 0:
                user_id = transaction.context.get('user', user_id)
            if user_id == 0:
                return True
            user = User(user_id)
            return origin and group in user.groups

        for model in self._credit_limit_to_lock():
            Model = pool.get(model)
            Transaction().database.lock(Transaction().connection, Model._table)
        if self.credit_limit_amount < self.credit_amount + amount:
            if not in_group():
                self.raise_user_error('credit_limit_amount',
                    (self.rec_name, self.credit_limit_amount))
            warning_name = 'credit_limit_amount_%s' % origin
            self.raise_user_warning(warning_name, 'credit_limit_amount',
                (self.rec_name, self.credit_limit_amount))

        if Dunning:
            dunnings = Dunning.search([
                    ('party', '=', self.id),
                    ('level.credit_limit', '=', True),
                    ('blocked', '!=', True),
                    ])
            if dunnings:
                dunning = dunnings[0]
                if not in_group():
                    self.raise_user_error('credit_limit_dunning',
                        (self.rec_name, dunning.rec_name))
                warning_name = 'credit_limit_dunning_%s' % origin
                self.raise_user_warning(warning_name, 'credit_limit_dunning',
                    (self.rec_name, dunning.rec_name))

    def get_credit_limit_digits(self, name):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = Transaction().context.get('company')
        if not company_id:
            return 2
        company = Company(company_id)
        return company.currency.digits
