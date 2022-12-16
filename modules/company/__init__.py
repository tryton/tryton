# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .company import *
from .cron import *
from . import party


def register():
    Pool.register(
        Company,
        Employee,
        UserEmployee,
        User,
        Sequence,
        SequenceStrict,
        Date,
        CompanyConfigStart,
        Cron,
        CronCompany,
        party.Configuration,
        party.PartyConfigurationLang,
        party.Party,
        party.PartyLang,
        Rule,
        module='company', type_='model')
    Pool.register(
        CompanyConfig,
        party.PartyReplace,
        party.PartyErase,
        module='company', type_='wizard')
    Pool.register(
        LetterReport,
        module='company', type_='report')
