# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Eval


class Char(ModelSQL):
    __name__ = 'test.char'
    char = fields.Char("Char")
    char_lstripped = fields.Char("Char", strip='leading')
    char_rstripped = fields.Char("Char", strip='trailing')
    char_unstripped = fields.Char("Char", strip=False)


class CharDefault(ModelSQL):
    __name__ = 'test.char_default'
    char = fields.Char("Char")

    @staticmethod
    def default_char():
        return 'Test'


class CharRequired(ModelSQL):
    __name__ = 'test.char_required'
    char = fields.Char("Char", required=True)


class CharSize(ModelSQL):
    __name__ = 'test.char_size'
    char = fields.Char("Char", size=5)


class CharSizePYSON(ModelSQL):
    __name__ = 'test.char_size_pyson'
    char = fields.Char(
        "Char", size=Eval('size', 0),
        depends=['size'])
    size = fields.Integer("Size")


class CharTranslate(ModelSQL):
    __name__ = 'test.char_translate'
    char = fields.Char("Char", translate=True)
    char_lstripped = fields.Char("Char", strip='leading', translate=True)
    char_rstripped = fields.Char("Char", strip='trailing', translate=True)
    char_unstripped = fields.Char("Char", strip=False, translate=True)
    char_translated = char.translated('char')


class CharUnaccentedOn(ModelSQL):
    __name__ = 'test.char_unaccented_on'
    char = fields.Char("Char")


class CharUnaccentedOff(ModelSQL):
    __name__ = 'test.char_unaccented_off'
    char = fields.Char("Char")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.char.search_unaccented = False


class CharUnaccentedTranslate(ModelSQL):
    __name__ = 'test.char_unaccented_translate'
    char = fields.Char("Char", translate=True)


def register(module):
    Pool.register(
        Char,
        CharDefault,
        CharRequired,
        CharSize,
        CharSizePYSON,
        CharTranslate,
        CharUnaccentedOn,
        CharUnaccentedOff,
        CharUnaccentedTranslate,
        module=module, type_='model')
