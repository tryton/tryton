# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import category
from . import party
from . import address
from . import contact_mechanism
from . import configuration
from . import ir


def register():
    Pool.register(
        category.Category,
        party.Party,
        party.PartyLang,
        party.PartyCategory,
        party.Identifier,
        party.CheckVIESResult,
        party.ReplaceAsk,
        party.EraseAsk,
        address.Address,
        address.AddressFormat,
        address.SubdivisionType,
        contact_mechanism.ContactMechanism,
        contact_mechanism.ContactMechanismLanguage,
        configuration.Configuration,
        configuration.ConfigurationSequence,
        configuration.ConfigurationLang,
        ir.Email,
        ir.EmailTemplate,
        module='party', type_='model')
    Pool.register(
        party.CheckVIES,
        party.Replace,
        party.Erase,
        module='party', type_='wizard')
