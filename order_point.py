#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.osv import fields, OSV
from trytond.wizard import Wizard, WizardOSV


class OrderPoint(OSV):
    """
    Order Point: Provide a way to define a supply policy for each
    product on each locations. Order points on warehouse are
    considered by the supply scheduler to generate purchase requests.
    """
    _name = 'stock.order_point'
    _description = "Order Point"

    product = fields.Many2One(
        'product.product', 'Product', required=True, select=True,
        domain=[('type', '=', 'stockable')])
    warehouse_location = fields.Many2One(
        'stock.location', 'Warehouse Location', select=True,
        domain="[('type', '=', 'warehouse')]",
        states={'invisible': "type != 'purchase'",
                'required': "type == 'purchase'"},)
    storage_location = fields.Many2One(
        'stock.location', 'Storage Location', select=True,
        domain="[('type', '=', 'storage')]",
        states={'invisible': "type != 'internal'",
                'required': "type == 'internal'"},)
    location = fields.Function(
        'get_location', type='many2one', relation='stock.location',
        fnct_search='search_location', string='Location')
    provisioning_location = fields.Many2One(
        'stock.location', 'Provisioning Location',
        domain="[('type', '=', 'storage')]",
        states={'invisible': "type != 'internal'",
                'required': "type == 'internal'"},)
    type = fields.Selection(
        [('internal', 'Internal'),
         ('purchase', 'Purchase')],
        'Type', select=True, required=True)
    min_quantity = fields.Float('Minimal Quantity', required=True)
    max_quantity = fields.Float('Maximal Quantity', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)

    def __init__(self):
        super(OrderPoint, self).__init__()
        self._constraints += [
            ('check_concurrent_internal', 'concurrent_internal_op'),
            ('check_uniqueness', 'unique_op'),
            ]
        self._sql_constraints += [
            ('check_min_max_quantity',
             'CHECK( max_quantity is null or min_quantity is null or max_quantity >= min_quantity )',
             'Maximal quantity must be bigger than Minimal quantity'),
            ]
        self._error_messages.update(
            {'unique_op': 'Only one order point is allowed '\
                 'for each product-location pair.',
             'concurrent_internal_op': 'You can not define two order point '\
                 'on the same product with opposite locations.',})

    def default_type(self, cursor, user, context=None):
        return "purchase"

    def check_concurrent_internal(self, cursor, user, ids):
        """
        Ensure that there is no 'concurrent' internal order
        points. I.E. no two order point with opposite location for the
        same product and same company.
        """
        internal_ids = self.search(
            cursor, user, [('id', 'in', ids), ('type', '=', 'internal')])
        if not internal_ids:
            return True

        query = ['OR']
        for op in self.browse(cursor, user, internal_ids):
            arg = ['AND',
                   ('provisioning_location', '=', op.storage_location.id),
                   ('storage_location', '=', op.provisioning_location.id),
                   ('company', '=', op.company.id),
                   ('type', '=', 'internal')]
            query.append(arg)
        ids = self.search(cursor, user, query)
        print ids
        return not bool(ids)

    def check_uniqueness_field(self, type):
        if type == 'purchase':
            return 'warehouse_location'
        elif type == 'internal':
            return 'storage_location'

    def check_uniqueness(self, cursor, user, ids):
        """
        Ensure uniqueness of order points. I.E that the is no several
        order point for the same location, the same product and the
        same company.
        """
        query = ['OR']
        for op in self.browse(cursor, user, ids):
            field = self.check_uniqueness_field(op.type)
            arg = ['AND',
                   (field, '=', op[field].id),
                   ('id', '!=', op.id),
                   ('company', '=', op.company.id),]
            query.append(arg)
        ids = self.search(cursor, user, query)
        return not bool(ids)

    def name_get(self, cursor, user, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = []
        for op in self.browse(cursor, user, ids, context=context):
            res.append((op.id, "%s@%s" % (op.product.name, op.location.name)))
        return res

    def get_location(self, cursor, user, ids, name, args, context=None):
        location_obj = self.pool.get('stock.location')
        res = {}
        for op in self.browse(cursor, user, ids, context=context):
            if op.type == 'purchase':
                res[op.id] = op.warehouse_location.id
            elif op.type == 'internal':
                res[op.id] = op.storage_location.id
            else:
                res[op.id] = False
        loc_id2name = dict(location_obj.name_get(
                cursor, user, [i for i in res.itervalues() if i]))

        for op_id, loc_id in res.iteritems():
            if loc_id in loc_id2name:
                res[op_id] = (loc_id, loc_id2name[loc_id])
        return res

    def search_location(self, cursor, user, name, domain=None, context=None):
        ids = []
        for field in ('warehouse_location', 'storage_location'):
            args = []
            for _, operator, operand in domain:
                args.append((field, operator, operand))
            ids.extend(self.search(cursor, user, args, context=context))
        return [('id', 'in', ids)]

    def default_company(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        if context.get('company'):
            return company_obj.name_get(cursor, user, context['company'],
                    context=context)[0]
        return False

OrderPoint()
