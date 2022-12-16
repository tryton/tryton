# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import work
from . import purchase


def register():
    Pool.register(
        work.Work,
        module='project_revenue', type_='model')
    Pool.register(
        purchase.Line,
        module='project_revenue', type_='model',
        depends=['purchase'])
