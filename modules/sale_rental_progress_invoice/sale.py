# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt
from decimal import Decimal

from sql import Null

from trytond.model import Check, ModelSQL, ModelView, Unique, fields
from trytond.modules.product import round_price
from trytond.modules.sale_rental import to_datetime
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.report import Report
from trytond.transaction import Transaction
from trytond.wizard import Button, StateTransition, StateView, Wizard


class Rental(metaclass=PoolMeta):
    __name__ = 'sale.rental'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'add_progress': {
                    'invisible': (
                        Eval('state').in_(['draft', 'quote'])
                        | ~Eval('has_returnable_lines')),
                    'icon': 'tryton-date',
                    'depends': ['state', 'has_returnable_lines'],
                    },
                })

    @classmethod
    @ModelView.button_action(
        'sale_rental_progress_invoice.wizard_sale_rental_add_progress')
    def add_progress(cls, rentals):
        pass


class RentalProgress(ModelSQL, ModelView):
    __name__ = 'sale.rental.progress'

    rental = fields.Many2One(
        'sale.rental', "Rental",
        required=True, ondelete='CASCADE', readonly=True)
    date = fields.Date("Date", required=True, readonly=True)
    line = fields.Many2One(
        'sale.rental.line', "Line", readonly=True,
        domain=[
            ('rental', '=', Eval('rental', -1)),
            ('id', 'in', Eval('lines', [])),
            ],
        states={
            'required': ~Eval('previous'),
            'invisible': ~Eval('line'),
            })
    previous = fields.Many2One(
        'sale.rental.progress', "Previous", readonly=True,
        domain=[
            ('rental', '=', Eval('rental', -1)),
            ('date', '<', Eval('date', None)),
            ('lines', 'in', Eval('lines', [])),
            ],
        states={
            'required': ~Eval('line'),
            'invisible': ~Eval('previous'),
            })
    lines = fields.Many2Many(
        'sale.rental.line-sale.rental.progress',
        'progress', 'line', "Lines", readonly=True,
        domain=[
            ('rental', '=', Eval('rental', -1)),
            ])

    duration = fields.Function(
        fields.TimeDelta(
            "Duration",
            states={
                'invisible': ~Eval('duration'),
                }),
        'on_change_with_duration')

    invoice_lines = fields.One2Many(
        'account.invoice.line', 'origin', "Invoice Lines", readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('rental')
        cls._order.insert(0, ('date', 'ASC'))

        t = cls.__table__()
        cls._sql_constraints = [
            ('line_unique', Unique(t, t.line),
                'sale_rental_progress_invoice.'
                'msg_sale_rental_progress_line_unique'),
            ('previous_unique', Unique(t, t.previous),
                'sale_rental_progress_invoice.'
                'msg_sale_rental_progress_previous_unique'),
            ('line_previous',
                Check(t, (t.line == Null) | (t.previous == Null)),
                'sale_rental_progress_invoice.'
                'msg_sale_rental_progress_line_previous'),
            ]

    @property
    @fields.depends('line', 'previous')
    def start(self):
        if self.line:
            return self.line.start
        elif self.previous:
            return self.previous.date

    @property
    @fields.depends('date')
    def end(self):
        return self.date

    @fields.depends('rental', methods=['start', 'end'])
    def on_change_with_duration(self, name=None):
        if self.rental:
            start = to_datetime(self.start, company=self.rental.company)
            end = to_datetime(self.end, company=self.rental.company)
            if start and end:
                return end - start

    def get_rec_name(self, name):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        converter = self.__class__.duration.converter
        duration = Report.format_timedelta(
            self.duration, converter=converter, lang=lang)
        rental = self.rental.rec_name
        return f'{duration} @ {rental}'

    def get_invoice_lines(self, line):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')

        assert line in self.lines
        if self.invoice_lines:
            return []

        tmp_line = line.__class__(
            line.id, duration=self.duration, progresses=[])
        duration_unit = tmp_line.duration_unit

        invoice_line = InvoiceLine(invoice_type='out', type='line')
        invoice_line.currency = self.rental.currency
        invoice_line.company = self.rental.company
        invoice_line.origin = self
        invoice_line.quantity = line.quantity
        invoice_line.unit = line.unit
        invoice_line.product = line.product
        invoice_line.unit_price = round_price(
            line.unit_price * Decimal(duration_unit))
        invoice_line.taxes = line.taxes
        invoice_line.account = line.product.account_rental_used
        return [invoice_line]


class RentalLine(metaclass=PoolMeta):
    __name__ = 'sale.rental.line'

    progresses = fields.Many2Many(
        'sale.rental.line-sale.rental.progress',
        'line', 'progress', "Progresses",
        domain=[
            ('rental', '=', Eval('rental', -1)),
            ],
        order=[
            ('progress.date', 'ASC'),
            ('id', None),
            ],
        states={
            'readonly': True,  # to be copied on split
            'invisible': ~Eval('progresses'),
            })

    @property
    def to_invoice(self):
        to_invoice = super().to_invoice
        return (
            to_invoice
            or any(not p.invoice_lines for p in self.progresses))

    @property
    def start_invoice(self):
        start = super().start_invoice
        if self.progresses:
            start = self.progresses[-1].end
        return start

    @property
    def duration_invoice(self):
        duration = super().duration_invoice
        if self.progresses:
            for progress in self.progresses:
                if p_duration := progress.duration:
                    duration -= p_duration
        return duration

    def get_invoice_lines(self):
        invoice_lines = super().get_invoice_lines()
        for progress in self.progresses:
            invoice_lines.extend(progress.get_invoice_lines(self))
        return invoice_lines

    def get_progress(self, date):
        pool = Pool()
        Progress = pool.get('sale.rental.progress')
        actual_start = (
            to_datetime(self.actual_start, company=self.company)
            or dt.datetime.max)
        actual_end = (
            to_datetime(self.actual_end, company=self.company)
            or dt.datetime.max)
        datetime = to_datetime(date, company=self.company)
        if actual_start < datetime < actual_end:
            progress = Progress(rental=self.rental, lines=[self])
            progress.date = date
            if self.progresses:
                progress.previous = self.progresses[-1]
            else:
                progress.line = self
            return progress

    @classmethod
    def copy(cls, lines, default=None):
        default = default.copy() if default is not None else {}
        if not Transaction().context.get('_sale_rental_line_split'):
            default.setdefault('progresses', None)
        return super().copy(lines, default=default)


class RentalLine_Progress(ModelSQL):
    __name__ = 'sale.rental.line-sale.rental.progress'

    line = fields.Many2One(
        'sale.rental.line', "Rental Line", required=True, ondelete='CASCADE')
    progress = fields.Many2One(
        'sale.rental.progress', "Progress", required=True, ondelete='CASCADE')


class RentalAddProgress(Wizard):
    __name__ = 'sale.rental.add_progress'

    start = StateView(
        'sale.rental.add_progress.start',
        'sale_rental_progress_invoice.'
        'sale_rental_add_progress_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Add", 'add', 'tryton-ok', default=True),
            ])
    add = StateTransition()

    def transition_add(self):
        pool = Pool()
        Progress = pool.get('sale.rental.progress')
        date = self.start.date
        progresses = []
        for rental in self.records:
            for line in rental.lines:
                if progress := line.get_progress(date):
                    progresses.append(progress)
        Progress.save(progresses)
        return 'end'


class RentalAddProgressStart(ModelView):
    __name__ = 'sale.rental.add_progress.start'

    date = fields.Date("Date", required=True)
