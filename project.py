# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.


from itertools import groupby
from collections import defaultdict
from decimal import Decimal
import datetime

from sql import Null
from sql.aggregate import Sum
from sql.functions import Extract
from sql.operators import Concat

from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool, If, Id, PYSONEncoder
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateAction
from trytond.tools import reduce_ids, grouped_slice

from .exceptions import InvoicingError


class Effort:

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.project_invoice_method.selection.append(
            ('effort', "On Effort"))

    @classmethod
    def _get_quantity_to_invoice_effort(cls, works):
        quantities = {}
        for work in works:
            if (work.progress == 1
                    and work.list_price
                    and not work.invoice_line):
                if work.price_list_hour:
                    quantity = work.effort_hours
                else:
                    quantity = 1
                if work.unit_to_invoice:
                    quantity = work.unit_to_invoice.round(quantity)
                quantities[work.id] = quantity
        return quantities

    @classmethod
    def _get_invoiced_amount_effort(cls, works):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        Currency = pool.get('currency.currency')

        invoice_lines = InvoiceLine.browse([
                w.invoice_line.id for w in works
                if w.invoice_line])

        id2invoice_lines = dict((l.id, l) for l in invoice_lines)
        amounts = {}
        for work in works:
            currency = work.company.currency
            if work.invoice_line:
                invoice_line = id2invoice_lines[work.invoice_line.id]
                invoice_currency = (invoice_line.invoice.currency
                    if invoice_line.invoice else invoice_line.currency)
                if work.price_list_hour:
                    amount = (
                        Decimal(str(work.effort_hours))
                        * invoice_line.unit_price)
                else:
                    amount = invoice_line.unit_price
                amounts[work.id] = Currency.compute(
                    invoice_currency, amount, currency)
            else:
                amounts[work.id] = Decimal(0)
        return amounts

    def get_origins_to_invoice(self):
        try:
            origins = super().get_origins_to_invoice()
        except AttributeError:
            origins = []
        if self.invoice_method == 'effort':
            origins.append(self)
        return origins


class Progress:

    invoiced_progress = fields.One2Many('project.work.invoiced_progress',
        'work', 'Invoiced Progress', readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.project_invoice_method.selection.append(
            ('progress', 'On Progress'))

    @classmethod
    def _get_quantity_to_invoice_progress(cls, works):
        pool = Pool()
        Progress = pool.get('project.work.invoiced_progress')

        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        progress = Progress.__table__()

        invoiced_progress = {}
        quantities = {}
        for sub_works in grouped_slice(works):
            sub_works = list(sub_works)
            where = reduce_ids(
                table.id, [x.id for x in sub_works if x.list_price])
            cursor.execute(*table.join(progress,
                    condition=progress.work == table.id
                    ).select(table.id, Sum(progress.progress),
                    where=where,
                    group_by=table.id))
            invoiced_progress.update(dict(cursor.fetchall()))

            for work in sub_works:
                delta = (
                    (work.progress or 0)
                    - invoiced_progress.get(work.id, 0.0))
                if work.list_price and delta > 0:
                    quantity = delta
                    if work.price_list_hour:
                        quantity *= work.effort_hours
                    if work.unit_to_invoice:
                        quantity = work.unit_to_invoice.round(quantity)
                    quantities[work.id] = quantity
        return quantities

    @property
    def progress_to_invoice(self):
        if self.quantity_to_invoice:
            if self.price_list_hour:
                return self.quantity_to_invoice / self.effort_hours
            else:
                return self.quantity_to_invoice

    @classmethod
    def _get_invoiced_amount_progress(cls, works):
        pool = Pool()
        Progress = pool.get('project.work.invoiced_progress')
        InvoiceLine = pool.get('account.invoice.line')
        Company = pool.get('company.company')
        Currency = pool.get('currency.currency')

        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        progress = Progress.__table__()
        invoice_line = InvoiceLine.__table__()
        company = Company.__table__()

        amounts = defaultdict(Decimal)
        work2currency = {}
        ids2work = dict((w.id, w) for w in works)
        for sub_ids in grouped_slice(ids2work.keys()):
            where = reduce_ids(table.id, sub_ids)
            cursor.execute(*table.join(progress,
                    condition=progress.work == table.id
                    ).join(invoice_line,
                    condition=progress.invoice_line == invoice_line.id
                    ).select(table.id,
                    Sum(progress.progress * invoice_line.unit_price),
                    where=where,
                    group_by=table.id))
            for work_id, amount in cursor.fetchall():
                if not isinstance(amount, Decimal):
                    amount = Decimal(str(amount))
                work = ids2work[work_id]
                if work.price_list_hour:
                    amount *= Decimal(str(work.effort_hours))
                amounts[work_id] = amount

            cursor.execute(*table.join(company,
                    condition=table.company == company.id
                    ).select(table.id, company.currency,
                    where=where))
            work2currency.update(cursor.fetchall())

        currencies = Currency.browse(set(work2currency.values()))
        id2currency = {c.id: c for c in currencies}

        for work in works:
            currency = id2currency[work2currency[work.id]]
            amounts[work.id] = currency.round(Decimal(amounts[work.id]))
        return amounts

    def get_origins_to_invoice(self):
        pool = Pool()
        InvoicedProgress = pool.get('project.work.invoiced_progress')
        try:
            origins = super().get_origins_to_invoice()
        except AttributeError:
            origins = []
        if self.invoice_method == 'progress':
            invoiced_progress = InvoicedProgress(
                work=self, progress=self.progress_to_invoice)
            origins.append(invoiced_progress)
        return origins


class Timesheet:

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.project_invoice_method.selection.append(
            ('timesheet', 'On Timesheet'))
        cls.product.domain = [
            cls.product.domain,
            If(Eval('invoice_method') == 'timesheet',
                ('default_uom_category', '=', Id('product', 'uom_cat_time')),
                ()),
            ]
        if 'invoice_method' not in cls.product.depends:
            cls.product.depends.append('invoice_method')

    @classmethod
    def _get_quantity_to_invoice_timesheet(cls, works):
        pool = Pool()
        TimesheetLine = pool.get('timesheet.line')
        cursor = Transaction().connection.cursor()
        line = TimesheetLine.__table__()

        durations = defaultdict(datetime.timedelta)
        twork2work = {tw.id: w.id for w in works for tw in w.timesheet_works}
        for sub_ids in grouped_slice(twork2work.keys()):
            red_sql = reduce_ids(line.work, sub_ids)
            cursor.execute(*line.select(line.work, Sum(line.duration),
                    where=red_sql & (line.invoice_line == Null),
                    group_by=line.work))
            for twork_id, duration in cursor.fetchall():
                if duration:
                    # SQLite uses float for SUM
                    if not isinstance(duration, datetime.timedelta):
                        duration = datetime.timedelta(seconds=duration)
                    durations[twork2work[twork_id]] += duration

        quantities = {}
        for work in works:
            duration = durations[work.id]
            if work.list_price:
                hours = duration.total_seconds() / 60 / 60
                if work.unit_to_invoice:
                    hours = work.unit_to_invoice.round(hours)
                quantities[work.id] = hours
        return quantities

    @classmethod
    def _get_invoiced_amount_timesheet(cls, works):
        pool = Pool()
        TimesheetWork = pool.get('timesheet.work')
        TimesheetLine = pool.get('timesheet.line')
        InvoiceLine = pool.get('account.invoice.line')
        Company = pool.get('company.company')
        Currency = pool.get('currency.currency')

        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        timesheet_work = TimesheetWork.__table__()
        timesheet_line = TimesheetLine.__table__()
        invoice_line = InvoiceLine.__table__()
        company = Company.__table__()

        amounts = {}
        work2currency = {}
        work_ids = [w.id for w in works]
        for sub_ids in grouped_slice(work_ids):
            where = reduce_ids(table.id, sub_ids)
            cursor.execute(*table.join(timesheet_work,
                    condition=(
                        Concat(cls.__name__ + ',', table.id)
                        == timesheet_work.origin)
                    ).join(timesheet_line,
                    condition=timesheet_line.work == timesheet_work.id
                    ).join(invoice_line,
                    condition=timesheet_line.invoice_line == invoice_line.id
                    ).select(table.id,
                    Sum(timesheet_line.duration * invoice_line.unit_price),
                    where=where,
                    group_by=table.id))
            amounts.update(cursor.fetchall())

            cursor.execute(*table.join(company,
                    condition=table.company == company.id
                    ).select(table.id, company.currency,
                    where=where))
            work2currency.update(cursor.fetchall())

        currencies = Currency.browse(set(work2currency.values()))
        id2currency = {c.id: c for c in currencies}

        for work in works:
            currency = id2currency[work2currency[work.id]]
            amount = amounts.get(work.id, 0)
            if isinstance(amount, datetime.timedelta):
                amount = amount.total_seconds()
            amount = amount / 60 / 60
            amounts[work.id] = currency.round(Decimal(str(amount)))
        return amounts

    def get_origins_to_invoice(self):
        try:
            origins = super().get_origins_to_invoice()
        except AttributeError:
            origins = []
        if self.invoice_method == 'timesheet':
            origins.extend(
                l for tw in self.timesheet_works
                for l in tw.timesheet_lines
                if not l.invoice_line)
        return origins


class Work(Effort, Progress, Timesheet, metaclass=PoolMeta):
    __name__ = 'project.work'
    project_invoice_method = fields.Selection([
            ('manual', "Manual"),
            ], "Invoice Method",
        states={
            'readonly': Bool(Eval('invoiced_amount')),
            'required': Eval('type') == 'project',
            'invisible': Eval('type') != 'project',
            },
        depends=['invoiced_amount', 'type'])
    invoice_method = fields.Function(fields.Selection(
            'get_invoice_methods', "Invoice Method"),
        'on_change_with_invoice_method')
    quantity_to_invoice = fields.Function(
        fields.Float("Quantity to Invoice"), '_get_invoice_values')
    amount_to_invoice = fields.Function(fields.Numeric("Amount to Invoice",
            digits=(16, Eval('currency_digits', 2)),
            states={
                'invisible': Eval('invoice_method') == 'manual',
                },
            depends=['currency_digits', 'invoice_method']),
        'get_total')
    invoiced_amount = fields.Function(fields.Numeric('Invoiced Amount',
            digits=(16, Eval('currency_digits', 2)),
            states={
                'invisible': Eval('invoice_method') == 'manual',
                },
            depends=['currency_digits', 'invoice_method']),
        'get_total')
    invoice_line = fields.Many2One('account.invoice.line', 'Invoice Line',
        readonly=True)

    @classmethod
    def __setup__(cls):
        super(Work, cls).__setup__()
        cls._buttons.update({
                'invoice': {
                    'invisible': ((Eval('type') != 'project')
                        | (Eval('project_invoice_method', 'manual')
                            == 'manual')),
                    'readonly': ~Eval('amount_to_invoice'),
                    'depends': [
                        'type', 'project_invoice_method', 'amount_to_invoice'],
                    },
                })

    @staticmethod
    def default_project_invoice_method():
        return 'manual'

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('invoice_line', None)
        return super(Work, cls).copy(records, default=default)

    @classmethod
    def get_invoice_methods(cls):
        field = 'project_invoice_method'
        return cls.fields_get(field)[field]['selection']

    @fields.depends('type', 'project_invoice_method',
        'parent', '_parent_parent.invoice_method')
    def on_change_with_invoice_method(self, name=None):
        if self.type == 'project':
            return self.project_invoice_method
        elif self.parent:
            return self.parent.invoice_method
        else:
            return 'manual'

    @classmethod
    def default_quantity_to_invoice(cls):
        return 0

    @classmethod
    def _get_quantity_to_invoice_manual(cls, works):
        return {}

    @classmethod
    def _get_amount_to_invoice(cls, works):
        amounts = {}
        for work in works:
            amounts[work.id] = work.company.currency.round(
                (work.invoice_unit_price or 0)
                * Decimal(str(work.quantity_to_invoice)))
        return amounts

    @classmethod
    def default_invoiced_amount(cls):
        return Decimal(0)

    @classmethod
    def _get_invoiced_amount_manual(cls, works):
        return {}

    @classmethod
    def _get_invoice_values(cls, works, name):
        default = getattr(cls, 'default_%s' % name)
        amounts = dict.fromkeys((w.id for w in works), default())
        method2works = defaultdict(list)
        for work in works:
            method2works[work.invoice_method].append(work)
        for method, m_works in method2works.items():
            method = getattr(cls, '_get_%s_%s' % (name, method))
            # Re-browse for cache alignment
            amounts.update(method(cls.browse(m_works)))
        return amounts

    @classmethod
    def _get_invoiced_amount(cls, works):
        return cls._get_invoice_values(works, 'invoiced_amount')

    @classmethod
    @ModelView.button
    def invoice(cls, works):
        pool = Pool()
        Invoice = pool.get('account.invoice')

        invoices = []
        uninvoiced = works[:]
        while uninvoiced:
            work = uninvoiced.pop(0)
            invoice_lines, uninvoiced_children = (
                work._get_all_lines_to_invoice())
            uninvoiced.extend(uninvoiced_children)
            if not invoice_lines:
                continue
            invoice = work._get_invoice()
            invoice.save()
            invoices.append(invoice)
            for key, lines in groupby(invoice_lines,
                    key=work._group_lines_to_invoice_key):
                lines = list(lines)
                key = dict(key)
                invoice_line = work._get_invoice_line(key, invoice, lines)
                invoice_line.invoice = invoice.id
                invoice_line.save()
                origins = defaultdict(list)
                for line in lines:
                    for origin in line['origins']:
                        origins[origin.__class__].append(origin)
                # TODO: remove when _check_access ignores record rule
                with Transaction().set_user(0):
                    for klass, records in origins.items():
                        klass.save(records)  # Store first new origins
                        klass.write(records, {
                                'invoice_line': invoice_line.id,
                                })
        Invoice.update_taxes(invoices)

    def _get_invoice(self):
        "Return invoice for the work"
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Journal = pool.get('account.journal')

        journals = Journal.search([
                ('type', '=', 'revenue'),
                ], limit=1)
        if journals:
            journal, = journals
        else:
            journal = None

        if not self.party:
            raise InvoicingError(
                gettext('project_invoice.msg_missing_party',
                    work=self.rec_name))

        return Invoice(
            company=self.company,
            type='out',
            journal=journal,
            party=self.party,
            invoice_address=self.party.address_get(type='invoice'),
            currency=self.company.currency,
            account=self.party.account_receivable_used,
            payment_term=self.party.customer_payment_term,
            description=self.name,
            )

    def _group_lines_to_invoice_key(self, line):
        "The key to group lines"
        return (('product', line['product']),
            ('unit', line['unit']),
            ('unit_price', line['unit_price']),
            ('description', line['description']))

    def _get_invoice_line(self, key, invoice, lines):
        "Return a invoice line for the lines"
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        AccountConfiguration = pool.get('account.configuration')
        account_config = AccountConfiguration(1)

        quantity = sum(l['quantity'] for l in lines)
        product = key['product']

        invoice_line = InvoiceLine()
        invoice_line.type = 'line'
        invoice_line.description = key['description']
        if product:
            invoice_line.account = product.account_revenue_used
            if not invoice_line.account:
                raise InvoicingError(
                    gettext(
                        'project_invoice.msg_product_missing_account_revenue',
                        work=self.rec_name,
                        product=product.rec_name))
        else:
            invoice_line.account = account_config.get_multivalue(
                'default_category_account_revenue')
            if not invoice_line.account:
                raise InvoicingError(
                    gettext('project_invoice.msg_missing_account_revenue',
                        work=self.rec_name))
        invoice_line.product = product
        invoice_line.unit_price = key['unit_price']
        invoice_line.quantity = quantity
        invoice_line.unit = key['unit']

        taxes = []
        pattern = invoice_line._get_tax_rule_pattern()
        party = invoice.party
        original_taxes = (
            product.customer_taxes_used if product else invoice.account.taxes)
        for tax in original_taxes:
            if party.customer_tax_rule:
                tax_ids = party.customer_tax_rule.apply(tax, pattern)
                if tax_ids:
                    taxes.extend(tax_ids)
                continue
            taxes.append(tax.id)
        if party.customer_tax_rule:
            tax_ids = party.customer_tax_rule.apply(None, pattern)
            if tax_ids:
                taxes.extend(tax_ids)
        invoice_line.taxes = taxes
        return invoice_line

    def _test_group_invoice(self):
        return (self.company, self.party)

    def _get_all_lines_to_invoice(self, test=None):
        "Return lines for work and children"
        lines = []
        if test is None:
            test = self._test_group_invoice()
        uninvoiced_children = []
        lines += self._get_lines_to_invoice()
        for children in self.children:
            if children.type == 'project':
                if test != children._test_group_invoice():
                    uninvoiced_children.append(children)
                    continue
            child_lines, uninvoiced = children._get_all_lines_to_invoice(
                test=test)
            lines.extend(child_lines)
            uninvoiced_children.extend(uninvoiced)
        return lines, uninvoiced_children

    def _get_lines_to_invoice(self):
        if self.quantity_to_invoice:
            if self.invoice_unit_price is None:
                raise InvoicingError(
                    gettext('project_invoice.msg_missing_list_price',
                        work=self.rec_name))
            return [{
                    'product': self.product,
                    'quantity': self.quantity_to_invoice,
                    'unit': self.unit_to_invoice,
                    'unit_price': self.invoice_unit_price,
                    'origins': self.get_origins_to_invoice(),
                    'description': self.name,
                    }]
        return []

    @property
    def invoice_unit_price(self):
        return self.list_price

    @property
    def unit_to_invoice(self):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Uom = pool.get('product.uom')
        if self.price_list_hour:
            return Uom(ModelData.get_id('product', 'uom_hour'))
        elif self.product:
            return self.product.default_uom

    def get_origins_to_invoice(self):
        return super().get_origins_to_invoice()


class WorkInvoicedProgress(ModelView, ModelSQL):
    'Work Invoiced Progress'
    __name__ = 'project.work.invoiced_progress'
    work = fields.Many2One('project.work', 'Work', ondelete='RESTRICT',
        select=True)
    progress = fields.Float('Progress', required=True,
        domain=[
            ('progress', '>=', 0),
            ])
    invoice_line = fields.Many2One('account.invoice.line', 'Invoice Line',
        ondelete='CASCADE')

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(module_name)
        sql_table = cls.__table__()
        pool = Pool()
        Work = pool.get('project.work')
        work = Work.__table__()

        created_progress = not table.column_exist('progress')
        effort_exist = table.column_exist('effort_duration')

        super().__register__(module_name)

        # Migration from 5.0: Effort renamed into to progress
        if created_progress and effort_exist:
            # Don't use UPDATE FROM because SQLite does not support it.
            value = work.select(
                (Extract('EPOCH', sql_table.effort_duration)
                    / Extract('EPOCH', work.effort_duration)),
                where=work.id == sql_table.work)
            cursor.execute(*sql_table.update([sql_table.progress], [value]))


class OpenInvoice(Wizard):
    'Open Invoice'
    __name__ = 'project.open_invoice'
    start_state = 'open_'
    open_ = StateAction('account_invoice.act_invoice_form')

    def do_open_(self, action):
        works = self.model.search([
                ('parent', 'child_of', map(int, self.records)),
                ])
        invoice_ids = set()
        for work in works:
            if work.invoice_line and work.invoice_line.invoice:
                invoice_ids.add(work.invoice_line.invoice.id)
            for twork in work.timesheet_works:
                for timesheet_line in twork.timesheet_lines:
                    if (timesheet_line.invoice_line
                            and timesheet_line.invoice_line.invoice):
                        invoice_ids.add(timesheet_line.invoice_line.invoice.id)
            if work.invoiced_progress:
                for progress in work.invoiced_progress:
                    invoice_ids.add(progress.invoice_line.invoice.id)
        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode(
            [('id', 'in', list(invoice_ids))])
        action['pyson_search_value'] = encoder.encode([])
        return action, {}
