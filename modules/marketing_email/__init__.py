# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import marketing
from . import ir
from . import web
from . import routes

__all__ = ['register', 'routes']


def register():
    Pool.register(
        marketing.Email,
        marketing.EmailList,
        marketing.Message,
        marketing.SendTestView,
        ir.Cron,
        web.ShortenedURL,
        module='marketing_email', type_='model')
    Pool.register(
        marketing.SendTest,
        module='marketing_email', type_='wizard')
    Pool.register(
        marketing.EmailSubscribe,
        marketing.EmailUnsubscribe,
        module='marketing_email', type_='report')
