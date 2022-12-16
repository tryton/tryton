# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import category
from . import party
from . import address
from . import contact_mechanism
from . import configuration


def register():
    Pool.register(
        category.Category,
        party.Party,
        party.PartyLang,
        party.PartyCategory,
        party.PartyIdentifier,
        party.CheckVIESResult,
        party.PartyReplaceAsk,
        party.PartyEraseAsk,
        address.Address,
        address.AddressFormat,
        contact_mechanism.ContactMechanism,
        configuration.Configuration,
        configuration.ConfigurationSequence,
        configuration.ConfigurationLang,
        module='party', type_='model')
    Pool.register(
        party.CheckVIES,
        party.PartyReplace,
        party.PartyErase,
        module='party', type_='wizard')
