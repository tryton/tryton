# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from collections import defaultdict

from trytond.model import ModelView, Workflow, fields
from trytond.modules.product import price_digits
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    customs_unit_price = fields.Numeric(
        "Customs Unit Price", digits=price_digits,
        domain=[
            If(~Eval('unit_price_required'),
                ('unit_price', '=', None),
                ()),
            ],
        states={
            'invisible': ~Eval('unit_price_required'),
            'readonly': Eval('state') != 'draft',
            },
        help="The price used to value the goods for customs purposes.\n"
        "Leave empty to use the unit price.")


class CustomsMixin:
    __slots__ = ()

    customs_agent = fields.Many2One(
        'customs.agent', "Customs Agent",
        states={
            'readonly': Eval('state') != 'draft',
            'invisible': ~Eval('customs_international', False),
            })
    customs_international = fields.Function(fields.Boolean("International"),
        'on_change_with_customs_international')

    company_party = fields.Function(
        fields.Many2One(
            'party.party', "Company Party",
            context={
                'company': Eval('company', -1),
                'party_contact_mechanism_usage': 'invoice',
                },
            depends={'company'}),
        'on_change_with_company_party')
    tax_identifier = fields.Many2One(
        'party.identifier', "Tax Identifier", ondelete='RESTRICT',
        states={
            'readonly': Eval('state') != 'draft',
            })

    @classmethod
    def __setup__(cls):
        pool = Pool()
        Party = pool.get('party.party')
        super().__setup__()
        tax_identifier_types = Party.tax_identifier_types()
        cls.tax_identifier.domain = [
            ('party', '=', Eval('company_party', -1)),
            ('type', 'in', tax_identifier_types),
            ]

    @fields.depends(
        'effective_date', 'planned_date',
        methods=['customs_from_country', 'customs_to_country'])
    def on_change_with_customs_international(self, name=None):
        from_country = self.customs_from_country
        to_country = self.customs_to_country

        if from_country:
            from_europe = from_country.is_member(
                'country.organization_eu',
                self.effective_date or self.planned_date)
        else:
            from_europe = None
        if to_country:
            to_europe = to_country.is_member(
                'country.organization_eu',
                self.effective_date or self.planned_date)
        else:
            to_europe = None

        return (
            (from_country != to_country)
            and not (from_europe and to_europe))

    @fields.depends(
        'company', 'tax_identifier', methods=['on_change_with_company_party'])
    def on_change_company(self):
        company_party = self.on_change_with_company_party()
        if self.company:
            if self.tax_identifier:
                if self.tax_identifier.party != company_party:
                    self.tax_identifier = None
        else:
            self.tax_identifier = None

    @fields.depends('company')
    def on_change_with_company_party(self, name=None):
        return self.company.party if self.company else None

    def get_tax_identifier(self, pattern=None):
        pattern = pattern.copy() if pattern is not None else {}
        if country := self.customs_from_country:
            pattern['country'] = country.id
        return self.company.get_tax_identifier(pattern=pattern)

    @property
    def customs_from_address(self):
        raise NotImplementedError

    @property
    @fields.depends(methods=['customs_from_address'])
    def customs_from_country(self):
        if address := self.customs_from_address:
            return address.country

    @property
    @fields.depends(methods=['shipping_to_address'])
    def customs_to_country(self):
        if address := self.shipping_to_address:
            return address.country

    @property
    def customs_moves(self):
        raise NotImplementedError

    @property
    def customs_products(self):
        """Return a dictionary with quantity and weight
        per (product, price, currency, unit)"""
        products = defaultdict(lambda: {'quantity': 0, 'weight': 0})
        for move in self.customs_moves:
            if move.customs_unit_price is not None:
                price = move.customs_unit_price
            else:
                price = move.unit_price
            key = move.product, price, move.currency, move.unit
            products[key]['quantity'] += move.quantity
            products[key]['weight'] += (move.internal_weight or 0)
        return products

    def set_customs_agent(self, pattern=None):
        pool = Pool()
        AgentSelection = pool.get('customs.agent.selection')
        if self.customs_international and not self.customs_agent:
            pattern = pattern.copy() if pattern is not None else {}
            if from_country := self.customs_from_country:
                pattern.setdefault('from_country', from_country.id)
            if to_country := self.customs_to_country:
                pattern.setdefault('to_country', to_country.id)
            if customs_agent := AgentSelection.get_agent(
                    self.company, pattern):
                self.customs_agent = customs_agent

    def set_tax_identifier(self):
        if not self.tax_identifier:
            self.tax_identifier = self.get_tax_identifier()


class ShipmentOut(CustomsMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    @property
    @fields.depends('warehouse')
    def customs_from_address(self):
        if self.warehouse:
            return self.warehouse.address

    @property
    def customs_moves(self):
        return self.outgoing_moves

    @classmethod
    @ModelView.button
    @Workflow.transition('waiting')
    def wait(cls, shipments, moves=None):
        super().wait(shipments, moves=moves)
        for shipment in shipments:
            shipment.set_customs_agent()
            shipment.set_tax_identifier()
        cls.save(shipments)


class ShipmentInReturn(CustomsMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'

    @property
    @fields.depends('warehouse')
    def customs_from_address(self):
        if self.warehouse:
            return self.warehouse.address

    @property
    def customs_moves(self):
        return self.moves

    @classmethod
    @ModelView.button
    @Workflow.transition('waiting')
    def wait(cls, shipments, moves=None):
        super().wait(shipments, moves=moves)
        for shipment in shipments:
            shipment.set_customs_agent()
            shipment.set_tax_identifier()
        cls.save(shipments)
