# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import company, party, res

__all__ = ['register']


def register():
    Pool.register(
        party.Party,
        module='party_avatar', type_='model')
    Pool.register(
        company.Company,
        company.Employee,
        res.User,
        module='party_avatar', type_='model', depends=['company'])
