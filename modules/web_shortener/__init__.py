# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import web
from . import routes

__all__ = ['register', 'routes']


def register():
    Pool.register(
        web.ShortenedURL,
        web.URLAccess,
        module='web_shortener', type_='model')
    Pool.register(
        module='web_shortener', type_='wizard')
    Pool.register(
        module='web_shortener', type_='report')
