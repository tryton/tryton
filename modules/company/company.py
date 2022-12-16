# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool
from trytond.pyson import Eval, If
from trytond.report import Report
from trytond.transaction import Transaction
from trytond.wizard import Button, StateTransition, StateView, Wizard

try:
    import pytz
    TIMEZONES = [(x, x) for x in pytz.common_timezones]
except ImportError:
    TIMEZONES = []
TIMEZONES += [(None, '')]

Transaction.cache_keys.update({'company', 'employee'})


class Company(ModelSQL, ModelView):
    'Company'
    __name__ = 'company.company'
    party = fields.Many2One('party.party', 'Party', required=True,
            ondelete='CASCADE')
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
        context={
            'company': If(
                Eval('company', -1) >= 0, Eval('company', None), None),
            },
        depends={'company'},
        help="The party which represents the employee.")
    company = fields.Many2One('company.company', 'Company', required=True,
        help="The company to which the employee belongs.")
    start_date = fields.Date('Start Date',
        domain=[If((Eval('start_date')) & (Eval('end_date')),
                ('start_date', '<=', Eval('end_date')),
                (),
                )
            ],
        help="When the employee joins the company.")
    end_date = fields.Date('End Date',
        domain=[If((Eval('start_date')) & (Eval('end_date')),
                ('end_date', '>=', Eval('start_date')),
                (),
                )
            ],
        help="When the employee leaves the company.")
    supervisor = fields.Many2One(
        'company.employee', "Supervisor",
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        help="The employee who oversees this employee.")
    subordinates = fields.One2Many(
        'company.employee', 'supervisor', "Subordinates",
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
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
                ('companies', '=', None),
                ])
        User.write(users, {
                'companies': [('add', [self.company.id])],
                'company': self.company.id,
                })
        return 'end'

    def end(self):
        return 'reload context'


class CompanyReport(Report):

    @classmethod
    def header_key(cls, record):
        return super().header_key(record) + (('company', record.company),)

    @classmethod
    def get_context(cls, records, header, data):
        context = super().get_context(records, header, data)
        context['company'] = header.get('company')
        return context
