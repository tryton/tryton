# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, MatchMixin, fields, \
        sequence_ordered
from trytond.pyson import Eval
from trytond.transaction import Transaction

from .account import AnalyticMixin


class Rule(sequence_ordered(), MatchMixin, AnalyticMixin, ModelSQL, ModelView):
    "Analytic Rule"
    __name__ = 'analytic_account.rule'

    company = fields.Many2One(
        'company.company', "Company", required=True)
    account = fields.Many2One(
        'account.account', "Account",
        domain=[
            ('company', '=', Eval('company', -1)),
            ('type', '!=', 'view'),
            ],
        depends=['company'])
    party = fields.Many2One(
        'party.party', "Party",
        states={
            'invisible': ~Eval('party_visible'),
            },
        depends=['party_visible'])
    party_visible = fields.Function(fields.Boolean("Party Visible"),
        'on_change_with_party_visible')
    journal = fields.Many2One('account.journal', "Journal")

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @fields.depends('account')
    def on_change_with_party_visible(self, name=None):
        if self.account:
            return self.account.party_required
        return False
