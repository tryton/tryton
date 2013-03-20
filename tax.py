#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.backend import TableHandler
from trytond.pyson import Eval, If, Bool, PYSONEncoder
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['TaxGroup', 'TaxCodeTemplate', 'TaxCode',
    'OpenChartTaxCodeStart', 'OpenChartTaxCode',
    'TaxTemplate', 'Tax', 'TaxLine', 'TaxRuleTemplate', 'TaxRule',
    'TaxRuleLineTemplate', 'TaxRuleLine',
    'OpenTaxCode',
    'AccountTemplateTaxTemplate', 'AccountTemplate2', 'AccountTax', 'Account2']
__metaclass__ = PoolMeta

KINDS = [
    ('sale', 'Sale'),
    ('purchase', 'Purchase'),
    ('both', 'Both'),
    ]


class TaxGroup(ModelSQL, ModelView):
    'Tax Group'
    __name__ = 'account.tax.group'
    name = fields.Char('Name', size=None, required=True, translate=True)
    code = fields.Char('Code', size=None, required=True)
    kind = fields.Selection(KINDS, 'Kind', required=True)

    @classmethod
    def __register__(cls, module_name):
        super(TaxGroup, cls).__register__(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        # Migration from 1.4 drop code_uniq constraint
        table.drop_constraint('code_uniq')

    @staticmethod
    def default_kind():
        return 'both'


class TaxCodeTemplate(ModelSQL, ModelView):
    'Tax Code Template'
    __name__ = 'account.tax.code.template'
    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code')
    parent = fields.Many2One('account.tax.code.template', 'Parent')
    childs = fields.One2Many('account.tax.code.template', 'parent', 'Children')
    account = fields.Many2One('account.account.template', 'Account Template',
            domain=[('parent', '=', None)], required=True)
    description = fields.Text('Description', translate=True)

    @classmethod
    def __setup__(cls):
        super(TaxCodeTemplate, cls).__setup__()
        cls._order.insert(0, ('code', 'ASC'))
        cls._order.insert(0, ('account', 'ASC'))

    @classmethod
    def validate(cls, templates):
        super(TaxCodeTemplate, cls).validate(templates)
        cls.check_recursion(templates)

    def _get_tax_code_value(self, code=None):
        '''
        Set values for tax code creation.
        '''
        res = {}
        if not code or code.name != self.name:
            res['name'] = self.name
        if not code or code.code != self.code:
            res['code'] = self.code
        if not code or code.description != self.description:
            res['description'] = self.description
        if not code or code.template.id != self.id:
            res['template'] = self.id
        return res

    def create_tax_code(self, company_id, template2tax_code=None,
            parent_id=None):
        '''
        Create recursively tax codes based on template.
        template2tax_code is a dictionary with tax code template id as key and
        tax code id as value, used to convert template id into tax code. The
        dictionary is filled with new tax codes.
        Return the id of the tax code created
        '''
        pool = Pool()
        TaxCode = pool.get('account.tax.code')
        Lang = pool.get('ir.lang')
        Config = pool.get('ir.configuration')

        if template2tax_code is None:
            template2tax_code = {}

        if self.id not in template2tax_code:
            vals = self._get_tax_code_value()
            vals['company'] = company_id
            vals['parent'] = parent_id

            new_tax_code, = TaxCode.create([vals])

            prev_lang = self._context.get('language') or Config.get_language()
            prev_data = {}
            for field_name, field in self._fields.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = getattr(self, field_name)
            for lang in Lang.get_translatable_languages():
                if lang == prev_lang:
                    continue
                with Transaction().set_context(language=lang):
                    template = self.__class__(self.id)
                    data = {}
                    for field_name, field in template._fields.iteritems():
                        if (getattr(field, 'translate', False)
                                and (getattr(template, field_name) !=
                                    prev_data[field_name])):
                            data[field_name] = getattr(template, field_name)
                    if data:
                        TaxCode.write([new_tax_code], data)
            template2tax_code[self.id] = new_tax_code.id
        new_id = template2tax_code[self.id]

        new_childs = []
        for child in self.childs:
            new_childs.append(child.create_tax_code(company_id,
                    template2tax_code=template2tax_code, parent_id=new_id))
        return new_id


class TaxCode(ModelSQL, ModelView):
    'Tax Code'
    __name__ = 'account.tax.code'
    name = fields.Char('Name', size=None, required=True, select=True,
                       translate=True)
    code = fields.Char('Code', size=None, select=True)
    active = fields.Boolean('Active', select=True)
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True)
    parent = fields.Many2One('account.tax.code', 'Parent', select=True,
            domain=[('company', '=', Eval('company', 0))], depends=['company'])
    childs = fields.One2Many('account.tax.code', 'parent', 'Children',
            domain=[('company', '=', Eval('company', 0))], depends=['company'])
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['company']), 'on_change_with_currency_digits')
    sum = fields.Function(fields.Numeric('Sum',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits']),
        'get_sum')
    template = fields.Many2One('account.tax.code.template', 'Template')
    description = fields.Text('Description', translate=True)

    @classmethod
    def __setup__(cls):
        super(TaxCode, cls).__setup__()
        cls._order.insert(0, ('code', 'ASC'))

    @classmethod
    def validate(cls, codes):
        super(TaxCode, cls).validate(codes)
        cls.check_recursion(codes)

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    def on_change_with_currency_digits(self, name=None):
        if self.company:
            return self.company.currency.digits
        return 2

    @classmethod
    def get_sum(cls, codes, name):
        cursor = Transaction().cursor
        res = {}
        pool = Pool()
        MoveLine = pool.get('account.move.line')

        childs = cls.search([
                ('parent', 'child_of', [c.id for c in codes]),
                ])
        all_codes = list(set(codes) | set(childs))
        line_query, _ = MoveLine.query_get()
        cursor.execute('SELECT c.id, SUM(tl.amount) '
            'FROM account_tax_code c, '
                'account_tax_line tl, '
                'account_move_line l '
            'WHERE c.id = tl.code '
                'AND tl.move_line = l.id '
                'AND c.id IN (' +
                    ','.join(('%s',) * len(all_codes)) + ') '
                'AND ' + line_query + ' '
                'AND c.active '
            'GROUP BY c.id', [c.id for c in all_codes])
        code_sum = {}
        for code_id, sum in cursor.fetchall():
            # SQLite uses float for SUM
            if not isinstance(sum, Decimal):
                sum = Decimal(str(sum))
            code_sum[code_id] = sum

        for code in codes:
            res.setdefault(code.id, Decimal('0.0'))
            childs = cls.search([
                    ('parent', 'child_of', [code.id]),
                    ])
            for child in childs:
                res[code.id] += code.company.currency.round(
                    code_sum.get(child.id, Decimal('0.0')))
            res[code.id] = code.company.currency.round(res[code.id])
        return res

    def get_rec_name(self, name):
        if self.code:
            return self.code + ' - ' + self.name
        else:
            return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        codes = cls.search([('code',) + tuple(clause[1:])], limit=1, order=[])
        if codes:
            return [('code',) + tuple(clause[1:])]
        return [('name',) + tuple(clause[1:])]

    @classmethod
    def delete(cls, codes):
        codes = cls.search([
                ('parent', 'child_of', [c.id for c in codes]),
                ])
        super(TaxCode, cls).delete(codes)

    def update_tax_code(self, template2tax_code=None):
        '''
        Update recursively tax code based on template.
        template2tax_code is a dictionary with tax code template id as key and
        tax code id as value, used to convert template id into tax code. The
        dictionary is filled with new tax codes
        '''
        pool = Pool()
        Lang = pool.get('ir.lang')
        Config = pool.get('ir.configuration')

        if template2tax_code is None:
            template2tax_code = {}

        if self.template:
            vals = self.template._get_tax_code_value(code=self)
            if vals:
                self.write([self], vals)

            prev_lang = self._context.get('language') or Config.get_language()
            prev_data = {}
            for field_name, field in self.template._fields.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = getattr(self.template, field_name)
            for lang in Lang.get_translatable_languages():
                if lang == prev_lang:
                    continue
                with Transaction().set_context(language=lang):
                    code = self.__class__(self.id)
                    data = {}
                    for field_name, field in code.template._fields.iteritems():
                        if (getattr(field, 'translate', False)
                                and (getattr(code.template, field_name) !=
                                    prev_data[field_name])):
                            data[field_name] = getattr(code.template,
                                field_name)
                    if data:
                        self.write([code], data)
            template2tax_code[self.template.id] = self.id

        for child in self.childs:
            child.update_tax_code(template2tax_code=template2tax_code)


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
            }, depends=['method'])
    periods = fields.Many2Many('account.period', None, None, 'Periods',
        help='Leave empty for all periods of all open fiscal year',
        states={
            'invisible': Eval('method') != 'periods',
            }, depends=['method'])

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
        if self.start.method == 'fiscalyear':
            action['pyson_context'] = PYSONEncoder().encode({
                    'fiscalyear': self.start.fiscalyear.id,
                    })
            if self.start.fiscalyear:
                action['name'] += ' - %s' % self.start.fiscalyear.rec_name
        else:
            action['pyson_context'] = PYSONEncoder().encode({
                    'periods': [x.id for x in self.start.periods],
                    })
            period_str = ', '.join(p.rec_name for p in self.start.periods)
            if period_str:
                action['name'] += ' (%s)' % period_str
        return action, {}

    def transition_open_(self):
        return 'end'


class TaxTemplate(ModelSQL, ModelView):
    'Account Tax Template'
    __name__ = 'account.tax.template'
    name = fields.Char('Name', required=True, translate=True)
    description = fields.Char('Description', required=True, translate=True)
    group = fields.Many2One('account.tax.group', 'Group')
    sequence = fields.Integer('Sequence',
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s')
    amount = fields.Numeric('Amount', digits=(16, 8))
    percentage = fields.Numeric('Percentage', digits=(16, 8))
    type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed'),
        ('none', 'None'),
        ], 'Type', required=True)
    parent = fields.Many2One('account.tax.template', 'Parent')
    childs = fields.One2Many('account.tax.template', 'parent', 'Children')
    invoice_account = fields.Many2One('account.account.template',
            'Invoice Account')
    credit_note_account = fields.Many2One('account.account.template',
            'Credit Note Account')
    invoice_base_code = fields.Many2One('account.tax.code.template',
            'Invoice Base Code')
    invoice_base_sign = fields.Numeric('Invoice Base Sign', digits=(2, 0))
    invoice_tax_code = fields.Many2One('account.tax.code.template',
            'Invoice Tax Code')
    invoice_tax_sign = fields.Numeric('Invoice Tax Sign', digits=(2, 0))
    credit_note_base_code = fields.Many2One('account.tax.code.template',
            'Credit Note Base Code')
    credit_note_base_sign = fields.Numeric('Credit Note Base Sign',
        digits=(2, 0))
    credit_note_tax_code = fields.Many2One('account.tax.code.template',
            'Credit Note Tax Code')
    credit_note_tax_sign = fields.Numeric('Credit Note Tax Sign',
        digits=(2, 0))
    account = fields.Many2One('account.account.template', 'Account Template',
            domain=[('parent', '=', None)], required=True)

    @classmethod
    def __setup__(cls):
        super(TaxTemplate, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))
        cls._order.insert(0, ('account', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        super(TaxTemplate, cls).__register__(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        # Migration from 1.0 group is no more required
        table.not_null_action('group', action='remove')

        #Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

    @staticmethod
    def default_type():
        return 'percentage'

    @staticmethod
    def default_include_base_amount():
        return False

    @staticmethod
    def default_invoice_base_sign():
        return Decimal('1')

    @staticmethod
    def default_invoice_tax_sign():
        return Decimal('1')

    @staticmethod
    def default_credit_note_base_sign():
        return Decimal('1')

    @staticmethod
    def default_credit_note_tax_sign():
        return Decimal('1')

    def _get_tax_value(self, tax=None):
        '''
        Set values for tax creation.
        '''
        res = {}
        for field in ('name', 'description', 'sequence', 'amount',
                'percentage', 'type', 'invoice_base_sign', 'invoice_tax_sign',
                'credit_note_base_sign', 'credit_note_tax_sign'):
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

    def create_tax(self, company_id, template2tax_code, template2account,
            template2tax=None, parent_id=None):
        '''
        Create recursively taxes based on template.

        template2tax_code is a dictionary with tax code template id as key and
        tax code id as value, used to convert tax code template into tax code.
        template2account is a dictionary with account template id as key and
        account id as value, used to convert account template into account
        code.
        template2tax is a dictionary with tax template id as key and tax id as
        value, used to convert template id into tax.  The dictionary is filled
        with new taxes.
        Return id of the tax created
        '''
        pool = Pool()
        Tax = pool.get('account.tax')
        Lang = pool.get('ir.lang')
        Config = pool.get('ir.configuration')

        if template2tax is None:
            template2tax = {}

        if self.id not in template2tax:
            vals = self._get_tax_value()
            vals['company'] = company_id
            vals['parent'] = parent_id
            if self.invoice_account:
                vals['invoice_account'] = \
                    template2account[self.invoice_account.id]
            else:
                vals['invoice_account'] = None
            if self.credit_note_account:
                vals['credit_note_account'] = \
                    template2account[self.credit_note_account.id]
            else:
                vals['credit_note_account'] = None
            if self.invoice_base_code:
                vals['invoice_base_code'] = \
                    template2tax_code[self.invoice_base_code.id]
            else:
                vals['invoice_base_code'] = None
            if self.invoice_tax_code:
                vals['invoice_tax_code'] = \
                    template2tax_code[self.invoice_tax_code.id]
            else:
                vals['invoice_tax_code'] = None
            if self.credit_note_base_code:
                vals['credit_note_base_code'] = \
                    template2tax_code[self.credit_note_base_code.id]
            else:
                vals['credit_note_base_code'] = None
            if self.credit_note_tax_code:
                vals['credit_note_tax_code'] = \
                    template2tax_code[self.credit_note_tax_code.id]
            else:
                vals['credit_note_tax_code'] = None

            new_tax, = Tax.create([vals])

            prev_lang = self._context.get('language') or Config.get_language()
            prev_data = {}
            for field_name, field in self._fields.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = getattr(self, field_name)
            for lang in Lang.get_translatable_languages():
                if lang == prev_lang:
                    continue
                with Transaction().set_context(language=lang):
                    template = self.__class__(self.id)
                    data = {}
                    for field_name, field in template._fields.iteritems():
                        if (getattr(field, 'translate', False)
                                and (getattr(template, field_name)
                                    != prev_data[field_name])):
                            data[field_name] = getattr(template, field_name)
                    if data:
                        Tax.write([new_tax], data)
            template2tax[self.id] = new_tax.id
        new_id = template2tax[self.id]

        new_childs = []
        for child in self.childs:
            new_childs.append(child.create_tax(company_id, template2tax_code,
                    template2account, template2tax=template2tax,
                    parent_id=new_id))
        return new_id


class Tax(ModelSQL, ModelView):
    '''
    Account Tax

    Type:
        percentage: tax = price * amount
        fixed: tax = amount
        none: tax = none
    '''
    __name__ = 'account.tax'
    name = fields.Char('Name', required=True, translate=True)
    description = fields.Char('Description', required=True, translate=True,
            help="The name that will be used in reports")
    group = fields.Many2One('account.tax.group', 'Group',
            states={
                'invisible': Bool(Eval('parent')),
            }, depends=['parent'])
    active = fields.Boolean('Active')
    sequence = fields.Integer('Sequence',
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s',
        help='Use to order the taxes')
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['company']), 'on_change_with_currency_digits')
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
        states={
            'required': Eval('type') == 'fixed',
            'invisible': Eval('type') != 'fixed',
            }, help='In company\'s currency',
        depends=['type', 'currency_digits'])
    percentage = fields.Numeric('Percentage', digits=(16, 8),
        states={
            'required': Eval('type') == 'percentage',
            'invisible': Eval('type') != 'percentage',
            }, help='In %', depends=['type'])
    type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed'),
        ('none', 'None'),
        ], 'Type', required=True)
    parent = fields.Many2One('account.tax', 'Parent', ondelete='CASCADE')
    childs = fields.One2Many('account.tax', 'parent', 'Children')
    company = fields.Many2One('company.company', 'Company', required=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', 0)),
            ], select=True)
    invoice_account = fields.Many2One('account.account', 'Invoice Account',
        domain=[
            ('company', '=', Eval('company')),
            ('kind', 'not in', ['view', 'receivable', 'payable']),
            ],
        states={
            'readonly': (Eval('type') == 'none') | ~Eval('company'),
            'required': (Eval('type') != 'none') & Eval('company'),
            },
        depends=['company', 'type'])
    credit_note_account = fields.Many2One('account.account',
        'Credit Note Account',
        domain=[
            ('company', '=', Eval('company')),
            ('kind', 'not in', ['view', 'receivable', 'payable']),
            ],
        states={
            'readonly': (Eval('type') == 'none') | ~Eval('company'),
            'required': (Eval('type') != 'none') & Eval('company'),
            },
        depends=['company', 'type'])
    invoice_base_code = fields.Many2One('account.tax.code',
        'Invoice Base Code',
        states={
            'readonly': Eval('type') == 'none',
            }, depends=['type'])
    invoice_base_sign = fields.Numeric('Invoice Base Sign', digits=(2, 0),
        help='Usualy 1 or -1',
        states={
            'required': Eval('type') != 'none',
            'readonly': Eval('type') == 'none',
            }, depends=['type'])
    invoice_tax_code = fields.Many2One('account.tax.code',
        'Invoice Tax Code',
        states={
            'readonly': Eval('type') == 'none',
            }, depends=['type'])
    invoice_tax_sign = fields.Numeric('Invoice Tax Sign', digits=(2, 0),
        help='Usualy 1 or -1',
        states={
            'required': Eval('type') != 'none',
            'readonly': Eval('type') == 'none',
            }, depends=['type'])
    credit_note_base_code = fields.Many2One('account.tax.code',
        'Credit Note Base Code',
        states={
            'readonly': Eval('type') == 'none',
            }, depends=['type'])
    credit_note_base_sign = fields.Numeric('Credit Note Base Sign',
        digits=(2, 0), help='Usualy 1 or -1',
        states={
            'required': Eval('type') != 'none',
            'readonly': Eval('type') == 'none',
            }, depends=['type'])
    credit_note_tax_code = fields.Many2One('account.tax.code',
        'Credit Note Tax Code',
        states={
            'readonly': Eval('type') == 'none',
            }, depends=['type'])
    credit_note_tax_sign = fields.Numeric('Credit Note Tax Sign',
        digits=(2, 0), help='Usualy 1 or -1',
        states={
            'required': Eval('type') != 'none',
            'readonly': Eval('type') == 'none',
            }, depends=['type'])
    template = fields.Many2One('account.tax.template', 'Template')

    @classmethod
    def __setup__(cls):
        super(Tax, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        super(Tax, cls).__register__(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        # Migration from 1.0 group is no more required
        table.not_null_action('group', action='remove')

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_type():
        return 'percentage'

    @staticmethod
    def default_include_base_amount():
        return False

    @staticmethod
    def default_invoice_base_sign():
        return Decimal('1')

    @staticmethod
    def default_invoice_tax_sign():
        return Decimal('1')

    @staticmethod
    def default_credit_note_base_sign():
        return Decimal('1')

    @staticmethod
    def default_credit_note_tax_sign():
        return Decimal('1')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    def on_change_with_currency_digits(self, name=None):
        if self.company:
            return self.company.currency.digits
        return 2

    def _process_tax(self, price_unit):
        if self.type == 'percentage':
            amount = price_unit * self.percentage / Decimal('100')
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

    @classmethod
    def _unit_compute(cls, taxes, price_unit):
        res = []
        for tax in taxes:
            if tax.type != 'none':
                res.append(tax._process_tax(price_unit))
            if len(tax.childs):
                res.extend(cls._unit_compute(tax.childs, price_unit))
        return res

    @classmethod
    def sort_taxes(cls, taxes):
        '''
        Return a list of taxes sorted
        '''
        return sorted(taxes, key=lambda t: (t.sequence, t.id))

    @classmethod
    def compute(cls, taxes, price_unit, quantity):
        '''
        Compute taxes for price_unit and quantity.
        Return list of dict for each taxes and their childs with:
            base
            amount
            tax
        '''
        taxes = cls.sort_taxes(taxes)
        res = cls._unit_compute(taxes, price_unit)
        quantity = Decimal(str(quantity or 0.0))
        for row in res:
            row['base'] *= quantity
            row['amount'] *= quantity
        return res

    def update_tax(self, template2tax_code, template2account,
            template2tax=None):
        '''
        Update recursively taxes based on template.
        template2tax_code is a dictionary with tax code template id as key and
        tax code id as value, used to convert tax code template into tax code.
        template2account is a dictionary with account template id as key and
        account id as value, used to convert account template into account
        code.
        template2tax is a dictionary with tax template id as key and tax id as
        value, used to convert template id into tax.  The dictionary is filled
        with new taxes.
        '''
        pool = Pool()
        Lang = pool.get('ir.lang')
        Config = pool.get('ir.configuration')

        if template2tax is None:
            template2tax = {}

        if self.template:
            vals = self.template._get_tax_value(tax=self)
            if (self.template.invoice_account
                    and self.invoice_account.id != template2account.get(
                        self.template.invoice_account.id)):
                vals['invoice_account'] = template2account.get(
                    self.template.invoice_account.id)
            elif (not self.template.invoice_account
                    and self.invoice_account):
                vals['invoice_account'] = None
            if (self.template.credit_note_account
                    and self.credit_note_account.id != template2account.get(
                        self.template.credit_note_account.id)):
                vals['credit_note_account'] = template2account.get(
                    self.template.credit_note_account.id)
            elif (not self.template.credit_note_account
                    and self.credit_note_account):
                vals['credit_note_account'] = None
            if (self.template.invoice_base_code
                    and self.invoice_base_code.id != template2tax_code.get(
                        self.template.invoice_base_code.id)):
                vals['invoice_base_code'] = template2tax_code.get(
                    self.template.invoice_base_code.id)
            elif (not self.template.invoice_base_code
                    and self.invoice_base_code):
                vals['invoice_base_code'] = None
            if (self.template.invoice_tax_code
                    and self.invoice_tax_code.id != template2tax_code.get(
                        self.template.invoice_tax_code.id)):
                vals['invoice_tax_code'] = template2tax_code.get(
                    self.template.invoice_tax_code.id)
            elif (not self.template.invoice_tax_code
                    and self.invoice_tax_code):
                vals['invoice_tax_code'] = None
            if (self.template.credit_note_base_code
                    and self.credit_note_base_code.id != template2tax_code.get(
                        self.template.credit_note_base_code.id)):
                vals['credit_note_base_code'] = template2tax_code.get(
                    self.template.credit_note_base_code.id)
            elif (not self.template.credit_note_base_code
                    and self.credit_note_base_code):
                vals['credit_note_base_code'] = None
            if (self.template.credit_note_tax_code
                    and self.credit_note_tax_code.id != template2tax_code.get(
                        self.template.credit_note_tax_code.id)):
                vals['credit_note_tax_code'] = template2tax_code.get(
                    self.template.credit_note_tax_code.id)
            elif (not self.template.credit_note_tax_code
                    and self.credit_note_tax_code):
                vals['credit_note_tax_code'] = None

            if vals:
                self.write([self], vals)

            prev_lang = self._context.get('language') or Config.get_language()
            prev_data = {}
            for field_name, field in self.template._fields.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = getattr(self.template, field_name)
            for lang in Lang.get_translatable_languages():
                if lang == prev_lang:
                    continue
                with Transaction().set_context(language=lang):
                    tax = self.__class__(self.id)
                    data = {}
                    for field_name, field in tax.template._fields.iteritems():
                        if (getattr(field, 'translate', False)
                                and (getattr(tax.template, field_name)
                                    != prev_data[field_name])):
                            data[field_name] = getattr(tax.template,
                                field_name)
                    if data:
                        self.write([tax], data)
            template2tax[self.template.id] = self.id

        for child in self.childs:
            child.update_tax(template2tax_code, template2account,
                template2tax=template2tax)


class TaxLine(ModelSQL, ModelView):
    'Tax Line'
    __name__ = 'account.tax.line'
    _rec_name = 'amount'
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['move_line']), 'on_change_with_currency_digits')
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
        required=True, depends=['currency_digits'])
    code = fields.Many2One('account.tax.code', 'Code', select=True,
        required=True)
    tax = fields.Many2One('account.tax', 'Tax', select=True,
        ondelete='RESTRICT', on_change=['tax'])
    move_line = fields.Many2One('account.move.line', 'Move Line',
            required=True, select=True, ondelete='CASCADE')

    def on_change_with_currency_digits(self, name=None):
        if self.move_line:
            return self.move_line.currency_digits
        return 2

    def on_change_tax(self):
        return {
            'code': None,
            }


class TaxRuleTemplate(ModelSQL, ModelView):
    'Tax Rule Template'
    __name__ = 'account.tax.rule.template'
    name = fields.Char('Name', required=True, translate=True)
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

    def create_rule(self, company_id, template2rule=None):
        '''
        Create tax rule based on template.
        template2rule is a dictionary with tax rule template id as key and tax
        rule id as value, used to convert template id into tax rule. The
        dictionary is filled with new tax rules.
        Return id of the tax rule created
        '''
        pool = Pool()
        Rule = pool.get('account.tax.rule')
        Lang = pool.get('ir.lang')
        Config = pool.get('ir.configuration')

        if template2rule is None:
            template2rule = {}

        if self.id not in template2rule:
            vals = self._get_tax_rule_value()
            vals['company'] = company_id
            new_rule, = Rule.create([vals])

            prev_lang = self._context.get('language') or Config.get_language()
            prev_data = {}
            for field_name, field in self._fields.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = getattr(self, field_name)
            for lang in Lang.get_translatable_languages():
                if lang == prev_lang:
                    continue
                with Transaction().set_context(language=lang):
                    template = self.__class__(self.id)
                    data = {}
                    for field_name, field in template._fields.iteritems():
                        if (getattr(field, 'translate', False)
                                and (getattr(self, field_name)
                                    != prev_data[field_name])):
                            data[field_name] = getattr(self, field_name)
                    if data:
                        Rule.write([new_rule], data)
            template2rule[self.id] = new_rule.id
        return template2rule[self.id]


class TaxRule(ModelSQL, ModelView):
    'Tax Rule'
    __name__ = 'account.tax.rule'
    name = fields.Char('Name', required=True, translate=True)
    kind = fields.Selection(KINDS, 'Kind', required=True)
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True, domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', 0)),
            ])
    lines = fields.One2Many('account.tax.rule.line', 'rule', 'Lines')
    template = fields.Many2One('account.tax.rule.template', 'Template')

    @staticmethod
    def default_kind():
        return 'both'

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
                return line.get_taxes()
        return tax and [tax.id] or None

    def update_rule(self, template2rule=None):
        '''
        Update tax rule based on template.
        template2rule is a dictionary with tax rule template id as key and tax
        rule id as value, used to convert template id into tax rule. The
        dictionary is filled with new tax rules.
        '''
        pool = Pool()
        Lang = pool.get('ir.lang')
        Config = pool.get('ir.configuration')

        if template2rule is None:
            template2rule = {}

        if self.template:
            vals = self.template._get_tax_rule_value(rule=self)
            if vals:
                self.write([self], vals)

            prev_lang = self._context.get('language') or Config.get_language()
            prev_data = {}
            for field_name, field in self.template._fields.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = getattr(self.template, field_name)
            for lang in Lang.get_translatable_languages():
                if lang == prev_lang:
                    continue
                with Transaction().set_context(language=lang):
                    rule = self.__class__(self.id)
                    data = {}
                    for field_name, field in rule.template._fields.iteritems():
                        if (getattr(field, 'translate', False)
                                and (getattr(rule.template, field_name)
                                    != prev_data[field_name])):
                            data[field_name] = getattr(rule.template,
                                field_name)
                    if data:
                        self.write([rule], data)
            template2rule[self.template.id] = self.id


class TaxRuleLineTemplate(ModelSQL, ModelView):
    'Tax Rule Line Template'
    __name__ = 'account.tax.rule.line.template'
    rule = fields.Many2One('account.tax.rule.template', 'Rule', required=True,
            ondelete='CASCADE')
    group = fields.Many2One('account.tax.group', 'Tax Group')
    origin_tax = fields.Many2One('account.tax.template', 'Original Tax',
        domain=[
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
        depends=['group'])
    tax = fields.Many2One('account.tax.template', 'Substitution Tax',
        domain=[
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
        depends=['group'])
    sequence = fields.Integer('Sequence',
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s')

    @classmethod
    def __setup__(cls):
        super(TaxRuleLineTemplate, cls).__setup__()
        cls._order.insert(0, ('rule', 'ASC'))
        cls._order.insert(0, ('sequence', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        super(TaxRuleLineTemplate, cls).__register__(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

    def _get_tax_rule_line_value(self, rule_line=None):
        '''
        Set values for tax rule line creation.
        '''
        res = {}
        if not rule_line or rule_line.group != self.group:
            res['group'] = self.group.id if self.group else None
        if not rule_line or rule_line.origin_tax != self.origin_tax:
            res['origin_tax'] = self.origin_tax.id if self.origin_tax else None
        if not rule_line or rule_line.sequence != self.sequence:
            res['sequence'] = self.sequence
        if not rule_line or rule_line.template != self:
            res['template'] = self.id
        return res

    def create_rule_line(self, template2tax, template2rule,
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
        Return id of the tax rule line created
        '''
        RuleLine = Pool().get('account.tax.rule.line')

        if template2rule_line is None:
            template2rule_line = {}

        if self.id not in template2rule_line:
            vals = self._get_tax_rule_line_value()
            vals['rule'] = template2rule[self.rule.id]
            if self.origin_tax:
                vals['origin_tax'] = template2tax[self.origin_tax.id]
            else:
                vals['origin_tax'] = None
            if self.tax:
                vals['tax'] = template2tax[self.tax.id]
            else:
                vals['tax'] = None
            new_rule_line, = RuleLine.create([vals])
            template2rule_line[self.id] = new_rule_line.id
        return template2rule_line[self.id]


class TaxRuleLine(ModelSQL, ModelView):
    'Tax Rule Line'
    __name__ = 'account.tax.rule.line'
    _rec_name = 'tax'
    rule = fields.Many2One('account.tax.rule', 'Rule', required=True,
            select=True, ondelete='CASCADE')
    group = fields.Many2One('account.tax.group', 'Tax Group')
    origin_tax = fields.Many2One('account.tax', 'Original Tax',
        domain=[
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
        depends=['group'])
    tax = fields.Many2One('account.tax', 'Substitution Tax',
        domain=[
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
        depends=['group'])
    sequence = fields.Integer('Sequence',
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s')
    template = fields.Many2One('account.tax.rule.line.template', 'Template')

    @classmethod
    def __setup__(cls):
        super(TaxRuleLine, cls).__setup__()
        cls._order.insert(0, ('rule', 'ASC'))
        cls._order.insert(0, ('sequence', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        super(TaxRuleLine, cls).__register__(module_name)

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

    def match(self, pattern):
        '''
        Match line on pattern
        pattern is a dictonary with rule line field as key and match value as
        value.
        '''
        for field in pattern.keys():
            if field not in self._fields:
                continue
            if not getattr(self, field) and field != 'group':
                continue
            if self._fields[field]._type == 'many2one':
                if ((getattr(self, field).id if getattr(self, field) else None)
                        != pattern[field]):
                    return False
            else:
                if getattr(self, field) != pattern[field]:
                    return False
        return True

    def get_taxes(self):
        '''
        Return list of taxes for a line
        '''
        if self.tax:
            return [self.tax.id]
        return None

    def update_rule_line(self, template2tax, template2rule,
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

        if self.template:
            vals = self.template._get_tax_rule_line_value(rule_line=self)
            if self.rule.id != template2rule[self.template.rule.id]:
                vals['rule'] = template2rule[self.template.rule.id]
            if self.origin_tax:
                if self.template.origin_tax:
                    if self.origin_tax.id != \
                            template2tax[self.template.origin_tax.id]:
                        vals['origin_tax'] = template2tax[
                            self.template.origin_tax.id]
            if self.tax:
                if self.template.tax:
                    if self.tax.id != template2tax[self.template.tax.id]:
                        vals['tax'] = template2tax[self.template.tax.id]
            if vals:
                self.write([self], vals)
            template2rule_line[self.template.id] = self.id


class OpenTaxCode(Wizard):
    'Open Code'
    __name__ = 'account.tax.open_code'
    start_state = 'open_'
    open_ = StateAction('account.act_tax_line_form')

    def do_open_(self, action):
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        Period = pool.get('account.period')

        if not Transaction().context.get('fiscalyear'):
            fiscalyears = FiscalYear.search([
                    ('state', '=', 'open'),
                    ])
        else:
            fiscalyears = [FiscalYear(Transaction().context['fiscalyear'])]

        periods = []
        if not Transaction().context.get('periods'):
            periods = Period.search([
                    ('fiscalyear', 'in', [f.id for f in fiscalyears]),
                    ])
        else:
            periods = Period.browse(Transaction().context['periods'])

        action['pyson_domain'] = PYSONEncoder().encode([
                ('move_line.period', 'in', [p.id for p in periods]),
                ('code', '=', Transaction().context['active_id']),
                ])
        if Transaction().context.get('fiscalyear'):
            action['pyson_context'] = PYSONEncoder().encode({
                    'fiscalyear': Transaction().context['fiscalyear'],
                    })
        else:
            action['pyson_context'] = PYSONEncoder().encode({
                    'periods': [p.id for p in periods],
                    })
        return action, {}


class AccountTemplateTaxTemplate(ModelSQL):
    'Account Template - Tax Template'
    __name__ = 'account.account.template-account.tax.template'
    _table = 'account_account_template_tax_rel'
    account = fields.Many2One('account.account.template', 'Account Template',
            ondelete='CASCADE', select=True, required=True)
    tax = fields.Many2One('account.tax.template', 'Tax Template',
            ondelete='RESTRICT', select=True, required=True)


class AccountTemplate2:
    __name__ = 'account.account.template'
    taxes = fields.Many2Many('account.account.template-account.tax.template',
            'account', 'tax', 'Default Taxes',
            domain=[('parent', '=', None)])


class AccountTax(ModelSQL):
    'Account - Tax'
    __name__ = 'account.account-account.tax'
    _table = 'account_account_tax_rel'
    account = fields.Many2One('account.account', 'Account', ondelete='CASCADE',
            select=True, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            select=True, required=True)


class Account2:
    __name__ = 'account.account'
    taxes = fields.Many2Many('account.account-account.tax',
            'account', 'tax', 'Default Taxes',
            domain=[
                ('company', '=', Eval('company')),
                ('parent', '=', None),
            ],
            help=('Default tax for manual encoding of move lines \n'
                'for journal types: "expense" and "revenue"'),
            depends=['company'])
