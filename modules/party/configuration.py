# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields
from trytond.model import MultiValueMixin, ValueMixin
from trytond.pool import Pool
from trytond.tools.multivalue import migrate_property

party_sequence = fields.Many2One('ir.sequence', 'Party Sequence',
    domain=[
        ('code', '=', 'party.party'),
        ],
    help="Used to generate the party code.")
party_lang = fields.Many2One("ir.lang", 'Party Language',
    help="The default language for new parties.")


class Configuration(ModelSingleton, ModelSQL, ModelView, MultiValueMixin):
    'Party Configuration'
    __name__ = 'party.configuration'

    party_sequence = fields.MultiValue(party_sequence)
    party_lang = fields.MultiValue(party_lang)

    @classmethod
    def default_party_sequence(cls, **pattern):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('party', 'sequence_party')
        except KeyError:
            return None


class _ConfigurationValue(ModelSQL):

    _configuration_value_field = None

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)

        super(_ConfigurationValue, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append(cls._configuration_value_field)
        value_names.append(cls._configuration_value_field)
        migrate_property(
            'party.configuration', field_names, cls, value_names,
            fields=fields)


class ConfigurationSequence(_ConfigurationValue, ModelSQL, ValueMixin):
    'Party Configuration Sequence'
    __name__ = 'party.configuration.party_sequence'
    party_sequence = party_sequence
    _configuration_value_field = 'party_sequence'

    @classmethod
    def check_xml_record(cls, records, values):
        return True


class ConfigurationLang(_ConfigurationValue, ModelSQL, ValueMixin):
    'Party Configuration Lang'
    __name__ = 'party.configuration.party_lang'
    party_lang = party_lang
    _configuration_value_field = 'party_lang'
