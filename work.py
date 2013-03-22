#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from itertools import groupby
from decimal import Decimal

from trytond.model import ModelView, fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool, PYSONEncoder
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateAction
from trytond.tools import reduce_ids


__all__ = ['Work', 'OpenInvoice']
__metaclass__ = PoolMeta

INVOICE_METHODS = [
    ('manual', 'Manual'),
    ('effort', 'On Effort'),
    ('timesheet', 'On Timesheet'),
    ]


class Work:
    __name__ = 'project.work'
    project_invoice_method = fields.Selection(INVOICE_METHODS,
        'Invoice Method',
        states={
            'readonly': Bool(Eval('invoiced_hours')),
            'required': Eval('type') == 'project',
            'invisible': Eval('type') != 'project',
            },
        depends=['invoiced_hours', 'type'])
    invoice_method = fields.Function(fields.Selection(INVOICE_METHODS,
            'Invoice Method'), 'get_invoice_method')
    invoiced_hours = fields.Function(fields.Float('Invoiced Hours',
            digits=(16, 2),
            states={
                'invisible': Eval('invoice_method') == 'manual',
                },
            depends=['invoice_method']), 'get_invoice_values')
    hours_to_invoice = fields.Function(fields.Float('Hours to Invoice',
            digits=(16, 2),
            states={
                'invisible': Eval('invoice_method') == 'manual',
                },
            depends=['invoice_method']), 'get_invoice_values')
    invoiced_amount = fields.Function(fields.Numeric('Invoiced Amount',
            digits=(16, Eval('currency_digits', 2)),
            states={
                'invisible': Eval('invoice_method') == 'manual',
                },
            depends=['currency_digits', 'invoice_method']),
        'get_invoice_values')
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
                    'readonly': ~Eval('hours_to_invoice'),
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
        else:
            return self.parent.invoice_method

    @staticmethod
    def default_invoiced_hours():
        return 0.

    @staticmethod
    def _get_invoiced_hours_manual(works):
        return {}

    @staticmethod
    def _get_invoiced_hours_effort(works):
        return dict((w.id, w.effort) for w in works
            if w.invoice_line)

    @classmethod
    def _get_invoiced_hours_timesheet(cls, works):
        return cls._get_hours_timesheet(works, True)

    @staticmethod
    def default_hours_to_invoice():
        return 0.

    @staticmethod
    def _get_hours_to_invoice_manual(works):
        return {}

    @staticmethod
    def _get_hours_to_invoice_effort(works):
        return dict((w.id, w.effort) for w in works
            if w.state == 'done' and not w.invoice_line)

    @classmethod
    def _get_hours_to_invoice_timesheet(cls, works):
        return cls._get_hours_timesheet(works, False)

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

        with Transaction().set_user(0, set_context=True):
            invoice_lines = InvoiceLine.browse([
                    w.invoice_line.id for w in works
                    if w.invoice_line])

        id2invoice_lines = dict((l.id, l) for l in invoice_lines)
        amounts = {}
        for work in works:
            if work.invoice_line:
                invoice_line = id2invoice_lines[work.invoice_line.id]
                amounts[work.id] = invoice_line.amount
            else:
                amounts[work.id] = Decimal(0)
        return amounts

    @staticmethod
    def _get_invoiced_amount_timesheet(works):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')

        with Transaction().set_user(0, set_context=True):
            invoice_lines = InvoiceLine.browse([
                    t.invoice_line.id for w in works
                    for t in w.work.timesheet_lines
                    if t.invoice_line])

        id2invoice_lines = dict((l.id, l) for l in invoice_lines)
        amounts = {}
        for work in works:
            amounts[work.id] = Decimal(0)
            for timesheet_line in work.work.timesheet_lines:
                if not timesheet_line.invoice_line:
                    continue
                invoice_line = id2invoice_lines[timesheet_line.invoice_line.id]
                amounts[work.id] += (invoice_line.unit_price
                    * Decimal(str(timesheet_line.hours)))
        return amounts

    @staticmethod
    def _get_hours_timesheet(works, invoiced):
        pool = Pool()
        TimesheetLine = pool.get('timesheet.line')
        cursor = Transaction().cursor

        hours = {}
        ids = [w.id for w in works]
        for i in range(0, len(ids), cursor.IN_MAX):
            sub_ids = ids[i:i + cursor.IN_MAX]
            red_sql, red_ids = reduce_ids('work', sub_ids)
            cursor.execute('SELECT work, SUM(hours) '
                'FROM "' + TimesheetLine._table + '" '
                'WHERE ' + red_sql + ' '
                    'AND invoice_line IS ' + (
                    'NOT NULL ' if invoiced else 'NULL ') +
                'GROUP BY work', red_ids)
            hours.update(dict(i for i in cursor.fetchall()))
        return hours

    @classmethod
    def get_invoice_values(cls, works, name):
        works += cls.search([
                ('parent', 'child_of', [w.id for w in works]),
                ])

        values = {}
        method2works = {}
        for work in works:
            method2works.setdefault(work.invoice_method, []).append(work)
        for method, m_works in method2works.iteritems():
            method = getattr(cls, '_get_%s_%s' % (name, method))
            values.update(method(m_works))

        default = getattr(cls, 'default_%s' % name)()
        return cls.sum_tree(works, lambda w: values.get(w.id, default))

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
                    klass.write(records, {
                            'invoice_line': invoice_line.id,
                            })
        with Transaction().set_user(0, set_context=True):
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

        with Transaction().set_user(0, set_context=True):
            return Invoice(
                company=self.company,
                type='out_invoice',
                journal=journal,
                party=self.party,
                invoice_address=self.party.address_get(type='invoice'),
                currency=self.company.currency,
                account=self.party.account_receivable,
                payment_term=self.party.customer_payment_term,
                description=self.work.name,
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

        with Transaction().set_user(0, set_context=True):
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
            if party.customer_taxes_used:
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
        if not self.invoice_line and self.effort and self.state == 'done':
            if not self.product:
                self.raise_user_error('missing_product', (self.rec_name,))
            elif self.list_price is None:
                self.raise_user_error('missing_list_price', (self.rec_name,))
            return [{
                    'product': self.product,
                    'quantity': self.effort,
                    'unit_price': self.list_price,
                    'origin': self,
                    'description': self.work.name,
                    }]
        return []

    def _get_lines_to_invoice_timesheet(self):
        if self.work.timesheet_lines:
            if not self.product:
                self.raise_user_error('missing_product', (self.rec_name,))
            elif self.list_price is None:
                self.raise_user_error('missing_list_price', (self.rec_name,))
            return [{
                    'product': self.product,
                    'quantity': l.hours,
                    'unit_price': self.list_price,
                    'origin': l,
                    'description': self.work.name,
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
            for timesheet_line in work.work.timesheet_lines:
                if (timesheet_line.invoice_line
                        and timesheet_line.invoice_line.invoice):
                    invoice_ids.add(timesheet_line.invoice_line.invoice.id)
        encoder = PYSONEncoder()
        action['pyson_domain'] = encoder.encode(
            [('id', 'in', list(invoice_ids))])
        action['pyson_search_value'] = encoder.encode([])
        return action, {}
