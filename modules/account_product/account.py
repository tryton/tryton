# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.model import fields
from trytond.transaction import Transaction


class CreateChartProperties(metaclass=PoolMeta):
    __name__ = 'account.create_chart.properties'

    category_account_expense = fields.Many2One(
        'account.account', 'Default Expense Account',
        domain=[
            ('type.expense', '=', True),
            ('company', '=', Eval('company')),
            ],
        depends=['company'])
    category_account_revenue = fields.Many2One(
        'account.account', 'Default Revenue Account',
        domain=[
            ('type.revenue', '=', True),
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


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    @property
    def product(self):
        pass

    @property
    def rule_pattern(self):
        def parents(categories):
            for category in categories:
                while category:
                    yield category
                    category = category.parent

        pattern = super().rule_pattern
        if self.product:
            pattern['product'] = self.product.id
            pattern['product_categories'] = [
                c.id for c in parents(self.product.categories_all)]
        else:
            pattern['product'] = None
            pattern['product_categories'] = []
        return pattern
