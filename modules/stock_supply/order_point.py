#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard


class OrderPoint(ModelSQL, ModelView):
    """
    Order Point: Provide a way to define a supply policy for each
    product on each locations. Order points on warehouse are
    considered by the supply scheduler to generate purchase requests.
    """
    _name = 'stock.order_point'
    _description = "Order Point"

    product = fields.Many2One(
        'product.product', 'Product', required=True, select=1,
        domain=[('type', '=', 'stockable'), "('purchasable', 'in', " \
                "type == 'purchase' and [True] or [True, False])"],
        on_change=['product'])
    warehouse_location = fields.Many2One(
        'stock.location', 'Warehouse Location', select=1,
        domain=[('type', '=', 'warehouse')],
        states={'invisible': "type != 'purchase'",
                'required': "type == 'purchase'"},)
    storage_location = fields.Many2One(
        'stock.location', 'Storage Location', select=1,
        domain=[('type', '=', 'storage')],
        states={'invisible': "type != 'internal'",
                'required': "type == 'internal'"},)
    location = fields.Function(
        'get_location', type='many2one', relation='stock.location',
        fnct_search='search_location', string='Location')
    provisioning_location = fields.Many2One(
        'stock.location', 'Provisioning Location',
        domain=[('type', '=', 'storage')],
        states={'invisible': "type != 'internal'",
                'required': "type == 'internal'"},)
    type = fields.Selection(
        [('internal', 'Internal'),
         ('purchase', 'Purchase')],
        'Type', select=1, required=True)
    min_quantity = fields.Float('Minimal Quantity', required=True,
            digits="(16, unit_digits)", depends=['unit_digits'])
    max_quantity = fields.Float('Maximal Quantity', required=True,
            digits="(16, unit_digits)", depends=['unit_digits'])
    company = fields.Many2One('company.company', 'Company', required=True,
            domain=["('id', 'company' in context and '=' or '!=', " \
                    "context.get('company', 0))"])
    unit = fields.Function('get_unit', type='many2one', relation='product.uom',
            string='Unit')
    unit_digits = fields.Function('get_unit_digits', type='integer',
            string='Unit Digits')

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
             'concurrent_internal_op': 'You can not define two order points '\
                 'on the same product with opposite locations.',})

    def default_type(self, cursor, user, context=None):
        return "purchase"

    def on_change_product(self, cursor, user, ids, vals, context=None):
        product_obj = self.pool.get('product.product')
        res = {
            'unit': False,
            'unit.rec_name': '',
            'unit_digits': 2,
        }
        if vals.get('product'):
            product = product_obj.browse(cursor, user, vals['product'],
                    context=context)
            res['unit'] = product.default_uom.id
            res['unit.rec_name'] = product.default_uom.rec_name
            res['unit_digits'] = product.default_uom.digits
        return res

    def get_unit(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for order in self.browse(cursor, user, ids, context=context):
            res[order.id] = order.product.default_uom.id
        return res

    def get_unit_digits(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for order in self.browse(cursor, user, ids, context=context):
            res[order.id] = order.product.default_uom.digits
        return res

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
        return not bool(ids)

    def _type2field(self, type=None):
        t2f = {'purchase': 'warehouse_location',
               'internal': 'storage_location',}
        if type == None:
            return t2f
        else:
            return t2f[type]

    def check_uniqueness(self, cursor, user, ids):
        """
        Ensure uniqueness of order points. I.E that there is no several
        order point for the same location, the same product and the
        same company.
        """
        query = ['OR']
        for op in self.browse(cursor, user, ids):
            field = self._type2field(op.type)
            arg = ['AND',
                   ('product', '=', op.product.id),
                   (field, '=', op[field].id),
                   ('id', '!=', op.id),
                   ('company', '=', op.company.id),]
            query.append(arg)
        ids = self.search(cursor, user, query)
        return not bool(ids)

    def get_rec_name(self, cursor, user, ids, name, arg, context=None):
        if not ids:
            return {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for op in self.browse(cursor, user, ids, context=context):
            res[op.id] = "%s@%s" % (op.product.name, op.location.name)
        return res

    def search_rec_name(self, cursor, user, name, args, context=None):
        args2 = []
        i = 0
        while i < len(args):
            names = args[i][2].split('@', 1)
            args2.append(('product.template.name', args[i][1], names[0]))
            if len(names) != 1 and names[1]:
                args2.append(('location', args[i][1], names[1]))
            i += 1
        return args2

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
        return res

    def search_location(self, cursor, user, name, domain=None, context=None):
        ids = []
        for type, field in self._type2field().iteritems():
            args = [('type', '=', type)]
            for _, operator, operand in domain:
                args.append((field, operator, operand))
            ids.extend(self.search(cursor, user, args, context=context))
        return [('id', 'in', ids)]

    def default_company(self, cursor, user, context=None):
        company_obj = self.pool.get('company.company')
        if context is None:
            context = {}
        if context.get('company'):
            return context['company']
        return False

OrderPoint()
