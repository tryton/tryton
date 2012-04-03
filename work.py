#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool


class TimesheetLine(ModelSQL, ModelView):
    _name = 'timesheet.line'

    def compute_cost(self, line):
        employee_obj = Pool().get('company.employee')
        currency_obj = Pool().get('currency.currency')

        cost_price = employee_obj.compute_cost_price(line.employee.id,
                date=line.date)

        line_company = line.employee.company
        work_company = line.work.company
        if line_company.id != work_company.id and\
                line_company.currency.id != work_company.currency.id:
            with Transaction().set_context(date=line.date):
                cost_price = currency_obj.compute(line_company.currency.id,
                    cost_price, work_company.currency.id)

        return Decimal(str(line.hours)) * cost_price

TimesheetLine()


class Work(ModelSQL, ModelView):
    'Work Effort'
    _name = 'project.work'

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
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits']),
        'get_cost')
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['company']), 'get_currency_digits')

    def get_cost(self, ids, name):
        timesheet_line_obj = Pool().get('timesheet.line')
        all_ids = self.search([
                ('parent', 'child_of', ids),
                ('active', '=', True)]) + ids
        all_ids = list(set(all_ids))
        res = {}
        id2work = {}
        leafs = set()
        for work in self.browse(all_ids):
            id2work[work.id] = work
            if not work.children:
                leafs.add(work.id)

            res[work.id] = Decimal('0')
            for ts_line in work.timesheet_lines:
                res[work.id] += timesheet_line_obj.compute_cost(ts_line)

        while leafs:
            parents = set()
            for work_id in leafs:
                work = id2work[work_id]
                if not work.active:
                    continue
                if work.parent and work.parent.id in res:
                    res[work.parent.id] += res[work_id]
                    parents.add(work.parent.id)
            leafs = parents

        for id in all_ids:
            if id not in ids:
                del res[id]

        return res

    def get_revenue(self, ids, name):
        all_ids = self.search([
                ('parent', 'child_of', ids),
                ('active', '=', True)]) + ids
        all_ids = list(set(all_ids))
        res = {}
        id2work = {}
        leafs = set()
        for work in self.browse(all_ids):
            id2work[work.id] = work
            if not work.children:
                leafs.add(work.id)

            if work.type == 'task' and work.list_price:
                res[work.id] = (work.list_price
                    * Decimal(str(work.total_effort)))
            else:
                res[work.id] = Decimal('0')

        while leafs:
            parents = set()
            for work_id in leafs:
                work = id2work[work_id]
                if not work.active:
                    continue
                if work.parent and work.parent.id in res:
                    res[work.parent.id] += res[work_id]
                    parents.add(work.parent.id)
            leafs = parents

        for id in all_ids:
            if id not in ids:
                del res[id]

        return res

    def get_currency_digits(self, ids, name):
        res = {}
        for work in self.browse(ids):
            res[work.id] = work.company.currency.digits
        return res

    def on_change_with_currency_digits(self, vals):
        company_obj = Pool().get('company.company')
        if vals.get('company'):
            company = company_obj.browse(vals['company'])
            return company.currency.digits
        return 2

    def default_currency_digits(self):
        company_obj = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = company_obj.browse(company)
            return company.currency.digits
        return 2

    def on_change_product(self, vals):
        pool = Pool()
        product_obj = pool.get('product.product')
        user_obj = pool.get('res.user')
        company_obj = pool.get('company.company')
        model_data_obj = pool.get('ir.model.data')
        uom_obj = pool.get('product.uom')
        currency_obj = pool.get('currency.currency')

        if not vals.get('product'):
            return {}

        context = {}

        product = product_obj.browse(vals['product'])

        if vals.get('party'):
            context['customer'] = vals['party']

        uom_id = model_data_obj.get_id('product', 'uom_hour')
        hour_uom = uom_obj.browse(uom_id)

        with Transaction().set_context(context):
            list_price = uom_obj.compute_price(product.default_uom,
                    product.list_price, hour_uom)

        if vals.get('company'):
            user = user_obj.browse(Transaction().user)
            if user.company.id != vals['company']:
                company = company_obj.browse(vals['company'])
                if user.company.currency.id != company.currency.id:
                    list_price = currency_obj.compute(user.company.currency,
                            list_price, company.currency)

        return {'list_price': list_price}
Work()
