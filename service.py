#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Service"

from trytond.osv import fields, OSV


class Service(OSV):
    'Service'
    _name = 'project_revenue.service'
    _description = __doc__

    employee = fields.Many2One('company.employee', 'Employee', required=True)
    product = fields.Many2One('product.product', 'Product', required=True,
            domain=[('type', '=', 'service')])
    sequence = fields.Integer('Sequence', help="Use to order Services")

    def __init__(self):
        super(Service, self).__init__()
        self._sql_constraints += [
            ('employee_product_uniq', 'UNIQUE(employee, product)',
                'You can have only once the same product by employee!'),
        ]
        self._constraints += [
            ('check_product_uom',
                'Error! You must use a product with UOM of time.',
                ['product']),
        ]
        self._order.insert(0, ('sequence', 'ASC'))

    def check_product_uom(self, cursor, user, ids):
        '''
        Check if products have an UOM of time.
        '''
        model_data_obj = self.pool.get('ir.model.data')
        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'uom_cat_time'),
            ('module', '=', 'product'),
            ], limit=1)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0])
        category_id = model_data.db_id
        for service in self.browse(cursor, user, ids):
            if service.product.default_uom.category.id != category_id:
                return False
        return True

Service()


class Employee(OSV):
    _name = 'company.employee'

    services = fields.One2Many('project_revenue.service',
            'employee', 'Services',
            help="Services allowed to use in timesheets.")

Employee()
