#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime

from trytond.wizard import Wizard
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.pyson import PYSONDecoder, PYSONEncoder

__all__ = ['OpenProductQuantitiesByWarehouse']


class OpenProductQuantitiesByWarehouse(Wizard):
    __name__ = 'stock.product_quantities_warehouse'

    def do_open_(self, action):
        Product = Pool().get('product.product')

        action, data = super(OpenProductQuantitiesByWarehouse,
            self).do_open_(action)

        product = Product(Transaction().context['active_id'])
        if product.product_suppliers:
            product_supplier = product.product_suppliers[0]
            supply_date = product_supplier.compute_supply_date()
            if supply_date != datetime.date.max:
                search_value = \
                    PYSONDecoder().decode(action['pyson_search_value'])
                clause = ('date', '<=', supply_date)
                if search_value and search_value[0] != 'OR':
                    search_value.append(clause)
                else:
                    search_value = [search_value, clause]
                action['pyson_search_value'] = PYSONEncoder().encode(
                    search_value)
        return action, data
