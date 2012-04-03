#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import If, Equal, Eval, Not, In, Get
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.backend import TableHandler


class OrderPoint(ModelSQL, ModelView):
    """
    Order Point: Provide a way to define a supply policy for each
    product on each locations. Order points on warehouse are
    considered by the supply scheduler to generate purchase requests.
    """
    _name = 'stock.order_point'
    _description = "Order Point"

    product = fields.Many2One('product.product', 'Product', required=True,
        select=True,
        domain=[
            ('type', '=', 'goods'),
            ('consumable', '=', False),
            ('purchasable', 'in', If(Equal(Eval('type'), 'purchase'),
                    [True], [True, False])),
            ],
        depends=['type'],
        on_change=['product'])
    warehouse_location = fields.Many2One('stock.location',
        'Warehouse Location', select=True,
        domain=[('type', '=', 'warehouse')],
        states={
            'invisible': Not(Equal(Eval('type'), 'purchase')),
            'required': Equal(Eval('type'), 'purchase'),
            },
        depends=['type'])
    storage_location = fields.Many2One('stock.location', 'Storage Location',
        select=True,
        domain=[('type', '=', 'storage')],
        states={
            'invisible': Not(Equal(Eval('type'), 'internal')),
            'required': Equal(Eval('type'), 'internal'),
        },
        depends=['type'])
    location = fields.Function(fields.Many2One('stock.location', 'Location'),
            'get_location', searcher='search_location')
    provisioning_location = fields.Many2One(
        'stock.location', 'Provisioning Location',
        domain=[('type', '=', 'storage')],
        states={
            'invisible': Not(Equal(Eval('type'), 'internal')),
            'required': Equal(Eval('type'), 'internal'),
        },
        depends=['type'])
    type = fields.Selection(
        [('internal', 'Internal'),
         ('purchase', 'Purchase')],
        'Type', select=True, required=True)
    min_quantity = fields.Float('Minimal Quantity', required=True,
            digits=(16, Eval('unit_digits', 2)), depends=['unit_digits'])
    max_quantity = fields.Float('Maximal Quantity', required=True,
            digits=(16, Eval('unit_digits', 2)), depends=['unit_digits'])
    company = fields.Many2One('company.company', 'Company', required=True,
            domain=[
                ('id', If(In('company', Eval('context', {})), '=', '!='),
                    Get(Eval('context', {}), 'company', 0)),
            ])
    unit = fields.Function(fields.Many2One('product.uom', 'Unit'), 'get_unit')
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
            'get_unit_digits')

    def __init__(self):
        super(OrderPoint, self).__init__()
        self._constraints += [
            ('check_concurrent_internal', 'concurrent_internal_op'),
            ('check_uniqueness', 'unique_op'),
            ]
        self._sql_constraints += [
            ('check_max_qty_greater_min_qty',
                'CHECK(max_quantity >= min_quantity)',
                'Maximal quantity must be bigger than Minimal quantity'),
            ]
        self._error_messages.update({
                'unique_op': 'Only one order point is allowed '\
                    'for each product-location pair.',
                'concurrent_internal_op': 'You can not define ' \
                    'two order points on the same product ' \
                    'with opposite locations.',
                })

    def init(self, module_name):
        cursor = Transaction().cursor
        # Migration from 2.2
        table = TableHandler(cursor, self, module_name)
        table.drop_constraint('check_min_max_quantity')

        super(OrderPoint, self).init(module_name)

    def default_type(self):
        return "purchase"

    def on_change_product(self, vals):
        product_obj = Pool().get('product.product')
        res = {
            'unit': None,
            'unit.rec_name': '',
            'unit_digits': 2,
        }
        if vals.get('product'):
            product = product_obj.browse(vals['product'])
            res['unit'] = product.default_uom.id
            res['unit.rec_name'] = product.default_uom.rec_name
            res['unit_digits'] = product.default_uom.digits
        return res

    def get_unit(self, ids, name):
        res = {}
        for order in self.browse(ids):
            res[order.id] = order.product.default_uom.id
        return res

    def get_unit_digits(self, ids, name):
        res = {}
        for order in self.browse(ids):
            res[order.id] = order.product.default_uom.digits
        return res

    def check_concurrent_internal(self, ids):
        """
        Ensure that there is no 'concurrent' internal order
        points. I.E. no two order point with opposite location for the
        same product and same company.
        """
        internal_ids = self.search([
            ('id', 'in', ids),
            ('type', '=', 'internal'),
            ])
        if not internal_ids:
            return True

        query = ['OR']
        for op in self.browse(internal_ids):
            arg = ['AND',
                   ('provisioning_location', '=', op.storage_location.id),
                   ('storage_location', '=', op.provisioning_location.id),
                   ('company', '=', op.company.id),
                   ('type', '=', 'internal')]
            query.append(arg)
        ids = self.search(query)
        return not bool(ids)

    def _type2field(self, type=None):
        t2f = {
            'purchase': 'warehouse_location',
            'internal': 'storage_location',
            }
        if type == None:
            return t2f
        else:
            return t2f[type]

    def check_uniqueness(self, ids):
        """
        Ensure uniqueness of order points. I.E that there is no several
        order point for the same location, the same product and the
        same company.
        """
        query = ['OR']
        for op in self.browse(ids):
            field = self._type2field(op.type)
            arg = ['AND',
                ('product', '=', op.product.id),
                (field, '=', op[field].id),
                ('id', '!=', op.id),
                ('company', '=', op.company.id),
                ]
            query.append(arg)
        ids = self.search(query)
        return not bool(ids)

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = {}
        for op in self.browse(ids):
            res[op.id] = "%s@%s" % (op.product.name, op.location.name)
        return res

    def search_rec_name(self, name, clause):
        res = []
        names = clause[2].split('@', 1)
        res.append(('product.template.name', clause[1], names[0]))
        if len(names) != 1 and names[1]:
            res.append(('location', clause[1], names[1]))
        return res

    def get_location(self, ids, name):
        res = {}
        for op in self.browse(ids):
            if op.type == 'purchase':
                res[op.id] = op.warehouse_location.id
            elif op.type == 'internal':
                res[op.id] = op.storage_location.id
            else:
                res[op.id] = None
        return res

    def search_location(self, name, domain=None):
        ids = []
        for type, field in self._type2field().iteritems():
            args = [('type', '=', type)]
            for _, operator, operand in domain:
                args.append((field, operator, operand))
            ids.extend(self.search(args))
        return [('id', 'in', ids)]

    def default_company(self):
        return Transaction().context.get('company')

OrderPoint()
