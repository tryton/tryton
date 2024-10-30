# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import ModelSQL, fields
from trytond.modules.company.model import CompanyValueMixin
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

from .exceptions import CreditLimitError, CreditLimitWarning


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    credit_amount = fields.Function(Monetary(
            "Credit Amount", currency='currency', digits='currency'),
        'get_credit_amount')
    credit_limit_amount = fields.MultiValue(Monetary(
            "Credit Limit Amount", currency='currency', digits='currency'))
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

    def check_credit_limit(self, amount, company, origin=None):
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
        Lang = pool.get('ir.lang')
        Warning = pool.get('res.user.warning')

        if amount <= 0:
            return

        credit_limit_amount = self.get_multivalue(
            'credit_limit_amount', company=company.id)
        if credit_limit_amount is None:
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
            Model.lock()
        exceeded_amount = (
            self.credit_amount + amount - self.credit_limit_amount)
        if exceeded_amount > 0:
            lang = Lang.get()
            limit = lang.currency(self.credit_limit_amount, company.currency)
            amount = lang.currency(amount, company.currency)
            if not in_group():
                raise CreditLimitError(
                    gettext('account_credit_limit'
                        '.msg_party_credit_limit_amount',
                        party=self.rec_name,
                        limit=limit,
                        amount=amount))
            warning_name = Warning.format('credit_limit_amount', [origin])
            if Warning.check(warning_name):
                raise CreditLimitWarning(warning_name,
                    gettext('account_credit_limit'
                        '.msg_party_credit_limit_amount',
                        party=self.rec_name,
                        limit=limit,
                        amount=amount))

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
                warning_name = Warning.format('credit_limit_dunning', [origin])
                if Warning.check(warning_name):
                    raise CreditLimitWarning(warning_name,
                        gettext('account_credit_limit'
                            '.msg_party_credit_limit_dunning',
                            party=self.rec_name,
                            dunning=dunning.rec_name))


class PartyCreditLimitAmount(ModelSQL, CompanyValueMixin):
    __name__ = 'party.party.credit_limit_amount'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE',
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    credit_limit_amount = Monetary(
        "Credit Limit Amount", currency='currency', digits='currency')
    currency = fields.Function(
        fields.Many2One('currency.currency', "Currency"),
        'on_change_with_currency')

    @fields.depends('company')
    def on_change_with_currency(self, name=None):
        if self.company:
            return self.company.currency
