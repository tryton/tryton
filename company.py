#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import copy
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, Button, StateTransition
from trytond.report import Report
from trytond.pyson import Eval, If
from trytond.transaction import Transaction
from trytond.pool import Pool


class Company(ModelSQL, ModelView):
    'Company'
    _name = 'company.company'
    _description = __doc__
    _inherits = {'party.party': 'party'}

    party = fields.Many2One('party.party', 'Party', required=True,
            ondelete='CASCADE')
    parent = fields.Many2One('company.company', 'Parent')
    childs = fields.One2Many('company.company', 'parent', 'Children')
    header = fields.Text('Header')
    footer = fields.Text('Footer')
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    employees = fields.One2Many('company.employee', 'company', 'Employees')

    def __init__(self):
        super(Company, self).__init__()
        self._constraints += [
            ('check_recursion', 'recursive_companies'),
        ]
        self._error_messages.update({
            'recursive_companies': 'You can not create recursive companies!',
        })

    def copy(self, ids, default=None):
        party_obj = Pool().get('party.party')

        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]
        if default is None:
            default = {}
        default = default.copy()
        new_ids = []
        for company in self.browse(ids):
            default['party'] = party_obj.copy(company.party.id)
            new_id = super(Company, self).copy(company.id, default=default)
            new_ids.append(new_id)

        if int_id:
            return new_ids[0]
        return new_ids

    def write(self, ids, vals):
        res = super(Company, self).write(ids, vals)
        # Restart the cache on the domain_get method
        Pool().get('ir.rule').domain_get.reset()
        return res

Company()


class Employee(ModelSQL, ModelView):
    'Employee'
    _name = 'company.employee'
    _description = __doc__
    _inherits = {'party.party': 'party'}

    party = fields.Many2One('party.party', 'Party', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)

Employee()


class UserEmployee(ModelSQL):
    'User - Employee'
    _name = 'res.user-company.employee'
    _description = __doc__
    user = fields.Many2One('res.user', 'User', ondelete='CASCADE', select=True,
        required=True)
    employee = fields.Many2One('company.employee', 'Employee',
        ondelete='CASCADE', select=True, required=True)

UserEmployee()


class User(ModelSQL, ModelView):
    _name = 'res.user'
    main_company = fields.Many2One('company.company', 'Main Company',
        on_change=['main_company'])
    company = fields.Many2One('company.company', 'Current Company',
        domain=[('parent', 'child_of', [Eval('main_company')], 'parent')],
        depends=['main_company'], on_change=['company', 'employees'])
    companies = fields.Function(fields.One2Many('company.company', None,
        'Current Companies'), 'get_companies')
    employees = fields.Many2Many('res.user-company.employee', 'user',
        'employee', 'Employees')
    employee = fields.Many2One('company.employee', 'Employee',
        domain=[
            ('company', '=', Eval('company')),
            ('id', 'in', Eval('employees', [])),
            ],
        depends=['company', 'employees'])

    def __init__(self):
        super(User, self).__init__()
        self._context_fields.insert(0, 'company')
        self._context_fields.insert(0, 'employee')

    def default_main_company(self):
        return Transaction().context.get('company')

    def default_company(self):
        return self.default_main_company()

    def get_companies(self, ids, name):
        company_obj = Pool().get('company.company')
        res = {}
        company_childs = {}
        for user in self.browse(ids):
            res[user.id] = []
            company_id = None
            if user.company:
                company_id = user.company.id
            elif user.main_company:
                company_id = user.main_company.id
            if company_id:
                if company_id in company_childs:
                    company_ids = company_childs[company_id]
                else:
                    company_ids = company_obj.search([
                        ('parent', 'child_of', [company_id]),
                        ])
                    company_childs[company_id] = company_ids
                if company_ids:
                    res[user.id].extend(company_ids)
        return res

    def get_status_bar(self, ids, name):
        res = super(User, self).get_status_bar(ids, name)
        for user in self.browse(ids):
            if user.company:
                res[user.id] += ' - %s [%s]' % (user.company.name,
                    user.company.currency.name)
        return res

    def on_change_main_company(self, vals):
        return {
            'company': vals.get('main_company'),
            'employee': None,
            }

    def on_change_company(self, values):
        employee_obj = Pool().get('company.employee')
        result = {
            'employee': None,
            }
        if values.get('company') and values.get('employees'):
            employee_ids = employee_obj.search([
                    ('id', 'in', [e['id'] for e in values['employees']]),
                    ('company', '=', values['company']),
                    ])
            if employee_ids:
                result['employee'] = employee_ids[0]
        return result

    def _get_preferences(self, user, context_only=False):
        res = super(User, self)._get_preferences(user,
                context_only=context_only)
        if not context_only:
            res['main_company'] = user.main_company.id
            if user.main_company.id:
                res['main_company.rec_name'] = user.main_company.rec_name
            res['employees'] = [e.id for e in user.employees]
        if user.employee:
            res['employee'] = user.employee.id
            if user.employee.id:
                res['employee.rec_name'] = user.employee.rec_name
        return res

    def get_preferences_fields_view(self):
        pool = Pool()
        company_obj = pool.get('company.company')

        res = super(User, self).get_preferences_fields_view()
        res = copy.deepcopy(res)

        def convert2selection(definition, name):
            del definition[name]['relation']
            definition[name]['type'] = 'selection'
            selection = []
            definition[name]['selection'] = selection
            return selection

        if 'company' in res['fields']:
            selection = convert2selection(res['fields'], 'company')
            user = self.browse(Transaction().user)
            company_ids = company_obj.search([
                    ('parent', 'child_of', [user.main_company.id], 'parent'),
                    ])
            for company in company_obj.browse(company_ids):
                selection.append((company.id, company.rec_name))
        return res

    def read(self, ids, fields_names=None):
        company_obj = Pool().get('company.company')
        user_id = Transaction().user
        if user_id == 0 and 'user' in Transaction().context:
            user_id = Transaction().context['user']
        result = super(User, self).read(ids, fields_names=fields_names)
        if (fields_names
                and 'company' in fields_names
                and 'company' in Transaction().context):
            values = None
            if isinstance(ids, (int, long)):
                if int(user_id) == ids:
                    values = result
            else:
                if int(user_id) in ids:
                    for vals in result:
                        if vals['id'] == int(user_id):
                            values = vals
                            break
            if values:
                main_company_id = values.get('main_company')
                if not main_company_id:
                    main_company_id = self.read(user_id,
                        ['main_company'])['main_company']
                companies = company_obj.search([
                    ('parent', 'child_of', [main_company_id]),
                ])
                company_id = Transaction().context['company']
                if ((company_id and company_id in companies)
                        or not company_id):
                    values['company'] = company_id
        return result

User()


class Property(ModelSQL, ModelView):
    _name = 'ir.property'
    company = fields.Many2One('company.company', 'Company',
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', 0)),
            ])

    def _set_values(self, model, res_id, val, field_id):
        user_obj = Pool().get('res.user')
        user_id = Transaction().user
        if user_id == 0:
            user_id = Transaction().context.get('user', user_id)
        user = user_obj.browse(user_id)
        res = super(Property, self)._set_values(model, res_id, val, field_id)
        if user:
            res['company'] = user.company.id
        return res

    def search(self, domain, offset=0, limit=None, order=None, count=False):
        if Transaction().user == 0 and not 'user' in Transaction().context:
            domain = ['AND', domain[:], ('company', '=', None)]
        return super(Property, self).search(domain, offset=offset,
                limit=limit, order=order, count=count)

Property()


class Sequence(ModelSQL, ModelView):
    _name = 'ir.sequence'
    company = fields.Many2One('company.company', 'Company',
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', 0)),
            ])

    def __init__(self):
        super(Sequence, self).__init__()
        self._order.insert(0, ('company', 'ASC'))

    def default_company(self):
        return Transaction().context.get('company')

Sequence()


class SequenceStrict(Sequence):
    _name = 'ir.sequence.strict'

SequenceStrict()


class CompanyConfigStart(ModelView):
    'Company Config'
    _name = 'company.company.config.start'
    _description = __doc__

CompanyConfigStart()


class CompanyConfig(Wizard):
    'Configure Company'
    _name = 'company.company.config'

    start = StateView('company.company.config.start',
        'company.company_config_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'company', 'tryton-ok', True),
            ])
    company = StateView('company.company',
        'company.company_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Add', 'add', 'tryton-ok', True),
            ])
    add = StateTransition()

    def transition_add(self, session):
        company_obj = Pool().get('company.company')
        user_obj = Pool().get('res.user')

        values = session.data['company'].copy()
        for fname in values.keys():
            if fname in ('id', 'party'):
                del values[fname]
                continue
            if fname in company_obj._columns:
                field = company_obj._columns[fname]
            else:
                field = company_obj._inherit_fields[fname][2]
            if field._type == 'one2many':
                values[fname] = [('create', v) for v in values[fname]]
            elif field._type == 'many2many':
                values[fname] = [('set', [v['id'] for v in values[fname]])]
        company_id = company_obj.create(values)
        user_ids = user_obj.search([
            ('main_company', '=', None),
            ])
        user_obj.write(user_ids, {
            'main_company': company_id,
            'company': company_id,
            })
        return 'end'

CompanyConfig()


class CompanyReport(Report):

    def parse(self, report, objects, datas, localcontext=None):
        user = Pool().get('res.user').browse(Transaction().user)
        if localcontext is None:
            localcontext = {}
        localcontext['company'] = user.company
        return super(CompanyReport, self).parse(report, objects, datas,
                localcontext=localcontext)


class LetterReport(CompanyReport):
    _name = 'party.letter'

LetterReport()
