#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Timesheet"

from trytond.osv import fields, OSV
import copy


class Line(OSV):
    _name = 'timesheet.line'

    product = fields.Many2One('product.product', 'Service', required=True,
            domain="[('type', '=', 'service'), " \
                    "('_employee', '=', employee)]")

    def __init__(self):
        super(Line, self).__init__()
        self.employee = copy.copy(self.employee)
        if self.employee.on_change is None:
            self.employee.on_change = []
        if 'employee' not in self.employee.on_change:
            self.employee.on_change += ['employee']
            self._reset_columns()
        self._constraints += [
            ('check_product', 'employee_service'),
        ]
        self._error_messages.update({
            'employee_service': 'You can not use a product ' \
                    'that is not an employee services!',
        })
        self._rpc_allowed += ['on_change_employee']

    def default_product(self, cursor, user, context=None):
        employee_obj = self.pool.get('company.employee')
        product_obj = self.pool.get('product.product')

        employee_id = self.default_employee(cursor, user, context=context)
        if employee_id:
            if isinstance(employee_id, (list, tuple)):
                employee_id = employee_id[0]
            employee = employee_obj.browse(cursor, user, employee_id,
                    context=context)
            if employee.services:
                return product_obj.name_get(cursor, user,
                        employee.services[0].product.id, context=context)[0]
        return False

    def on_change_employee(self, cursor, user, ids, vals, context=None):
        employee_obj = self.pool.get('company.employee')
        product_obj = self.pool.get('product.product')

        res = {}
        if hasattr(super(Line, self), 'on_change_employee'):
            res = super(Line, self).on_change_employee(cursor, user, ids, vals,
                    context=context)

        res['product'] = False
        if vals.get('employee'):
            employee = employee_obj.browse(cursor, user, vals['employee'],
                    context=context)
            if employee.services:
                res['product'] = product_obj.name_get(cursor, user,
                        employee.services[0].product.id, context=context)[0]
        return res

    def check_product(self, cursor, user, ids):
        '''
        Check if product is in employee services.
        '''
        for line in self.browse(cursor, user, ids):
            if line.product.id not in \
                    [x.product.id for x in line.employee.services]:
                return False
        return True

Line()


class Product(OSV):
    _name = 'product.product'

    def search(self, cursor, user, args, offset=0, limit=None, order=None,
            context=None, count=False, query_string=False):
        employee_obj = self.pool.get('company.employee')

        args = args[:]
        def process_args(args):
            i = 0
            while i < len(args):
                if isinstance(args[i], list):
                    process_args(args[i])
                if isinstance(args[i], tuple) \
                        and args[i][0] == '_employee':
                    if not args[i][2]:
                        args[i] = ('id', '=', '0')
                    else:
                        employee = employee_obj.browse(cursor, user, args[i][2],
                                context=context)
                        if not employee.services:
                            args[i] = ('id', '=', '0')
                        else:
                            args[i] = ('id', 'in',
                                    [x.product.id for x in employee.services])
                i += 1
        process_args(args)
        return super(Product, self).search(cursor, user, args, offset=offset,
                limit=limit, order=order, context=context, count=count,
                query_string=query_string)

Product()
