# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.model import ModelView, Workflow, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

from .common import IncotermAvailableMixin, IncotermMixin


class Sale(IncotermAvailableMixin, metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.incoterm_location.search_context['incoterm_type'] = 'sale'

    @property
    @fields.depends('party')
    def _party_incoterms(self):
        return self.party.sale_incoterms if self.party else []

    def _get_shipment_sale(self, Shipment, key):
        pool = Pool()
        ShipmentOut = pool.get('stock.shipment.out')
        shipment = super()._get_shipment_sale(Shipment, key)
        if isinstance(shipment, ShipmentOut):
            shipment.incoterm = self.incoterm
            shipment.incoterm_location = self.incoterm_location
        return shipment

    def _get_shipment_grouping_fields(self, shipment):
        return super()._get_shipment_grouping_fields(shipment) | {
            'incoterm', 'incoterm_location'}

    @property
    @fields.depends('company', 'warehouse', 'shipment_address', 'sale_date')
    def _incoterm_required(self):
        if self.company and self.company.incoterms:
            if (self.warehouse and self.warehouse.address
                    and self.shipment_address):
                from_country = self.warehouse.address.country
                if from_country:
                    from_europe = from_country.is_member(
                        'country.organization_eu',
                        self.sale_date)
                else:
                    from_europe = None
                to_country = self.shipment_address.country
                if to_country:
                    to_europe = to_country.is_member(
                        'country.organization_eu',
                        self.sale_date)
                else:
                    to_europe = None
                return (
                    (from_country != to_country)
                    and not (from_europe and to_europe))
        return False

    def check_for_quotation(self):
        from trytond.modules.sale.exceptions import SaleQuotationError
        super().check_for_quotation()
        if not self.incoterm and self._incoterm_required:
            for line in self.lines:
                if line.movable:
                    raise SaleQuotationError(
                        gettext('incoterm'
                            '.msg_sale_incoterm_required_for_quotation',
                            sale=self.rec_name))


class Sale_Carrier(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @fields.depends('carrier', 'shipment_cost_method')
    def _get_incoterm_pattern(self):
        pattern = super()._get_incoterm_pattern()
        if self.carrier:
            pattern['mode'] = self.carrier.mode
            pattern['carrier'] = (
                'seller' if self.shipment_cost_method else 'buyer')
        return pattern

    @fields.depends(methods=['_set_default_incoterm'])
    def on_change_carrier(self):
        try:
            super_on_change = super().on_change_carrier
        except AttributeError:
            pass
        else:
            super_on_change()
        self._set_default_incoterm()

    @fields.depends(methods=['_set_default_incoterm'])
    def on_change_shipment_cost_method(self):
        try:
            super_on_change = super().on_change_shipment_cost_method
        except AttributeError:
            pass
        else:
            super_on_change()
        self._set_default_incoterm()


class Sale_WebShop(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @property
    @fields.depends('web_shop')
    def _party_incoterms(self):
        incoterms = super()._party_incoterms
        if self.web_shop:
            incoterms = []
        return incoterms

    @classmethod
    @ModelView.button
    @Workflow.transition('quotation')
    def quote(cls, sales):
        for sale in sales:
            if sale.web_shop and sale._incoterm_required:
                if not sale.incoterm:
                    sale.incoterm = sale.web_shop.default_incoterm
                if sale.incoterm and sale.incoterm.location:
                    sale.incoterm_location = sale.shipment_address
        cls.save(sales)
        super().quote(sales)


class Opportunity(IncotermMixin, metaclass=PoolMeta):
    __name__ = 'sale.opportunity'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.incoterm_location.search_context['incoterm_type'] = 'sale'

    @classmethod
    def _incoterm_readonly_state(cls):
        return ~Eval('state').in_(['lead', 'opportunity'])

    def _get_sale_opportunity(self):
        sale = super()._get_sale_opportunity()
        sale.incoterm = self.incoterm
        sale.incoterm_location = self.incoterm_location
        return sale
