# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import DictSchemaMixin, ModelSQL, fields
from trytond.pool import Pool


class DictSchema(DictSchemaMixin, ModelSQL):
    'Dict Schema'
    __name__ = 'test.dict.schema'


class Dict(ModelSQL):
    'Dict'
    __name__ = 'test.dict'
    dico = fields.Dict('test.dict.schema', 'Test Dict')
    dico_string = dico.translated('dico')
    dico_string_keys = dico.translated('dico', 'keys')


class DictDefault(ModelSQL):
    'Dict Default'
    __name__ = 'test.dict_default'
    dico = fields.Dict(None, 'Test Dict')

    @staticmethod
    def default_dico():
        return dict(a=1)


class DictRequired(ModelSQL):
    'Dict Required'
    __name__ = 'test.dict_required'
    dico = fields.Dict(None, 'Test Dict', required=True)


class DictText(ModelSQL):
    'Dict TEXT'
    __name__ = 'test.dict_text'
    dico = fields.Dict('test.dict.schema', 'Test Dict')
    dico._sql_type = 'TEXT'


class DictNoSchema(ModelSQL):
    "Dict No Schema"
    __name__ = 'test.dict_noschema'
    dico = fields.Dict(None, "Dict")


class DictUnaccentedOn(ModelSQL):
    "Dict Unaccented On"
    __name__ = 'test.dict_unaccented_on'
    dico = fields.Dict(None, "Dict")


class DictUnaccentedOff(ModelSQL):
    "Dict Unaccented Off"
    __name__ = 'test.dict_unaccented_off'
    dico = fields.Dict(None, "Dict")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.dico.search_unaccented = False


def register(module):
    Pool.register(
        DictSchema,
        Dict,
        DictDefault,
        DictRequired,
        DictText,
        DictNoSchema,
        DictUnaccentedOn,
        DictUnaccentedOff,
        module=module, type_='model')
