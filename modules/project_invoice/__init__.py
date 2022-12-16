# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import project
from . import timesheet
from . import invoice


def register():
    Pool.register(
        project.Work,
        project.WorkInvoicedProgress,
        timesheet.Line,
        invoice.InvoiceLine,
        module='project_invoice', type_='model')
    Pool.register(
        project.OpenInvoice,
        module='project_invoice', type_='wizard')
