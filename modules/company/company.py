# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields, tree
from trytond.wizard import Wizard, StateView, Button, StateTransition
from trytond.report import Report
from trytond.pyson import Eval, If
from trytond.transaction import Transaction
from trytond.pool import Pool

try:
    import pytz
    TIMEZONES = [(x, x) for x in pytz.common_timezones]
except ImportError:
    TIMEZONES = []
TIMEZONES += [(None, '')]

Transaction.cache_keys.update({'company', 'employee'})


class Company(tree(), ModelSQL, ModelView):
    'Company'
    __name__ = 'company.company'
    party = fields.Many2One('party.party', 'Party', required=True,
            ondelete='CASCADE')
    parent = fields.Many2One('company.company', 'Parent',
        help="Add the company below the parent.")
    childs = fields.One2Many('company.company', 'parent', 'Children',
        help="Add children below the company.")
    header = fields.Text(
        'Header', help="The text to display on report headers.")
    footer = fields.Text(
        'Footer', help="The text to display on report footers.")
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        help="The main currency for the company.")
    timezone = fields.Selection(TIMEZONES, 'Timezone', translate=False,
        help="Used to compute the today date.")
    employees = fields.One2Many('company.employee', 'company', 'Employees',
        help="Add employees to the company.")

    def get_rec_name(self, name):
        return self.party.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('party.rec_name',) + tuple(clause[1:])]

    @classmethod
    def write(cls, companies, values, *args):
        super(Company, cls).write(companies, values, *args)
        # Restart the cache on the domain_get method
        Pool().get('ir.rule')._domain_get_cache.clear()


class Employee(ModelSQL, ModelView):
    'Employee'
    __name__ = 'company.employee'
    party = fields.Many2One('party.party', 'Party', required=True,
        help="The party which represents the employee.")
    company = fields.Many2One('company.company', 'Company', required=True,
        help="The company to which the employee belongs.")
    start_date = fields.Date('Start Date',
        domain=[If((Eval('start_date')) & (Eval('end_date')),
                ('start_date', '<=', Eval('end_date')),
                (),
                )
            ],
        depends=['end_date'],
        help="When the employee joins the company.")
    end_date = fields.Date('End Date',
        domain=[If((Eval('start_date')) & (Eval('end_date')),
                ('end_date', '>=', Eval('start_date')),
                (),
                )
            ],
        depends=['start_date'],
        help="When the employee leaves the company.")
    supervisor = fields.Many2One(
        'company.employee', "Supervisor",
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'],
        help="The employee who oversees this employee.")
    subordinates = fields.One2Many(
        'company.employee', 'supervisor', "Subordinates",
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'],
        help="The employees to be overseen by this employee.")

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    def get_rec_name(self, name):
        return self.party.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('party.rec_name',) + tuple(clause[1:])]


class CompanyConfigStart(ModelView):
    'Company Config'
    __name__ = 'company.company.config.start'


class CompanyConfig(Wizard):
    'Configure Company'
    __name__ = 'company.company.config'
    start = StateView('company.company.config.start',
        'company.company_config_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'company', 'tryton-ok', True),
            ])
    company = StateView('company.company',
        'company.company_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Add', 'add', 'tryton-ok', True),
            ])
    add = StateTransition()

    def transition_add(self):
        User = Pool().get('res.user')

        self.company.save()
        users = User.search([
                ('main_company', '=', None),
                ])
        User.write(users, {
                'main_company': self.company.id,
                'company': self.company.id,
                })
        return 'end'

    def end(self):
        return 'reload context'


class CompanyReport(Report):

    @classmethod
    def get_context(cls, records, data):
        report_context = super(CompanyReport, cls).get_context(records, data)
        report_context['company'] = report_context['user'].company
        return report_context
