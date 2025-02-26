# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.modules.account.exceptions import FiscalYearNotFoundError
from trytond.pool import Pool, PoolMeta


class Sale_Incoterm(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @property
    @fields.depends('company')
    def _incoterm_required(self):
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')

        required = super()._incoterm_required

        if not required and self.company and self.company.incoterms:
            if (self.warehouse and self.warehouse.address
                    and self.shipment_address):
                try:
                    fiscalyear = FiscalYear.find(
                        self.company.id,
                        date=self.sale_date)
                except FiscalYearNotFoundError:
                    pass
                else:
                    if fiscalyear.intrastat_extended:
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
                    required = (
                        (from_country != to_country)
                        and not (from_europe and to_europe))
        return required
