#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from ..model import ModelSQL, ModelSingleton, fields
from ..cache import Cache
from ..config import CONFIG

__all__ = ['Configuration']


class Configuration(ModelSingleton, ModelSQL):
    'Configuration'
    __name__ = 'ir.configuration'
    language = fields.Char('language')
    _get_language_cache = Cache('ir_configuration.get_language')

    @staticmethod
    def default_language():
        return CONFIG['language']

    @classmethod
    def get_language(cls):
        language = cls._get_language_cache.get(None)
        if language is not None:
            return language
        config = cls(1)
        language = config.language
        if not language:
            language = CONFIG['language']
        cls._get_language_cache.set(None, language)
        return language
