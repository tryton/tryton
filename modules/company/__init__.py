# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .company import *
from .cron import *
from .party import *


def register():
    Pool.register(
        Company,
        Employee,
        UserEmployee,
        User,
        Property,
        Sequence,
        SequenceStrict,
        Date,
        CompanyConfigStart,
        Cron,
        CronCompany,
        PartyConfiguration,
        Rule,
        module='company', type_='model')
    Pool.register(
        CompanyConfig,
        module='company', type_='wizard')
    Pool.register(
        LetterReport,
        module='company', type_='report')
