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
    def write(cls, *args):
        actions = iter(args)
        for lines, values in zip(actions, actions):
            if (('duration' in values or 'work' in values)
                    and any(l.invoice_line for l in lines)):
                raise AccessError(
                    gettext('project_invoice.msg_modify_invoiced_line'))
        super().write(*args)

    @classmethod
    def delete(cls, records):
        if any(r.invoice_line for r in records):
            raise AccessError(
                gettext('project_invoice.msg_delete_invoiced_line'))
        super().delete(records)
