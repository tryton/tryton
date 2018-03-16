# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.pool import Pool


class Char(ModelSQL):
    'Char'
    __name__ = 'test.char'
    char = fields.Char("Char")


class CharDefault(ModelSQL):
    'Char Default'
    __name__ = 'test.char_default'
    char = fields.Char("Char")

    @staticmethod
    def default_char():
        return 'Test'


class CharRequired(ModelSQL):
    'Char Required'
    __name__ = 'test.char_required'
    char = fields.Char("Char", required=True)


class CharSize(ModelSQL):
    'Char Size'
    __name__ = 'test.char_size'
    char = fields.Char("Char", size=5)


class CharTranslate(ModelSQL):
    'Char Translate'
    __name__ = 'test.char_translate'
    char = fields.Char("Char", translate=True)


class CharUnaccentedOn(ModelSQL):
    'Char Unaccented'
    __name__ = 'test.char_unaccented_on'
    char = fields.Char("Char")


class CharUnaccentedOff(ModelSQL):
    'Char Unaccented'
    __name__ = 'test.char_unaccented_off'
    char = fields.Char("Char")

    @classmethod
    def __setup__(cls):
        super(CharUnaccentedOff, cls).__setup__()
        cls.char.search_unaccented = False


class CharUnaccentedTranslate(ModelSQL):
    'Char Unaccented Translate'
    __name__ = 'test.char_unaccented_translate'
    char = fields.Char("Char", translate=True)


def register(module):
    Pool.register(
        Char,
        CharDefault,
        CharRequired,
        CharSize,
        CharTranslate,
        CharUnaccentedOn,
        CharUnaccentedOff,
        CharUnaccentedTranslate,
        module=module, type_='model')
