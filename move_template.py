# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from xml.sax.saxutils import quoteattr
from decimal import Decimal

from simpleeval import simple_eval

from trytond import backend
from trytond.model import (
    ModelSQL, ModelView, DeactivableMixin, fields, sequence_ordered)
from trytond.pyson import Eval
from trytond.wizard import (Wizard, StateView, StateAction, StateTransition,
    Button)
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.tools import decistmt

__all__ = ['MoveTemplate', 'MoveTemplateKeyword',
    'MoveLineTemplate', 'TaxLineTemplate',
    'CreateMove', 'CreateMoveTemplate', 'CreateMoveKeywords']


class MoveTemplate(DeactivableMixin, ModelSQL, ModelView):
    'Account Move Template'
    __name__ = 'account.move.template'
    name = fields.Char('Name', required=True, translate=True)
    keywords = fields.One2Many('account.move.template.keyword', 'move',
        'Keywords')
    company = fields.Many2One('company.company', 'Company', required=True)
    journal = fields.Many2One('account.journal', 'Journal', required=True)
    date = fields.Char('Date', help='Leave empty for today.')
    description = fields.Char('Description',
        help="Keyword values substitutions are identified "
        "by braces ('{' and '}').")
    lines = fields.One2Many('account.move.line.template', 'move', 'Lines',
        domain=[
            ('account.company', '=', Eval('company', -1)),
            ],
        depends=['company'])

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
        if self.date:
            move.date = values.get(self.date)
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
    move = fields.Many2One('account.move.template', 'Move', required=True)
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
            }, depends=['type_'])

    @staticmethod
    def default_required():
        return False

    def get_field(self):
        field = getattr(self, '_get_field_%s' % self.type_)()
        field.update({
                'name': self.name,
                'string': self.string,
                'required': self.required,
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

        for k, v in values.iteritems():
            keyword = keywords[k]
            func = getattr(keyword, '_format_%s' % keyword.type_, None)
            if func:
                yield k, func(lang, v)
            else:
                yield k, v


class MoveLineTemplate(ModelSQL, ModelView):
    'Account Move Line Template'
    __name__ = 'account.move.line.template'
    move = fields.Many2One('account.move.template', 'Move', required=True)
    operation = fields.Selection([
            ('debit', 'Debit'),
            ('credit', 'Credit'),
            ], 'Operation', required=True)
    amount = fields.Char('Amount', required=True,
        help="A python expression that will be evaluated with the keywords.")
    account = fields.Many2One('account.account', 'Account', required=True,
        domain=[
            ('kind', '!=', 'view'),
            ('company', '=', Eval('_parent_move', {}).get('company', -1)),
            ])
    party = fields.Char('Party',
        states={
            'required': Eval('party_required', False),
            'invisible': ~Eval('party_required', False),
            },
        depends=['party_required'],
        help="The name of the 'Party' keyword.")
    party_required = fields.Function(fields.Boolean('Party Required'),
        'on_change_with_party_required')
    description = fields.Char('Description',
        help="Keywords values substitutions are identified "
        "by braces ('{' and '}').")
    taxes = fields.One2Many('account.tax.line.template', 'line', 'Taxes')

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
        amount = simple_eval(decistmt(self.amount),
            functions={'Decimal': Decimal}, names=values)
        amount = self.move.company.currency.round(amount)
        if self.operation == 'debit':
            line.debit = amount
        else:
            line.credit = amount
        line.account = self.account
        if self.party:
            line.party = values.get(self.party)
        if self.description:
            line.description = self.description.format(
                **dict(Keyword.format_values(self.move, values)))
        line.tax_lines = [t.get_line(values) for t in self.taxes]

        return line


class TaxLineTemplate(ModelSQL, ModelView):
    'Account Tax Line Template'
    __name__ = 'account.tax.line.template'
    line = fields.Many2One('account.move.line.template', 'Line', required=True)
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
            ])

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')

        super(TaxLineTemplate, cls).__register__(module_name)

        table_h = TableHandler(cls, module_name)

        # Migration from 4.6: remove code
        table_h.drop_column('code')

    def get_line(self, values):
        'Return the tax line for the keyword values'
        pool = Pool()
        TaxLine = pool.get('account.tax.line')

        line = TaxLine()
        amount = simple_eval(decistmt(self.amount),
            functions={'Decimal': Decimal}, names=values)
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
            Button('Next', 'keywords', 'tryton-go-next', default=True),
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
        move.period = self.template.period
        move.save()
        return move

    def transition_start(self):
        context = Transaction().context
        model = context.get('active_model')
        action_id = context.get('action_id')
        period = context.get('period')
        if model == 'account.move.line':
            # Template id is used as action
            self.template.template = action_id
            self.template.period = period
            return 'keywords'
        else:
            return 'template'

    def transition_create_(self):
        model = Transaction().context.get('active_model')
        if model == 'account.move.line':
            self.create_move()
            return 'end'
        else:
            return 'open_'

    def do_open_(self, action):
        move = self.create_move()
        action['res_id'] = [move.id]
        return action, {}

    def end(self):
        model = Transaction().context.get('active_model')
        if model == 'account.move.line':
            return 'reload'


class CreateMoveTemplate(ModelView):
    'Create Move from Template'
    __name__ = 'account.move.template.create.template'
    template = fields.Many2One('account.move.template', 'Template',
        required=True,
        domain=[
            ('company', '=', Eval('context', {}).get('company', -1)),
            ])
    period = fields.Many2One('account.period', 'Period', required=True,
        domain=[
            ('state', '!=', 'close'),
            ('fiscalyear.company.id', '=',
                Eval('context', {}).get('company', 0)),
            ])

    @staticmethod
    def default_period():
        pool = Pool()
        Period = pool.get('account.period')
        company = Transaction().context.get('company')
        return Period.find(company, exception=False)


class CreateMoveKeywords(ModelView):
    'Create Move from Template'
    __name__ = 'account.move.template.create.keywords'
