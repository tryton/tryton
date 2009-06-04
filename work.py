#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model import ModelView, ModelSQL, fields


class Work(ModelSQL, ModelView):
    'Work Effort'
    _name = 'project.work'

    product = fields.Many2One('product.product', 'Product',
            states={
                'invisible': "type!= 'task'"
            }, on_change=['product', 'party', 'hours', 'company'],
            depends=['type', 'party', 'hours', 'company'])
    list_price = fields.Numeric('List Price', digits=(12, 6),
            states={
                'invisible': "type!= 'task'"
            }, depends=['type'])
    revenue = fields.Function('get_revenue',
            string='Revenue', digits=(12, 6),
            states={
                'invisible': "type!= 'project'"
            }, depends=['type'])
    cost_price = fields.Function('get_cost_price', string='Cost Price',
            digits=(12, 6))

    def get_cost_price(self, cursor, user, ids, name, arg, context=None):
        employee_obj = self.pool.get('company.employee')
        ctx = context and context.copy() or {}

        all_ids = self.search(cursor, user, [
                ('parent', 'child_of', ids),
                ('active', '=', True)], context=context) + ids
        all_ids = list(set(all_ids))
        res = {}
        id2work = {}
        leafs = set()
        for work in self.browse(cursor, user, all_ids, context=context):
            id2work[work.id] = work
            if not work.children:
                leafs.add(work.id)

            res[work.id] = 0
            for ts_line in work.timesheet_lines:
                ctx['date'] = ts_line.date
                employee = employee_obj.browse(cursor, user,
                        ts_line.employee.id, context=ctx)
                res[work.id] += ts_line.hours * float(employee.cost_price)

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

    def get_revenue(self, cursor, user, ids, name, arg, context=None):
        all_ids = self.search(cursor, user, [
                ('parent', 'child_of', ids),
                ('active', '=', True)], context=context) + ids
        all_ids = list(set(all_ids))
        res = {}
        id2work = {}
        leafs = set()
        for work in self.browse(cursor, user, all_ids, context=context):
            id2work[work.id] = work
            if not work.children:
                leafs.add(work.id)

            if work.type == 'task':
                res[work.id] = float(work.list_price) * work.total_effort
            else:
                res[work.id] = 0

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

    def on_change_product(self, cursor, user, ids, vals, context=None):
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

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'uom_hour'),
            ('module', '=', 'product'),
            ('model', '=', 'product.uom'),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        hour_uom = uom_obj.browse(cursor, user, model_data.db_id,
                context=context)

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
