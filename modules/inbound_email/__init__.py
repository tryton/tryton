# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import inbound_email, routes

__all__ = ['register', 'routes']


def register():
    Pool.register(
        inbound_email.Inbox,
        inbound_email.Email,
        inbound_email.Rule,
        inbound_email.RuleHeader,
        module='inbound_email', type_='model')
