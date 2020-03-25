# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import json
import re
from decimal import Decimal

from simpleeval import simple_eval

from trytond.model import ModelSQL, ModelView, sequence_ordered, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import If, Eval
from trytond.tools import decistmt
from trytond.transaction import Transaction


class Statement(metaclass=PoolMeta):
    __name__ = 'account.statement'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update(
            apply_rules={
                'invisible': Eval('state') != 'draft',
                'depends': ['state'],
                },
            )

    @classmethod
    @ModelView.button
    def apply_rules(cls, statements):
        pool = Pool()
        Rule = pool.get('account.statement.rule')
        Line = pool.get('account.statement.line')

        lines = []
        rules = Rule.search([])
        for statement in statements:
            lines.extend(statement._apply_rules(rules))
        Line.save(lines)

    def _apply_rules(self, rules):
        for origin in self.origins:
            if origin.lines:
                continue
            for rule in rules:
                keywords = rule.match(origin)
                if keywords:
                    yield from rule.apply(origin, keywords)


class StatementRule(sequence_ordered(), ModelSQL, ModelView):
    "Account Statement Rule"
    __name__ = 'account.statement.rule'

    name = fields.Char("Name")

    company = fields.Many2One('company.company', "Company")
    journal = fields.Many2One(
        'account.statement.journal', "Journal",
        domain=[
            If(Eval('company'),
                ('company', '=', Eval('company')),
                ()),
            ],
        depends=['company'])
    amount_low = fields.Numeric(
        "Amount Low",
        digits=(16, Eval('currency_digits', 2)),
        domain=[If(Eval('amount_high'),
                ['OR',
                    ('amount_low', '=', None),
                    ('amount_low', '<=', Eval('amount_high')),
                    ],
                [])],
        depends=['currency_digits', 'amount_high'])
    amount_high = fields.Numeric(
        "Amount High",
        digits=(16, Eval('currency_digits', 2)),
        domain=[If(Eval('amount_low'),
                ['OR',
                    ('amount_high', '=', None),
                    ('amount_high', '>=', Eval('amount_low')),
                    ],
                [])],
        depends=['currency_digits', 'amount_low'])
    description = fields.Char("Description",
        help="The regular expression the description is searched with.\n"
        "It may define the groups named:\n"
        "'party', 'bank_account', 'invoice'.")
    information_rules = fields.One2Many(
        'account.statement.rule.information', 'rule', "Information Rules")

    lines = fields.One2Many(
        'account.statement.rule.line', 'rule', "Lines")

    currency_digits = fields.Function(
        fields.Integer("Currency Digits"),
        'on_change_with_currency_digits')

    @fields.depends('journal')
    def on_change_with_currency_digits(self, name=None):
        if self.journal:
            return self.journal.currency.digits
        return None

    def match(self, origin):
        keywords = {}
        if self.company and self.company != origin.company:
            return False
        if self.journal and self.journal != origin.statement.journal:
            return False
        if self.amount_low is not None and self.amount_low > origin.amount:
            return False
        if self.amount_high is not None and self.amount_high < origin.amount:
            return False
        if self.information_rules:
            for irule in self.information_rules:
                result = irule.match(origin)
                if isinstance(result, dict):
                    keywords.update(result)
                elif not result:
                    return False
        if self.description:
            result = re.search(self.description, origin.description or '')
            if not result:
                return False
            keywords.update(result.groupdict())
        keywords.update(amount=origin.amount, pending=origin.amount)
        return keywords

    def apply(self, origin, keywords):
        keywords = keywords.copy()
        for rule_line in self.lines:
            line = rule_line.get_line(origin, keywords)
            if not line:
                return
            keywords['pending'] -= line.amount
            yield line


class StatementRuleInformation(sequence_ordered(), ModelSQL, ModelView):
    "Account Statement Rule Information"
    __name__ = 'account.statement.rule.information'

    rule = fields.Many2One(
        'account.statement.rule', "Rule", required=True, ondelete='CASCADE')
    key = fields.Many2One(
        'account.statement.origin.information', "Key", required=True,
        domain=[
            ('type_', 'in', [
                    'boolean', 'integer', 'float', 'number', 'char',
                    'selection']),
            ])

    boolean = fields.Boolean("Boolean",
        states={
            'invisible': Eval('key_type') != 'boolean',
            },
        depends=['key_type'])
    char = fields.Char("Char",
        states={
            'invisible': Eval('key_type') != 'char',
            },
        depends=['key_type'],
        help="The regular expression the key information is searched with.\n"
        "It may define the groups named:\n"
        "party, bank_account, invoice.")
    selection = fields.Selection(
        'get_selections', "Selection",
        states={
            'invisible': Eval('key_type') != 'selection',
            },
        depends=['key_type'])

    key_type = fields.Function(
        fields.Selection('get_key_types', "Key Type"),
        'on_change_with_key_type')

    @classmethod
    def get_key_types(cls):
        pool = Pool()
        OriginInformation = pool.get('account.statement.origin.information')
        return OriginInformation.fields_get(['type_'])['type_']['selection']

    @fields.depends('key')
    def on_change_with_key_type(self, name=None):
        if self.key:
            return self.key.type_

    @fields.depends('key')
    def get_selections(self):
        if self.key and self.key.type_ == 'selection':
            return json.loads(self.key.selection_json)
        return [(None, '')]

    @classmethod
    def view_attributes(cls):
        return [
            ('//group[@id="%s"]' % type_, 'states', {
                    'invisible': Eval('key_type') != type_,
                    }) for type_ in ['integer', 'float', 'number']]

    def match(self, origin):
        return getattr(self, '_match_%s' % self.key_type)(
            origin, origin.information or {})

    def _match_boolean(self, origin, information):
        return self.boolean == information.get(self.key.name, False)

    def _match_range(self, origin, information):
        low = getattr(self, '%s_low' % self.key_type)
        high = getattr(self, '%_high' % self.key_type)
        amount = information.get(self.key.name)
        if amount is None:
            return False
        if low is not None and low > amount:
            return False
        if high is not None and high < amount:
            return False
    _match_integer = _match_range
    _match_float = _match_range
    _match_number = _match_range

    def _match_char(self, origin, information):
        result = re.search(
            self.char, information.get(self.key.name, ''))
        if not result:
            return False
        return result.groupdict()

    def _match_selection(self, origin, information):
        return self.selection == information.get(self.key.name)


def _add_range(cls, name, type_, string):
    low_name = '%s_low' % name
    high_name = '%s_high' % name
    setattr(cls, low_name,
        type_("%s Low" % string,
            domain=[If(Eval(high_name),
                    ['OR',
                        (low_name, '=', None),
                        (low_name, '<=', Eval(high_name)),
                        ],
                    [])],
            states={
                'invisible': Eval('key_type') != name,
                },
            depends=['key_type', high_name]))
    setattr(cls, high_name,
        type_("%s High" % string,
            domain=[If(Eval(low_name),
                    ['OR',
                        (high_name, '=', None),
                        (high_name, '<=', Eval(low_name)),
                        ],
                    [])],
            states={
                'invisible': Eval('key_type') != name,
                },
            depends=['key_type', low_name]))


_add_range(StatementRuleInformation, 'integer', fields.Integer, "Integer")
_add_range(StatementRuleInformation, 'float', fields.Float, "Float")
_add_range(StatementRuleInformation, 'number', fields.Numeric, "Numeric")


class StatementRuleLine(sequence_ordered(), ModelSQL, ModelView):
    "Account Statement Rule Line"
    __name__ = 'account.statement.rule.line'

    rule = fields.Many2One(
        'account.statement.rule', "Rule", required=True, ondelete='CASCADE')
    amount = fields.Char(
        "Amount", required=True,
        help="A Python expression evaluated with 'amount' and 'pending'.")
    party = fields.Many2One(
        'party.party', "Party",
        help="Leave empty to use the group named 'party' "
        "from the regular expressions.")
    account = fields.Many2One(
        'account.account', "Account",
        domain=[
            ('company', '=', Eval('company')),
            ('type', '!=', None),
            ],
        states={
            'readonly': ~Eval('company'),
            },
        depends=['company'],
        help="Leave empty to use the party's receivable or payable account.\n"
        "The rule must have a company to use this field.")

    company = fields.Function(
        fields.Many2One('company.company', "Company"),
        'on_change_with_company')

    @fields.depends('rule', '_parent_rule.company')
    def on_change_with_company(self, name=None):
        if self.rule and self.rule.company:
            return self.rule.company.id

    def get_line(self, origin, keywords, **context):
        pool = Pool()
        Line = pool.get('account.statement.line')
        context.setdefault('functions', {})['Decimal'] = Decimal
        context.setdefault('names', {}).update(keywords)

        currency = origin.statement.journal.currency
        amount = currency.round(simple_eval(decistmt(self.amount), **context))
        party = self._get_party(origin, keywords)
        invoice = self._get_invoice(origin, keywords)

        if invoice and party and invoice.party != party:
            return
        if invoice and not party:
            party = invoice.party

        account = self.account
        if not account:
            if invoice:
                account = invoice.account
            elif party:
                with Transaction().set_context(date=origin.date):
                    if amount > Decimal('0.0'):
                        account = party.account_receivable_used
                    else:
                        account = party.account_payable_used

        if not account:
            return
        if not party:
            party = origin.party
        if account.party_required and not party:
            return
        if not account.party_required:
            party = None

        line = Line()
        line.statement = origin.statement
        line.number = origin.number
        line.description = origin.description
        line.origin = origin
        line.amount = amount
        line.date = origin.date
        line.party = party
        line.account = account
        line.invoice = invoice
        return line

    def _get_party(self, origin, keywords):
        pool = Pool()
        Party = pool.get('party.party')
        try:
            AccountNumber = pool.get('bank.account.number')
        except KeyError:
            AccountNumber = None

        party = self.party
        if not party:
            if keywords.get('bank_account') and AccountNumber:
                bank_account = keywords['bank_account']
                numbers = AccountNumber.search(['OR',
                        ('number', '=', bank_account),
                        ('number_compact', '=', bank_account),
                        ])
                if len(numbers) == 1:
                    number, = numbers
                    if number.account.owners:
                        party = number.account.owners[0]
            elif keywords.get('party'):
                parties = Party.search(
                    [('rec_name', 'ilike', keywords['party'])])
                if len(parties) == 1:
                    party, = parties
        return party

    def _get_invoice(self, origin, keywords):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        if keywords.get('invoice'):
            invoices = Invoice.search([('rec_name', '=', keywords['invoice'])])
            if len(invoices) == 1:
                invoice, = invoices
                return invoice
