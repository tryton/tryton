#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Not, Equal, Eval
from decimal import Decimal

class TimesheetLine(ModelSQL, ModelView):
    _name = 'timesheet.line'

    def compute_cost(self, cursor, user, line, context=None):
        employee_obj = self.pool.get('company.employee')
        currency_obj = self.pool.get('currency.currency')

        cost_price = employee_obj.compute_cost_price(cursor, user,
                line.employee.id, date=line.date, context=context)

        line_company = line.employee.company
        work_company = line.work.company
        if line_company.id != work_company.id and\
                line_company.currency.id != work_company.currency.id:

            cost_price = currency_obj.compute(cursor, user,
                    line_company.currency, cost_price,
                    work_company.currency, context=context)

        return Decimal(str(line.hours)) * cost_price

TimesheetLine()

class Work(ModelSQL, ModelView):
    'Work Effort'
    _name = 'project.work'

    product = fields.Many2One('product.product', 'Product',
            states={
                'invisible': Not(Equal(Eval('type'), 'task')),
            }, on_change=['product', 'party', 'hours', 'company'],
            depends=['type', 'party', 'hours', 'company'])
    list_price = fields.Numeric('List Price',
            digits=(16, Eval('currency_digits', 2)),
            states={
                'invisible': Not(Equal(Eval('type'), 'task')),
            }, depends=['type', 'currency_digits'])
    revenue = fields.Function(fields.Numeric('Revenue',
        digits=(16, Eval('currency_digits', 2)),
        states={
            'invisible': Not(Equal(Eval('type'), 'project')),
        }, depends=['type', 'currency_digits']), 'get_revenue')
    cost = fields.Function(fields.Numeric('Cost',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits']),
        'get_cost')
    currency_digits = fields.Function(fields.Integer('Currency Digits',
        on_change_with=['company']), 'get_currency_digits')

    def get_cost(self, cursor, user, ids, name, context=None):
        timesheet_line_obj = self.pool.get('timesheet.line')
        all_ids = self.search(cursor, user, [
                ('parent', 'child_of', ids),
                ('active', '=', True)], context=context) + ids
        all_ids = list(set(all_ids))
        works = set(self.browse(cursor, user, all_ids, context=context))
        res = {}
        id2work = {}
        leafs = set()
        for work in works:
            id2work[work.id] = work
            if not work.children:
                leafs.add(work.id)

            res[work.id] = Decimal('0')
            for ts_line in work.timesheet_lines:
                res[work.id] += timesheet_line_obj.compute_cost(cursor, user,
                        ts_line, context=context)

        while leafs:
            for work_id in leafs:
                work = id2work[work_id]
                works.remove(work)
                if not work.active:
                    continue
                if work.parent and work.parent.id in res:
                    res[work.parent.id] += res[work_id]
            next_leafs = set(w.id for w in works)
            for work in works:
                if not work.parent:
                    continue
                if work.parent.id in next_leafs and work.parent in works:
                    next_leafs.remove(work.parent.id)
            leafs = next_leafs
        return res

    def get_revenue(self, cursor, user, ids, name, context=None):
        all_ids = self.search(cursor, user, [
                ('parent', 'child_of', ids),
                ('active', '=', True)], context=context) + ids
        all_ids = list(set(all_ids))
        works = set(self.browse(cursor, user, all_ids, context=context))
        res = {}
        id2work = {}
        leafs = set()
        for work in works:
            id2work[work.id] = work
            if not work.children:
                leafs.add(work.id)

            if work.type == 'task':
                res[work.id] = work.list_price * Decimal(str(work.total_effort))
            else:
                res[work.id] = Decimal('0')

        while leafs:
            for work_id in leafs:
                work = id2work[work_id]
                works.remove(work)
                if not work.active:
                    continue
                if work.parent and work.parent.id in res:
                    res[work.parent.id] += res[work_id]
            next_leafs = set(w.id for w in works)
            for work in works:
                if not work.parent:
                    continue
                if work.parent.id in next_leafs and work.parent in works:
                    next_leafs.remove(work.parent.id)
            leafs = next_leafs
        return res

    def get_currency_digits(self, cursor, user, ids, name, context=None):
        res = {}
        for work in self.browse(cursor, user, ids, context=context):
            res[work.id] = work.company.currency.digits
        return res

    def on_change_with_currency_digits(self, cursor, user, vals, context=None):
        company_obj = self.pool.get('company.company')
        if vals.get('company'):
            company = company_obj.browse(cursor, user, vals['company'],
                    context=context)
            return company.currency.digits
        return 2

    def default_currency_digits(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        company = None
        if context.get('company'):
            company = company_obj.browse(cursor, user, context['company'],
                    context=context)
            return company.currency.digits
        return 2

    def on_change_product(self, cursor, user, vals, context=None):
        product_obj = self.pool.get('product.product')
        user_obj = self.pool.get('res.user')
        company_obj = self.pool.get('company.company')
        model_data_obj = self.pool.get('ir.model.data')
        uom_obj = self.pool.get('product.uom')

        if not vals.get('product'):
            return {}

        ctx = context and context.copy() or {}

        product = product_obj.browse(cursor, user, vals['product'],
                context=context)

        if vals.get('party'):
            ctx2['customer'] = vals['party']

        uom_id = model_data_obj.get_id(cursor, user, 'product', 'uom_hour',
                context=context)
        hour_uom = uom_obj.browse(cursor, user, uom_id, context=context)

        list_price = uom_obj.compute_price(cursor, user,
                product.default_uom, product.list_price, hour_uom,
                context=ctx)

        if vals.get('company'):
            user_record = user_obj.browse(cursor, user, user, context=context)
            if user_record.company.id != vals['company']:
                company = company_obj.browse(cursor, user, vals['company'],
                        context=context)
                if user_record.company.currency.id != company.currency.id:
                    list_price = currency_obj.compute(cursor, user,
                            user_record.company.currency, list_price,
                            company.currency, context=context)

        return {'list_price': list_price}
Work()
