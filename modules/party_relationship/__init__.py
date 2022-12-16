# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import party


def register():
    Pool.register(
        party.RelationType,
        party.Relation,
        party.RelationAll,
        party.Party,
        party.ContactMechanism,
        module='party_relationship', type_='model')
