#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, ModelView, fields


class Boolean(ModelSQL, ModelView):
    'Boolean'
    _name = 'tests.boolean'
    _description = __doc__
    boolean = fields.Boolean(string='Boolean', help='Test boolean',
            required=False)

Boolean()


class BooleanDefault(ModelSQL, ModelView):
    'Boolean Default'
    _name = 'tests.boolean_default'
    _description = __doc__
    boolean = fields.Boolean(string='Boolean', help='Test boolean',
            required=False)

    def default_boolean(self, cursor, user, context=None):
        return True

BooleanDefault()


class Integer(ModelSQL, ModelView):
    'Integer'
    _name = 'tests.integer'
    _description = __doc__
    integer = fields.Integer(string='Integer', help='Test integer',
            required=False)

Integer()


class IntegerDefault(ModelSQL, ModelView):
    'Integer Default'
    _name = 'tests.integer_default'
    _description = __doc__
    integer = fields.Integer(string='Integer', help='Test integer',
            required=False)

    def default_integer(self, cursor, user, context=None):
        return 5

IntegerDefault()


class IntegerRequired(ModelSQL, ModelView):
    'Integer Required'
    _name = 'tests.integer_required'
    _description = __doc__
    integer = fields.Integer(string='Integer', help='Test integer',
            required=True)

IntegerRequired()


class Float(ModelSQL, ModelView):
    'Float'
    _name = 'tests.float'
    _description = __doc__
    float = fields.Float(string='Float', help='Test float',
            required=False)

Float()


class FloatDefault(ModelSQL, ModelView):
    'Float Default'
    _name = 'tests.float_default'
    _description = __doc__
    float = fields.Float(string='Float', help='Test float',
            required=False)

    def default_float(self, cursor, user, context=None):
        return 5.5

FloatDefault()


class FloatRequired(ModelSQL, ModelView):
    'Float Required'
    _name = 'tests.float_required'
    _description = __doc__
    float = fields.Float(string='Float', help='Test float',
            required=True)

FloatRequired()


class Numeric(ModelSQL, ModelView):
    'Numeric'
    _name = 'tests.numeric'
    _description = __doc__
    numeric = fields.Numeric(string='Numeric', help='Test numeric',
            required=False)

Numeric()


class NumericDefault(ModelSQL, ModelView):
    'Numeric Default'
    _name = 'tests.numeric_default'
    _description = __doc__
    numeric = fields.Numeric(string='Numeric', help='Test numeric',
            required=False)

    def default_numeric(self, cursor, user, context=None):
        return 5.5

NumericDefault()


class NumericRequired(ModelSQL, ModelView):
    'Numeric Required'
    _name = 'tests.numeric_required'
    _description = __doc__
    numeric = fields.Numeric(string='Numeric', help='Test numeric',
            required=True)

NumericRequired()


class Char(ModelSQL, ModelView):
    'Char'
    _name = 'tests.char'
    _description = __doc__
    char = fields.Char(string='Char', size=None, help='Test char',
            required=False)

Char()


class CharDefault(ModelSQL, ModelView):
    'Char Default'
    _name = 'tests.char_default'
    _description = __doc__
    char = fields.Char(string='Char', size=None, help='Test char',
            required=False)

    def default_char(self, cursor, user, context=None):
        return 'Test'

CharDefault()


class CharRequired(ModelSQL, ModelView):
    'Char Required'
    _name = 'tests.char_required'
    _description = __doc__
    char = fields.Char(string='Char', size=None, help='Test char',
            required=True)

CharRequired()


class CharSize(ModelSQL, ModelView):
    'Char Size'
    _name = 'tests.char_size'
    _description = __doc__
    char = fields.Char(string='Char', size=5, help='Test char',
            required=False)

CharSize()


class Text(ModelSQL, ModelView):
    'Text'
    _name = 'tests.text'
    _description = __doc__
    text = fields.Text(string='Text', size=None, help='Test text',
            required=False)

Text()


class TextDefault(ModelSQL, ModelView):
    'Text Default'
    _name = 'tests.text_default'
    _description = __doc__
    text = fields.Text(string='Text', size=None, help='Test text',
            required=False)

    def default_text(self, cursor, user, context=None):
        return 'Test'

TextDefault()


class TextRequired(ModelSQL, ModelView):
    'Text Required'
    _name = 'tests.text_required'
    _description = __doc__
    text = fields.Text(string='Text', size=None, help='Test text',
            required=True)

TextRequired()


class TextSize(ModelSQL, ModelView):
    'Text Size'
    _name = 'tests.text_size'
    _description = __doc__
    text = fields.Text(string='Text', size=5, help='Test text',
            required=False)

TextSize()


class Sha(ModelSQL, ModelView):
    'Sha'
    _name = 'tests.sha'
    _description = __doc__
    sha = fields.Sha(string='Sha', help='Sha sha',
            required=False)

Sha()


class ShaDefault(ModelSQL, ModelView):
    'Sha Default'
    _name = 'tests.sha_default'
    _description = __doc__
    sha = fields.Sha(string='Sha', help='Sha sha',
            required=False)

    def default_sha(self, cursor, user, consha=None):
        return 'Sha'

ShaDefault()


class ShaRequired(ModelSQL, ModelView):
    'Sha Required'
    _name = 'tests.sha_required'
    _description = __doc__
    sha = fields.Sha(string='Sha', help='Sha sha',
            required=True)

ShaRequired()
