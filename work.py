# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from collections import defaultdict

from sql.aggregate import Sum
from sql.operators import Concat

from trytond.model import fields
from trytond.pyson import Eval, Id
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.tools import reduce_ids, grouped_slice

from trytond.modules.product import price_digits

__all__ = ['Work']


class Work:
    __metaclass__ = PoolMeta
    __name__ = 'project.work'
    product = fields.Many2One('product.product', 'Product',
        domain=[
            ('type', '=', 'service'),
            ('default_uom_category', '=', Id('product', 'uom_cat_time')),
            ])
    list_price = fields.Numeric('List Price', digits=price_digits)
    revenue = fields.Function(fields.Numeric('Revenue',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_total')
    cost = fields.Function(fields.Numeric('Cost',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_total')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')

    @classmethod
    def __setup__(cls):
        pool = Pool()

        super(Work, cls).__setup__()

        try:
            pool.get('purchase.line')
        except KeyError:
            pass
        else:
            # Add purchase lines if purchase is installed
            cls.purchase_lines = fields.One2Many('purchase.line', 'work',
                'Purchase Lines', domain=[
                    ('purchase.company', '=', Eval('company', -1)),
                    ],
                depends=['company'])

    @classmethod
    def _get_cost(cls, works):
        pool = Pool()
        Line = pool.get('timesheet.line')
        Work = pool.get('timesheet.work')
        transaction = Transaction()
        cursor = transaction.connection.cursor()

        costs = dict.fromkeys([w.id for w in works], 0)

        table = cls.__table__()
        work = Work.__table__()
        line = Line.__table__()

        # Timesheet cost
        work_ids = [w.id for w in works]
        for sub_ids in grouped_slice(work_ids):
            red_sql = reduce_ids(table.id, sub_ids)
            cursor.execute(*table.join(work,
                    condition=table.work == work.id
                    ).join(line, condition=line.work == work.id
                    ).select(table.id, Sum(line.cost_price * line.duration),
                    where=red_sql,
                    group_by=[table.id]))
            for work_id, cost in cursor.fetchall():
                # SQLite stores timedelta as float
                if not isinstance(cost, float):
                    cost = cost.total_seconds()
                # Convert from seconds
                cost /= 60 * 60
                costs[work_id] += Decimal(str(cost))

        # Purchase cost
        if hasattr(cls, 'purchase_lines'):
            for work_id, cost in cls._purchase_cost(works).iteritems():
                costs[work_id] += cost

        for work in works:
            costs[work.id] = work.company.currency.round(costs[work.id])
        return costs

    @classmethod
    def _purchase_cost(cls, works):
        'Compute direct purchase cost'
        pool = Pool()
        Currency = pool.get('currency.currency')
        PurchaseLine = pool.get('purchase.line')
        InvoiceLine = pool.get('account.invoice.line')
        Invoice = pool.get('account.invoice')
        Company = pool.get('company.company')

        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        purchase_line = PurchaseLine.__table__()
        invoice_line = InvoiceLine.__table__()
        invoice = Invoice.__table__()
        company = Company.__table__()

        amounts = defaultdict(Decimal)
        work_ids = [w.id for w in works]
        work2currency = {}
        iline2work = {}
        for sub_ids in grouped_slice(work_ids):
            where = reduce_ids(table.id, sub_ids)
            cursor.execute(*table.join(purchase_line,
                    condition=purchase_line.work == table.id
                    ).join(invoice_line,
                    condition=invoice_line.origin == Concat(
                        'purchase.line,', purchase_line.id)
                    ).join(invoice,
                    condition=invoice_line.invoice == invoice.id
                    ).select(invoice_line.id, table.id,
                    where=where & ~invoice.state.in_(['draft', 'cancel'])))
            iline2work.update(cursor.fetchall())

            cursor.execute(*table.join(company,
                    condition=table.company == company.id
                    ).select(table.id, company.currency,
                    where=where))
            work2currency.update(cursor.fetchall())

        currencies = Currency.browse(set(work2currency.itervalues()))
        id2currency = {c.id: c for c in currencies}

        invoice_lines = InvoiceLine.browse(iline2work.keys())
        for invoice_line in invoice_lines:
            invoice = invoice_line.invoice
            work_id = iline2work[invoice_line.id]
            currency_id = work2currency[work_id]
            currency = id2currency[currency_id]
            if currency != invoice.currency:
                with Transaction().set_context(date=invoice.currency_date):
                    amount = Currency.compute(invoice.currency,
                        invoice_line.amount, currency)
            else:
                amount = invoice_line.amount
            amounts[work_id] += amount
        return amounts

    @classmethod
    def _get_revenue(cls, works):
        return {w.id: (w.list_price * Decimal(str(w.effort_hours))
                if w.list_price else Decimal(0))
            for w in works}

    @fields.depends('company')
    def on_change_with_currency_digits(self, name=None):
        if self.company:
            return self.company.currency.digits
        return 2

    @staticmethod
    def default_currency_digits():
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = Company(company)
            return company.currency.digits
        return 2

    @fields.depends('product', 'company')
    def on_change_product(self):
        pool = Pool()
        User = pool.get('res.user')
        ModelData = pool.get('ir.model.data')
        Uom = pool.get('product.uom')
        Currency = pool.get('currency.currency')

        if not self.product:
            return

        hour_uom = Uom(ModelData.get_id('product', 'uom_hour'))
        self.list_price = Uom.compute_price(self.product.default_uom,
            self.product.list_price, hour_uom)

        if self.company:
            user = User(Transaction().user)
            if user.company != self.company:
                if user.company.currency != self.company.currency:
                    self.list_price = Currency.compute(user.company.currency,
                        self.list_price, self.company.currency, round=False)

        digits = self.__class__.list_price.digits
        self.list_price = self.list_price.quantize(
            Decimal(str(10.0 ** -digits[1])))
