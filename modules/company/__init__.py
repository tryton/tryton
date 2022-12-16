# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import company, ir, party, res
from .company import CompanyReport

__all__ = ['register', 'CompanyReport']


def register():
    Pool.register(
        company.Company,
        company.Employee,
        company.CompanyConfigStart,
        res.UserCompany,
        res.UserEmployee,
        res.User,
        ir.Sequence,
        ir.SequenceStrict,
        ir.Date,
        ir.Rule,
        ir.Cron,
        ir.CronCompany,
        ir.EmailTemplate,
        party.Configuration,
        party.ConfigurationLang,
        party.Party,
        party.PartyLang,
        party.ContactMechanism,
        party.ContactMechanismLanguage,
        module='company', type_='model')
    Pool.register(
        company.CompanyConfig,
        party.Replace,
        party.Erase,
        module='company', type_='wizard')
    Pool.register(
        party.LetterReport,
        module='company', type_='report')
