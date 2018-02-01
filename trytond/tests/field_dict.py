# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, DictSchemaMixin, fields
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


class DictJSONB(ModelSQL):
    'Dict JSONB'
    __name__ = 'test.dict_jsonb'
    dico = fields.Dict('test.dict.schema', 'Test Dict')


def register(module):
    Pool.register(
        DictSchema,
        Dict,
        DictDefault,
        DictRequired,
        DictJSONB,
        module=module, type_='model')
