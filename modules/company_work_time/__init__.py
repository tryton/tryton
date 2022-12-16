# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import company
from . import res


def register():
    Pool.register(
        company.Company,
        res.User,
        module='company_work_time', type_='model')
