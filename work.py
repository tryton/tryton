# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import division

from itertools import groupby
from collections import defaultdict
from decimal import Decimal
import datetime

from sql import Null
from sql.aggregate import Sum

from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool, PYSONEncoder
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateAction
from trytond.tools import reduce_ids, grouped_slice


__all__ = ['Work', 'WorkInvoicedProgress', 'OpenInvoice']

INVOICE_METHODS = [
    ('manual', 'Manual'),
    ('effort', 'On Effort'),
    ('progress', 'On Progress'),
    ('timesheet', 'On Timesheet'),
    ]


class Work:
    __metaclass__ = PoolMeta
    __name__ = 'project.work'
    project_invoice_method = fields.Selection(INVOICE_METHODS,
        'Invoice Method',
        states={
            'readonly': Bool(Eval('invoiced_duration')),
            'required': Eval('type') == 'project',
            'invisible': Eval('type') != 'project',
            },
        depends=['invoiced_duration', 'type'])
    invoice_method = fields.Function(fields.Selection(INVOICE_METHODS,
            'Invoice Method'), 'get_invoice_method')
    invoiced_duration = fields.Function(fields.TimeDelta('Invoiced Duration',
            'company_work_time',
            states={
                'invisible': Eval('invoice_method') == 'manual',
                },
            depends=['invoice_method']), 'get_total')
    duration_to_invoice = fields.Function(fields.TimeDelta(
            'Duration to Invoice', 'company_work_time',
            states={
                'invisible': Eval('invoice_method') == 'manual',
                },
            depends=['invoice_method']), 'get_total')
    invoiced_amount = fields.Function(fields.Numeric('Invoiced Amount',
            digits=(16, Eval('currency_digits', 2)),
            states={
                'invisible': Eval('invoice_method') == 'manual',
                },
            depends=['currency_digits', 'invoice_method']),
        'get_total')
    invoice_line = fields.Many2One('account.invoice.line', 'Invoice Line',
        readonly=True)
    invoiced_progress = fields.One2Many('project.work.invoiced_progress',
        'work', 'Invoiced Progress', readonly=True)

    @classmethod
    def __setup__(cls):
        super(Work, cls).__setup__()
        cls._buttons.update({
                'invoice': {
                    'invisible': ((Eval('type') != 'project')
                        | (Eval('project_invoice_method', 'manual')
                            == 'manual')),
                    'readonly': ~Eval('duration_to_invoice'),
                    },
                })
        cls._error_messages.update({
                'missing_product': 'There is no product on work "%s".',
                'missing_list_price': 'There is no list price on work "%s".',
                'missing_party': 'There is no party on work "%s".',
                })

    @staticmethod
    def default_project_invoice_method():
        return 'manual'

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default.setdefault('invoice_line', None)
        return super(Work, cls).copy(records, default=default)

    def get_invoice_method(self, name):
        if self.type == 'project':
            return self.project_invoice_method
        elif self.parent:
            return self.parent.invoice_method
        else:
            return 'manual'

    @staticmethod
    def default_invoiced_duration():
        return datetime.timedelta()

    @staticmethod
    def _get_invoiced_duration_manual(works):
        return {}

    @staticmethod
    def _get_invoiced_duration_effort(works):
        return dict((w.id, w.effort_duration) for w in works
            if w.invoice_line and w.effort_duration)

    @staticmethod
    def _get_invoiced_duration_progress(works):
        durations = {}
        for work in works:
            durations[work.id] = sum((p.effort_duration
                    for p in work.invoiced_progress if p.effort_duration),
                datetime.timedelta())
        return durations

    @classmethod
    def _get_invoiced_duration_timesheet(cls, works):
        return cls._get_duration_timesheet(works, True)

    @staticmethod
    def default_duration_to_invoice():
        return datetime.timedelta()

    @staticmethod
    def _get_duration_to_invoice_manual(works):
        return {}

    @staticmethod
    def _get_duration_to_invoice_effort(works):
        return dict((w.id, w.effort_duration) for w in works
            if w.state == 'done' and not w.invoice_line)

    @staticmethod
    def _get_duration_to_invoice_progress(works):
        durations = {}
        for work in works:
            if work.progress is None or work.effort_duration is None:
                continue
            effort_to_invoice = datetime.timedelta(
                hours=work.effort_hours * work.progress)
            effort_invoiced = sum(
                (p.effort_duration
                    for p in work.invoiced_progress),
                datetime.timedelta())
            if effort_to_invoice > effort_invoiced:
                durations[work.id] = effort_to_invoice - effort_invoiced
            else:
                durations[work.id] = datetime.timedelta()
        return durations

    @classmethod
    def _get_duration_to_invoice_timesheet(cls, works):
        return cls._get_duration_timesheet(works, False)

    @staticmethod
    def default_invoiced_amount():
        return Decimal(0)

    @staticmethod
    def _get_invoiced_amount_manual(works):
        return {}

    @staticmethod
    def _get_invoiced_amount_effort(works):
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
                amounts[work.id] = Currency.compute(invoice_currency,
                    Decimal(str(work.effort_hours)) * invoice_line.unit_price,
                    currency)
            else:
                amounts[work.id] = Decimal(0)
        return amounts

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
        work_ids = [w.id for w in works]
        for sub_ids in grouped_slice(work_ids):
            where = reduce_ids(table.id, sub_ids)
            cursor.execute(*table.join(progress,
                    condition=progress.work == table.id
                    ).join(invoice_line,
                    condition=progress.invoice_line == invoice_line.id
                    ).select(table.id,
                    Sum(progress.effort_duration * invoice_line.unit_price),
                    where=where,
                    group_by=table.id))
            for work_id, amount in cursor.fetchall():
                if isinstance(amount, datetime.timedelta):
                    amount = amount.total_seconds()
                # Amount computed in second instead of hours
                if amount is not None:
                    amount /= 60 * 60
                else:
                    amount = 0
                amounts[work_id] = amount

            cursor.execute(*table.join(company,
                    condition=table.company == company.id
                    ).select(table.id, company.currency,
                    where=where))
            work2currency.update(cursor.fetchall())

        currencies = Currency.browse(set(work2currency.itervalues()))
        id2currency = {c.id: c for c in currencies}

        for work in works:
            currency = id2currency[work2currency[work.id]]
            amounts[work.id] = currency.round(Decimal(amounts[work.id]))
        return amounts

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
                    condition=table.work == timesheet_work.id
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

        currencies = Currency.browse(set(work2currency.itervalues()))
        id2currency = {c.id: c for c in currencies}

        for work in works:
            currency = id2currency[work2currency[work.id]]
            amount = amounts.get(work.id, 0)
            if isinstance(amount, datetime.timedelta):
                amount = amount.total_seconds()
            amount = amount / 60 / 60
            amounts[work.id] = currency.round(Decimal(str(amount)))
        return amounts

    @staticmethod
    def _get_duration_timesheet(works, invoiced):
        pool = Pool()
        TimesheetLine = pool.get('timesheet.line')
        cursor = Transaction().connection.cursor()
        line = TimesheetLine.__table__()

        durations = {}
        twork2work = dict((w.work.id, w.id) for w in works if w.work)
        ids = twork2work.keys()
        for sub_ids in grouped_slice(ids):
            red_sql = reduce_ids(line.work, sub_ids)
            if invoiced:
                where = line.invoice_line != Null
            else:
                where = line.invoice_line == Null
            cursor.execute(*line.select(line.work, Sum(line.duration),
                    where=red_sql & where,
                    group_by=line.work))
            for twork_id, duration in cursor.fetchall():
                if duration:
                    # SQLite uses float for SUM
                    if not isinstance(duration, datetime.timedelta):
                        duration = datetime.timedelta(seconds=duration)
                    durations[twork2work[twork_id]] = duration
        return durations

    @classmethod
    def _get_invoice_values(cls, works, name):
        default = getattr(cls, 'default_%s' % name)
        durations = dict.fromkeys((w.id for w in works), default())
        method2works = defaultdict(list)
        for work in works:
            method2works[work.invoice_method].append(work)
        for method, m_works in method2works.iteritems():
            method = getattr(cls, '_get_%s_%s' % (name, method))
            # Re-browse for cache alignment
            durations.update(method(cls.browse(m_works)))
        return durations

    @classmethod
    def _get_invoiced_duration(cls, works):
        return cls._get_invoice_values(works, 'invoiced_duration')

    @classmethod
    def _get_duration_to_invoice(cls, works):
        return cls._get_invoice_values(works, 'duration_to_invoice')

    @classmethod
    def _get_invoiced_amount(cls, works):
        return cls._get_invoice_values(works, 'invoiced_amount')

    @classmethod
    @ModelView.button
    def invoice(cls, works):
        pool = Pool()
        Invoice = pool.get('account.invoice')

        invoices = []
        for work in works:
            invoice_lines = work._get_lines_to_invoice()
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
                origins = {}
                for line in lines:
                    origin = line['origin']
                    origins.setdefault(origin.__class__, []).append(origin)
                for klass, records in origins.iteritems():
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
            self.raise_user_error('missing_party', (self.rec_name,))

        return Invoice(
            company=self.company,
            type='out',
            journal=journal,
            party=self.party,
            invoice_address=self.party.address_get(type='invoice'),
            currency=self.company.currency,
            account=self.party.account_receivable,
            payment_term=self.party.customer_payment_term,
            description=self.name,
            )

    def _group_lines_to_invoice_key(self, line):
        "The key to group lines"
        return (('product', line['product']),
            ('unit_price', line['unit_price']),
            ('description', line['description']))

    def _get_invoice_line(self, key, invoice, lines):
        "Return a invoice line for the lines"
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        ModelData = pool.get('ir.model.data')
        Uom = pool.get('product.uom')

        hour = Uom(ModelData.get_id('product', 'uom_hour'))
        quantity = sum(l['quantity'] for l in lines)
        product = key['product']

        invoice_line = InvoiceLine()
        invoice_line.type = 'line'
        invoice_line.quantity = Uom.compute_qty(hour, quantity,
            product.default_uom)
        invoice_line.unit = product.default_uom
        invoice_line.product = product
        invoice_line.description = key['description']
        invoice_line.account = product.account_revenue_used
        invoice_line.unit_price = Uom.compute_price(hour, key['unit_price'],
            product.default_uom)

        taxes = []
        pattern = invoice_line._get_tax_rule_pattern()
        party = invoice.party
        for tax in product.customer_taxes_used:
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

    def _get_lines_to_invoice_manual(self):
        return []

    def _get_lines_to_invoice_effort(self):
        if (not self.invoice_line
                and self.effort_hours
                and self.state == 'done'):
            if not self.product:
                self.raise_user_error('missing_product', (self.rec_name,))
            elif self.list_price is None:
                self.raise_user_error('missing_list_price', (self.rec_name,))
            return [{
                    'product': self.product,
                    'quantity': self.effort_hours,
                    'unit_price': self.list_price,
                    'origin': self,
                    'description': self.name,
                    }]
        return []

    def _get_lines_to_invoice_progress(self):
        pool = Pool()
        InvoicedProgress = pool.get('project.work.invoiced_progress')
        ModelData = pool.get('ir.model.data')
        Uom = pool.get('product.uom')

        hour = Uom(ModelData.get_id('product', 'uom_hour'))

        if self.progress is None or self.effort_duration is None:
            return []

        invoiced_progress = sum(x.effort_hours for x in self.invoiced_progress)
        quantity = self.effort_hours * self.progress - invoiced_progress
        quantity = Uom.compute_qty(hour, quantity, self.product.default_uom)
        if quantity > 0:
            if not self.product:
                self.raise_user_error('missing_product', (self.rec_name,))
            elif self.list_price is None:
                self.raise_user_error('missing_list_price', (self.rec_name,))
            invoiced_progress = InvoicedProgress(work=self,
                effort_duration=datetime.timedelta(hours=quantity))
            return [{
                    'product': self.product,
                    'quantity': quantity,
                    'unit_price': self.list_price,
                    'origin': invoiced_progress,
                    'description': self.name,
                    'description': self.name,
                    }]
        return []

    def _get_lines_to_invoice_timesheet(self):
        if self.work and self.work.timesheet_lines:
            if not self.product:
                self.raise_user_error('missing_product', (self.rec_name,))
            elif self.list_price is None:
                self.raise_user_error('missing_list_price', (self.rec_name,))
            return [{
                    'product': self.product,
                    'quantity': l.hours,
                    'unit_price': self.list_price,
                    'origin': l,
                    'description': self.name,
                    } for l in self.work.timesheet_lines
                if not l.invoice_line]
        return []

    def _test_group_invoice(self):
        return (self.company, self.party)

    def _get_lines_to_invoice(self, test=None):
        "Return lines for work and children"
        lines = []
        if test is None:
            test = self._test_group_invoice()
        lines += getattr(self, '_get_lines_to_invoice_%s' %
            self.invoice_method)()
        for children in self.children:
            if children.type == 'project':
                if test != children._test_group_invoice():
                    continue
            lines += children._get_lines_to_invoice(test=test)
        return lines


class WorkInvoicedProgress(ModelView, ModelSQL):
    'Work Invoiced Progress'
    __name__ = 'project.work.invoiced_progress'
    work = fields.Many2One('project.work', 'Work', ondelete='RESTRICT',
        select=True)
    effort_duration = fields.TimeDelta('Effort', 'company_work_time')
    invoice_line = fields.Many2One('account.invoice.line', 'Invoice Line',
        ondelete='CASCADE')

    @property
    def effort_hours(self):
        if not self.effort_duration:
            return 0
        return self.effort_duration.total_seconds() / 60 / 60


class OpenInvoice(Wizard):
    'Open Invoice'
    __name__ = 'project.open_invoice'
    start_state = 'open_'
    open_ = StateAction('account_invoice.act_invoice_form')

    def do_open_(self, action):
        pool = Pool()
        Work = pool.get('project.work')
        works = Work.search([
                ('parent', 'child_of', Transaction().context['active_ids']),
                ])
        invoice_ids = set()
        for work in works:
            if work.invoice_line and work.invoice_line.invoice:
                invoice_ids.add(work.invoice_line.invoice.id)
            if work.work:
                for timesheet_line in work.work.timesheet_lines:
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
