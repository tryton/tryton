# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import document, inbound_email, res, routes

__all__ = ['register', 'routes']


def register():
    Pool.register(
        res.UserApplication,
        document.IncomingConfiguration,
        document.Incoming,
        document.IncomingSplitStart,
        module='document_incoming', type_='model')
    Pool.register(
        document.IncomingSplit,
        module='document_incoming', type_='wizard')
    Pool.register(
        inbound_email.Rule,
        module='document_incoming', type_='model', depends=['inbound_email'])
