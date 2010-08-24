#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from __future__ import with_statement
from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
from trytond.backend import TableHandler
from trytond.pyson import Eval, Not, Equal, If, In, Bool, Get, Or, And, \
        PYSONEncoder
from trytond.transaction import Transaction
from trytond.cache import Cache


class Group(ModelSQL, ModelView):
    'Tax Group'
    _name = 'account.tax.group'
    _description = __doc__

    name = fields.Char('Name', size=None, required=True, translate=True)
    code = fields.Char('Code', size=None, required=True)

    def init(self, module_name):
        super(Group, self).init(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, self, module_name)

        # Migration from 1.4 drop code_uniq constraint
        table.drop_constraint('code_uniq')

Group()


class CodeTemplate(ModelSQL, ModelView):
    'Tax Code Template'
    _name = 'account.tax.code.template'
    _description = __doc__

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code')
    parent = fields.Many2One('account.tax.code.template', 'Parent')
    childs = fields.One2Many('account.tax.code.template', 'parent', 'Children')
    account = fields.Many2One('account.account.template', 'Account Template',
            domain=[('parent', '=', False)], required=True)
    description = fields.Text('Description', translate=True)

    def __init__(self):
        super(CodeTemplate, self).__init__()
        self._constraints += [
            ('check_recursion', 'recursive_tax_code'),
        ]
        self._error_messages.update({
            'recursive_tax_code': 'You can not create recursive tax codes!',
        })
        self._order.insert(0, ('code', 'ASC'))
        self._order.insert(0, ('account', 'ASC'))

    def _get_tax_code_value(self, template, code=None):
        '''
        Set values for tax code creation.

        :param template: the BrowseRecord of the template
        :param code: the BrowseRecord of the code to update
        :return: a dictionary with tax code fields as key and values as value
        '''
        res = {}
        if not code or code.name != template.name:
            res['name'] = template.name
        if not code or code.code != template.code:
            res['code'] = template.code
        if not code or code.description != template.description:
            res['description'] = template.description
        if not code or code.template.id != template.id:
            res['template'] = template.id
        return res

    def create_tax_code(self, template, company_id, template2tax_code=None,
            parent_id=False):
        '''
        Create recursively tax codes based on template.

        :param template: the template id or the BrowseRecord of template
                used for tax code creation
        :param company_id: the id of the company for which tax codes are
                created
        :param template2tax_code: a dictionary with tax code template id as key
                and tax code id as value, used to convert template id into
                tax code. The dictionary is filled with new tax codes
        :param parent_id: the tax code id of the parent of the tax codes that
                must be created
        :return: id of the tax code created
        '''
        tax_code_obj = self.pool.get('account.tax.code')
        lang_obj = self.pool.get('ir.lang')

        if template2tax_code is None:
            template2tax_code = {}

        if isinstance(template, (int, long)):
            template = self.browse(template)

        if template.id not in template2tax_code:
            vals = self._get_tax_code_value(template)
            vals['company'] = company_id
            vals['parent'] = parent_id

            new_id = tax_code_obj.create(vals)

            prev_lang = template._context.get('language') or 'en_US'
            prev_data = {}
            for field_name, field in template._columns.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = template[field_name]
            for lang in lang_obj.get_translatable_languages():
                if lang == prev_lang:
                    continue
                template.setLang(lang)
                data = {}
                for field_name, field in template._columns.iteritems():
                    if getattr(field, 'translate', False) \
                            and template[field_name] != prev_data[field_name]:
                        data[field_name] = template[field_name]
                if data:
                    with Transaction().set_context(language=lang):
                        tax_code_obj.write(new_id, data)
            template.setLang(prev_lang)
            template2tax_code[template.id] = new_id
        else:
            new_id = template2tax_code[template.id]

        new_childs = []
        for child in template.childs:
            new_childs.append(self.create_tax_code(child, company_id,
                template2tax_code=template2tax_code, parent_id=new_id))
        return new_id

CodeTemplate()


class Code(ModelSQL, ModelView):
    'Tax Code'
    _name = 'account.tax.code'
    _description = __doc__

    name = fields.Char('Name', size=None, required=True, select=1,
                       translate=True)
    code = fields.Char('Code', size=None, select=1)
    active = fields.Boolean('Active', select=2)
    company = fields.Many2One('company.company', 'Company', required=True)
    parent = fields.Many2One('account.tax.code', 'Parent', select=1,
            domain=[('company', '=', Eval('company', 0))], depends=['company'])
    childs = fields.One2Many('account.tax.code', 'parent', 'Children',
            domain=[('company', '=', Eval('company', 0))], depends=['company'])
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['company']), 'get_currency_digits')
    sum = fields.Function(fields.Numeric('Sum',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits']),
        'get_sum')
    template = fields.Many2One('account.tax.code.template', 'Template')
    description = fields.Text('Description', translate=True)

    def __init__(self):
        super(Code, self).__init__()
        self._constraints += [
            ('check_recursion', 'recursive_tax_code'),
        ]
        self._error_messages.update({
            'recursive_tax_code': 'You can not create recursive tax codes!',
        })
        self._order.insert(0, ('code', 'ASC'))

    def default_active(self):
        return True

    def default_company(self):
        return Transaction().context.get('company') or False

    def on_change_with_currency_digits(self, vals):
        company_obj = self.pool.get('company.company')
        if vals.get('company'):
            company = company_obj.browse(vals['company'])
            return company.currency.digits
        return 2

    def get_currency_digits(self, ids, name):
        res = {}
        for code in self.browse(ids):
            res[code.id] = code.company.currency.digits
        return res

    def get_sum(self, ids, name):
        cursor = Transaction().cursor
        res = {}
        move_line_obj = self.pool.get('account.move.line')
        currency_obj = self.pool.get('currency.currency')

        child_ids = self.search([('parent', 'child_of', ids)])
        all_ids = {}.fromkeys(ids + child_ids).keys()
        line_query, _ = move_line_obj.query_get()
        cursor.execute('SELECT c.id, ' \
                    'SUM(tl.amount) ' \
                'FROM account_tax_code c, ' \
                    'account_tax_line tl, ' \
                    'account_move_line l ' \
                'WHERE c.id = tl.code ' \
                    'AND tl.move_line = l.id ' \
                    'AND c.id IN (' + \
                        ','.join(('%s',) * len(all_ids))+ ') ' \
                    'AND ' + line_query + ' ' \
                    'AND c.active ' \
                'GROUP BY c.id', all_ids)
        code_sum = {}
        for code_id, sum in cursor.fetchall():
            # SQLite uses float for SUM
            if not isinstance(sum, Decimal):
                sum = Decimal(str(sum))
            code_sum[code_id] = sum

        for code in self.browse(ids):
            res.setdefault(code.id, Decimal('0.0'))
            child_ids = self.search([
                ('parent', 'child_of', [code.id]),
                ])
            for child_id in child_ids:
                res[code.id] += currency_obj.round(code.company.currency,
                        code_sum.get(child_id, Decimal('0.0')))
            res[code.id] = currency_obj.round(code.company.currency,
                    res[code.id])
        return res

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}
        for code in self.browse(ids):
            if code.code:
                res[code.id] = code.code + ' - ' + code.name
            else:
                res[code.id] = code.name
        return res

    def search_rec_name(self, name, clause):
        ids = self.search([('code',) + clause[1:]], limit=1, order=[])
        if ids:
            return [('code',) + clause[1:]]
        return [('name',) + clause[1:]]

    def delete(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        code_ids = self.search([
            ('parent', 'child_of', ids),
            ])
        return super(Code, self).delete(code_ids)

    def update_tax_code(self, code, template2tax_code=None):
        '''
        Update recursively tax code based on template.

        :param code: a code id or the BrowseRecord of the code
        :param template2tax_code: a dictionary with tax code template id as key
                and tax code id as value, used to convert template id into
                tax code. The dictionary is filled with new tax codes
        '''
        template_obj = self.pool.get('account.tax.code.template')
        lang_obj = self.pool.get('ir.lang')

        if template2tax_code is None:
            template2tax_code = {}

        if isinstance(code, (int, long)):
            code = self.browse(code)

        if code.template:
            vals = template_obj._get_tax_code_value(code.template, code=code)
            if vals:
                self.write(code.id, vals)

            prev_lang = code._context.get('language') or 'en_US'
            prev_data = {}
            for field_name, field in code.template._columns.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = code.template[field_name]
            for lang in lang_obj.get_translatable_languages():
                if lang == prev_lang:
                    continue
                code.setLang(lang)
                data = {}
                for field_name, field in code.template._columns.iteritems():
                    if (getattr(field, 'translate', False)
                            and code.template[field_name] !=
                            prev_data[field_name]):
                        data[field_name] = code.template[field_name]
                if data:
                    with Transaction().set_context(language=lang):
                        self.write(code.id, data)
            code.setLang(prev_lang)
            template2tax_code[code.template.id] = code.id

        for child in code.childs:
            self.update_tax_code(child, template2tax_code=template2tax_code)

Code()


class OpenChartCodeInit(ModelView):
    'Open Chart Code Init'
    _name = 'account.tax.open_chart_code.init'
    _description = __doc__
    method = fields.Selection([
        ('fiscalyear', 'By Fiscal Year'),
        ('periods', 'By Periods'),
        ], 'Method', required=True)
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            help='Leave empty for all open fiscal year',
            states={
                'invisible': Not(Equal(Eval('method'), 'fiscalyear')),
            }, depends=['method'])
    periods = fields.Many2Many('account.period', None, None, 'Periods',
            help='Leave empty for all periods of all open fiscal year',
            states={
                'invisible': Not(Equal(Eval('method'), 'periods')),
            }, depends=['method'])

    def default_method(self):
        return 'periods'

OpenChartCodeInit()


class OpenChartCode(Wizard):
    'Open Chart Of Tax Code by Fiscal Year'
    _name = 'account.tax.open_chart_code'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'account.tax.open_chart_code.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('open', 'Open', 'tryton-ok', True),
                ],
            },
        },
        'open': {
            'result': {
                'type': 'action',
                'action': '_action_open_chart',
                'state': 'end',
            },
        },
    }

    def _action_open_chart(self, data):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')
        act_window_id = model_data_obj.get_id('account', 'act_tax_code_tree2')
        res = act_window_obj.read(act_window_id)
        if data['form']['method'] == 'fiscalyear':
            res['pyson_context'] = PYSONEncoder().encode({
                'fiscalyear': data['form']['fiscalyear'],
            })
        else:
            res['pyson_context'] = PYSONEncoder().encode({
                'periods': data['form']['periods'][0][1],
            })
        return res

OpenChartCode()


class TaxTemplate(ModelSQL, ModelView):
    'Account Tax Template'
    _name = 'account.tax.template'
    _description = __doc__

    name = fields.Char('Name', required=True, translate=True)
    description = fields.Char('Description', required=True, translate=True)
    group = fields.Many2One('account.tax.group', 'Group')
    sequence = fields.Integer('Sequence')
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
    credit_note_base_sign = fields.Numeric('Credit Note Base Sign', digits=(2, 0))
    credit_note_tax_code = fields.Many2One('account.tax.code.template',
            'Credit Note Tax Code')
    credit_note_tax_sign = fields.Numeric('Credit Note Tax Sign', digits=(2, 0))
    account = fields.Many2One('account.account.template', 'Account Template',
            domain=[('parent', '=', False)], required=True)

    def __init__(self):
        super(TaxTemplate, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))
        self._order.insert(0, ('account', 'ASC'))

    def init(self, module_name):
        super(TaxTemplate, self).init(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, self, module_name)

        # Migration from 1.0 group is no more required
        table.not_null_action('group', action='remove')

    def default_type(self):
        return 'percentage'

    def default_include_base_amount(self):
        return False

    def default_invoice_base_sign(self):
        return Decimal('1')

    def default_invoice_tax_sign(self):
        return Decimal('1')

    def default_credit_note_base_sign(self):
        return Decimal('1')

    def default_credit_note_tax_sign(self):
        return Decimal('1')

    def _get_tax_value(self, template, tax=None):
        '''
        Set values for tax creation.

        :param template: the BrowseRecord of the template
        :param tax: the BrowseRecord of the tax to update
        :return: a dictionary with account fields as key and values as value
        '''
        res = {}
        for field in ('name', 'description', 'sequence', 'amount',
                'percentage', 'type', 'invoice_base_sign', 'invoice_tax_sign',
                'credit_note_base_sign', 'credit_note_tax_sign'):
            if not tax or tax[field] != template[field]:
                res[field] = template[field]
        for field in ('group',):
            if not tax or tax[field].id != template[field].id:
                res[field] = template[field].id
        if not tax or tax.template.id != template.id:
            res['template'] = template.id
        return res

    def create_tax(self, template, company_id, template2tax_code,
            template2account, template2tax=None, parent_id=False):
        '''
        Create recursively taxes based on template.

        :param template: the template id or the BrowseRecord of template
                used for tax creation
        :param company_id: the id of the company for which taxes are created
        :param template2tax_code: a dictionary with tax code template id as key
                and tax code id as value, used to convert tax code template into
                tax code
        :param template2account: a dictionary with account template id as key
                and account id as value, used to convert account template into
                account code
        :param template2tax: a dictionary with tax template id as key and
                tax id as value, used to convert template id into tax.
                The dictionary is filled with new taxes
        :param parent_id: the tax id of the parent of the tax that must be
                created
        :return: id of the tax created
        '''
        tax_obj = self.pool.get('account.tax')
        lang_obj = self.pool.get('ir.lang')

        if template2tax is None:
            template2tax = {}

        if isinstance(template, (int, long)):
            template = self.browse(template)

        if template.id not in template2tax:
            vals = self._get_tax_value(template)
            vals['company'] = company_id
            vals['parent'] = parent_id
            if template.invoice_account:
                vals['invoice_account'] = \
                        template2account[template.invoice_account.id]
            else:
                vals['invoice_account'] =  False
            if template.credit_note_account:
                vals['credit_note_account'] = \
                        template2account[template.credit_note_account.id]
            else:
                vals['credit_note_account'] = False
            if template.invoice_base_code:
                vals['invoice_base_code'] = \
                        template2tax_code[template.invoice_base_code.id]
            else:
                vals['invoice_base_code'] = False
            if template.invoice_tax_code:
                vals['invoice_tax_code'] = \
                        template2tax_code[template.invoice_tax_code.id]
            else:
                vals['invoice_tax_code'] = False
            if template.credit_note_base_code:
                vals['credit_note_base_code'] = \
                        template2tax_code[template.credit_note_base_code.id]
            else:
                vals['credit_note_base_code'] = False
            if template.credit_note_tax_code:
                vals['credit_note_tax_code'] = \
                        template2tax_code[template.credit_note_tax_code.id]
            else:
                vals['credit_note_tax_code'] = False

            new_id = tax_obj.create(vals)

            prev_lang = template._context.get('language') or 'en_US'
            prev_data = {}
            for field_name, field in template._columns.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = template[field_name]
            for lang in lang_obj.get_translatable_languages():
                if lang == prev_lang:
                    continue
                template.setLang(lang)
                data = {}
                for field_name, field in template._columns.iteritems():
                    if getattr(field, 'translate', False) \
                            and template[field_name] != prev_data[field_name]:
                        data[field_name] = template[field_name]
                if data:
                    with Transaction().set_context(language=lang):
                        tax_obj.write(new_id, data)
            template.setLang(prev_lang)
            template2tax[template.id] = new_id
        else:
            new_id = template2tax[template.id]

        new_childs = []
        for child in template.childs:
            new_childs.append(self.create_tax(child, company_id,
                template2tax_code, template2account, template2tax=template2tax,
                parent_id=new_id))
        return new_id

TaxTemplate()


class Tax(ModelSQL, ModelView):
    '''
    Account Tax

    Type:
        percentage: tax = price * amount
        fixed: tax = amount
        none: tax = none
    '''
    _name = 'account.tax'
    _description = 'Account Tax'

    name = fields.Char('Name', required=True, translate=True)
    description = fields.Char('Description', required=True, translate=True,
            help="The name that will be used in reports")
    group = fields.Many2One('account.tax.group', 'Group',
            states={
                'invisible': Bool(Eval('parent')),
            }, depends=['parent'])
    active = fields.Boolean('Active')
    sequence = fields.Integer('Sequence',
            help='Use to order the taxes')
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['company']), 'get_currency_digits')
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
            states={
                'invisible': Not(Equal(Eval('type'), 'fixed')),
            }, help='In company\'s currency', depends=['type', 'currency_digits'])
    percentage = fields.Numeric('Percentage', digits=(16, 8),
            states={
                'invisible': Not(Equal(Eval('type'), 'percentage')),
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
                ('id', If(In('company', Eval('context', {})), '=', '!='),
                    Get(Eval('context', {}), 'company', 0)),
            ])
    invoice_account = fields.Many2One('account.account', 'Invoice Account',
            domain=[
                ('company', '=', Eval('company')),
                ('kind', '!=', 'view'),
            ],
            states={
                'readonly': Or(Equal(Eval('type'), 'none'),
                    Not(Bool(Eval('company')))),
                'required': And(Not(Equal(Eval('type'), 'none')),
                    Bool(Eval('company'))),
            }, depends=['company'])
    credit_note_account = fields.Many2One('account.account', 'Credit Note Account',
            domain=[
                ('company', '=', Eval('company')),
                ('kind', '!=', 'view'),
            ],
            states={
                'readonly': Or(Equal(Eval('type'), 'none'),
                    Not(Bool(Eval('company')))),
                'required': And(Not(Equal(Eval('type'), 'none')),
                    Bool(Eval('company'))),
            }, depends=['company', 'type'])

    invoice_base_code = fields.Many2One('account.tax.code',
            'Invoice Base Code',
            states={
                'readonly': Equal(Eval('type'), 'none'),
            }, depends=['type'])
    invoice_base_sign = fields.Numeric('Invoice Base Sign', digits=(2, 0),
            help='Usualy 1 or -1',
            states={
                'readonly': Equal(Eval('type'), 'none'),
            }, depends=['type'])
    invoice_tax_code = fields.Many2One('account.tax.code',
            'Invoice Tax Code',
            states={
                'readonly': Equal(Eval('type'), 'none'),
            }, depends=['type'])
    invoice_tax_sign = fields.Numeric('Invoice Tax Sign', digits=(2, 0),
            help='Usualy 1 or -1',
            states={
                'readonly': Equal(Eval('type'), 'none'),
            }, depends=['type'])
    credit_note_base_code = fields.Many2One('account.tax.code',
            'Credit Note Base Code',
            states={
                'readonly': Equal(Eval('type'), 'none'),
            }, depends=['type'])
    credit_note_base_sign = fields.Numeric('Credit Note Base Sign', digits=(2, 0),
            help='Usualy 1 or -1',
            states={
                'readonly': Equal(Eval('type'), 'none'),
            }, depends=['type'])
    credit_note_tax_code = fields.Many2One('account.tax.code',
            'Credit Note Tax Code',
            states={
                'readonly': Equal(Eval('type'), 'none'),
            }, depends=['type'])
    credit_note_tax_sign = fields.Numeric('Credit Note Tax Sign', digits=(2, 0),
            help='Usualy 1 or -1',
            states={
                'readonly': Equal(Eval('type'), 'none'),
            }, depends=['type'])
    template = fields.Many2One('account.tax.template', 'Template')

    def __init__(self):
        super(Tax, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def init(self, module_name):
        super(Tax, self).init(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, self, module_name)

        # Migration from 1.0 group is no more required
        table.not_null_action('group', action='remove')

    def default_active(self):
        return True

    def default_type(self):
        return 'percentage'

    def default_include_base_amount(self):
        return False

    def default_invoice_base_sign(self):
        return Decimal('1')

    def default_invoice_tax_sign(self):
        return Decimal('1')

    def default_credit_note_base_sign(self):
        return Decimal('1')

    def default_credit_note_tax_sign(self):
        return Decimal('1')

    def default_company(self):
        return Transaction().context.get('company') or False

    def on_change_with_currency_digits(self, vals):
        company_obj = self.pool.get('company.company')
        if vals.get('company'):
            company = company_obj.browse(vals['company'])
            return company.currency.digits
        return 2

    def get_currency_digits(self, ids, name):
        res = {}
        for tax in self.browse(ids):
            res[tax.id] = tax.company.currency.digits
        return res

    def _process_tax(self, tax, price_unit):
        if tax.type == 'percentage':
            amount = price_unit * tax.percentage / Decimal('100')
            return {
                'base': price_unit,
                'amount': amount,
                'tax': tax,
            }
        if tax.type == 'fixed':
            amount = tax.amount
            return {
                'base': price_unit,
                'amount': amount,
                'tax': tax,
            }

    def _unit_compute(self, taxes, price_unit):
        res = []
        for tax in taxes:
            if tax.type != 'none':
                res.append(self._process_tax(tax, price_unit))
            if len(tax.childs):
                res.extend(self._unit_compute(tax.childs, price_unit))
        return res

    def delete(self, ids):
        # Restart the cache
        self.sort_taxes.reset()
        return super(Tax, self).delete(ids)

    def create(self, vals):
        # Restart the cache
        self.sort_taxes.reset()
        return super(Tax, self).create(vals)

    def write(self, ids, vals):
        # Restart the cache
        self.sort_taxes.reset()
        return super(Tax, self).write(ids, vals)

    @Cache('account_tax.sort_taxes')
    def sort_taxes(self, ids):
        '''
        Return a list of taxe ids sorted

        :param ids: a list of tax ids
        :return: a list of tax ids sorted
        '''
        return self.search([
            ('id', 'in', ids),
            ], order=[('sequence', 'ASC'), ('id', 'ASC')])

    def compute(self, ids, price_unit, quantity):
        '''
        Compute taxes for price_unit and quantity.
        Return list of dict for each taxes and their childs with:
            base
            amount
            tax
        '''
        ids = self.sort_taxes(ids)
        taxes = self.browse(ids)
        res = self._unit_compute(taxes, price_unit)
        quantity = Decimal(str(quantity or 0.0))
        for row in res:
            row['base'] *= quantity
            row['amount'] *= quantity
        return res

    def update_tax(self, tax, template2tax_code, template2account,
            template2tax=None):
        '''
        Update recursively taxes based on template.

        :param tax: a tax id or the BrowseRecord of the tax
        :param template2tax_code: a dictionary with tax code template id as key
                and tax code id as value, used to convert tax code template into
                tax code
        :param template2account: a dictionary with account template id as key
                and account id as value, used to convert account template into
                account code
        :param template2tax: a dictionary with tax template id as key and
                tax id as value, used to convert template id into tax.
                The dictionary is filled with new taxes
        '''
        template_obj = self.pool.get('account.tax.template')
        lang_obj = self.pool.get('ir.lang')

        if template2tax is None:
            template2tax = {}

        if isinstance(tax, (int, long)):
            tax = self.browse(tax)

        if tax.template:
            vals = template_obj._get_tax_value(tax.template, tax=tax)
            if tax.template.invoice_account \
                    and tax.invoice_account.id != \
                    template2account.get(tax.template.invoice_account.id,
                            False):
                vals['invoice_account'] = \
                        template2account.get(tax.template.invoice_account.id,
                                False)
            elif not tax.template.invoice_account \
                    and tax.invoice_account:
                vals['invoice_account'] =  False
            if tax.template.credit_note_account \
                    and tax.credit_note_account.id != \
                    template2account.get(tax.template.credit_note_account.id,
                            False):
                vals['credit_note_account'] = \
                        template2account.get(tax.template.credit_note_account.id,
                                False)
            elif not tax.template.credit_note_account \
                    and tax.credit_note_account:
                vals['credit_note_account'] = False
            if tax.template.invoice_base_code \
                    and tax.invoice_base_code.id != \
                    template2tax_code.get(tax.template.invoice_base_code.id,
                            False):
                vals['invoice_base_code'] = \
                        template2tax_code.get(tax.template.invoice_base_code.id,
                                False)
            elif not tax.template.invoice_base_code \
                    and tax.invoice_base_code:
                vals['invoice_base_code'] = False
            if tax.template.invoice_tax_code \
                    and tax.invoice_tax_code.id != \
                    template2tax_code.get(tax.template.invoice_tax_code.id,
                            False):
                vals['invoice_tax_code'] = \
                        template2tax_code.get(tax.template.invoice_tax_code.id,
                                False)
            elif not tax.template.invoice_tax_code \
                    and tax.invoice_tax_code:
                vals['invoice_tax_code'] = False
            if tax.template.credit_note_base_code \
                    and tax.credit_note_base_code.id != \
                    template2tax_code.get(tax.template.credit_note_base_code.id,
                            False):
                vals['credit_note_base_code'] = \
                        template2tax_code.get(tax.template.credit_note_base_code.id,
                                False)
            elif not tax.template.credit_note_base_code \
                    and tax.credit_note_base_code:
                vals['credit_note_base_code'] = False
            if tax.template.credit_note_tax_code \
                    and tax.credit_note_tax_code.id != \
                    template2tax_code.get(tax.template.credit_note_tax_code.id,
                            False):
                vals['credit_note_tax_code'] = \
                        template2tax_code.get(tax.template.credit_note_tax_code.id,
                                False)
            elif not tax.template.credit_note_tax_code \
                    and tax.credit_note_tax_code:
                vals['credit_note_tax_code'] = False

            if vals:
                self.write(tax.id, vals)

            prev_lang = tax._context.get('language') or 'en_US'
            prev_data = {}
            for field_name, field in tax.template._columns.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = tax.template[field_name]
            for lang in lang_obj.get_translatable_languages():
                if lang == prev_lang:
                    continue
                tax.setLang(lang)
                data = {}
                for field_name, field in tax.template._columns.iteritems():
                    if (getattr(field, 'translate', False)
                            and tax.template[field_name] !=
                            prev_data[field_name]):
                        data[field_name] = tax.template[field_name]
                if data:
                    with Transaction().set_context(language=lang):
                        self.write(tax.id, data)
            tax.setLang(prev_lang)
            template2tax[tax.template.id] = tax.id

        for child in tax.childs:
            self.update_tax(child, template2tax_code, template2account,
                    template2tax=template2tax)

Tax()


class Line(ModelSQL, ModelView):
    'Tax Line'
    _name = 'account.tax.line'
    _description = __doc__
    _rec_name = 'amount'

    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['move_line']), 'get_currency_digits')
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits'])
    code = fields.Many2One('account.tax.code', 'Code', select=1, required=True)
    tax = fields.Many2One('account.tax', 'Tax', select=1, ondelete='RESTRICT',
            on_change=['tax'])
    move_line = fields.Many2One('account.move.line', 'Move Line',
            required=True, select=1, ondelete='CASCADE')

    def on_change_with_currency_digits(self, vals):
        move_line_obj = self.pool.get('account.move.line')
        if vals.get('move_line'):
            move_line = move_line_obj.browse(vals['move_line'])
            return move_line.currency_digits
        return 2

    def get_currency_digits(self, ids, name):
        res = {}
        for line in self.browse(ids):
            res[line.id] = line.move_line.currency_digits
        return res

    def on_change_tax(self, vals):
        res = {
            'code': False,
            }
        return res

Line()


class RuleTemplate(ModelSQL, ModelView):
    'Tax Rule Template'
    _name = 'account.tax.rule.template'
    _description = __doc__
    name = fields.Char('Name', required=True, translate=True)
    lines = fields.One2Many('account.tax.rule.line.template', 'rule', 'Lines')
    account = fields.Many2One('account.account.template', 'Account Template',
            domain=[('parent', '=', False)], required=True)

    def _get_tax_rule_value(self, template, rule=None):
        '''
        Set values for tax rule creation.

        :param template: the BrowseRecord of the template
        :param rule: the BrowseRecord of the rule to update
        :return: a dictionary with rule fields as key and values as value
        '''
        res = {}
        if not rule or rule.name != template.name:
            res['name'] = template.name
        if not rule or rule.template.id != template.id:
            res['template'] = template.id
        return res

    def create_rule(self, template, company_id, template2rule=None):
        '''
        Create tax rule based on template.

        :param template: the template id or the BrowseRecord of template
                used for tax rule creation
        :param company_id: the id of the company for which tax rules are
                created
        :param template2rule: a dictionary with tax rule template id as key
                and tax rule id as value, used to convert template id into
                tax rule. The dictionary is filled with new tax rules
        :return: id of the tax rule created
        '''
        rule_obj = self.pool.get('account.tax.rule')
        lang_obj = self.pool.get('ir.lang')

        if template2rule is None:
            template2rule = {}

        if isinstance(template, (int, long)):
            template = self.browse(template)

        if template.id not in template2rule:
            vals = self._get_tax_rule_value(template)
            vals['company'] = company_id
            new_id = rule_obj.create(vals)

            prev_lang = template._context.get('language') or 'en_US'
            prev_data = {}
            for field_name, field in template._columns.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = template[field_name]
            for lang in lang_obj.get_translatable_languages():
                if lang == prev_lang:
                    continue
                template.setLang(lang)
                data = {}
                for field_name, field in template._columns.iteritems():
                    if getattr(field, 'translate', False) \
                            and template[field_name] != prev_data[field_name]:
                        data[field_name] = template[field_name]
                if data:
                    with Transaction().set_context(language=lang):
                        rule_obj.write(new_id, data)
            template.setLang(prev_lang)
            template2rule[template.id] = new_id
        else:
            new_id = template2rule[template.id]
        return new_id

RuleTemplate()


class Rule(ModelSQL, ModelView):
    'Tax Rule'
    _name = 'account.tax.rule'
    _description = __doc__
    name = fields.Char('Name', required=True, translate=True)
    company = fields.Many2One('company.company', 'Company', required=True,
            select=1, domain=[
                ('id', If(In('company', Eval('context', {})), '=', '!='),
                    Get(Eval('context', {}), 'company', 0)),
            ])
    lines = fields.One2Many('account.tax.rule.line', 'rule', 'Lines')
    template = fields.Many2One('account.tax.rule.template', 'Template')

    def apply(self, rule, tax, pattern):
        '''
        Apply rule on tax

        :param rule: a rule id or the BrowseRecord of the rule
        :param tax: a tax id or the BrowseRecord of the tax
        :param pattern: a dictonary with rule line field as key
                and match value as value
        :return: a list of the tax id to use or False
        '''
        tax_obj = self.pool.get('account.tax')
        rule_line_obj = self.pool.get('account.tax.rule.line')

        if isinstance(rule, (int, long)) and rule:
            rule = self.browse(rule)

        if isinstance(tax, (int, long)) and tax:
            tax = tax_obj.browse(tax)

        pattern = pattern.copy()
        pattern['group'] = tax and tax.group.id or False
        pattern['origin_tax'] = tax and tax.id or False

        for line in rule.lines:
            if rule_line_obj.match(line, pattern):
                return rule_line_obj.get_taxes(line)
        return tax and [tax.id] or False

    def update_rule(self, rule, template2rule=None):
        '''
        Update tax rule based on template.

        :param rule: a rule id or the BrowseRecord of the rule
        :param template2rule: a dictionary with tax rule template id as key
                and tax rule id as value, used to convert template id into
                tax rule. The dictionary is filled with new tax rules
        '''
        template_obj = self.pool.get('account.tax.rule.template')
        lang_obj = self.pool.get('ir.lang')

        if template2rule is None:
            template2rule = {}

        if isinstance(rule, (int, long)):
            rule = self.browse(rule)

        if rule.template:
            vals = template_obj._get_tax_rule_value(rule.template, rule=rule)
            if vals:
                self.write(rule.id, vals)

            prev_lang = rule._context.get('language') or 'en_US'
            prev_data = {}
            for field_name, field in rule.template._columns.iteritems():
                if getattr(field, 'translate', False):
                    prev_data[field_name] = rule.template[field_name]
            for lang in lang_obj.get_translatable_languages():
                if lang == prev_lang:
                    continue
                rule.setLang(lang)
                data = {}
                for field_name, field in rule.template._columns.iteritems():
                    if (getattr(field, 'translate', False)
                            and rule.template[field_name] !=
                            prev_data[field_name]):
                        data[field_name] = rule.template[field_name]
                if data:
                    with Transaction().set_context(language=lang):
                        self.write(rule.id, data)
            rule.setLang(prev_lang)
            template2rule[rule.template.id] = rule.id

Rule()


class RuleLineTemplate(ModelSQL, ModelView):
    'Tax Rule Line Template'
    _name = 'account.tax.rule.line.template'
    _description = __doc__
    rule = fields.Many2One('account.tax.rule.template', 'Rule', required=True,
            ondelete='CASCADE')
    group = fields.Many2One('account.tax.group', 'Tax Group')
    origin_tax = fields.Many2One('account.tax.template', 'Original Tax',
            domain=[
                ('account', '=', Get(Eval('_parent_rule', {}), 'account')),
                ('group', '=', Eval('group'))
            ],
            help='If the original tax template is filled, the rule will be ' \
                    'applied only for this tax template.')
    tax = fields.Many2One('account.tax.template', 'Substitution Tax',
            domain=[
                ('account', '=', Get(Eval('_parent_rule', {}), 'account')),
                ('group', '=', Eval('group')),
            ])
    sequence = fields.Integer('Sequence')

    def __init__(self):
        super(RuleLineTemplate, self).__init__()
        self._order.insert(0, ('rule', 'ASC'))
        self._order.insert(0, ('sequence', 'ASC'))

    def _get_tax_rule_line_value(self, template, rule_line=None):
        '''
        Set values for tax rule line creation.

        :param template: the BrowseRecord of the template
        :param rule_line: the BrowseRecord of the rule line to update
        :return: a dictionary with rule line fields as key and values as value
        '''
        res = {}
        if not rule_line or rule_line.group.id != template.group.id:
            res['group'] = template.group.id
        if not rule_line or rule_line.origin_tax.id != template.origin_tax.id:
            res['origin_tax'] = template.origin_tax.id
        if not rule_line or rule_line.sequence != template.sequence:
            res['sequence'] = template.sequence
        if not rule_line or rule_line.template.id != template.id:
            res['template'] = template.id
        return res

    def create_rule_line(self, template, template2tax, template2rule,
            template2rule_line=None):
        '''
        Create tax rule line based on template.

        :param template: the template id or the BrowseRecord of template
                used for tax rule line creation
        :param template2tax: a dictionary with tax template id as key
                and tax id as value, used to convert template id into
                tax.
        :param template2rule: a dictionary with tax rule template id as key
                and tax rule id as value, used to convert template id into
                tax rule.
        :param template2rule_line: a dictionary with tax rule line template id
                as key and tax rule line id as value, used to convert template
                id into tax rule line. The dictionary is filled with new
                tax rule lines
        :return: id of the tax rule line created
        '''
        rule_line_obj = self.pool.get('account.tax.rule.line')

        if template2rule_line is None:
            template2rule_line = {}

        if isinstance(template, (int, long)):
            template = self.browse(template)

        if template.id not in template2rule_line:
            vals = self._get_tax_rule_line_value(template)
            vals['rule'] = template2rule[template.rule.id]
            if template.origin_tax:
                vals['origin_tax'] = template2tax[template.origin_tax.id]
            else:
                vals['origin_tax'] = False
            if template.tax:
                vals['tax'] = template2tax[template.tax.id]
            else:
                vals['tax'] = False
            new_id = rule_line_obj.create(vals)
            template2rule_line[template.id] = new_id
        else:
            new_id = template2rule_line[template.id]
        return new_id

RuleLineTemplate()


class RuleLine(ModelSQL, ModelView):
    'Tax Rule Line'
    _name = 'account.tax.rule.line'
    _description = __doc__
    _rec_name = 'tax'
    rule = fields.Many2One('account.tax.rule', 'Rule', required=True,
            select=1, ondelete='CASCADE')
    group = fields.Many2One('account.tax.group', 'Tax Group')
    origin_tax = fields.Many2One('account.tax', 'Original Tax',
            domain=[
                ('company', '=', Get(Eval('_parent_rule', {}), 'company')),
                ('group', '=', Eval('group')),
            ],
            help='If the original tax is filled, the rule will be applied ' \
                    'only for this tax.')
    tax = fields.Many2One('account.tax', 'Substitution Tax',
            domain=[
                ('company', '=', Get(Eval('_parent_rule', {}), 'company')),
                ('group', '=', Eval('group')),
            ])
    sequence = fields.Integer('Sequence')
    template = fields.Many2One('account.tax.rule.line.template', 'Template')

    def __init__(self):
        super(RuleLine, self).__init__()
        self._order.insert(0, ('rule', 'ASC'))
        self._order.insert(0, ('sequence', 'ASC'))

    def match(self, line, pattern):
        '''
        Match line on pattern

        :param line: a BrowseRecord of rule line
        :param pattern: a dictonary with rule line field as key
                and match value as value
        :return: a boolean
        '''
        res = True
        for field in pattern.keys():
            if field not in self._columns:
                continue
            if not line[field] and field != 'group':
                continue
            if self._columns[field]._type == 'many2one':
                if line[field].id != pattern[field]:
                    res = False
                    break
            else:
                if line[field] != pattern[field]:
                    res = False
                    break
        return res

    def get_taxes(self, line):
        '''
        Return list of taxes for a line

        :param line: a BrowseRecord of rule line
        :return: a list of tax id
        '''
        if line.tax:
            return [line.tax.id]
        return False

    def update_rule_line(self, rule_line, template2tax, template2rule,
            template2rule_line=None):
        '''
        Update tax rule line based on template.

        :param rule_line: a rule line id or the BrowseRecord of the rule line
        :param template2tax: a dictionary with tax template id as key
                and tax id as value, used to convert template id into
                tax.
        :param template2rule: a dictionary with tax rule template id as key
                and tax rule id as value, used to convert template id into
                tax rule.
        :param template2rule_line: a dictionary with tax rule line template id
                as key and tax rule line id as value, used to convert template
                id into tax rule line. The dictionary is filled with new
                tax rule lines
        '''
        template_obj = self.pool.get('account.tax.rule.line.template')

        if template2rule_line is None:
            template2rule_line = {}

        if isinstance(rule_line, (int, long)):
            rule_line = self.browse(rule_line)

        if rule_line.template:
            vals = template_obj._get_tax_rule_line_value(rule_line.template,
                    rule_line=rule_line)
            if rule_line.rule.id != template2rule[rule_line.template.rule.id]:
                vals['rule'] = template2rule[rule_line.template.rule.id]
            if rule_line.origin_tax:
                if rule_line.template.origin_tax:
                    if rule_line.origin_tax.id != \
                            template2tax[rule_line.template.origin_tax.id]:
                        vals['origin_tax'] = template2tax[
                            rule_line.template.origin_tax.id]
            if rule_line.tax:
                if rule_line.template.tax:
                    if rule_line.tax.id != \
                            template2tax[rule_line.template.tax.id]:
                        vals['tax'] = template2tax[rule_line.template.tax.id]
            if vals:
                self.write(rule_line.id, vals)
            template2rule_line[rule_line.template.id] = rule_line.id

RuleLine()


class OpenCode(Wizard):
    'Open Code'
    _name = 'account.tax.open_code'
    states = {
        'init': {
            'result': {
                'type': 'action',
                'action': '_action_open_code',
                'state': 'end',
            },
        },
    }

    def _action_open_code(self, data):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        period_obj = self.pool.get('account.period')

        if not Transaction().context.get('fiscalyear'):
            fiscalyear_ids = fiscalyear_obj.search([
                ('state', '=', 'open'),
                ])
        else:
            fiscalyear_ids = [Transaction().context['fiscalyear']]

        period_ids = []
        if not Transaction().context.get('periods'):
            period_ids = period_obj.search([
                ('fiscalyear', 'in', fiscalyear_ids),
                ])
        else:
            period_ids = Transaction().context['periods']

        act_window_id = model_data_obj.get_id('account', 'act_tax_line_form')
        res = act_window_obj.read(act_window_id)
        res['pyson_domain'] = PYSONEncoder().encode([
            ('move_line.period', 'in', period_ids),
            ('code', '=', data['id']),
            ])
        if Transaction().context.get('fiscalyear'):
            res['pyson_context'] = PYSONEncoder().encode({
                'fiscalyear': Transaction().context['fiscalyear'],
            })
        else:
            res['pyson_context'] = PYSONEncoder().encode({
                'periods': period_ids,
            })
        return res

OpenCode()


class AccountTemplateTaxTemplate(ModelSQL):
    'Account Template - Tax Template'
    _name = 'account.account.template-account.tax.template'
    _table = 'account_account_template_tax_rel'
    _description = __doc__
    account = fields.Many2One('account.account.template', 'Account Template',
            ondelete='CASCADE', select=1, required=True)
    tax = fields.Many2One('account.tax.template', 'Tax Template',
            ondelete='RESTRICT', select=1, required=True)

AccountTemplateTaxTemplate()


class AccountTemplate(ModelSQL, ModelView):
    _name = 'account.account.template'
    taxes = fields.Many2Many('account.account.template-account.tax.template',
            'account', 'tax', 'Default Taxes',
            domain=[('parent', '=', False)])

AccountTemplate()


class AccountTax(ModelSQL):
    'Account - Tax'
    _name = 'account.account-account.tax'
    _table = 'account_account_tax_rel'
    _description = __doc__
    account = fields.Many2One('account.account', 'Account', ondelete='CASCADE',
            select=1, required=True)
    tax = fields.Many2One('account.tax', 'Tax', ondelete='RESTRICT',
            select=1, required=True)

AccountTax()


class Account(ModelSQL, ModelView):
    _name = 'account.account'
    taxes = fields.Many2Many('account.account-account.tax',
            'account', 'tax', 'Default Taxes',
            domain=[
                ('company', '=', Eval('company')),
                ('parent', '=', False),
            ],
            help='Default tax for manual encoding of move lines \n' \
                    'for journal types: "expense" and "revenue"',
            depends=['company'])

Account()
