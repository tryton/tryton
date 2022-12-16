#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
from sql import Literal
from sql.aggregate import Count

from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval, If
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond import backend

__all__ = ['Template', 'Product', 'ProductSupplier', 'ProductSupplierPrice']
__metaclass__ = PoolMeta


class Template:
    __name__ = "product.template"
    purchasable = fields.Boolean('Purchasable', states={
            'readonly': ~Eval('active', True),
            }, depends=['active'])
    product_suppliers = fields.One2Many('purchase.product_supplier',
        'product', 'Suppliers', states={
            'readonly': ~Eval('active', True),
            'invisible': (~Eval('purchasable', False)
                | ~Eval('context', {}).get('company')),
            }, depends=['active', 'purchasable'])
    purchase_uom = fields.Many2One('product.uom', 'Purchase UOM', states={
            'readonly': ~Eval('active'),
            'invisible': ~Eval('purchasable'),
            'required': Eval('purchasable', False),
            },
        domain=[('category', '=', Eval('default_uom_category'))],
        depends=['active', 'purchasable', 'default_uom_category'])

    @classmethod
    def __setup__(cls):
        super(Template, cls).__setup__()
        cls._error_messages.update({
                'change_purchase_uom': ('Purchase prices are based '
                    'on the purchase uom, are you sure to change it?'),
                })
        required = ~Eval('account_category') & Eval('purchasable', False)
        if not cls.account_expense.states.get('required'):
            cls.account_expense.states['required'] = required
        else:
            cls.account_expense.states['required'] = (
                cls.account_expense.states['required'] | required)
        if 'account_category' not in cls.account_expense.depends:
            cls.account_expense.depends.append('account_category')
        if 'purchasable' not in cls.account_expense.depends:
            cls.account_expense.depends.append('purchasable')

    @fields.depends('default_uom', 'purchase_uom', 'purchasable')
    def on_change_with_purchase_uom(self):
        if self.default_uom:
            if self.purchase_uom:
                if self.default_uom.category == self.purchase_uom.category:
                    return self.purchase_uom.id
                else:
                    return self.default_uom.id
            else:
                return self.default_uom.id

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        for templates, values in zip(actions, actions):
            if not values.get("purchase_uom"):
                continue
            for template in templates:
                if not template.purchase_uom:
                    continue
                if template.purchase_uom.id == values["purchase_uom"]:
                    continue
                for product in template.products:
                    if not product.product_suppliers:
                        continue
                    cls.raise_user_warning(
                            '%s@product_template' % template.id,
                            'change_purchase_uom')
        super(Template, cls).write(*args)


class Product:
    __name__ = 'product.product'

    @classmethod
    def get_purchase_price(cls, products, quantity=0):
        '''
        Return purchase price for product ids.
        The context that can have as keys:
            uom: the unit of measure
            supplier: the supplier party id
            currency: the currency id for the returned price
        '''
        pool = Pool()
        Uom = pool.get('product.uom')
        User = pool.get('res.user')
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')

        today = Date.today()
        res = {}

        uom = None
        if Transaction().context.get('uom'):
            uom = Uom(Transaction().context['uom'])

        currency = None
        if Transaction().context.get('currency'):
            currency = Currency(Transaction().context['currency'])

        user = User(Transaction().user)

        for product in products:
            res[product.id] = product.cost_price
            default_uom = product.default_uom
            default_currency = (user.company.currency if user.company
                else None)
            if not uom:
                uom = default_uom
            if (Transaction().context.get('supplier')
                    and product.product_suppliers):
                supplier_id = Transaction().context['supplier']
                for product_supplier in product.product_suppliers:
                    if product_supplier.party.id == supplier_id:
                        for price in product_supplier.prices:
                            if Uom.compute_qty(product.purchase_uom,
                                    price.quantity, uom) <= quantity:
                                res[product.id] = price.unit_price
                                default_uom = product.purchase_uom
                                default_currency = product_supplier.currency
                        break
            res[product.id] = Uom.compute_price(default_uom, res[product.id],
                uom)
            if currency and default_currency:
                date = Transaction().context.get('purchase_date') or today
                with Transaction().set_context(date=date):
                    res[product.id] = Currency.compute(default_currency,
                        res[product.id], currency, round=False)
        return res


class ProductSupplier(ModelSQL, ModelView):
    'Product Supplier'
    __name__ = 'purchase.product_supplier'
    product = fields.Many2One('product.template', 'Product', required=True,
            ondelete='CASCADE', select=True)
    party = fields.Many2One('party.party', 'Supplier', required=True,
        ondelete='CASCADE', select=True)
    name = fields.Char('Name', size=None, translate=True, select=True)
    code = fields.Char('Code', size=None, select=True)
    sequence = fields.Integer('Sequence')
    prices = fields.One2Many('purchase.product_supplier.price',
            'product_supplier', 'Prices')
    company = fields.Many2One('company.company', 'Company', required=True,
        ondelete='CASCADE', select=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ])
    delivery_time = fields.Integer('Delivery Time', help="In number of days")
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(ProductSupplier, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)
        sql_table = cls.__table__()

        # Migration from 2.2 new field currency
        created_currency = table.column_exist('currency')

        super(ProductSupplier, cls).__register__(module_name)

        # Migration from 2.2 fill currency
        if not created_currency:
            Company = Pool().get('company.company')
            company = Company.__table__()
            limit = cursor.IN_MAX
            cursor.execute(*sql_table.select(Count(sql_table.id)))
            product_supplier_count, = cursor.fetchone()
            for offset in range(0, product_supplier_count, limit):
                cursor.execute(*sql_table.join(company,
                        condition=sql_table.company == company.id
                        ).select(sql_table.id, company.currency,
                        order_by=sql_table.id,
                        limit=limit, offset=offset))
                for product_supplier_id, currency_id in cursor.fetchall():
                    cursor.execute(*sql_table.update(
                            columns=[sql_table.currency],
                            values=[currency_id],
                            where=sql_table.id == product_supplier_id))

        # Migration from 2.4: drop required on sequence
        table.not_null_action('sequence', action='remove')

        # Migration from 2.6: drop required on delivery_time
        table.not_null_action('delivery_time', action='remove')

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [table.sequence == None, table.sequence]

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.id

    @fields.depends('party')
    def on_change_party(self):
        cursor = Transaction().cursor
        changes = {
            'currency': self.default_currency(),
            }
        if self.party:
            table = self.__table__()
            cursor.execute(*table.select(table.currency,
                    where=table.party == self.party.id,
                    group_by=table.currency,
                    order_by=Count(Literal(1)).desc))
            row = cursor.fetchone()
            if row:
                changes['currency'], = row
        return changes

    def compute_supply_date(self, date=None):
        '''
        Compute the supply date for the Product Supplier at the given date
        '''
        Date = Pool().get('ir.date')

        if not date:
            date = Date.today()
        if self.delivery_time is None:
            return datetime.date.max
        return date + datetime.timedelta(self.delivery_time)

    def compute_purchase_date(self, date):
        '''
        Compute the purchase date for the Product Supplier at the given date
        '''
        Date = Pool().get('ir.date')

        if self.delivery_time is None:
            return Date.today()
        return date - datetime.timedelta(self.delivery_time)


class ProductSupplierPrice(ModelSQL, ModelView):
    'Product Supplier Price'
    __name__ = 'purchase.product_supplier.price'
    product_supplier = fields.Many2One('purchase.product_supplier',
            'Supplier', required=True, ondelete='CASCADE')
    quantity = fields.Float('Quantity', required=True, help='Minimal quantity')
    unit_price = fields.Numeric('Unit Price', required=True, digits=(16, 4))

    @classmethod
    def __setup__(cls):
        super(ProductSupplierPrice, cls).__setup__()
        cls._order.insert(0, ('quantity', 'ASC'))

    @staticmethod
    def default_quantity():
        return 0.0
