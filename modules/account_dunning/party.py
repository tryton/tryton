# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ValueMixin, fields
from trytond.pool import Pool, PoolMeta

dunning_procedure = fields.Many2One(
    'account.dunning.procedure', "Dunning Procedure", ondelete='RESTRICT')


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'
    dunning_procedure = fields.MultiValue(dunning_procedure)
    dunning_procedures = fields.One2Many(
        'party.party.dunning_procedure', 'party', "Dunning Procedures")

    @classmethod
    def default_dunning_procedure(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        config = Configuration(1)
        dunning_procedure = config.get_multivalue(
            'default_dunning_procedure', **pattern)
        return dunning_procedure.id if dunning_procedure else None


class PartyDunningProcedure(ModelSQL, ValueMixin):
    __name__ = 'party.party.dunning_procedure'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE')
    dunning_procedure = dunning_procedure
