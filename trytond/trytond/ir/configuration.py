# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import trytond.config as config
from trytond.cache import Cache
from trytond.model import ModelSingleton, ModelSQL, fields


class Configuration(ModelSingleton, ModelSQL):
    __name__ = 'ir.configuration'
    series = fields.Char("Series")
    language = fields.Char('language')
    hostname = fields.Char("Hostname", strip=False)
    _get_language_cache = Cache('ir_configuration.get_language')

    @staticmethod
    def default_language():
        return config.get('database', 'language')

    @classmethod
    def get_language(cls):
        language = cls._get_language_cache.get(None)
        if language is not None:
            return language
        language = cls(1).language
        if not language:
            language = config.get('database', 'language')
        cls._get_language_cache.set(None, language)
        return language

    def check(self):
        "Check configuration coherence on pool initialisation"
        pass

    @classmethod
    def on_modification(cls, mode, records, field_names=None):
        super().on_modification(mode, records, field_names=field_names)
        cls._get_language_cache.clear()
