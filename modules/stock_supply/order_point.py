# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields, Check
from trytond.pyson import If, Equal, Eval, Not, In
from trytond.transaction import Transaction
from trytond import backend

__all__ = ['OrderPoint']


class OrderPoint(ModelSQL, ModelView):
    """
    Order Point
    Provide a way to define a supply policy for each
    product on each locations. Order points on warehouse are
    considered by the supply scheduler to generate purchase requests.
    """
    __name__ = 'stock.order_point'
    product = fields.Many2One('product.product', 'Product', required=True,
        select=True,
        domain=[
            ('type', '=', 'goods'),
            ('consumable', '=', False),
            ('purchasable', 'in', If(Equal(Eval('type'), 'purchase'),
                    [True], [True, False])),
            ],
        depends=['type'])
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
        domain=[('type', 'in', ['storage', 'view'])],
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
                    Eval('context', {}).get('company', -1)),
            ])
    unit = fields.Function(fields.Many2One('product.uom', 'Unit'), 'get_unit')
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
            'get_unit_digits')

    @classmethod
    def __setup__(cls):
        super(OrderPoint, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('check_max_qty_greater_min_qty',
                Check(t, t.max_quantity >= t.min_quantity),
                'Maximal quantity must be bigger than Minimal quantity'),
            ]
        cls._error_messages.update({
                'unique_op': ('Only one order point is allowed '
                    'for each product-location pair.'),
                'concurrent_internal_op': ('You can not define '
                    'two order points on the same product '
                    'with opposite locations.'),
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        # Migration from 2.2
        table = TableHandler(cls, module_name)
        table.drop_constraint('check_min_max_quantity')

        super(OrderPoint, cls).__register__(module_name)

    @staticmethod
    def default_type():
        return "purchase"

    @fields.depends('product')
    def on_change_product(self):
        self.unit = None
        self.unit_digits = 2
        if self.product:
            self.unit = self.product.default_uom
            self.unit_digits = self.product.default_uom.digits

    def get_unit(self, name):
        return self.product.default_uom.id

    def get_unit_digits(self, name):
        return self.product.default_uom.digits

    @classmethod
    def validate(cls, orderpoints):
        super(OrderPoint, cls).validate(orderpoints)
        cls.check_concurrent_internal(orderpoints)
        cls.check_uniqueness(orderpoints)

    @classmethod
    def check_concurrent_internal(cls, orders):
        """
        Ensure that there is no 'concurrent' internal order
        points. I.E. no two order point with opposite location for the
        same product and same company.
        """
        internals = cls.search([
                ('id', 'in', [o.id for o in orders]),
                ('type', '=', 'internal'),
                ])
        if not internals:
            return

        query = ['OR']
        for op in internals:
            arg = ['AND',
                   ('product', '=', op.product.id),
                   ('provisioning_location', '=', op.storage_location.id),
                   ('storage_location', '=', op.provisioning_location.id),
                   ('company', '=', op.company.id),
                   ('type', '=', 'internal')]
            query.append(arg)
        if cls.search(query):
            cls.raise_user_error('concurrent_internal_op')

    @staticmethod
    def _type2field(type=None):
        t2f = {
            'purchase': 'warehouse_location',
            'internal': 'storage_location',
            }
        if type is None:
            return t2f
        else:
            return t2f[type]

    @classmethod
    def check_uniqueness(cls, orders):
        """
        Ensure uniqueness of order points. I.E that there is no several
        order point for the same location, the same product and the
        same company.
        """
        query = ['OR']
        for op in orders:
            field = cls._type2field(op.type)
            arg = ['AND',
                ('product', '=', op.product.id),
                (field, '=', getattr(op, field).id),
                ('id', '!=', op.id),
                ('company', '=', op.company.id),
                ]
            query.append(arg)
        if cls.search(query):
            cls.raise_user_error('unique_op')

    def get_rec_name(self, name):
        return "%s@%s" % (self.product.name, self.location.name)

    @classmethod
    def search_rec_name(cls, name, clause):
        res = []
        names = clause[2].split('@', 1)
        res.append(('product.template.name', clause[1], names[0]))
        if len(names) != 1 and names[1]:
            res.append(('location', clause[1], names[1]))
        return res

    def get_location(self, name):
        if self.type == 'purchase':
            return self.warehouse_location.id
        elif self.type == 'internal':
            return self.storage_location.id

    @classmethod
    def search_location(cls, name, domain=None):
        ids = []
        for type, field in cls._type2field().iteritems():
            args = [('type', '=', type)]
            for _, operator, operand in domain:
                args.append((field, operator, operand))
            ids.extend([o.id for o in cls.search(args)])
        return [('id', 'in', ids)]

    @staticmethod
    def default_company():
        return Transaction().context.get('company')
