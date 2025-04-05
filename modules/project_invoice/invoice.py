# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt

from sql.aggregate import Sum

from trytond.i18n import gettext
from trytond.model import fields
from trytond.modules.account_invoice.exceptions import (
    InvoiceLineValidationError)
from trytond.pool import Pool, PoolMeta
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    project_invoice_works = fields.One2Many(
        'project.work', 'invoice_line',
        "Project Invoice Works", readonly=True)
    project_invoice_progresses = fields.One2Many(
        'project.work.invoiced_progress', 'invoice_line',
        "Project Invoice Progresses", readonly=True)
    project_invoice_timesheet_duration = fields.Function(
        fields.TimeDelta("Project Invoice Timesheet Duration"),
        'get_project_invoice_timesheet_duration')

    @classmethod
    def check_validate_project_invoice_quantity(cls, lines, field_names):
        pool = Pool()
        Lang = pool.get('ir.lang')
        if field_names and not (field_names & {
                    'quantity', 'project_invoice_works'}):
            return
        for line in lines:
            project_invoice_quantity = line.project_invoice_quantity
            if project_invoice_quantity is None:
                continue
            if line.unit:
                project_invoice_quantity = line.unit.round(
                    project_invoice_quantity)
            if line.quantity != project_invoice_quantity:
                lang = Lang.get()
                if line.unit:
                    quantity = lang.format_number_symbol(
                        project_invoice_quantity, line.unit)
                else:
                    quantity = lang.format_number(project_invoice_quantity)
                raise InvoiceLineValidationError(gettext(
                        'project_invoice.msg_project_invoice_line_quantity',
                        invoice_line=line.rec_name,
                        quantity=quantity,
                        ))

    @property
    def project_invoice_quantity(self):
        quantity = None
        for work in self.project_invoice_works:
            if quantity is None:
                quantity = 0
            if work.price_list_hour:
                quantity += work.effort_hours
            else:
                quantity += 1
        for progress in self.project_invoice_progresses:
            if quantity is None:
                quantity = 0
            work = progress.work
            if work.price_list_hour:
                quantity += progress.progress * work.effort_hours
            else:
                quantity += progress.progress
        if self.project_invoice_timesheet_duration is not None:
            if quantity is None:
                quantity = 0
            quantity += (
                self.project_invoice_timesheet_duration.total_seconds()
                / 60 / 60)
        return quantity

    @classmethod
    def get_project_invoice_timesheet_duration(cls, lines, name):
        pool = Pool()
        TimesheetLine = pool.get('timesheet.line')
        cursor = Transaction().connection.cursor()
        ts_line = TimesheetLine.__table__()

        durations = dict.fromkeys(map(int, lines))
        query = ts_line.select(
            ts_line.invoice_line, Sum(ts_line.duration),
            group_by=ts_line.invoice_line)
        for sub_lines in grouped_slice(lines):
            query.where = reduce_ids(
                ts_line.invoice_line, map(int, sub_lines))
            cursor.execute(*query)

            for line_id, duration in cursor:
                # SQLite uses float for SUM
                if (duration is not None
                        and not isinstance(duration, dt.timedelta)):
                    duration = dt.timedelta(seconds=duration)
                durations[line_id] = duration
        return durations

    @classmethod
    def validate_fields(cls, lines, field_names):
        super().validate_fields(lines, field_names)
        cls.check_validate_project_invoice_quantity(lines, field_names)

    @classmethod
    def copy(cls, lines, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('project_invoice_works')
        default.setdefault('project_invoice_progresses')
        return super().copy(lines, default=default)
