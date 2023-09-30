# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from xml.sax.saxutils import quoteattr

from simpleeval import InvalidExpression, simple_eval

from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, ModelSQL, ModelView, fields, sequence_ordered)
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.tools import decistmt
from trytond.transaction import Transaction
from trytond.wizard import (
    Button, StateAction, StateTransition, StateView, Wizard)

from .exceptions import (
    MoveTemplateExpressionError, MoveTemplateKeywordValidationError,
    PeriodNotFoundError)


class MoveTemplate(DeactivableMixin, ModelSQL, ModelView):
    'Account Move Template'
    __name__ = 'account.move.template'
    name = fields.Char('Name', required=True, translate=True)
    keywords = fields.One2Many('account.move.template.keyword', 'move',
        'Keywords')
    company = fields.Many2One('company.company', 'Company', required=True)
    journal = fields.Many2One(
        'account.journal', 'Journal', required=True,
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    description = fields.Char('Description',
        help="Keyword value substitutions are identified "
        "by braces ('{' and '}').")
    lines = fields.One2Many('account.move.line.template', 'move', 'Lines',
        domain=[
            ('account.company', '=', Eval('company', -1)),
            ])

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    def get_move(self, values):
        'Return the move for the keyword values'
        pool = Pool()
        Move = pool.get('account.move')
        Keyword = pool.get('account.move.template.keyword')

        move = Move()
        move.company = self.company
        move.journal = self.journal
        if self.description:
            move.description = self.description.format(
                **dict(Keyword.format_values(self, values)))
        move.lines = [l.get_line(values) for l in self.lines]

        return move


class MoveTemplateKeyword(sequence_ordered(), ModelSQL, ModelView):
    'Account Move Template Keyword'
    __name__ = 'account.move.template.keyword'
    name = fields.Char('Name', required=True)
    string = fields.Char('String', required=True, translate=True)
    move = fields.Many2One(
        'account.move.template', "Move", required=True, ondelete='CASCADE')
    type_ = fields.Selection([
            ('char', 'Char'),
            ('numeric', 'Numeric'),
            ('date', 'Date'),
            ('party', 'Party'),
            ], 'Type')
    required = fields.Boolean('Required')
    digits = fields.Integer('Digits', states={
            'invisible': Eval('type_') != 'numeric',
            'required': Eval('type_') == 'numeric',
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('move')

    @classmethod
    def validate(cls, keywords):
        for keyword in keywords:
            keyword.check_name()

    def check_name(self):
        if self.name and not self.name.isidentifier():
            raise MoveTemplateKeywordValidationError(
                gettext('account.msg_name_not_valid',
                    name=self.name))

    @staticmethod
    def default_required():
        return False

    def get_field(self):
        field = getattr(self, '_get_field_%s' % self.type_)()
        field.update({
                'name': self.name,
                'string': self.string,
                'required': self.required,
                'help': '',
                })
        return field

    def _get_field_char(self):
        return {'type': 'char'}

    def _get_field_numeric(self):
        return {'type': 'numeric', 'digits': (16, self.digits)}

    def _format_numeric(self, lang, value):
        if value:
            return lang.format('%.*f', (self.digits, value), True)
        else:
            return ''

    def _get_field_date(self):
        return {'type': 'date'}

    def _format_date(self, lang, value):
        if value:
            return lang.strftime(value)
        else:
            return ''

    def _get_field_party(self):
        return {
            'type': 'many2one',
            'relation': 'party.party',
            }

    def _format_party(self, lang, value):
        pool = Pool()
        Party = pool.get('party.party')
        if value:
            return Party(value).rec_name
        else:
            return ''

    @staticmethod
    def format_values(template, values):
        "Yield key and formatted value"
        pool = Pool()
        Lang = pool.get('ir.lang')

        lang, = Lang.search([
                ('code', '=', Transaction().language),
                ])
        keywords = {k.name: k for k in template.keywords}

        for k, v in values.items():
            keyword = keywords[k]
            func = getattr(keyword, '_format_%s' % keyword.type_, None)
            if func:
                yield k, func(lang, v)
            else:
                yield k, v


class MoveLineTemplate(ModelSQL, ModelView):
    'Account Move Line Template'
    __name__ = 'account.move.line.template'
    move = fields.Many2One(
        'account.move.template', "Move", required=True, ondelete='CASCADE')
    operation = fields.Selection([
            ('debit', 'Debit'),
            ('credit', 'Credit'),
            ], 'Operation', required=True)
    amount = fields.Char('Amount', required=True,
        help="A python expression that will be evaluated with the keywords.")
    account = fields.Many2One('account.account', 'Account', required=True,
        domain=[
            ('type', '!=', None),
            ('closed', '!=', True),
            ('company', '=', Eval('_parent_move', {}).get('company', -1)),
            ])
    party = fields.Char('Party',
        states={
            'required': Eval('party_required', False),
            'invisible': ~Eval('party_required', False),
            },
        help="The name of the 'Party' keyword.")
    party_required = fields.Function(fields.Boolean('Party Required'),
        'on_change_with_party_required')
    description = fields.Char('Description',
        help="Keyword value substitutions are identified "
        "by braces ('{' and '}').")
    taxes = fields.One2Many('account.tax.line.template', 'line', 'Taxes')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('move')

    @fields.depends('account')
    def on_change_with_party_required(self, name=None):
        if self.account:
            return self.account.party_required
        return False

    def get_line(self, values):
        'Return the move line for the keyword values'
        pool = Pool()
        Line = pool.get('account.move.line')
        Keyword = pool.get('account.move.template.keyword')

        line = Line()
        try:
            amount = simple_eval(decistmt(self.amount),
                functions={'Decimal': Decimal}, names=values)
        except (InvalidExpression, SyntaxError) as e:
            raise MoveTemplateExpressionError(
                gettext('account.msg_move_template_invalid_expression',
                    expression=values,
                    template=self.move.rec_name,
                    error=e)) from e

        if not isinstance(amount, Decimal):
            raise MoveTemplateExpressionError(
                gettext('account.msg_move_template_expression_not_number',
                    value=amount,
                    expression=self.move.name,
                    template=self.move.rec_name))

        amount = self.move.company.currency.round(amount)
        if self.operation == 'debit':
            line.debit = amount
        else:
            line.credit = amount
        line.account = self.account
        if self.party:
            line.party = values.get(self.party)
        if self.description:
            try:
                line.description = self.description.format(
                    **dict(Keyword.format_values(self.move, values)))
            except KeyError as e:
                raise MoveTemplateExpressionError(
                    gettext('account.msg_move_template_invalid_expression',
                        expression=values,
                        template=self.move.name,
                        error=e)) from e
        line.tax_lines = [t.get_line(values) for t in self.taxes]

        return line


class TaxLineTemplate(ModelSQL, ModelView):
    'Account Tax Line Template'
    __name__ = 'account.tax.line.template'
    line = fields.Many2One(
        'account.move.line.template', "Line",
        required=True, ondelete='CASCADE')
    amount = fields.Char('Amount', required=True,
        help="A python expression that will be evaluated with the keywords.")
    type = fields.Selection([
            ('tax', "Tax"),
            ('base', "Base"),
            ], "Type", required=True)

    tax = fields.Many2One('account.tax', 'Tax',
        domain=[
            ('company', '=', Eval('_parent_line', {}
                    ).get('_parent_move', {}).get('company', -1)),
            ],
        depends={'line'})

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('line')

    def get_line(self, values):
        'Return the tax line for the keyword values'
        pool = Pool()
        TaxLine = pool.get('account.tax.line')

        line = TaxLine()
        try:
            amount = simple_eval(decistmt(self.amount),
                functions={'Decimal': Decimal}, names=values)
        except (InvalidExpression, SyntaxError) as e:
            raise MoveTemplateExpressionError(
                gettext('account.msg_template_invalid_expression',
                    expression=values,
                    template=self.line.rec_name,
                    error=e)) from e

        if not isinstance(amount, Decimal):
            raise MoveTemplateExpressionError(
                gettext('account.msg_not_number',
                    result=amount,
                    expression=self.move.rec_name))
        amount = self.line.move.company.currency.round(amount)
        line.amount = amount
        line.type = self.type
        line.tax = self.tax
        return line


class KeywordStateView(StateView):

    def get_view(self, wizard, state_name):
        fields = {}
        view = {
            'model': 'account.move.template.create.keywords',
            'view_id': 0,
            'type': 'form',
            'fields': fields,
            }
        if not hasattr(wizard.template, 'template'):
            return view
        template = wizard.template.template
        field_template = ('<label name=%(name)s/>'
            '<field name=%(name)s/>')
        view['arch'] = ('<?xml version="1.0"?>'
            '<form col="2" string=%s>%s</form>' % (
                quoteattr(template.name),
                ''.join(field_template % {'name': quoteattr(keyword.name)}
                    for keyword in template.keywords)
                ))
        for keyword in template.keywords:
            fields[keyword.name] = keyword.get_field()
        return view

    def get_defaults(self, wizard, state_name, fields):
        return {}


class CreateMove(Wizard):
    'Create Move from Template'
    __name__ = 'account.move.template.create'
    start = StateTransition()
    template = StateView('account.move.template.create.template',
        'account.move_template_create_template_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'keywords', 'tryton-forward', default=True),
            ])
    keywords = KeywordStateView('account.move.template.create.keywords',
        None, [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'create_', 'tryton-ok', default=True),
            ])
    create_ = StateTransition()
    open_ = StateAction('account.act_move_from_template')

    def create_move(self):
        template = self.template.template
        values = {}
        for keyword in template.keywords:
            values[keyword.name] = getattr(self.keywords, keyword.name, None)
        move = template.get_move(values)
        move.date = self.template.date
        move.period = self.template.period
        move.save()
        return move

    def transition_start(self):
        context = Transaction().context
        action_id = context.get('action_id')
        period = context.get('period')
        if self.model and self.model.__name__ == 'account.move.line':
            # Template id is used as action
            self.template.template = action_id
            self.template.period = period
            return 'keywords'
        else:
            return 'template'

    def transition_create_(self):
        if self.model and self.model.__name__ == 'account.move.line':
            self.create_move()
            return 'end'
        else:
            return 'open_'

    def do_open_(self, action):
        move = self.create_move()
        return action, {'res_id': move.id}

    def end(self):
        if self.model and self.model.__name__ == 'account.move.line':
            return 'reload'


class CreateMoveTemplate(ModelView):
    'Create Move from Template'
    __name__ = 'account.move.template.create.template'
    template = fields.Many2One('account.move.template', 'Template',
        required=True,
        domain=[
            ('company', '=', Eval('context', {}).get('company', -1)),
            ])
    date = fields.Date('Effective Date', required=True)
    period = fields.Many2One('account.period', 'Period', required=True,
        domain=[
            ('state', '!=', 'closed'),
            ('fiscalyear.company.id', '=',
                Eval('context', {}).get('company', 0)),
            ])

    @classmethod
    def default_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()

    @classmethod
    def default_period(cls):
        pool = Pool()
        Period = pool.get('account.period')
        company = Transaction().context.get('company')
        try:
            period = Period.find(company)
        except PeriodNotFoundError:
            return None
        return period.id

    @fields.depends('date', 'period')
    def on_change_date(self):
        pool = Pool()
        Period = pool.get('account.period')
        company = Transaction().context.get('company')
        if self.date:
            if (not self.period
                or not (
                    self.period.start_date <= self.date
                    <= self.period.end_date)):
                try:
                    self.period = Period.find(company, date=self.date)
                except PeriodNotFoundError:
                    pass

    @fields.depends('period', 'date')
    def on_change_period(self):
        pool = Pool()
        Date = pool.get('ir.date')
        today = Date.today()
        if self.period:
            start_date = self.period.start_date
            end_date = self.period.end_date
            if (not self.date
                    or not (start_date <= self.date <= end_date)):
                if start_date <= today:
                    if today <= end_date:
                        self.date = today
                    else:
                        self.date = end_date
                else:
                    self.date = start_date


class CreateMoveKeywords(ModelView):
    'Create Move from Template'
    __no_slots__ = True
    __name__ = 'account.move.template.create.keywords'
