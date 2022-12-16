# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import notification
from . import ir


def register():
    Pool.register(
        notification.Email,
        notification.EmailAttachment,
        notification.EmailLog,
        ir.Trigger,
        module='notification_email', type_='model')
