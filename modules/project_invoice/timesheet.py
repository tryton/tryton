# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import fields
from trytond.model.exceptions import AccessError
from trytond.pool import PoolMeta


class Line(metaclass=PoolMeta):
    __name__ = 'timesheet.line'
    invoice_line = fields.Many2One('account.invoice.line', 'Invoice Line',
        readonly=True)

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('invoice_line', None)
        return super().copy(records, default=default)

    @classmethod
    def check_modification(cls, mode, lines, values=None, external=False):
        super().check_modification(
            mode, lines, values=values, external=external)
        if mode == 'write':
            if (values.keys() & {'duration', 'work'}
                    and any(l.invoice_line for l in lines)):
                line = next(l for l in lines if l.invoice_line)
                if 'duration' in values:
                    msg = 'msg_invoiced_timesheet_line_modify_duration'
                else:
                    msg = 'msg_invoiced_timesheet_line_modify_work'
                raise AccessError(gettext(
                        f'project_invoice.{msg}',
                        line=line.rec_name))
        elif mode == 'delete':
            if any(r.invoice_line for r in lines):
                line = next((l for l in lines if l.invoice_line))
                raise AccessError(gettext(
                        'project_invoice.msg_invoiced_timesheet_line_delete',
                        line=line.rec_name))
