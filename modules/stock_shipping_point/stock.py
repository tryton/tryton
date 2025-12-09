# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import (
    DeactivableMixin, MatchMixin, ModelSQL, ModelView, Workflow, fields,
    sequence_ordered)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Id, If


class Location(metaclass=PoolMeta):
    __name__ = 'stock.location'

    shipping_points = fields.One2Many(
        'stock.shipping.point', 'warehouse', "Shipping Points",
        states={
            'invisible': Eval('type') != 'warehouse',
            })


class ShippingPoint(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'stock.shipping.point'

    name = fields.Char("Name", required=True)
    warehouse = fields.Many2One(
        'stock.location', "Warehouse", required=True,
        domain=[
            ('type', '=', 'warehouse'),
            ])

    @classmethod
    def default_warehouse(cls):
        Location = Pool().get('stock.location')
        return Location.get_default_warehouse()


class ShippingPointSelection(
        sequence_ordered(), MatchMixin, ModelSQL, ModelView):
    __name__ = 'stock.shipping.point.selection'

    warehouse = fields.Many2One(
        'stock.location', "Warehouse", required=True,
        domain=[
            ('type', '=', 'warehouse'),
            ])
    shipping_point = fields.Many2One(
        'stock.shipping.point', "Shipping Point", required=True,
        domain=[
            ('warehouse', '=', Eval('warehouse', -1)),
            ])

    delivery_country = fields.Many2One(
        'country.country', "Country", ondelete='CASCADE',
        help="Apply only when delivering to this country.\n"
        "Leave empty for any country.")
    contains_product_categories = fields.Many2Many(
        'stock.shipping.point.selection-contains-product.category',
        'selection', 'category', "Contains Product Categories",
        help="Apply only when at least one product shipped "
        "is in one of these categories.\n"
        "Leave empty for any product category.")

    @classmethod
    def default_warehouse(cls):
        Location = Pool().get('stock.location')
        return Location.get_default_warehouse()

    @classmethod
    def get_shipping_point(cls, shipment, pattern=None):
        pattern = pattern.copy() if pattern else {}
        pattern.update(shipment.shipping_point_pattern())
        selections = cls.search([
                ('warehouse', '=', shipment.warehouse),
                ])
        for selection in selections:
            if selection.match(pattern):
                return selection.shipping_point

    def match(self, pattern, match_none=False):
        def parents(categories):
            for category in categories:
                while category:
                    yield category
                    category = category.parent

        pattern = pattern.copy()
        products = pattern.pop('products', [])
        if self.contains_product_categories:
            categories = set()
            for product in set(products):
                categories.update(parents(product.categories_all))
            if not categories & set(self.contains_product_categories):
                return False
        return super().match(pattern, match_none=match_none)


class ShippingPointSelection_Contains_ProductCategory(ModelSQL):
    __name__ = 'stock.shipping.point.selection-contains-product.category'

    selection = fields.Many2One(
        'stock.shipping.point.selection', "Selection",
        required=True, ondelete='CASCADE')
    category = fields.Many2One(
        'product.category', "Category", required=True, ondelete='CASCADE')


class ShippingPointSelection_ProductClassification(metaclass=PoolMeta):
    __name__ = 'stock.shipping.point.selection'

    contains_product_classification = fields.Reference(
        "Contains Product Classification",
        selection='get_product_classifications',
        help="Apply only when at least one product shipped "
        "belongs to this classification.\n"
        "Leave empty for any product classification.")

    @classmethod
    def get_product_classifications(cls):
        pool = Pool()
        Template = pool.get('product.template')
        return Template.get_classification()

    def match(self, pattern, match_none=False):
        def parents(classification):
            while classification:
                yield classification
                classification = classification.parent

        products = pattern.get('products', [])
        if self.contains_product_classification:
            classifications = set()
            for product in set(products):
                if hasattr(product.classification, 'parent'):
                    classifications.update(parents(product.classification))
                else:
                    classifications.add(product.classification)
            if self.contains_product_classification not in classifications:
                return False
        return super().match(pattern, match_none=match_none)


class ShippingPointSelection_ShipmentMeasurements(metaclass=PoolMeta):
    __name__ = 'stock.shipping.point.selection'

    min_weight = fields.Float(
        "Minimal Weight", digits='weight_uom',
        domain=[
            If(Eval('max_weight'),
                ['OR',
                    ('min_weight', '=', None),
                    ('min_weight', '<=', Eval('max_weight', 0)),
                    ],
                []),
            ])
    max_weight = fields.Float(
        "Maximum Weight", digits='weight_uom',
        domain=[
            If(Eval('min_weight'),
                ['OR',
                    ('max_weight', '=', None),
                    ('max_weight', '>=', Eval('min_weight', 0)),
                    ],
                []),
            ])
    weight_uom = fields.Many2One(
        'product.uom', "Weight UoM",
        domain=[('category', '=', Id('product', 'uom_cat_weight'))],
        states={
            'required': Eval('min_weight') | Eval('max_weight'),
            })

    min_volume = fields.Float(
        "Minimal Volume", digits='volume_uom',
        domain=[
            If(Eval('max_volume'),
                ['OR',
                    ('min_volume', '=', None),
                    ('min_volume', '<=', Eval('max_volume', 0)),
                    ],
                []),
            ])
    max_volume = fields.Float(
        "Maximal Volume", digits='volume_uom',
        domain=[
            If(Eval('min_volume'),
                ['OR',
                    ('max_volume', '=', None),
                    ('max_volume', '>=', Eval('min_volume', 0)),
                    ],
                []),
            ])
    volume_uom = fields.Many2One(
        'product.uom', "Volume UoM",
        domain=[('category', '=', Id('product', 'uom_cat_volume'))],
        states={
            'required': Eval('min_volume') | Eval('max_volume'),
            })

    @classmethod
    def get_shipping_point(cls, shipment, pattern=None):
        pool = Pool()
        UoM = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')

        kg = UoM(ModelData.get_id('product', 'uom_kilogram'))
        liter = UoM(ModelData.get_id('product', 'uom_liter'))

        pattern = pattern.copy() if pattern else {}
        pattern['weight'] = UoM.compute_qty(
            shipment.weight_uom, shipment.weight, kg, round=False)
        pattern['volume'] = UoM.compute_qty(
            shipment.volume_uom, shipment.volume, liter, round=False)
        return super().get_shipping_point(shipment, pattern=pattern)

    def match(self, pattern, match_none=False):
        pool = Pool()
        UoM = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')

        kg = UoM(ModelData.get_id('product', 'uom_kilogram'))
        liter = UoM(ModelData.get_id('product', 'uom_liter'))

        pattern = pattern.copy()

        weight = pattern.pop('weight', 0)
        if self.weight_uom:
            weight = UoM.compute_qty(
                kg, weight, self.weight_uom, round=False)
            if self.min_weight and weight < self.min_weight:
                return False
            if self.max_weight and weight > self.max_weight:
                return False

        volume = pattern.pop('volume', 0)
        if self.volume_uom:
            volume = UoM.compute_qty(
                liter, volume, self.volume_uom, round=False)
            if self.min_volume and volume < self.min_volume:
                return False
            if self.max_volume and volume > self.max_volume:
                return False

        return super().match(pattern, match_none=match_none)


class ShippingPointMixin:
    __slots__ = ()

    shipping_point = fields.Many2One(
        'stock.shipping.point', "Shipping Point",
        domain=[
            ('warehouse', '=', Eval('warehouse', -1)),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            })


class ShippingPointAssignMixin(ShippingPointMixin):
    __slots__ = ()

    def shipping_point_pattern(self):
        pattern = {}
        if getattr(self, 'delivery_address', None):
            pattern['delivery_country'] = self.delivery_address.country
        pattern['products'] = {m.product for m in self.moves}
        return pattern

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, shipments):
        super().draft(shipments)
        cls.write(shipments, {'shipping_point': None})

    @classmethod
    @ModelView.button
    @Workflow.transition('waiting')
    def wait(cls, shipments, moves=None):
        pool = Pool()
        Selection = pool.get('stock.shipping.point.selection')

        super().wait(shipments, moves=moves)

        for shipment in shipments:
            if not shipment.shipping_point:
                shipment.shipping_point = Selection.get_shipping_point(
                    shipment)
        cls.save(shipments)


class ShipmentIn(ShippingPointMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'


class ShipmentInReturn(ShippingPointAssignMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'


class ShipmentOut(ShippingPointAssignMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'


class ShipmentOutReturn(ShippingPointMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'


class ShipmentInternal(ShippingPointAssignMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.internal'

    incoming_shipping_point = fields.Many2One(
        'stock.shipping.point', "Incoming Shipping Point",
        domain=[
            ('warehouse', '=', Eval('to_warehouse', -1)),
            ],
        states={
            'readonly': Eval('state') != 'shipped',
            'invisible': ~Eval('transit_location'),
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.shipping_point.string = "Outgoing Shipping Point"
        cls.shipping_point.states['invisible'] = ~Eval('transit_location')

    def shipping_point_pattern(self):
        pattern = super().shipping_point_pattern()
        if self.to_warehouse and self.to_warehouse.address:
            pattern['delivery_country'] = self.to_warehouse.address.country
        return pattern
