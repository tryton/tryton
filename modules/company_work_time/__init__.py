#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .company import *
from .res import *


def register():
    Pool.register(
        Company,
        User,
        module='company_work_time', type_='model')
