# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from collections import namedtuple
from decimal import Decimal
from itertools import groupby

from sql import Literal
from sql.aggregate import Sum
from sql.conditionals import Case

from trytond.i18n import gettext
from trytond.model import (
    ModelView, ModelSQL, MatchMixin, DeactivableMixin, fields,
    sequence_ordered, tree)
from trytond.model.exceptions import AccessError
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond import backend
from trytond.pyson import Eval, If, Bool, PYSONEncoder
from trytond.transaction import Transaction
from trytond.tools import cursor_dict, lstrip_wildcard
from trytond.pool import Pool

from .common import PeriodMixin, ActivePeriodMixin

__all__ = ['TaxGroup', 'TaxCodeTemplate', 'TaxCode',
    'TaxCodeLineTemplate', 'TaxCodeLine',
    'OpenChartTaxCodeStart', 'OpenChartTaxCode',
    'TaxTemplate', 'Tax', 'TaxLine', 'TaxRuleTemplate', 'TaxRule',
    'TaxRuleLineTemplate', 'TaxRuleLine',
    'OpenTaxCode',
    'TestTax', 'TestTaxView', 'TestTaxViewResult']

KINDS = [
    ('sale', 'Sale'),
    ('purchase', 'Purchase'),
    ('both', 'Both'),
    ]


class TaxGroup(ModelSQL, ModelView):
    'Tax Group'
    __name__ = 'account.tax.group'
    name = fields.Char('Name', size=None, required=True)
    code = fields.Char('Code', size=None, required=True)
    kind = fields.Selection(KINDS, 'Kind', required=True)

    @staticmethod
    def default_kind():
        return 'both'


class TaxCodeTemplate(PeriodMixin, tree(), ModelSQL, ModelView):
    'Tax Code Template'
    __name__ = 'account.tax.code.template'
    name = fields.Char('Name', required=True)
    code = fields.Char('Code')
    parent = fields.Many2One('account.tax.code.template', 'Parent')
    lines = fields.One2Many('account.tax.code.line.template', 'code', "Lines")
    childs = fields.One2Many('account.tax.code.template', 'parent', 'Children')
    account = fields.Many2One('account.account.template', 'Account Template',
            domain=[('parent', '=', None)], required=True)
    description = fields.Text('Description')

    @classmethod
    def __setup__(cls):
        super(TaxCodeTemplate, cls).__setup__()
        cls._order.insert(0, ('code', 'ASC'))
        cls._order.insert(0, ('account', 'ASC'))

    def _get_tax_code_value(self, code=None):
        '''
        Set values for tax code creation.
        '''
        res = {}
        if not code or code.name != self.name:
            res['name'] = self.name
        if not code or code.code != self.code:
            res['code'] = self.code
        if not code or code.start_date != self.start_date:
            res['start_date'] = self.start_date
        if not code or code.end_date != self.end_date:
            res['end_date'] = self.end_date
        if not code or code.description != self.description:
            res['description'] = self.description
        if not code or code.template.id != self.id:
            res['template'] = self.id
        return res

    @classmethod
    def create_tax_code(cls, account_id, company_id, template2tax_code=None):
        '''
        Create recursively tax codes based on template.
        template2tax_code is a dictionary with tax code template id as key and
        tax code id as value, used to convert template id into tax code. The
        dictionary is filled with new tax codes.
        '''
        pool = Pool()
        TaxCode = pool.get('account.tax.code')

        if template2tax_code is None:
            template2tax_code = {}

        def create(templates):
            values = []
            created = []
            for template in templates:
                if template.id not in template2tax_code:
                    vals = template._get_tax_code_value()
                    vals['company'] = company_id
                    if template.parent:
                        vals['parent'] = template2tax_code[template.parent.id]
                    else:
                        vals['parent'] = None
                    values.append(vals)
                    created.append(template)

            tax_codes = TaxCode.create(values)
            for template, tax_code in zip(created, tax_codes):
                template2tax_code[template.id] = tax_code.id

        childs = cls.search([
                ('account', '=', account_id),
                ('parent', '=', None),
                ])
        while childs:
            create(childs)
            childs = sum((c.childs for c in childs), ())


class TaxCode(ActivePeriodMixin, tree(), ModelSQL, ModelView):
    'Tax Code'
    __name__ = 'account.tax.code'
    _states = {
        'readonly': (Bool(Eval('template', -1))
            & ~Eval('template_override', False)),
        }
    name = fields.Char('Name', required=True, select=True, states=_states)
    code = fields.Char('Code', select=True, states=_states)
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True)
    parent = fields.Many2One(
        'account.tax.code', 'Parent', select=True, states=_states)
    lines = fields.One2Many('account.tax.code.line', 'code', "Lines")
    childs = fields.One2Many('account.tax.code', 'parent', 'Children')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    amount = fields.Function(fields.Numeric(
            "Amount", digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_amount')
    template = fields.Many2One('account.tax.code.template', 'Template')
    template_override = fields.Boolean('Override Template',
        help="Check to override template definition",
        states={
            'invisible': ~Bool(Eval('template', -1)),
            },
        depends=['template'])
    description = fields.Text('Description')
    del _states

    @classmethod
    def __setup__(cls):
        super(TaxCode, cls).__setup__()
        for date in [cls.start_date, cls.end_date]:
            date.states = {
                'readonly': (Bool(Eval('template', -1))
                    & ~Eval('template_override', False)),
                }
        cls._order.insert(0, ('code', 'ASC'))

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def default_template_override(cls):
        return False

    @fields.depends('company')
    def on_change_with_currency_digits(self, name=None):
        if self.company:
            return self.company.currency.digits
        return 2

    @classmethod
    def get_amount(cls, codes, name):
        result = {}

        parents = {}
        childs = cls.search([
                ('parent', 'child_of', [c.id for c in codes]),
                ])
        for code in childs:
            exp = Decimal(str(10.0 ** -code.currency_digits))
            result[code.id] = sum(
                (l.value for l in code.lines), Decimal(0)).quantize(exp)
            parents[code.id] = code.parent.id if code.parent else None

        ids = set(map(int, childs))
        leafs = ids - set(parents.values())
        while leafs:
            for code in leafs:
                ids.remove(code)
                parent = parents.get(code)
                if parent in result:
                    result[parent] += result[code]
            next_leafs = set(ids)
            for code in ids:
                parent = parents.get(code)
                if not parent:
                    continue
                if parent in next_leafs and parent in ids:
                    next_leafs.remove(parent)
            leafs = next_leafs
        return result

    def get_rec_name(self, name):
        if self.code:
            return self.code + ' - ' + self.name
        else:
            return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        code_value = clause[2]
        if clause[1].endswith('like'):
            code_value = lstrip_wildcard(clause[2])
        return [bool_op,
            ('code', clause[1], code_value) + tuple(clause[3:]),
            (cls._rec_name,) + tuple(clause[1:]),
            ]

    @classmethod
    def copy(cls, codes, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('template', None)
        return super(TaxCode, cls).copy(codes, default=default)

    @classmethod
    def delete(cls, codes):
        codes = cls.search([
                ('parent', 'child_of', [c.id for c in codes]),
                ])
        super(TaxCode, cls).delete(codes)

    @classmethod
    def update_tax_code(cls, company_id, template2tax_code=None):
        '''
        Update recursively tax code based on template.
        template2tax_code is a dictionary with tax code template id as key and
        tax code id as value, used to convert template id into tax code. The
        dictionary is filled with new tax codes
        '''
        if template2tax_code is None:
            template2tax_code = {}

        values = []
        childs = cls.search([
                ('company', '=', company_id),
                ('parent', '=', None),
                ])
        while childs:
            for child in childs:
                if child.template:
                    if not child.template_override:
                        vals = child.template._get_tax_code_value(code=child)
                        if vals:
                            values.append([child])
                            values.append(vals)
                    template2tax_code[child.template.id] = child.id
            childs = sum((c.childs for c in childs), ())
        if values:
            cls.write(*values)


class TaxCodeLineTemplate(ModelSQL, ModelView):
    "Tax Code Line Template"
    __name__ = 'account.tax.code.line.template'

    code = fields.Many2One('account.tax.code.template', "Code", required=True)
    operator = fields.Selection([
            ('+', "+"),
            ('-', "-"),
            ], "Operator", required=True)
    tax = fields.Many2One('account.tax.template', "Tax", required=True)
    amount = fields.Selection([
            ('tax', "Tax"),
            ('base', "Base"),
            ], "Amount", required=True)
    type = fields.Selection([
            ('invoice', "Invoice"),
            ('credit', "Credit"),
            ], "Type", required=True)

    def _get_tax_code_line_value(self, line=None):
        value = {}
        for name in ['operator', 'amount', 'type']:
            if not line or getattr(line, name) != getattr(self, name):
                value[name] = getattr(self, name)
        if not line or line.template != self:
            value['template'] = self.id
        return value

    @classmethod
    def create_tax_code_line(cls, account_id, template2tax, template2tax_code,
            template2tax_code_line=None):
        "Create tax code lines based on template"
        pool = Pool()
        TaxCodeLine = pool.get('account.tax.code.line')

        if template2tax_code_line is None:
            template2tax_code_line = {}

        values = []
        created = []
        for template in cls.search([('code.account', '=', account_id)]):
            if template.id not in template2tax_code_line:
                value = template._get_tax_code_line_value()
                value['code'] = template2tax_code.get(template.code.id)
                value['tax'] = template2tax.get(template.tax.id)
                values.append(value)
                created.append(template)

        lines = TaxCodeLine.create(values)
        for template, line in zip(created, lines):
            template2tax_code_line[template.id] = line.id


class TaxCodeLine(ModelSQL, ModelView):
    "Tax Code Line"
    __name__ = 'account.tax.code.line'
    _states = {
        'readonly': (Bool(Eval('template', -1))
            & ~Eval('template_override', False)),
        }

    code = fields.Many2One('account.tax.code', "Code", required=True)
    operator = fields.Selection([
            ('+', "+"),
            ('-', "-"),
            ], "Operator", required=True, states=_states)
    tax = fields.Many2One(
        'account.tax', "Tax", required=True, states=_states,
        domain=[
            ('company', '=', Eval('_parent_code', {}).get('company')),
            ])
    amount = fields.Selection([
            ('tax', "Tax"),
            ('base', "Base"),
            ], "Amount", required=True, states=_states)
    type = fields.Selection([
            ('invoice', "Invoice"),
            ('credit', "Credit"),
            ], "Type", required=True, states=_states)

    template = fields.Many2One(
        'account.tax.code.line.template', 'Template', ondelete='CASCADE')
    template_override = fields.Boolean('Override Template',
        help="Check to override template definition",
        states={
            'invisible': ~Bool(Eval('template', -1)),
            },
        depends=['template'])

    del _states

    @classmethod
    def default_operator(cls):
        return '+'

    @property
    def value(self):
        value = getattr(self.tax, '%s_%s_amount' % (self.type, self.amount))
        value = abs(value)
        if self.operator == '-':
            value *= -1
        return value

    @property
    def _line_domain(self):
        domain = [
            ('tax', '=', self.tax.id),
            ('type', '=', self.amount),
            ]
        if self.type == 'invoice':
            domain.append(['OR',
                    [('amount', '>', 0), ['OR',
                            ('move_line.debit', '>', 0),
                            ('move_line.credit', '>', 0),
                            ]],
                    [('amount', '<', 0), ['OR',
                            ('move_line.debit', '<', 0),
                            ('move_line.credit', '<', 0),
                            ]],
                    ])
        elif self.type == 'credit':
            domain.append(['OR',
                    [('amount', '<', 0), ['OR',
                            ('move_line.debit', '>', 0),
                            ('move_line.credit', '>', 0),
                            ]],
                    [('amount', '>', 0), ['OR',
                            ('move_line.debit', '<', 0),
                            ('move_line.credit', '<', 0),
                            ]],
                    ])
        return domain

    @classmethod
    def update_tax_code_line(cls, company_id, template2tax, template2tax_code,
            template2tax_code_line=None):
        "Update tax code lines based on template."
        if template2tax_code_line is None:
            template2tax_code_line = {}

        values = []
        for line in cls.search([('tax.company', '=', company_id)]):
            if line.template:
                if not line.template_override:
                    template = line.template
                    value = template._get_tax_code_line_value(line=line)
                    if line.code.id != template2tax_code.get(template.code.id):
                        value['code'] = template2tax_code.get(template.code.id)
                    if line.tax.id != template2tax.get(template.tax.id):
                        value['tax'] = template2tax.get(template.tax.id)
                    if value:
                        values.append([line])
                        values.append(value)
                template2tax_code_line[line.template.id] = line.id
        if values:
            cls.write(*values)


class OpenChartTaxCodeStart(ModelView):
    'Open Chart of Tax Codes'
    __name__ = 'account.tax.code.open_chart.start'
    method = fields.Selection([
        ('fiscalyear', 'By Fiscal Year'),
        ('periods', 'By Periods'),
        ], 'Method', required=True)
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
        help='Leave empty for all open fiscal year',
        states={
            'invisible': Eval('method') != 'fiscalyear',
            'required': Eval('method') == 'fiscalyear',
            },
        depends=['method'])
    periods = fields.Many2Many('account.period', None, None, 'Periods',
        help='Leave empty for all periods of all open fiscal year',
        states={
            'invisible': Eval('method') != 'periods',
            'required': Eval('method') == 'periods',
            },
        depends=['method'])

    @staticmethod
    def default_method():
        return 'periods'


class OpenChartTaxCode(Wizard):
    'Open Chart of Tax Codes'
    __name__ = 'account.tax.code.open_chart'
    start = StateView('account.tax.code.open_chart.start',
        'account.tax_code_open_chart_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_', 'tryton-ok', default=True),
            ])
    open_ = StateAction('account.act_tax_code_tree2')

    def do_open_(self, action):
        periods = []
        if self.start.method == 'fiscalyear':
            if self.start.fiscalyear:
                periods = self.start.fiscalyear.periods
                action['name'] += ' - %s' % self.start.fiscalyear.rec_name
        elif self.start.method == 'periods':
            if self.start.periods:
                periods = self.start.periods
                action['name'] += ' (%s)' % ', '.join(
                    p.rec_name for p in self.start.periods)
        action['pyson_context'] = PYSONEncoder().encode({
                'periods': [p.id for p in periods],
                })
        return action, {}

    def transition_open_(self):
        return 'end'


class TaxTemplate(sequence_ordered(), ModelSQL, ModelView, DeactivableMixin):
    'Account Tax Template'
    __name__ = 'account.tax.template'
    name = fields.Char('Name', required=True)
    description = fields.Char('Description', required=True)
    group = fields.Many2One('account.tax.group', 'Group')
    start_date = fields.Date('Starting Date')
    end_date = fields.Date('Ending Date')
    amount = fields.Numeric('Amount', digits=(16, 8),
        states={
            'required': Eval('type') == 'fixed',
            'invisible': Eval('type') != 'fixed',
            },
        depends=['type'])
    rate = fields.Numeric('Rate', digits=(14, 10),
        states={
            'required': Eval('type') == 'percentage',
            'invisible': Eval('type') != 'percentage',
            }, depends=['type'])
    type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed'),
        ('none', 'None'),
        ], 'Type', required=True)
    update_unit_price = fields.Boolean('Update Unit Price',
        states={
            'invisible': Bool(Eval('parent')),
            },
        depends=['parent'])
    parent = fields.Many2One('account.tax.template', 'Parent')
    childs = fields.One2Many('account.tax.template', 'parent', 'Children')
    invoice_account = fields.Many2One(
        'account.account.template', 'Invoice Account',
        domain=[
            ('type.statement', '=', 'balance'),
            ('closed', '!=', True),
            ],
        states={
            'invisible': Eval('type') == 'none',
            'required': Eval('type') != 'none',
            },
        depends=['type'])
    credit_note_account = fields.Many2One(
        'account.account.template', 'Credit Note Account',
        domain=[
            ('type.statement', '=', 'balance'),
            ('closed', '!=', True),
            ],
        states={
            'invisible': Eval('type') == 'none',
            'required': Eval('type') != 'none',
            },
        depends=['type'])
    account = fields.Many2One('account.account.template', 'Account Template',
            domain=[('parent', '=', None)], required=True)
    legal_notice = fields.Text("Legal Notice")

    @classmethod
    def __setup__(cls):
        super(TaxTemplate, cls).__setup__()
        cls._order.insert(0, ('account', 'ASC'))

    @classmethod
    def validate(cls, tax_templates):
        super(TaxTemplate, cls).validate(tax_templates)
        for tax_template in tax_templates:
            tax_template.check_update_unit_price()

    def check_update_unit_price(self):
        if self.update_unit_price and self.parent:
            raise AccessError(
                gettext('account.msg_tax_update_unit_price_with_parent',
                    tax=self.rec_name))

    @staticmethod
    def default_type():
        return 'percentage'

    @staticmethod
    def default_update_unit_price():
        return False

    def _get_tax_value(self, tax=None):
        '''
        Set values for tax creation.
        '''
        res = {}
        for field in ['name', 'description', 'sequence', 'amount', 'rate',
                'type', 'start_date', 'end_date', 'update_unit_price',
                'legal_notice', 'active']:
            if not tax or getattr(tax, field) != getattr(self, field):
                res[field] = getattr(self, field)
        for field in ('group',):
            if not tax or getattr(tax, field) != getattr(self, field):
                value = getattr(self, field)
                if value:
                    res[field] = getattr(self, field).id
                else:
                    res[field] = None
        if not tax or tax.template != self:
            res['template'] = self.id
        return res

    @classmethod
    def create_tax(cls, account_id, company_id,
            template2account, template2tax=None):
        '''
        Create recursively taxes based on template.

        template2account is a dictionary with account template id as key and
        account id as value, used to convert account template into account
        code.
        template2tax is a dictionary with tax template id as key and tax id as
        value, used to convert template id into tax.  The dictionary is filled
        with new taxes.
        '''
        pool = Pool()
        Tax = pool.get('account.tax')

        if template2tax is None:
            template2tax = {}

        def create(templates):
            values = []
            created = []
            for template in templates:
                if template.id not in template2tax:
                    vals = template._get_tax_value()
                    vals['company'] = company_id
                    if template.parent:
                        vals['parent'] = template2tax[template.parent.id]
                    else:
                        vals['parent'] = None
                    if template.invoice_account:
                        vals['invoice_account'] = \
                            template2account[template.invoice_account.id]
                    else:
                        vals['invoice_account'] = None
                    if template.credit_note_account:
                        vals['credit_note_account'] = \
                            template2account[template.credit_note_account.id]
                    else:
                        vals['credit_note_account'] = None
                    values.append(vals)
                    created.append(template)

            taxes = Tax.create(values)
            for template, tax in zip(created, taxes):
                template2tax[template.id] = tax.id

        childs = cls.search([
                ('account', '=', account_id),
                ('parent', '=', None),
                ])
        while childs:
            create(childs)
            childs = sum((c.childs for c in childs), ())


class Tax(sequence_ordered(), ModelSQL, ModelView, DeactivableMixin):
    '''
    Account Tax

    Type:
        percentage: tax = price * rate
        fixed: tax = amount
        none: tax = none
    '''
    __name__ = 'account.tax'
    _states = {
        'readonly': (Bool(Eval('template', -1))
            & ~Eval('template_override', False)),
        }
    name = fields.Char('Name', required=True, states=_states)
    description = fields.Char('Description', required=True, translate=True,
            help="The name that will be used in reports", states=_states)
    group = fields.Many2One('account.tax.group', 'Group',
        states={
            'invisible': Bool(Eval('parent')),
            'readonly': _states['readonly'],
            }, depends=['parent'])
    start_date = fields.Date('Starting Date', states=_states)
    end_date = fields.Date('Ending Date', states=_states)
    amount = fields.Numeric('Amount', digits=(16, 8),
        states={
            'required': Eval('type') == 'fixed',
            'invisible': Eval('type') != 'fixed',
            'readonly': _states['readonly'],
            }, help='In company\'s currency',
        depends=['type'])
    rate = fields.Numeric('Rate', digits=(14, 10),
        states={
            'required': Eval('type') == 'percentage',
            'invisible': Eval('type') != 'percentage',
            'readonly': _states['readonly'],
            }, depends=['type'])
    type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed'),
        ('none', 'None'),
        ], 'Type', required=True, states=_states)
    update_unit_price = fields.Boolean('Update Unit Price',
        states={
            'invisible': Bool(Eval('parent')),
            'readonly': _states['readonly'],
            },
        depends=['parent'],
        help=('If checked then the unit price for further tax computation will'
            ' be modified by this tax'))
    parent = fields.Many2One('account.tax', 'Parent', ondelete='CASCADE',
        states=_states)
    childs = fields.One2Many('account.tax', 'parent', 'Children')
    company = fields.Many2One('company.company', 'Company', required=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ], select=True)
    invoice_account = fields.Many2One('account.account', 'Invoice Account',
        domain=[
            ('company', '=', Eval('company')),
            ('type.statement', '=', 'balance'),
            ('closed', '!=', True),
            ],
        states={
            'readonly': _states['readonly'],
            'invisible': Eval('type') == 'none',
            'required': (Eval('type') != 'none') & Eval('company'),
            },
        depends=['company', 'type'])
    credit_note_account = fields.Many2One('account.account',
        'Credit Note Account',
        domain=[
            ('company', '=', Eval('company')),
            ('type.statement', '=', 'balance'),
            ('closed', '!=', True),
            ],
        states={
            'readonly': _states['readonly'],
            'invisible': Eval('type') == 'none',
            'required': (Eval('type') != 'none') & Eval('company'),
            },
        depends=['company', 'type'])
    legal_notice = fields.Text("Legal Notice", translate=True,
        states=_states)
    template = fields.Many2One('account.tax.template', 'Template',
        ondelete='RESTRICT')
    template_override = fields.Boolean('Override Template',
        help="Check to override template definition",
        states={
            'invisible': ~Bool(Eval('template', -1)),
            },
        depends=['template'])

    invoice_base_amount = fields.Function(fields.Numeric(
            "Invoice Base Amount", digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_amount')
    invoice_tax_amount = fields.Function(fields.Numeric(
            "Invoice Tax Amount", digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_amount')
    credit_base_amount = fields.Function(fields.Numeric(
            "Credit Base Amount", digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_amount')
    credit_tax_amount = fields.Function(fields.Numeric(
            "Credit Tax Amount", digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_amount')

    currency_digits = fields.Function(fields.Integer("Currency Digits"),
        'on_change_with_currency_digits')

    del _states

    @classmethod
    def validate(cls, taxes):
        super(Tax, cls).validate(taxes)
        for tax in taxes:
            tax.check_update_unit_price()

    def check_update_unit_price(self):
        if self.parent and self.update_unit_price:
            raise AccessError(
                gettext('account.msg_tax_update_unit_price_with_parent',
                    tax=self.rec_name))

    @staticmethod
    def default_type():
        return 'percentage'

    @staticmethod
    def default_update_unit_price():
        return False

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def default_template_override(cls):
        return False

    @classmethod
    def get_amount(cls, taxes, names):
        pool = Pool()
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')
        TaxLine = pool.get('account.tax.line')
        cursor = Transaction().connection.cursor()

        move = Move.__table__()
        move_line = MoveLine.__table__()
        tax_line = TaxLine.__table__()

        tax_ids = list(map(int, taxes))
        result = {}
        for name in names:
            result[name] = dict.fromkeys(tax_ids, Decimal(0))

        columns = []
        amount = tax_line.amount
        debit = move_line.debit
        credit = move_line.credit
        if backend.name() == 'sqlite':
            amount = TaxLine.amount.sql_cast(tax_line.amount)
            debit = MoveLine.debit.sql_cast(debit)
            credit = MoveLine.credit.sql_cast(credit)
        is_invoice = (
            ((amount > 0) & ((debit > 0) | (credit > 0)))
            | ((amount < 0) & ((debit < 0) | (credit < 0)))
            )
        is_credit = (
            ((amount < 0) & ((debit > 0) | (credit > 0)))
            | ((amount > 0) & ((debit < 0) | (credit < 0)))
            )
        for name, clause in [
                ('invoice_base_amount',
                    is_invoice & (tax_line.type == 'base')),
                ('invoice_tax_amount',
                    is_invoice & (tax_line.type == 'tax')),
                ('credit_base_amount',
                    is_credit & (tax_line.type == 'base')),
                ('credit_tax_amount',
                    is_credit & (tax_line.type == 'tax')),
                ]:
            if name not in names:
                continue
            if backend.name() == 'postgresql':  # FIXME
                columns.append(Sum(amount, filter_=clause).as_(name))
            else:
                columns.append(Sum(Case([clause, amount])).as_(name))

        where = cls._amount_where(tax_line, move_line, move)
        query = (tax_line
            .join(move_line, condition=tax_line.move_line == move_line.id)
            .join(move, condition=move_line.move == move.id)
            .select(tax_line.tax.as_('tax'),
                *columns,
                where=tax_line.tax.in_(tax_ids)
                & (move_line.state != 'draft')
                & where,
                group_by=tax_line.tax)
            )

        cursor.execute(*query)
        for row in cursor_dict(cursor):
            for name in names:
                value = row[name] or 0
                if not isinstance(value, Decimal):
                    value = Decimal(str(value))
                result[name][row['tax']] = value
        return result

    @classmethod
    def _amount_where(cls, tax_line, move_line, move):
        context = Transaction().context
        periods = context.get('periods', [])
        if periods:
            return move.period.in_(periods)
        else:
            return Literal(False)

    @classmethod
    def _amount_domain(cls):
        context = Transaction().context
        periods = context.get('periods', [])
        return [('move_line.move.period', 'in', periods)]

    @fields.depends('company')
    def on_change_with_currency_digits(self, name=None):
        if self.company:
            return self.company.currency.digits
        return 2

    @classmethod
    def copy(cls, taxes, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('template', None)
        return super(Tax, cls).copy(taxes, default=default)

    def _process_tax(self, price_unit):
        if self.type == 'percentage':
            amount = price_unit * self.rate
            return {
                'base': price_unit,
                'amount': amount,
                'tax': self,
                }
        if self.type == 'fixed':
            amount = self.amount
            return {
                'base': price_unit,
                'amount': amount,
                'tax': self,
                }

    def _group_taxes(self):
        'Key method used to group taxes'
        return (self.sequence,)

    @classmethod
    def _unit_compute(cls, taxes, price_unit, date):
        res = []
        for _, group_taxes in groupby(taxes, key=cls._group_taxes):
            unit_price_variation = 0
            for tax in group_taxes:
                start_date = tax.start_date or datetime.date.min
                end_date = tax.end_date or datetime.date.max
                values = []
                if not (start_date <= date <= end_date):
                    continue
                if tax.type != 'none':
                    values.append(tax._process_tax(price_unit))
                if len(tax.childs):
                    values.extend(
                        cls._unit_compute(tax.childs, price_unit, date))
                if tax.update_unit_price:
                    for value in values:
                        unit_price_variation += value['amount']
                res.extend(values)
            price_unit += unit_price_variation
        return res

    @classmethod
    def _reverse_rate_amount(cls, taxes, date):
        rate, amount = 0, 0
        for tax in taxes:
            start_date = tax.start_date or datetime.date.min
            end_date = tax.end_date or datetime.date.max
            if not (start_date <= date <= end_date):
                continue

            if tax.type == 'percentage':
                rate += tax.rate
            elif tax.type == 'fixed':
                amount += tax.amount

            if tax.childs:
                child_rate, child_amount = cls._reverse_rate_amount(
                    tax.childs, date)
                rate += child_rate
                amount += child_amount
        return rate, amount

    @classmethod
    def _reverse_unit_compute(cls, price_unit, taxes, date):
        rate, amount = 0, 0
        update_unit_price = False
        unit_price_variation_amount = 0
        unit_price_variation_rate = 0
        for _, group_taxes in groupby(taxes, key=cls._group_taxes):
            group_taxes = list(group_taxes)
            g_rate, g_amount = cls._reverse_rate_amount(group_taxes, date)
            if update_unit_price:
                g_amount += unit_price_variation_amount * g_rate
                g_rate += unit_price_variation_rate * g_rate

            g_update_unit_price = any(t.update_unit_price for t in group_taxes)
            update_unit_price |= g_update_unit_price
            if g_update_unit_price:
                unit_price_variation_amount += g_amount
                unit_price_variation_rate += g_rate

            rate += g_rate
            amount += g_amount

        return (price_unit - amount) / (1 + rate)

    @classmethod
    def sort_taxes(cls, taxes, reverse=False):
        '''
        Return a list of taxes sorted
        '''
        def key(tax):
            return 0 if tax.sequence is None else 1, tax.sequence or 0, tax.id
        return sorted(taxes, key=key, reverse=reverse)

    @classmethod
    def compute(cls, taxes, price_unit, quantity, date=None):
        '''
        Compute taxes for price_unit and quantity at the date.
        Return list of dict for each taxes and their childs with:
            base
            amount
            tax
        '''
        pool = Pool()
        Date = pool.get('ir.date')
        if date is None:
            date = Date.today()
        taxes = cls.sort_taxes(taxes)
        res = cls._unit_compute(taxes, price_unit, date)
        quantity = Decimal(str(quantity or 0.0))
        for row in res:
            row['base'] *= quantity
            row['amount'] *= quantity
        return res

    @classmethod
    def reverse_compute(cls, price_unit, taxes, date=None):
        '''
        Reverse compute the price_unit for taxes at the date.
        '''
        pool = Pool()
        Date = pool.get('ir.date')
        if date is None:
            date = Date.today()
        taxes = cls.sort_taxes(taxes)
        return cls._reverse_unit_compute(price_unit, taxes, date)

    @classmethod
    def update_tax(cls, company_id, template2account, template2tax=None):
        '''
        Update recursively taxes based on template.
        template2account is a dictionary with account template id as key and
        account id as value, used to convert account template into account
        code.
        template2tax is a dictionary with tax template id as key and tax id as
        value, used to convert template id into tax.  The dictionary is filled
        with new taxes.
        '''
        if template2tax is None:
            template2tax = {}

        values = []
        childs = cls.search([
                ('company', '=', company_id),
                ('parent', '=', None),
                ])
        while childs:
            for child in childs:
                if child.template:
                    if not child.template_override:
                        vals = child.template._get_tax_value(tax=child)
                        invoice_account_id = (child.invoice_account.id
                            if child.invoice_account else None)
                        if (child.template.invoice_account and
                                invoice_account_id != template2account.get(
                                        child.template.invoice_account.id)):
                            vals['invoice_account'] = template2account.get(
                                child.template.invoice_account.id)
                        elif (not child.template.invoice_account
                                and child.invoice_account):
                            vals['invoice_account'] = None
                        credit_note_account_id = (child.credit_note_account.id
                            if child.credit_note_account else None)
                        if (child.template.credit_note_account and
                                credit_note_account_id != template2account.get(
                                    child.template.credit_note_account.id)):
                            vals['credit_note_account'] = template2account.get(
                                child.template.credit_note_account.id)
                        elif (not child.template.credit_note_account
                                and child.credit_note_account):
                            vals['credit_note_account'] = None
                        if vals:
                            values.append([child])
                            values.append(vals)
                    template2tax[child.template.id] = child.id
            childs = sum((c.childs for c in childs), ())
        if values:
            cls.write(*values)


class _TaxKey(dict):

    def __init__(self, **kwargs):
        self.update(kwargs)

    def _key(self):
        return (self['account'], self['tax'], self['base'] >= 0)

    def __eq__(self, other):
        if isinstance(other, _TaxKey):
            return self._key() == other._key()
        return self._key() == other

    def __hash__(self):
        return hash(self._key())


_TaxableLine = namedtuple('_TaxableLine', ('taxes', 'unit_price', 'quantity'))


class TaxableMixin(object):
    __slots__ = ()

    @property
    def taxable_lines(self):
        """A list of tuples where
            - the first element is the taxes applicable
            - the second element is the line unit price
            - the third element is the line quantity
        """
        return []

    @property
    def currency(self):
        "The currency used by the taxable object"
        return None

    @property
    def tax_date(self):
        "Date to use when computing the tax"
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()

    def _get_tax_context(self):
        return {}

    @staticmethod
    def _compute_tax_line(amount, base, tax):
        if base >= 0:
            type_ = 'invoice'
        else:
            type_ = 'credit_note'

        line = {}
        line['manual'] = False
        line['description'] = tax.description
        line['legal_notice'] = tax.legal_notice
        line['base'] = base
        line['amount'] = amount
        line['tax'] = tax.id
        line['account'] = getattr(tax, '%s_account' % type_).id

        return _TaxKey(**line)

    def _round_taxes(self, taxes):
        if not self.currency:
            return
        for taxline in taxes.values():
            taxline['amount'] = self.currency.round(taxline['amount'])

    def _get_taxes(self):
        pool = Pool()
        Tax = pool.get('account.tax')
        Configuration = pool.get('account.configuration')

        config = Configuration(1)
        tax_rounding = config.tax_rounding
        taxes = {}
        with Transaction().set_context(self._get_tax_context()):
            taxable_lines = [_TaxableLine(*params)
                for params in self.taxable_lines]
            for line in taxable_lines:
                l_taxes = Tax.compute(Tax.browse(line.taxes), line.unit_price,
                    line.quantity, self.tax_date)
                for tax in l_taxes:
                    taxline = self._compute_tax_line(**tax)
                    if self.currency:
                        taxline['base'] = self.currency.round(taxline['base'])
                    if taxline not in taxes:
                        taxes[taxline] = taxline
                    else:
                        taxes[taxline]['base'] += taxline['base']
                        taxes[taxline]['amount'] += taxline['amount']
                if tax_rounding == 'line':
                    self._round_taxes(taxes)
        if tax_rounding == 'document':
            self._round_taxes(taxes)
        return taxes


class TaxLine(ModelSQL, ModelView):
    'Tax Line'
    __name__ = 'account.tax.line'
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
        required=True, depends=['currency_digits'])
    type = fields.Selection([
            ('tax', "Tax"),
            ('base', "Base"),
            ], "Type", required=True)
    tax = fields.Many2One('account.tax', 'Tax', select=True,
        ondelete='RESTRICT', required=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    move_line = fields.Many2One('account.move.line', 'Move Line',
            required=True, select=True, ondelete='CASCADE')
    company = fields.Function(fields.Many2One('company.company', 'Company'),
        'on_change_with_company')

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Tax = pool.get('account.tax')
        TableHandler = backend.get('TableHandler')
        transaction = Transaction()
        table = cls.__table__()
        tax = Tax.__table__()

        migrate_type = False
        if TableHandler.table_exist(cls._table):
            table_h = cls.__table_handler__(module_name)
            migrate_type = not table_h.column_exist('type')

        super(TaxLine, cls).__register__(module_name)

        table_h = cls.__table_handler__(module_name)

        # Migrate from 4.6: remove code and fill type
        table_h.not_null_action('code', action='remove')
        if migrate_type:
            # XXX base on no tax code is used for both tax and base
            cursor = transaction.connection.cursor()
            cursor.execute(*tax.select(
                    tax.id, tax.company,
                    tax.invoice_base_code, tax.invoice_tax_code,
                    tax.credit_note_base_code, tax.credit_note_tax_code))
            update = transaction.connection.cursor()
            for (tax, company,
                    invoice_base_code, invoice_tax_code,
                    credit_note_base_code, credit_note_tax_code) in cursor:
                update.execute(*table.update(
                        [table.type], ['tax'],
                        where=(table.tax == tax)
                        & (table.code.in_(
                                [invoice_tax_code, credit_note_tax_code]))))
                update.execute(*table.update(
                        [table.type], ['base'],
                        where=(table.tax == tax)
                        & (table.code.in_(
                                [invoice_base_code, credit_note_base_code]))))

    @fields.depends('move_line', '_parent_move_line.currency_digits')
    def on_change_with_currency_digits(self, name=None):
        if self.move_line:
            return self.move_line.currency_digits
        return 2

    @fields.depends('_parent_move_line.account', 'move_line')
    def on_change_with_company(self, name=None):
        if self.move_line and self.move_line.account:
            return self.move_line.account.company.id

    def get_rec_name(self, name):
        name = super(TaxLine, self).get_rec_name(name)
        if self.tax:
            name = self.tax.rec_name
        return name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('tax',) + tuple(clause[1:])]

    @classmethod
    def create(cls, vlist):
        lines = super(TaxLine, cls).create(vlist)
        cls.check_modify(lines)
        return lines

    @classmethod
    def write(cls, *args):
        lines = sum(args[0:None:2], [])
        cls.check_modify(lines)
        super(TaxLine, cls).write(*args)

    @classmethod
    def delete(cls, lines):
        cls.check_modify(lines)
        super(TaxLine, cls).delete(lines)

    @property
    def period_checked(self):
        return self.move_line.period

    @classmethod
    def check_modify(cls, lines):
        for line in lines:
            period = line.period_checked
            if period and period.state != 'open':
                raise AccessError(
                    gettext('account.msg_modify_tax_line_closed_period',
                        period=period.rec_name))


class TaxRuleTemplate(ModelSQL, ModelView):
    'Tax Rule Template'
    __name__ = 'account.tax.rule.template'
    name = fields.Char('Name', required=True)
    kind = fields.Selection(KINDS, 'Kind', required=True)
    lines = fields.One2Many('account.tax.rule.line.template', 'rule', 'Lines')
    account = fields.Many2One('account.account.template', 'Account Template',
            domain=[('parent', '=', None)], required=True)

    @staticmethod
    def default_kind():
        return 'both'

    def _get_tax_rule_value(self, rule=None):
        '''
        Set values for tax rule creation.
        '''
        res = {}
        if not rule or rule.name != self.name:
            res['name'] = self.name
        if not rule or rule.kind != self.kind:
            res['kind'] = self.kind
        if not rule or rule.template.id != self.id:
            res['template'] = self.id
        return res

    @classmethod
    def create_rule(cls, account_id, company_id, template2rule=None):
        '''
        Create tax rule based on template.
        template2rule is a dictionary with tax rule template id as key and tax
        rule id as value, used to convert template id into tax rule. The
        dictionary is filled with new tax rules.
        '''
        pool = Pool()
        Rule = pool.get('account.tax.rule')

        if template2rule is None:
            template2rule = {}

        templates = cls.search([
                ('account', '=', account_id),
                ])

        values = []
        created = []
        for template in templates:
            if template.id not in template2rule:
                vals = template._get_tax_rule_value()
                vals['company'] = company_id
                values.append(vals)
                created.append(template)

        rules = Rule.create(values)
        for template, rule in zip(created, rules):
            template2rule[template.id] = rule.id


class TaxRule(ModelSQL, ModelView):
    'Tax Rule'
    __name__ = 'account.tax.rule'
    _states = {
        'readonly': (Bool(Eval('template', -1))
            & ~Eval('template_override', False)),
        }
    name = fields.Char('Name', required=True, states=_states)
    kind = fields.Selection(KINDS, 'Kind', required=True, states=_states)
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True, domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])
    lines = fields.One2Many('account.tax.rule.line', 'rule', 'Lines')
    template = fields.Many2One('account.tax.rule.template', 'Template')
    template_override = fields.Boolean("Override Template",
        help="Check to override template definition",
        states={
            'invisible': ~Bool(Eval('template', -1)),
            },
        depends=['template'])
    del _states

    @staticmethod
    def default_kind():
        return 'both'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def copy(cls, rules, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('template', None)
        return super(TaxRule, cls).copy(rules, default=default)

    def apply(self, tax, pattern):
        '''
        Apply rule on tax
        pattern is a dictonary with rule line field as key and match value as
        value.
        Return a list of the tax id to use or None
        '''
        pattern = pattern.copy()
        pattern['group'] = tax.group.id if tax and tax.group else None
        pattern['origin_tax'] = tax.id if tax else None

        for line in self.lines:
            if line.match(pattern):
                return line.get_taxes(tax)
        return tax and [tax.id] or None

    @classmethod
    def update_rule(cls, company_id, template2rule=None):
        '''
        Update tax rule based on template.
        template2rule is a dictionary with tax rule template id as key and tax
        rule id as value, used to convert template id into tax rule. The
        dictionary is filled with new tax rules.
        '''
        if template2rule is None:
            template2rule = {}

        values = []
        rules = cls.search([
                ('company', '=', company_id),
                ])
        for rule in rules:
            if rule.template:
                template2rule[rule.template.id] = rule.id
                if rule.template_override:
                    continue
                vals = rule.template._get_tax_rule_value(rule=rule)
                if vals:
                    values.append([rule])
                    values.append(vals)
        if values:
            cls.write(*values)


class TaxRuleLineTemplate(sequence_ordered(), ModelSQL, ModelView):
    'Tax Rule Line Template'
    __name__ = 'account.tax.rule.line.template'
    rule = fields.Many2One('account.tax.rule.template', 'Rule', required=True,
            ondelete='CASCADE')
    group = fields.Many2One('account.tax.group', 'Tax Group',
        ondelete='RESTRICT')
    origin_tax = fields.Many2One('account.tax.template', 'Original Tax',
        domain=[
            ('parent', '=', None),
            ('account', '=', Eval('_parent_rule', {}).get('account', 0)),
            ('group', '=', Eval('group')),
            ['OR',
                ('group', '=', None),
                If(Eval('_parent_rule', {}).get('kind', 'both') == 'sale',
                    ('group.kind', 'in', ['sale', 'both']),
                    If(Eval('_parent_rule', {}).get('kind', 'both') ==
                        'purchase',
                        ('group.kind', 'in', ['purchase', 'both']),
                        ('group.kind', 'in', ['sale', 'purchase', 'both']))),
                ],
            ],
        help=('If the original tax template is filled, the rule will be '
            'applied only for this tax template.'),
        depends=['group'],
        ondelete='RESTRICT')
    keep_origin = fields.Boolean("Keep Origin",
        help="Check to append the original tax to substituted tax.")
    tax = fields.Many2One('account.tax.template', 'Substitution Tax',
        domain=[
            ('parent', '=', None),
            ('account', '=', Eval('_parent_rule', {}).get('account', 0)),
            ('group', '=', Eval('group')),
            ['OR',
                ('group', '=', None),
                If(Eval('_parent_rule', {}).get('kind', 'both') == 'sale',
                    ('group.kind', 'in', ['sale', 'both']),
                    If(Eval('_parent_rule', {}).get('kind', 'both') ==
                        'purchase',
                        ('group.kind', 'in', ['purchase', 'both']),
                        ('group.kind', 'in', ['sale', 'purchase', 'both']))),
                ],
            ],
        depends=['group'],
        ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(TaxRuleLineTemplate, cls).__setup__()
        cls._order.insert(1, ('rule', 'ASC'))

    def _get_tax_rule_line_value(self, rule_line=None):
        '''
        Set values for tax rule line creation.
        '''
        res = {}
        if not rule_line or rule_line.group != self.group:
            res['group'] = self.group.id if self.group else None
        if not rule_line or rule_line.sequence != self.sequence:
            res['sequence'] = self.sequence
        if not rule_line or rule_line.keep_origin != self.keep_origin:
            res['keep_origin'] = self.keep_origin
        if not rule_line or rule_line.template != self:
            res['template'] = self.id
        return res

    @classmethod
    def create_rule_line(cls, account_id, template2tax, template2rule,
            template2rule_line=None):
        '''
        Create tax rule line based on template.
        template2tax is a dictionary with tax template id as key and tax id as
        value, used to convert template id into tax.
        template2rule is a dictionary with tax rule template id as key and tax
        rule id as value, used to convert template id into tax rule.
        template2rule_line is a dictionary with tax rule line template id as
        key and tax rule line id as value, used to convert template id into tax
        rule line. The dictionary is filled with new tax rule lines.
        '''
        RuleLine = Pool().get('account.tax.rule.line')

        if template2rule_line is None:
            template2rule_line = {}

        templates = cls.search([
                ('rule.account', '=', account_id),
                ])

        values = []
        created = []
        for template in templates:
            if template.id not in template2rule_line:
                vals = template._get_tax_rule_line_value()
                vals['rule'] = template2rule[template.rule.id]
                if template.origin_tax:
                    vals['origin_tax'] = template2tax[template.origin_tax.id]
                else:
                    vals['origin_tax'] = None
                if template.tax:
                    vals['tax'] = template2tax[template.tax.id]
                else:
                    vals['tax'] = None
                values.append(vals)
                created.append(template)

        rule_lines = RuleLine.create(values)
        for template, rule_line in zip(created, rule_lines):
            template2rule_line[template.id] = rule_line.id


class TaxRuleLine(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    'Tax Rule Line'
    __name__ = 'account.tax.rule.line'
    _states = {
        'readonly': (Bool(Eval('template', -1))
            & ~Eval('template_override', False)),
        }
    rule = fields.Many2One('account.tax.rule', 'Rule', required=True,
            select=True, ondelete='CASCADE', states=_states)
    group = fields.Many2One('account.tax.group', 'Tax Group',
        ondelete='RESTRICT', states=_states)
    origin_tax = fields.Many2One('account.tax', 'Original Tax',
        domain=[
            ('parent', '=', None),
            ('company', '=', Eval('_parent_rule', {}).get('company')),
            ('group', '=', Eval('group')),
            ['OR',
                ('group', '=', None),
                If(Eval('_parent_rule', {}).get('kind', 'both') == 'sale',
                    ('group.kind', 'in', ['sale', 'both']),
                    If(Eval('_parent_rule', {}).get('kind', 'both') ==
                        'purchase',
                        ('group.kind', 'in', ['purchase', 'both']),
                        ('group.kind', 'in', ['sale', 'purchase', 'both']))),
                ],
            ],
        help=('If the original tax is filled, the rule will be applied '
            'only for this tax.'),
        depends=['group'],
        ondelete='RESTRICT', states=_states)
    keep_origin = fields.Boolean("Keep Origin", states=_states,
        help="Check to append the original tax to substituted tax.")
    tax = fields.Many2One('account.tax', 'Substitution Tax',
        domain=[
            ('parent', '=', None),
            ('company', '=', Eval('_parent_rule', {}).get('company')),
            ('group', '=', Eval('group')),
            ['OR',
                ('group', '=', None),
                If(Eval('_parent_rule', {}).get('kind', 'both') == 'sale',
                    ('group.kind', 'in', ['sale', 'both']),
                    If(Eval('_parent_rule', {}).get('kind', 'both') ==
                        'purchase',
                        ('group.kind', 'in', ['purchase', 'both']),
                        ('group.kind', 'in', ['sale', 'purchase', 'both']))),
                ],
            ],
        depends=['group'],
        ondelete='RESTRICT', states=_states)
    template = fields.Many2One(
        'account.tax.rule.line.template', 'Template', ondelete='CASCADE')
    template_override = fields.Boolean("Override Template",
        help="Check to override template definition",
        states={
            'invisible': ~Bool(Eval('template', -1)),
            },
        depends=['template'])
    del _states

    @classmethod
    def __setup__(cls):
        super(TaxRuleLine, cls).__setup__()
        cls._order.insert(1, ('rule', 'ASC'))

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('template', None)
        return super(TaxRuleLine, cls).copy(lines, default=default)

    def match(self, pattern):
        if 'group' in pattern and not self.group:
            if pattern['group']:
                return False
        return super(TaxRuleLine, self).match(pattern)

    def get_taxes(self, origin_tax):
        '''
        Return list of taxes for a line
        '''
        if self.tax:
            taxes = [self.tax.id]
            if self.keep_origin and origin_tax:
                taxes.append(origin_tax.id)
            return taxes
        return None

    @classmethod
    def update_rule_line(cls, company_id, template2tax, template2rule,
            template2rule_line=None):
        '''
        Update tax rule line based on template.
        template2tax is a dictionary with tax template id as key and tax id as
        value, used to convert template id into tax.
        template2rule is a dictionary with tax rule template id as key and tax
        rule id as value, used to convert template id into tax rule.
        template2rule_line is a dictionary with tax rule line template id as
        key and tax rule line id as value, used to convert template id into tax
        rule line. The dictionary is filled with new tax rule lines.
        '''
        if template2rule_line is None:
            template2rule_line = {}

        values = []
        lines = cls.search([
                ('rule.company', '=', company_id),
                ])
        for line in lines:
            if line.template:
                template2rule_line[line.template.id] = line.id
                if line.template_override:
                    continue
                vals = line.template._get_tax_rule_line_value(rule_line=line)
                if line.rule.id != template2rule[line.template.rule.id]:
                    vals['rule'] = template2rule[line.template.rule.id]
                if line.origin_tax:
                    if line.template.origin_tax:
                        if (line.origin_tax.id !=
                                template2tax[line.template.origin_tax.id]):
                            vals['origin_tax'] = template2tax[
                                line.template.origin_tax.id]
                    else:
                        vals['origin_tax'] = None
                elif line.template.origin_tax:
                    vals['origin_tax'] = template2tax[
                        line.template.origin_tax.id]
                if line.tax:
                    if line.template.tax:
                        if line.tax.id != template2tax[line.template.tax.id]:
                            vals['tax'] = template2tax[line.template.tax.id]
                    else:
                        vals['tax'] = None
                elif line.template.tax:
                    vals['tax'] = template2tax[line.template.tax.id]
                if vals:
                    values.append([line])
                    values.append(vals)
        if values:
            cls.write(*values)


class OpenTaxCode(Wizard):
    'Open Code'
    __name__ = 'account.tax.open_code'
    start_state = 'open_'
    open_ = StateAction('account.act_tax_line_form')

    def do_open_(self, action):
        pool = Pool()
        TaxCode = pool.get('account.tax.code')
        Tax = pool.get('account.tax')
        tax_code = TaxCode(Transaction().context['active_id'])
        if tax_code.lines:
            domain = ['OR'] + [l._line_domain for l in tax_code.lines]
        else:
            domain = ('id', '=', None)
        action['pyson_domain'] = PYSONEncoder().encode([
                Tax._amount_domain(),
                domain,
                ])
        return action, {}


class TestTax(Wizard):
    "Test Tax"
    __name__ = 'account.tax.test'
    start_state = 'test'
    test = StateView(
        'account.tax.test', 'account.tax_test_view_form',
        [Button('Close', 'end', 'tryton-close', default=True)])

    def default_test(self, fields):
        context = Transaction().context
        default = {}
        if context['active_model'] == 'account.tax':
            default['taxes'] = context['active_ids']
        return default


class TestTaxView(ModelView, TaxableMixin):
    "Test Tax"
    __name__ = 'account.tax.test'
    tax_date = fields.Date("Date")
    taxes = fields.One2Many('account.tax', None, "Taxes",
        domain=[
            ('parent', '=', None),
            ])
    unit_price = fields.Numeric("Unit Price")
    quantity = fields.Numeric("Quantity")
    currency = fields.Many2One('currency.currency', 'Currency')
    result = fields.One2Many(
        'account.tax.test.result', None, "Result", readonly=True)

    @classmethod
    def default_tax_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()

    @classmethod
    def default_quantity(cls):
        return 1

    @classmethod
    def default_currency(cls):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = Transaction().context.get('company')
        if company_id:
            company = Company(company_id)
            return company.currency.id

    @property
    def taxable_lines(self):
        return [(self.taxes, self.unit_price, self.quantity)]

    @fields.depends(
        'tax_date', 'taxes', 'unit_price', 'quantity', 'currency', 'result')
    def on_change_with_result(self):
        pool = Pool()
        Result = pool.get('account.tax.test.result')
        result = []
        if all([self.tax_date, self.unit_price, self.quantity, self.currency]):
            for taxline in self._get_taxes():
                del taxline['manual']
                result.append(Result(**taxline))
        self.result = result
        return self._changed_values.get('result', [])


class TestTaxViewResult(ModelView):
    "Test Tax"
    __name__ = 'account.tax.test.result'
    tax = fields.Many2One('account.tax', "Tax")
    description = fields.Char("Description")
    legal_notice = fields.Char("Legal Notice")
    account = fields.Many2One('account.account', "Account")
    base = fields.Numeric("Base")
    amount = fields.Numeric("Amount")
