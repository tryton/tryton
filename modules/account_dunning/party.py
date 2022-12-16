# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.model import ModelSQL, ValueMixin, fields
from trytond.pool import PoolMeta, Pool
from trytond.tools.multivalue import migrate_property

__all__ = ['Party', 'PartyDunningProcedure']
dunning_procedure = fields.Many2One(
    'account.dunning.procedure', "Dunning Procedure")


class Party:
    __metaclass__ = PoolMeta
    __name__ = 'party.party'
    dunning_procedure = fields.MultiValue(dunning_procedure)
    dunning_procedures = fields.One2Many(
        'party.party.dunning_procedure', 'party', "Dunning Procedures")

    @classmethod
    def default_dunning_procedure(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        config = Configuration(1)
        dunning_procedure = config.default_dunning_procedure
        return dunning_procedure.id if dunning_procedure else None


class PartyDunningProcedure(ModelSQL, ValueMixin):
    "Party Dunning Procedure"
    __name__ = 'party.party.dunning_procedure'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE', select=True)
    dunning_procedure = dunning_procedure

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)

        super(PartyDunningProcedure, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('dunning_procedure')
        value_names.append('dunning_procedure')
        migrate_property(
            'party.party', field_names, cls, value_names,
            parent='party', fields=fields)
