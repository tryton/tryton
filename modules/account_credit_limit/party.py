# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.i18n import gettext
from trytond.model import ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.tools.multivalue import migrate_property
from trytond.modules.company.model import CompanyValueMixin

from .exceptions import CreditLimitError, CreditLimitWarning


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    credit_amount = fields.Function(fields.Numeric('Credit Amount',
            digits=(16, Eval('credit_limit_digits', 2)),
            depends=['credit_limit_digits']),
        'get_credit_amount')
    credit_limit_amount = fields.MultiValue(fields.Numeric(
            'Credit Limit Amount',
            digits=(16, Eval('credit_limit_digits', 2)),
            depends=['credit_limit_digits']))
    credit_limit_digits = fields.Function(fields.Integer('Currency Digits'),
        'get_credit_limit_digits')
    credit_limit_amounts = fields.One2Many(
        'party.party.credit_limit_amount', 'party', "Credit Limit Amounts")

    @classmethod
    def default_credit_limit_amount(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        config = Configuration(1)
        return config.get_multivalue(
            'default_credit_limit_amount', **pattern)

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
        Company = pool.get('company.company')
        Lang = pool.get('ir.lang')
        Warning = pool.get('res.user.warning')

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
            company = Company(Transaction().context.get('company'))
            lang = Lang.get()
            limit = lang.currency(self.credit_limit_amount, company.currency)
            if not in_group():
                raise CreditLimitError(
                    gettext('account_credit_limit'
                        '.msg_party_credit_limit_amount',
                        party=self.rec_name,
                        limit=limit))
            warning_name = 'credit_limit_amount_%s' % origin
            if Warning.check(warning_name):
                raise CreditLimitWarning(warning_name,
                    gettext('account_credit_limit'
                        '.msg_party_credit_limit_amount',
                        party=self.rec_name,
                        limit=limit))

        if Dunning:
            dunnings = Dunning.search([
                    ('party', '=', self.id),
                    ('level.credit_limit', '=', True),
                    ('blocked', '!=', True),
                    ])
            if dunnings:
                dunning = dunnings[0]
                if not in_group():
                    raise CreditLimitError(
                        gettext('account_credit_limit'
                            '.msg_party_credit_limit_dunning',
                            party=self.rec_name,
                            dunning=dunning.rec_name))
                warning_name = 'credit_limit_dunning_%s' % origin
                if Warning.check(warning_name):
                    raise CreditLimitWarning(warning_name,
                        gettext('account_credit_limit'
                            '.msg_party_credit_limit_dunning',
                            party=self.rec_name,
                            dunning=dunning.rec_name))

    def get_credit_limit_digits(self, name):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = Transaction().context.get('company')
        if company_id:
            company = Company(company_id)
            return company.currency.digits


class PartyCreditLimitAmount(ModelSQL, CompanyValueMixin):
    "Party Credit Limit Amount"
    __name__ = 'party.party.credit_limit_amount'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE', select=True)
    credit_limit_amount = fields.Numeric(
        "Credit Limit Amount", digits=(16, Eval('credit_limit_digits', 2)),
        depends=['credit_limit_digits'])
    credit_limit_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_credit_limit_digits')

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)

        super(PartyCreditLimitAmount, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('credit_limit_amount')
        value_names.append('credit_limit_amount')
        fields.append('company')
        migrate_property(
            'party.party', field_names, cls, value_names,
            parent='party', fields=fields)

    @fields.depends('company')
    def on_change_with_credit_limit_digits(self, name=None):
        if self.company:
            return self.company.currency.digits
