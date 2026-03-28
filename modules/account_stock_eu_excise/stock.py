# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, ModelView, Unique, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.transaction import Transaction

from .party import EXCISE_IDENTIFIER_TYPES, IDENTIFIER_TYPES


class Location(metaclass=PoolMeta):
    __name__ = 'stock.location'

    eu_excise_numbers = fields.One2Many(
        'stock.location.eu_excise_number',
        'warehouse', "Excise Number",
        states={
            'invisible': Eval('type') != 'warehouse',
            })

    def get_eu_excise_number(self, company):
        for excise_number in self.eu_excise_numbers:
            if excise_number.company == company:
                return excise_number.eu_excise_number


class WarehouseEUExciseNumber(ModelSQL, ModelView):
    __name__ = 'stock.location.eu_excise_number'

    company = fields.Many2One(
        'company.company', "Company", required=True, ondelete='CASCADE')
    warehouse = fields.Many2One(
        'stock.location', "Warehouse", required=True, ondelete='CASCADE',
        domain=[
            ('type', '=', 'warehouse'),
            ],
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    eu_excise_number = fields.Many2One(
        'party.identifier', "Excise Number", required=True,
        domain=[
            ('type', 'in', EXCISE_IDENTIFIER_TYPES),
            ('party', '=', Eval('company_party', -1)),
            ('address', '=', Eval('warehouse_address', -1)),
            ])
    company_party = fields.Function(
        fields.Many2One(
            'party.party', "Company Party",
            context={
                'company': Eval('company', -1),
                },
            depends={'company'}),
        'on_change_with_company_party')
    warehouse_address = fields.Function(
        fields.Many2One('party.address', "Warehouse Address"),
        'on_change_with_warehouse_address')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls.__access__.add('warehouse')
        cls._sql_constraints += [
            ('warehouse_company_unique',
                Unique(t, t.warehouse, t.company),
                'account_stock_eu_excise.msg_warehouse_excise_company_unique'),
            ]

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @fields.depends('company')
    def on_change_with_company_party(self, name=None):
        return self.company.party if self.company else None

    @fields.depends('warehouse', '_parent_warehouse.address')
    def on_change_with_warehouse_address(self, name=None):
        return self.warehouse.address if self.warehouse else None


class ShipmentEUExciseMixin:
    __slots__ = ()

    warehouse_eu_excise_number = fields.Function(
        fields.Many2One('party.identifier', "Warehouse Excise Number"),
        'on_change_with_warehouse_eu_excise_number')
    eu_excise_number = fields.Many2One(
        'party.identifier', "Excise Number",
        domain=[
            ('type', 'in', Eval('eu_excise_types', [])),
            ('party', '=', Eval('eu_excise_party', -1)),
            ],
        states={
            'invisible': (
                ~Eval('warehouse_eu_excise_number')
                | ~Eval('has_eu_excise_goods')),
            })
    eu_excise_types = fields.Function(
        fields.MultiSelection(IDENTIFIER_TYPES, "Excise Types"),
        'on_change_with_eu_excise_types')
    eu_excise_party = fields.Function(
        fields.Many2One(
            'party.party', "Excise Party",
            context={
                'company': Eval('company', -1),
                },
            depends=['company']),
        'on_change_with_eu_excise_party')
    has_eu_excise_goods = fields.Function(
        fields.Boolean("Has Excise Goods"),
        'on_change_with_has_eu_excise_goods')

    @fields.depends('warehouse', 'company')
    def on_change_with_warehouse_eu_excise_number(self, name=None):
        if self.warehouse:
            return self.warehouse.get_eu_excise_number(self.company)

    @fields.depends('warehouse_eu_excise_number')
    def on_change_with_eu_excise_types(self, name=None):
        types = set()
        if self.warehouse_eu_excise_number:
            types.add('eu_excise')
            types.add(self.warehouse_eu_excise_number.type)
        return list(types)

    def on_change_with_eu_excise_party(self, name=None):
        raise NotImplementedError

    @fields.depends(methods=['eu_excise_moves'])
    def on_change_with_has_eu_excise_goods(self, name=None):
        if self.warehouse_eu_excise_number:
            excise_number = self.warehouse_eu_excise_number
            for move in self.eu_excise_moves:
                if (move.product
                        and excise_number.is_excise_product(move.product)):
                    return True
        return False

    @property
    def eu_excise_moves(self):
        "The moves on which the excise duty may apply"
        raise NotImplementedError

    @classmethod
    def on_modification(cls, mode, shipments, field_names=None):
        super().on_modification(mode, shipments, field_names=field_names)
        cls._sync_eu_excise_duty(shipments)

    @classmethod
    def _sync_eu_excise_duty(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        moves = []
        for shipment in shipments:
            warehouse_excise_number = shipment.warehouse_eu_excise_number
            excise_number = shipment.eu_excise_number
            for move in shipment.eu_excise_moves:
                excise_duty = None
                if warehouse_excise_number and excise_number:
                    if (warehouse_excise_number.is_excise_product(move.product)
                            and excise_number.is_excise_product(move.product)):
                        # TODO: free
                        excise_duty = 'suspension'
                if move.eu_excise_duty != excise_duty:
                    move.eu_excise_duty = excise_duty
                    moves.append(move)
        Move.save(moves)


class ShipmentIn(ShipmentEUExciseMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    @fields.depends('supplier')
    def on_change_with_eu_excise_party(self, name=None):
        return self.supplier

    @property
    @fields.depends('incoming_moves')
    def eu_excise_moves(self):
        return self.incoming_moves


class ShipmentInReturn(ShipmentEUExciseMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.eu_excise_number.domain = [
            cls.eu_excise_number.domain,
            ('address', '=', Eval('delivery_address', -1)),
            ]

    @fields.depends('supplier')
    def on_change_with_eu_excise_party(self, name=None):
        return self.supplier

    @property
    @fields.depends('moves')
    def eu_excise_moves(self):
        return self.moves


class ShipmentOut(ShipmentEUExciseMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.eu_excise_number.domain = [
            cls.eu_excise_number.domain,
            ('address', '=', Eval('delivery_address', -1)),
            ]

    @fields.depends('customer')
    def on_change_with_eu_excise_party(self, name=None):
        return self.customer

    @property
    @fields.depends('outgoing_moves')
    def eu_excise_moves(self):
        return self.outgoing_moves


class ShipmentOutReturn(ShipmentEUExciseMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'

    @fields.depends('customer')
    def on_change_with_eu_excise_party(self, name=None):
        return self.customer

    @property
    @fields.depends('incoming_moves')
    def eu_excise_moves(self):
        return self.incoming_moves


class ShipmentInternal(metaclass=PoolMeta):
    __name__ = 'stock.shipment.internal'

    @classmethod
    def on_modification(cls, mode, shipments, field_names=None):
        super().on_modification(mode, shipments, field_names=field_names)
        cls._sync_eu_excise_duty(shipments)

    @classmethod
    def _sync_eu_excise_duty(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        moves = []
        for shipment in shipments:
            if (shipment.from_location.warehouse
                    == shipment.to_location.warehouse):
                continue
            if from_warehouse := shipment.from_location.warehouse:
                from_excise_number = from_warehouse.get_eu_excise_number(
                    shipment.company)
            else:
                from_excise_number = None
            if to_warehouse := shipment.to_location.warehouse:
                to_excise_number = to_warehouse.get_eu_excise_number(
                    shipment.company)
            else:
                to_excise_number = None
            for move in shipment.moves:
                excise_duty = None
                if (from_excise_number and to_excise_number
                        and from_excise_number != to_excise_number):
                    if (from_excise_number.is_excise_product(move.product)
                            and to_excise_number.is_excise_product(
                                move.product)):
                        # TODO: free
                        excise_duty = 'suspension'
                if move.eu_excise_duty != excise_duty:
                    move.eu_excise_duty = excise_duty
                    moves.append(move)
        Move.save(moves)


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    eu_excise_duty = fields.Selection([
            (None, ""),
            ('suspension', "Suspension"),
            ('free', "Free"),
            ], "Excise Duty", readonly=True,
        domain=[If(~Eval('eu_excise_duty_applicable', False),
                ('eu_excise_duty', '=', None),
                ()),
            ],
        states={
            'invisible': ~Eval('eu_excise_duty_applicable'),
            })
    eu_excise_duty_applicable = fields.Function(
        fields.Boolean("Excise Duty Applicable"),
        'on_change_with_eu_excise_duty_applicable')

    @fields.depends('from_location', 'to_location', 'company')
    def on_change_with_eu_excise_duty_applicable(self, name=None):
        if not self.from_location or not self.to_location:
            return False
        if self.from_location.warehouse == self.to_location.warehouse:
            return False
        if (self.from_location.type not in {'storage', 'view'}
                and self.to_location.type not in {'storage', 'view'}):
            return False
        return True
