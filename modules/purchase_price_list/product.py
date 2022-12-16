# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    def _get_purchase_unit_price(self, quantity=0):
        pool = Pool()
        Date = pool.get('ir.date')
        Party = pool.get('party.party')
        Tax = pool.get('account.tax')
        UoM = pool.get('product.uom')
        context = Transaction().context
        today = Date.today()

        unit_price = super()._get_purchase_unit_price(quantity=quantity)

        if context.get('supplier'):
            supplier = Party(context['supplier'])
            price_list = supplier.get_multivalue('purchase_price_list')
            if price_list:
                context_uom = None
                if context.get('uom'):
                    context_uom = UoM(context['uom'])
                if context.get('taxes'):
                    taxes = Tax.browse(context.get('taxes'))
                uom = context_uom or self.purchase_uom
                if uom.category != self.purchase_uom.category:
                    uom = self.purchase_uom
                unit_price = price_list.compute(
                     supplier, self, unit_price, quantity, uom)
                if price_list.tax_included and taxes:
                    unit_price = Tax.reverse_compute(unit_price, taxes, today)
        return unit_price


class PriceList(metaclass=PoolMeta):
    __name__ = 'product.price_list'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.unit.selection.append(('product_purchase', "Product Purchase"))

    def get_uom(self, product):
        uom = super().get_uom(product)
        if self.unit == 'product_purchase' and product.purchase_uom:
            uom = product.purchase_uom
        return uom
