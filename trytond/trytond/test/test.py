#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import datetime
from decimal import Decimal
from trytond.model import ModelSQL, fields
from trytond.pyson import Eval


class Boolean(ModelSQL):
    'Boolean'
    _name = 'test.boolean'
    _description = __doc__
    boolean = fields.Boolean(string='Boolean', help='Test boolean')

Boolean()


class BooleanDefault(ModelSQL):
    'Boolean Default'
    _name = 'test.boolean_default'
    _description = __doc__
    boolean = fields.Boolean(string='Boolean', help='Test boolean')

    def default_boolean(self):
        return True

BooleanDefault()


class Integer(ModelSQL):
    'Integer'
    _name = 'test.integer'
    _description = __doc__
    integer = fields.Integer(string='Integer', help='Test integer',
            required=False)

Integer()


class IntegerDefault(ModelSQL):
    'Integer Default'
    _name = 'test.integer_default'
    _description = __doc__
    integer = fields.Integer(string='Integer', help='Test integer',
            required=False)

    def default_integer(self):
        return 5

IntegerDefault()


class IntegerRequired(ModelSQL):
    'Integer Required'
    _name = 'test.integer_required'
    _description = __doc__
    integer = fields.Integer(string='Integer', help='Test integer',
            required=True)

IntegerRequired()


class Float(ModelSQL):
    'Float'
    _name = 'test.float'
    _description = __doc__
    float = fields.Float(string='Float', help='Test float',
            required=False)

Float()


class FloatDefault(ModelSQL):
    'Float Default'
    _name = 'test.float_default'
    _description = __doc__
    float = fields.Float(string='Float', help='Test float',
            required=False)

    def default_float(self):
        return 5.5

FloatDefault()


class FloatRequired(ModelSQL):
    'Float Required'
    _name = 'test.float_required'
    _description = __doc__
    float = fields.Float(string='Float', help='Test float',
            required=True)

FloatRequired()


class FloatDigits(ModelSQL):
    'Float Digits'
    _name = 'test.float_digits'
    _description = __doc__
    digits = fields.Integer('Digits')
    float = fields.Float(string='Float', help='Test float',
        required=False, digits=(16, Eval('digits', 2)),
        depends=['digits'])

FloatDigits()


class Numeric(ModelSQL):
    'Numeric'
    _name = 'test.numeric'
    _description = __doc__
    numeric = fields.Numeric(string='Numeric', help='Test numeric',
            required=False)

Numeric()


class NumericDefault(ModelSQL):
    'Numeric Default'
    _name = 'test.numeric_default'
    _description = __doc__
    numeric = fields.Numeric(string='Numeric', help='Test numeric',
            required=False)

    def default_numeric(self):
        return Decimal('5.5')

NumericDefault()


class NumericRequired(ModelSQL):
    'Numeric Required'
    _name = 'test.numeric_required'
    _description = __doc__
    numeric = fields.Numeric(string='Numeric', help='Test numeric',
            required=True)

NumericRequired()


class NumericDigits(ModelSQL):
    'Numeric Digits'
    _name = 'test.numeric_digits'
    _description = __doc__
    digits = fields.Integer('Digits')
    numeric = fields.Numeric(string='Numeric', help='Test numeric',
        required=False, digits=(16, Eval('digits', 2)),
        depends=['digits'])

NumericDigits()


class Char(ModelSQL):
    'Char'
    _name = 'test.char'
    _description = __doc__
    char = fields.Char(string='Char', size=None, help='Test char',
            required=False)

Char()


class CharDefault(ModelSQL):
    'Char Default'
    _name = 'test.char_default'
    _description = __doc__
    char = fields.Char(string='Char', size=None, help='Test char',
            required=False)

    def default_char(self):
        return 'Test'

CharDefault()


class CharRequired(ModelSQL):
    'Char Required'
    _name = 'test.char_required'
    _description = __doc__
    char = fields.Char(string='Char', size=None, help='Test char',
            required=True)

CharRequired()


class CharSize(ModelSQL):
    'Char Size'
    _name = 'test.char_size'
    _description = __doc__
    char = fields.Char(string='Char', size=5, help='Test char',
            required=False)

CharSize()


class CharTranslate(ModelSQL):
    'Char Translate'
    _name = 'test.char_translate'
    _description = __doc__
    char = fields.Char(string='Char', size=None, help='Test char',
            required=False, translate=True)

CharTranslate()


class Text(ModelSQL):
    'Text'
    _name = 'test.text'
    _description = __doc__
    text = fields.Text(string='Text', size=None, help='Test text',
            required=False)

Text()


class TextDefault(ModelSQL):
    'Text Default'
    _name = 'test.text_default'
    _description = __doc__
    text = fields.Text(string='Text', size=None, help='Test text',
            required=False)

    def default_text(self):
        return 'Test'

TextDefault()


class TextRequired(ModelSQL):
    'Text Required'
    _name = 'test.text_required'
    _description = __doc__
    text = fields.Text(string='Text', size=None, help='Test text',
            required=True)

TextRequired()


class TextSize(ModelSQL):
    'Text Size'
    _name = 'test.text_size'
    _description = __doc__
    text = fields.Text(string='Text', size=5, help='Test text',
            required=False)

TextSize()


class TextTranslate(ModelSQL):
    'Text Translate'
    _name = 'test.text_translate'
    _description = __doc__
    text = fields.Text(string='Text', size=None, help='Test text',
            required=False, translate=True)

TextTranslate()


class Sha(ModelSQL):
    'Sha'
    _name = 'test.sha'
    _description = __doc__
    sha = fields.Sha(string='Sha', help='Test sha',
            required=False)

Sha()


class ShaDefault(ModelSQL):
    'Sha Default'
    _name = 'test.sha_default'
    _description = __doc__
    sha = fields.Sha(string='Sha', help='Test sha',
            required=False)

    def default_sha(self):
        return 'Sha'

ShaDefault()


class ShaRequired(ModelSQL):
    'Sha Required'
    _name = 'test.sha_required'
    _description = __doc__
    sha = fields.Sha(string='Sha', help='Test sha',
            required=True)

ShaRequired()


class Date(ModelSQL):
    'Date'
    _name = 'test.date'
    _description = __doc__
    date = fields.Date(string='Date', help='Test date',
            required=False)

Date()


class DateDefault(ModelSQL):
    'Date Default'
    _name = 'test.date_default'
    _description = __doc__
    date = fields.Date(string='Date', help='Test date',
            required=False)

    def default_date(self):
        return datetime.date(2000, 1, 1)

DateDefault()


class DateRequired(ModelSQL):
    'Date Required'
    _name = 'test.date_required'
    _description = __doc__
    date = fields.Date(string='Date', help='Test date',
            required=True)

DateRequired()


class DateTime(ModelSQL):
    'DateTime'
    _name = 'test.datetime'
    _description = __doc__
    datetime = fields.DateTime(string='DateTime', help='Test datetime',
            required=False)

DateTime()


class DateTimeDefault(ModelSQL):
    'DateTime Default'
    _name = 'test.datetime_default'
    _description = __doc__
    datetime = fields.DateTime(string='DateTime', help='Test datetime',
            required=False)

    def default_datetime(self):
        return datetime.datetime(2000, 1, 1, 12, 0, 0, 0)

DateTimeDefault()


class DateTimeRequired(ModelSQL):
    'DateTime Required'
    _name = 'test.datetime_required'
    _description = __doc__
    datetime = fields.DateTime(string='DateTime', help='Test datetime',
            required=True)

DateTimeRequired()


class One2One(ModelSQL):
    'One2One'
    _name = 'test.one2one'
    _description = __doc__
    name = fields.Char('Name', required=True)
    one2one = fields.One2One('test.one2one.relation', 'origin', 'target',
            string='One2One', help='Test one2one', required=False)

One2One()


class One2OneTarget(ModelSQL):
    'One2One Target'
    _name = 'test.one2one.target'
    name = fields.Char('Name', required=True)

One2OneTarget()


class One2OneRelation(ModelSQL):
    'One2One Relation'
    _name = 'test.one2one.relation'
    _description = __doc__
    origin = fields.Many2One('test.one2one', 'Origin')
    target = fields.Many2One('test.one2one.target', 'Target')

    def __init__(self):
        super(One2OneRelation, self).__init__()
        self._sql_constraints += [
            ('origin_unique', 'UNIQUE(origin)',
                'Origin must be unique'),
            ('target_unique', 'UNIQUE(target)',
                'Target must be unique'),
        ]

One2OneRelation()


class One2OneRequired(ModelSQL):
    'One2One'
    _name = 'test.one2one_required'
    _description = __doc__
    name = fields.Char('Name', required=True)
    one2one = fields.One2One('test.one2one_required.relation', 'origin', 'target',
            string='One2One', help='Test one2one', required=True)

One2OneRequired()


class One2OneRequiredRelation(ModelSQL):
    'One2One Relation'
    _name = 'test.one2one_required.relation'
    _description = __doc__
    origin = fields.Many2One('test.one2one_required', 'Origin')
    target = fields.Many2One('test.one2one.target', 'Target')

    def __init__(self):
        super(One2OneRequiredRelation, self).__init__()
        self._sql_constraints += [
            ('origin_unique', 'UNIQUE(origin)',
                'Origin must be unique'),
            ('target_unique', 'UNIQUE(target)',
                'Target must be unique'),
        ]

One2OneRequiredRelation()


class Property(ModelSQL):
    'Property'
    _name = 'test.property'
    _description = __doc__

    char = fields.Property(fields.Char('Test Char'))
    many2one = fields.Property(fields.Many2One('test.char',
            'Test Many2One'))
    numeric = fields.Property(fields.Numeric('Test Numeric'))
    selection = fields.Property(fields.Selection([
                ('option_a', 'Option A'),
                ('option_b', 'Option B')
            ], 'Test Selection'))

Property()
