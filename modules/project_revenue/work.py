#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import fields
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['TimesheetLine', 'Work']
__metaclass__ = PoolMeta


class TimesheetLine:
    __name__ = 'timesheet.line'

    def compute_cost(self):
        Currency = Pool().get('currency.currency')

        cost_price = self.employee.compute_cost_price(date=self.date)

        line_company = self.employee.company
        work_company = self.work.company
        if (line_company != work_company and
                line_company.currency != work_company.currency):
            with Transaction().set_context(date=self.date):
                cost_price = Currency.compute(line_company.currency,
                    cost_price, work_company.currency)

        return Decimal(str(self.hours)) * cost_price


class Work:
    __name__ = 'project.work'
    product = fields.Many2One('product.product', 'Product',
        states={
            'invisible': ~Eval('timesheet_available'),
            },
        depends=['timesheet_available'],
        on_change=['product', 'party', 'hours', 'company'])
    list_price = fields.Numeric('List Price',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    revenue = fields.Function(fields.Numeric('Revenue',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_revenue')
    cost = fields.Function(fields.Numeric('Cost',
            states={
                'invisible': ~Eval('timesheet_available'),
                },
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits', 'timesheet_available']), 'get_cost')
    currency_digits = fields.Function(fields.Integer('Currency Digits',
            on_change_with=['company']), 'on_change_with_currency_digits')

    @classmethod
    def get_cost(cls, works, name):
        works += cls.search([
                ('parent', 'child_of', [w.id for w in works]),
                ('active', '=', True)]) + works
        works = set(works)

        costs = {}
        id2work = {}
        leafs = set()
        for work in works:
            id2work[work.id] = work
            if not work.children:
                leafs.add(work.id)

            costs[work.id] = Decimal('0')
            for ts_line in work.timesheet_lines:
                costs[work.id] += ts_line.compute_cost()

        while leafs:
            for work_id in leafs:
                work = id2work[work_id]
                works.remove(work)
                if not work.active:
                    continue
                if work.parent and work.parent.id in costs:
                    costs[work.parent.id] += costs[work_id]
            next_leafs = set(w.id for w in works)
            for work in works:
                if not work.parent:
                    continue
                if work.parent.id in next_leafs and work.parent in works:
                    next_leafs.remove(work.parent.id)
            leafs = next_leafs
        return costs

    @classmethod
    def get_revenue(cls, works, name):
        works = cls.search([
                ('parent', 'child_of', [w.id for w in works]),
                ('active', '=', True)]) + works
        works = set(works)

        revenues = {}
        id2work = {}
        leafs = set()
        for work in works:
            id2work[work.id] = work
            if not work.children:
                leafs.add(work.id)

            if work.type == 'task' and work.list_price:
                revenues[work.id] = (work.list_price
                    * Decimal(str(work.total_effort)))
            else:
                revenues[work.id] = Decimal('0')

        while leafs:
            for work_id in leafs:
                work = id2work[work_id]
                works.remove(work)
                if not work.active:
                    continue
                if work.parent and work.parent.id in revenues:
                    revenues[work.parent.id] += revenues[work_id]
            next_leafs = set(w.id for w in works)
            for work in works:
                if not work.parent:
                    continue
                if work.parent.id in next_leafs and work.parent in works:
                    next_leafs.remove(work.parent.id)
            leafs = next_leafs
        return revenues

    def on_change_with_currency_digits(self, name=None):
        if self.company:
            return self.company.currency.digits
        return 2

    @staticmethod
    def default_currency_digits():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = Company(company)
            return company.currency.digits
        return 2

    def on_change_product(self):
        pool = Pool()
        User = pool.get('res.user')
        ModelData = pool.get('ir.model.data')
        Uom = pool.get('product.uom')
        Currency = pool.get('currency.currency')

        if not self.product:
            return {}

        context = {}

        if self.party:
            context['customer'] = self.party.id

        hour_uom = Uom(ModelData.get_id('product', 'uom_hour'))

        with Transaction().set_context(context):
            list_price = Uom.compute_price(self.product.default_uom,
                self.product.list_price, hour_uom)

        if self.company:
            user = User(Transaction().user)
            if user.company != self.company:
                if user.company.currency != self.company.currency:
                    list_price = Currency.compute(user.company.currency,
                        list_price, self.company.currency)

        return {'list_price': list_price}
