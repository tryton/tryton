#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
from trytond.osv import fields, OSV
from trytond.wizard import Wizard, WizardOSV

class OrderPoint(OSV):
    """
    Order Point: Provide a way to define a supply policy for each
    product on each locations. Order points on warehouse are
    conciderer by the supply scheduler to generate purchase requests.
    """
    _name = 'stock.order_point'
    _description = __doc__

    product = fields.Many2One(
        'product.product', 'Product', required=True, select=True)
    location = fields.Many2One(
        'stock.location', 'Location', required=True, select=True)
    min_quantity = fields.Float('Minimal Quantity', required=True)
    max_quantity = fields.Float('Maximal Quantity', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)

    def default_company(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        if context.get('company'):
            return company_obj.name_get(cursor, user, context['company'],
                    context=context)[0]
        return False

    def __init__(self):
        super(OrderPoint, self).__init__()
        self._sql_constraints += [
            ('product_location_uniq', 'UNIQUE(product,location,company)',
             'Only one order point is allowed for each product-location pair.'),
            ('check_min_max_quantity',
             'CHECK( max_quantity is null or min_quantity is null or max_quantity >= min_quantity )',
             'Maximal quantity must be bigger than Minimal quantity'),
        ]

OrderPoint()
