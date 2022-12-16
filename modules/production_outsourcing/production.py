# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import hashlib
from itertools import groupby

from trytond.i18n import gettext
from trytond.model import ModelView, Workflow, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, If

from trytond.modules.product import round_price

from .exceptions import PurchaseWarning


class Routing(metaclass=PoolMeta):
    __name__ = 'production.routing'

    supplier = fields.Many2One(
        'party.party', "Supplier",
        help="The supplier to outsource the production.")
    supplier_service = fields.Many2One(
        'product.product', "Service",
        ondelete='RESTRICT',
        domain=[
            ('purchasable', '=', True),
            ('template.type', '=', 'service'),
            ],
        states={
            'required': Bool(Eval('supplier')),
            'invisible': ~Eval('supplier'),
            },
        depends=['supplier', 'supplier_service_supplier'],
        help="The service to buy to the supplier for the production.")
    supplier_service_supplier = fields.Many2One(
        'purchase.product_supplier', "Supplier's Service",
        ondelete='RESTRICT',
        domain=[
            ('template.type', '=', 'service'),
            If(Bool('supplier_service'),
                ['OR',
                    [
                        ('template.products', '=', Eval('supplier_service')),
                        ('product', '=', None),
                        ],
                    ('product', '=', Eval('supplier_service')),
                    ],
                []),
            ('party', '=', Eval('supplier', -1)),
            ],
        states={
            'invisible': ~Eval('supplier'),
            },
        depends=['supplier_service', 'supplier'],
        help="The supplier's service to buy for the production.")
    supplier_quantity = fields.Float("Quantity",
        states={
            'invisible': ~Eval('supplier_service'),
            'required': Bool(Eval('supplier_service')),
            },
        depends=['supplier_service'],
        help="The quantity to buy to produce one time the BOM.")

    @classmethod
    def default_supplier_quantity(cls):
        return 1

    @fields.depends('supplier')
    def _get_product_supplier_pattern(self):
        return {
            'party': self.supplier.id if self.supplier else -1,
            }

    @fields.depends('supplier', 'supplier_service',
        'supplier_service_supplier')
    def on_change_supplier_service(self):
        if self.supplier_service:
            product_suppliers = list(
                self.supplier_service.product_suppliers_used(
                    **self._get_product_supplier_pattern()))
            if len(product_suppliers) == 1:
                self.supplier_service_supplier, = product_suppliers
            elif (self.supplier_service_supplier
                    and (self.supplier_service_supplier
                        not in product_suppliers)):
                self.supplier_service = None

    @fields.depends('supplier_service', 'supplier_service_supplier')
    def on_change_supplier_service_supplier(self):
        if self.supplier_service_supplier:
            if self.supplier_service_supplier.product:
                self.supplier_service = self.supplier_service_supplier.product
            elif not self.supplier_service:
                products = self.supplier_service_supplier.template.products
                if len(products) == 1:
                    self.supplier_service, = products

    @classmethod
    def view_attributes(cls):
        return super(Routing, cls).view_attributes() + [
            ('//page[@id="supplier"]', 'states', {
                    'invisible': ~Eval('supplier'),
                    }),
            ]


class Production(metaclass=PoolMeta):
    __name__ = 'production'

    purchase_lines = fields.One2Many(
        'purchase.line', 'production', "Purchase Lines",
        domain=[
            ('purchase.company', '=', Eval('company', -1)),
            ],
        depends=['company'],
        help="The lines to add to the production cost.")

    def get_cost(self, name):
        pool = Pool()
        Currency = pool.get('currency.currency')
        cost = super(Production, self).get_cost(name)
        for line in self.purchase_lines:
            if line.purchase.state != 'cancelled':
                cost += Currency.compute(
                    line.purchase.currency, line.amount,
                    self.company.currency, round=False)
        return round_price(cost)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, productions):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        super(Production, cls).draft(productions)
        PurchaseLine.delete([l for p in productions for l in p.purchase_lines
                if l.purchase_state in {'draft', 'cancelled'}])

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, productions):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        super(Production, cls).cancel(productions)
        PurchaseLine.delete([l for p in productions for l in p.purchase_lines
                if l.purchase_state in {'draft', 'cancelled'}])

    @classmethod
    @ModelView.button
    @Workflow.transition('waiting')
    def wait(cls, productions):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        PurchaseLine = pool.get('purchase.line')
        Date = pool.get('ir.date')

        draft_productions = [p for p in productions if p.state == 'draft']

        super(Production, cls).wait(productions)

        today = Date.today()
        purchases = []
        lines = []

        def has_supplier(production):
            return production.routing and production.routing.supplier
        productions = cls.browse(sorted(
                filter(has_supplier, draft_productions),
                key=cls._group_purchase_key))
        for key, grouped in groupby(productions, key=cls._group_purchase_key):
            productions = list(grouped)
            try:
                purchase_date = min(p.planned_start_date or p.planned_date
                    for p in productions if p.planned_date)
            except ValueError:
                purchase_date = today
            if purchase_date < today:
                purchase_date = today
            purchase = Purchase(purchase_date=purchase_date)
            for f, v in key:
                setattr(purchase, f, v)
            purchases.append(purchase)
            for production in productions:
                line = production._get_purchase_line(purchase)
                line.purchase = purchase
                line.production = production
                lines.append(line)
        Purchase.save(purchases)
        PurchaseLine.save(lines)

    def _group_purchase_key(self):
        supplier = self.routing.supplier
        if self.routing.supplier_service_supplier:
            currency = self.routing.supplier_service_supplier.currency
        else:
            currency = self.company.currency
        return (
            ('company', self.company),
            ('party', supplier),
            ('payment_term', supplier.supplier_payment_term),
            ('warehouse', self.warehouse),
            ('currency', currency),
            ('invoice_address', supplier.address_get(type='invoice')),
            )

    def _get_purchase_line(self, purchase):
        pool = Pool()
        Line = pool.get('purchase.line')
        line = Line()
        line.product = self.routing.supplier_service
        line.product_supplier = self.routing.supplier_service_supplier
        line.unit = self.routing.supplier_service.purchase_uom
        factor = self.bom.compute_factor(
            self.product, self.quantity or 0, self.uom)
        line.quantity = line.unit.round(
            factor * self.routing.supplier_quantity)
        line.purchase = purchase
        line.on_change_product()
        return line

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, productions):
        pool = Pool()
        Warning = pool.get('res.user.warning')

        def pending_purchase(production):
            return any(l.purchase_state in {'draft', 'quotation'}
                for l in production.purchase_lines)
        pendings = list(filter(pending_purchase, productions))
        if pendings:
            names = ', '.join(p.rec_name for p in productions[:5])
            if len(pendings) > 5:
                names += '...'
            warning_name = '%s.pending_purchase.done' % hashlib.md5(
                str(pendings).encode('utf-8')).hexdigest()
            if Warning.check(warning_name):
                raise PurchaseWarning(
                    warning_name,
                    gettext('production_outsourcing.msg_pending_purchase_done',
                        productions=names))
        super(Production, cls).done(productions)
