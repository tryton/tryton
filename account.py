# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.model import fields
from trytond.transaction import Transaction

__all__ = ['CreateChart', 'CreateChartProperties']


class CreateChartProperties(metaclass=PoolMeta):
    __name__ = 'account.create_chart.properties'

    category_account_expense = fields.Many2One(
        'account.account', 'Default Expense Account',
        domain=[
            ('kind', '=', 'expense'),
            ('company', '=', Eval('company')),
            ],
        depends=['company'])
    category_account_revenue = fields.Many2One(
        'account.account', 'Default Revenue Account',
        domain=[
            ('kind', '=', 'revenue'),
            ('company', '=', Eval('company')),
            ],
        depends=['company'])


class CreateChart(metaclass=PoolMeta):
    __name__ = 'account.create_chart'

    def transition_create_properties(self):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        state = super(CreateChart, self).transition_create_properties()

        with Transaction().set_context(company=self.properties.company.id):
            config = Configuration(1)
            for name in [
                    'category_account_expense',
                    'category_account_revenue']:
                setattr(config, 'default_%s' % name,
                    getattr(self.properties, name, None))
            config.save()
        return state
