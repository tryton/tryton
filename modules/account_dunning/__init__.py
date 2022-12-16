# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import account, dunning, party


def register():
    Pool.register(
        dunning.Procedure,
        dunning.Level,
        dunning.Dunning,
        dunning.CreateDunningStart,
        dunning.ProcessDunningStart,
        party.Party,
        party.PartyDunningProcedure,
        account.Configuration,
        account.ConfigurationDefaultDunningProcedure,
        account.MoveLine,
        module='account_dunning', type_='model')
    Pool.register(
        dunning.CreateDunning,
        dunning.ProcessDunning,
        dunning.RescheduleDunning,
        module='account_dunning', type_='wizard')
