# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import ir, notification


def register():
    Pool.register(
        ir.Trigger,
        ir.Email,
        notification.Email,
        notification.EmailAttachment,
        module='notification_email', type_='model')
