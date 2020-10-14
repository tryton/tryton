# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.cache import Cache
from trytond.config import config
from trytond.model import ModelSQL, ModelSingleton, fields


class Configuration(ModelSingleton, ModelSQL):
    'Configuration'
    __name__ = 'ir.configuration'
    language = fields.Char('language')
    hostname = fields.Char("Hostname")
    _get_language_cache = Cache('ir_configuration.get_language')

    @staticmethod
    def default_language():
        return config.get('database', 'language')

    @classmethod
    def get_language(cls):
        language = cls._get_language_cache.get(None)
        if language is not None:
            return language
        config = cls(1)
        language = config.language
        if not language:
            language = config.get('database', 'language')
        cls._get_language_cache.set(None, language)
        return language

    def check(self):
        "Check configuration coherence on pool initialisation"
        pass

    @classmethod
    def create(cls, vlist):
        records = super().create(vlist)
        cls._get_language_cache.clear()
        return records

    @classmethod
    def write(cls, *args):
        super().write(*args)
        cls._get_language_cache.clear()

    @classmethod
    def delete(cls, records):
        super().delete(records)
        cls._get_language_cache.clear()
