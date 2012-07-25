#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime

from trytond.wizard import Wizard
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.pyson import PYSONDecoder, PYSONEncoder


class OpenProductQuantitiesByWarehouse(Wizard):
    _name = 'stock.product_quantities_warehouse'

    def do_open_(self, session, action):
        pool = Pool()
        product_obj = pool.get('product.product')
        product_supplier_obj = pool.get('purchase.product_supplier')

        action, data = super(OpenProductQuantitiesByWarehouse,
            self).do_open_(session, action)

        product = product_obj.browse(Transaction().context['active_id'])
        if product.product_suppliers:
            product_supplier = product.product_suppliers[0]
            supply_date = \
                product_supplier_obj.compute_supply_date(product_supplier)
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

OpenProductQuantitiesByWarehouse()
