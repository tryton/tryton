#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import copy
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
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


class User(ModelSQL, ModelView):
    _name = 'res.user'
    main_company = fields.Many2One('company.company', 'Main Company',
            on_change=['main_company'])
    company = fields.Many2One('company.company', 'Current Company',
            domain=[('parent', 'child_of', [Eval('main_company')], 'parent')],
            depends=['main_company'])
    companies = fields.Function(fields.One2Many('company.company', None,
        'Current Companies'), 'get_companies')
    employee = fields.Many2One('company.employee', 'Employee',
        domain=[('company', 'child_of', [Eval('main_company')], 'parent')],
        depends=['main_company'])

    def __init__(self):
        super(User, self).__init__()
        self._context_fields.insert(0, 'company')
        self._constraints += [
                ('check_company', 'child_company'),
                ]
        self._error_messages.update({
            'child_company': 'You can not set a company that is not ' \
                    'a child of your main company!',
        })

    def default_main_company(self):
        return Transaction().context.get('company') or False

    def default_company(self):
        return self.default_main_company()

    def get_companies(self, ids, name):
        company_obj = Pool().get('company.company')
        res = {}
        company_childs = {}
        for user in self.browse(ids):
            res[user.id] = []
            company_id = False
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
        return {'company': vals.get('main_company', False)}

    def check_company(self, ids):
        company_obj = Pool().get('company.company')
        for user in self.browse(ids):
            if user.main_company:
                companies = company_obj.search([
                    ('parent', 'child_of', [user.main_company.id]),
                    ])
                if user.company.id and (user.company.id not in companies):
                    return False
            elif user.company:
                return False
        return True

    def _get_preferences(self, user, context_only=False):
        res = super(User, self)._get_preferences(user, 
                context_only=context_only)
        if not context_only:
            res['main_company'] = user.main_company.id
        if user.employee:
            res['employee'] = user.employee.id
        return res

    def get_preferences_fields_view(self):
        company_obj = Pool().get('company.company')

        user = self.browse(Transaction().user)

        res = super(User, self).get_preferences_fields_view()
        res = copy.deepcopy(res)
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

    def _set_values(self, name, model, res_id, val, field_id):
        user_obj = Pool().get('res.user')
        user_id = Transaction().user
        if user_id == 0:
            user_id = Transaction().context.get('user', user_id)
        user = user_obj.browse(user_id)
        res = super(Property, self)._set_values(name, model, res_id, val, 
                field_id)
        if user:
            res['company'] = user.company.id
        return res

    def search(self, domain, offset=0, limit=None, order=None, count=False,
            query_string=False):
        if Transaction().user == 0 and not 'user' in Transaction().context:
            domain = ['AND', domain[:], ('company', '=', False)]
        return super(Property, self).search(domain, offset=offset, limit=limit,
            order=order, count=count, query_string=query_string)

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
        return Transaction().context.get('company') or False

Sequence()


class SequenceStrict(Sequence):
    _name = 'ir.sequence.strict'

SequenceStrict()


class CompanyConfigInit(ModelView):
    'Company Config Init'
    _name = 'company.company.config.init'
    _description = __doc__

CompanyConfigInit()


class CompanyConfig(Wizard):
    'Configure companies'
    _name = 'company.company.config'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'company.company.config.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('company', 'Ok', 'tryton-ok', True),
                ],
            },
        },
        'company': {
            'result': {
                'type': 'form',
                'object': 'company.company',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('add', 'Add', 'tryton-ok', True),
                ],
            },
        },
        'add': {
            'result': {
                'type': 'action',
                'action': '_add',
                'state': 'end',
            },
        },
    }

    def _add(self, data):
        company_obj = Pool().get('company.company')
        user_obj = Pool().get('res.user')

        company_id = company_obj.create(data['form'])
        user_ids = user_obj.search([
            ('main_company', '=', False),
            ])
        user_obj.write(user_ids, {
            'main_company': company_id,
            'company': company_id,
            })
        return {}

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
