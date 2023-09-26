# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import (
    ModelSingleton, ModelSQL, ModelView, MultiValueMixin, ValueMixin, fields)
from trytond.model.exceptions import AccessError
from trytond.pool import Pool
from trytond.pyson import Id

from .party import IDENTIFIER_TYPES, replace_vat

party_sequence = fields.Many2One('ir.sequence', 'Party Sequence',
    domain=[
        ('sequence_type', '=', Id('party', 'sequence_type_party')),
        ],
    help="Used to generate the party code.")
party_lang = fields.Many2One("ir.lang", 'Party Language',
    help="The default language for new parties.")


class Configuration(ModelSingleton, ModelSQL, ModelView, MultiValueMixin):
    'Party Configuration'
    __name__ = 'party.configuration'

    party_sequence = fields.MultiValue(party_sequence)
    party_lang = fields.MultiValue(party_lang)
    identifier_types = fields.MultiSelection(
        IDENTIFIER_TYPES, "Identifier Types",
        help="Defines which identifier types are available.\n"
        "Leave empty for all of them.")

    @classmethod
    def __register__(cls, module):
        super().__register__(module)

        # Migration from 6.8: Use vat alias
        configuration = cls(1)
        if configuration.identifier_types:
            configuration.identifier_types = list(map(
                    replace_vat, configuration.identifier_types))

    @classmethod
    def default_party_sequence(cls, **pattern):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('party', 'sequence_party')
        except KeyError:
            return None

    def get_identifier_types(self):
        selection = self.fields_get(
            ['identifier_types'])['identifier_types']['selection']
        if self.identifier_types:
            selection = [
                (k, v) for k, v in selection if k in self.identifier_types]
        return selection

    @classmethod
    def create(cls, vlist):
        records = super().create(vlist)
        ModelView._fields_view_get_cache.clear()
        return records

    @classmethod
    def write(cls, *args):
        super().write(*args)
        ModelView._fields_view_get_cache.clear()

    @classmethod
    def delete(cls, records):
        super().delete(records)
        ModelView._fields_view_get_cache.clear()

    @classmethod
    def validate_fields(cls, records, field_names):
        super().validate_fields(records, field_names)
        cls(1).check_identifier_types(field_names)

    def check_identifier_types(self, field_names=None):
        pool = Pool()
        Identifier = pool.get('party.identifier')
        if field_names and 'identifier_types' not in field_names:
            return
        if self.identifier_types:
            identifier_types = [None, ''] + list(self.identifier_types)
            identifiers = Identifier.search([
                    ('type', 'not in', identifier_types),
                    ], limit=1, order=[])
            if identifiers:
                identifier, = identifiers
                selection = self.fields_get(
                    ['identifier_types'])['identifier_types']['selection']
                selection = dict(selection)
                raise AccessError(gettext(
                        'party.msg_identifier_type_remove',
                        type=selection.get(identifier.type, identifier.type),
                        identifier=identifier.rec_name,
                        ))


class ConfigurationSequence(ModelSQL, ValueMixin):
    'Party Configuration Sequence'
    __name__ = 'party.configuration.party_sequence'
    party_sequence = party_sequence

    @classmethod
    def check_xml_record(cls, records, values):
        pass


class ConfigurationLang(ModelSQL, ValueMixin):
    'Party Configuration Lang'
    __name__ = 'party.configuration.party_lang'
    party_lang = party_lang
