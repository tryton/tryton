# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime
from decimal import Decimal
from trytond.model import ModelSQL, DictSchemaMixin, fields, Unique
from trytond.pyson import Eval

__all__ = [
    'Boolean', 'BooleanDefault',
    'Integer', 'IntegerDefault', 'IntegerRequired', 'IntegerDomain',
    'Float', 'FloatDefault', 'FloatRequired', 'FloatDigits',
    'Numeric', 'NumericDefault', 'NumericRequired', 'NumericDigits',
    'Char', 'CharDefault', 'CharRequired', 'CharSize', 'CharTranslate',
    'Text', 'TextDefault', 'TextRequired', 'TextSize', 'TextTranslate',
    'Date', 'DateDefault', 'DateRequired',
    'DateTime', 'DateTimeDefault', 'DateTimeRequired', 'DateTimeFormat',
    'Time', 'TimeDefault', 'TimeRequired', 'TimeFormat',
    'TimeDelta', 'TimeDeltaDefault', 'TimeDeltaRequired',
    'One2One', 'One2OneTarget', 'One2OneRelation', 'One2OneRequired',
    'One2OneRequiredRelation', 'One2OneDomain', 'One2OneDomainRelation',
    'One2Many', 'One2ManyTarget',
    'One2ManyRequired', 'One2ManyRequiredTarget',
    'One2ManyReference', 'One2ManyReferenceTarget',
    'One2ManySize', 'One2ManySizeTarget',
    'One2ManySizePYSON', 'One2ManySizePYSONTarget',
    'Many2Many', 'Many2ManyTarget', 'Many2ManyRelation',
    'Many2ManyRequired', 'Many2ManyRequiredTarget',
    'Many2ManyRequiredRelation',
    'Many2ManyReference', 'Many2ManyReferenceTarget',
    'Many2ManyReferenceRelation',
    'Many2ManySize', 'Many2ManySizeTarget', 'Many2ManySizeRelation',
    'Reference', 'ReferenceTarget', 'ReferenceRequired',
    'Property',
    'Selection', 'SelectionRequired',
    'DictSchema', 'Dict', 'DictDefault', 'DictRequired',
    'Binary', 'BinaryDefault', 'BinaryRequired',
    'Many2OneDomainValidation', 'Many2OneTarget', 'Many2OneOrderBy',
    'Many2OneSearch',
    ]


class Boolean(ModelSQL):
    'Boolean'
    __name__ = 'test.boolean'
    boolean = fields.Boolean(string='Boolean', help='Test boolean')


class BooleanDefault(ModelSQL):
    'Boolean Default'
    __name__ = 'test.boolean_default'
    boolean = fields.Boolean(string='Boolean', help='Test boolean')

    @staticmethod
    def default_boolean():
        return True


class Integer(ModelSQL):
    'Integer'
    __name__ = 'test.integer'
    integer = fields.Integer(string='Integer', help='Test integer',
            required=False)


class IntegerDefault(ModelSQL):
    'Integer Default'
    __name__ = 'test.integer_default'
    integer = fields.Integer(string='Integer', help='Test integer',
            required=False)

    @staticmethod
    def default_integer():
        return 5


class IntegerRequired(ModelSQL):
    'Integer Required'
    __name__ = 'test.integer_required'
    integer = fields.Integer(string='Integer', help='Test integer',
            required=True)


class IntegerDomain(ModelSQL):
    'Integer Domain'
    __name__ = 'test.integer_domain'
    integer = fields.Integer('Integer', domain=[('integer', '>', 42)])


class Float(ModelSQL):
    'Float'
    __name__ = 'test.float'
    float = fields.Float(string='Float', help='Test float',
            required=False)


class FloatDefault(ModelSQL):
    'Float Default'
    __name__ = 'test.float_default'
    float = fields.Float(string='Float', help='Test float',
            required=False)

    @staticmethod
    def default_float():
        return 5.5


class FloatRequired(ModelSQL):
    'Float Required'
    __name__ = 'test.float_required'
    float = fields.Float(string='Float', help='Test float',
            required=True)


class FloatDigits(ModelSQL):
    'Float Digits'
    __name__ = 'test.float_digits'
    digits = fields.Integer('Digits')
    float = fields.Float(string='Float', help='Test float',
        required=False, digits=(16, Eval('digits', 2)),
        depends=['digits'])


class Numeric(ModelSQL):
    'Numeric'
    __name__ = 'test.numeric'
    numeric = fields.Numeric(string='Numeric', help='Test numeric',
            required=False)


class NumericDefault(ModelSQL):
    'Numeric Default'
    __name__ = 'test.numeric_default'
    numeric = fields.Numeric(string='Numeric', help='Test numeric',
            required=False)

    @staticmethod
    def default_numeric():
        return Decimal('5.5')


class NumericRequired(ModelSQL):
    'Numeric Required'
    __name__ = 'test.numeric_required'
    numeric = fields.Numeric(string='Numeric', help='Test numeric',
            required=True)


class NumericDigits(ModelSQL):
    'Numeric Digits'
    __name__ = 'test.numeric_digits'
    digits = fields.Integer('Digits')
    numeric = fields.Numeric(string='Numeric', help='Test numeric',
        required=False, digits=(16, Eval('digits', 2)),
        depends=['digits'])


class Char(ModelSQL):
    'Char'
    __name__ = 'test.char'
    char = fields.Char(string='Char', size=None, help='Test char',
            required=False)


class CharDefault(ModelSQL):
    'Char Default'
    __name__ = 'test.char_default'
    char = fields.Char(string='Char', size=None, help='Test char',
            required=False)

    @staticmethod
    def default_char():
        return 'Test'


class CharRequired(ModelSQL):
    'Char Required'
    __name__ = 'test.char_required'
    char = fields.Char(string='Char', size=None, help='Test char',
            required=True)


class CharSize(ModelSQL):
    'Char Size'
    __name__ = 'test.char_size'
    char = fields.Char(string='Char', size=5, help='Test char',
            required=False)


class CharTranslate(ModelSQL):
    'Char Translate'
    __name__ = 'test.char_translate'
    char = fields.Char(string='Char', size=None, help='Test char',
            required=False, translate=True)


class Text(ModelSQL):
    'Text'
    __name__ = 'test.text'
    text = fields.Text(string='Text', size=None, help='Test text',
            required=False)


class TextDefault(ModelSQL):
    'Text Default'
    __name__ = 'test.text_default'
    text = fields.Text(string='Text', size=None, help='Test text',
            required=False)

    @staticmethod
    def default_text():
        return 'Test'


class TextRequired(ModelSQL):
    'Text Required'
    __name__ = 'test.text_required'
    text = fields.Text(string='Text', size=None, help='Test text',
            required=True)


class TextSize(ModelSQL):
    'Text Size'
    __name__ = 'test.text_size'
    text = fields.Text(string='Text', size=5, help='Test text',
            required=False)


class TextTranslate(ModelSQL):
    'Text Translate'
    __name__ = 'test.text_translate'
    text = fields.Text(string='Text', size=None, help='Test text',
            required=False, translate=True)


class Date(ModelSQL):
    'Date'
    __name__ = 'test.date'
    date = fields.Date(string='Date', help='Test date',
            required=False)


class DateDefault(ModelSQL):
    'Date Default'
    __name__ = 'test.date_default'
    date = fields.Date(string='Date', help='Test date',
            required=False)

    @staticmethod
    def default_date():
        return datetime.date(2000, 1, 1)


class DateRequired(ModelSQL):
    'Date Required'
    __name__ = 'test.date_required'
    date = fields.Date(string='Date', help='Test date',
            required=True)


class DateTime(ModelSQL):
    'DateTime'
    __name__ = 'test.datetime'
    datetime = fields.DateTime(string='DateTime', help='Test datetime',
            required=False)


class DateTimeDefault(ModelSQL):
    'DateTime Default'
    __name__ = 'test.datetime_default'
    datetime = fields.DateTime(string='DateTime', help='Test datetime',
            required=False)

    @staticmethod
    def default_datetime():
        return datetime.datetime(2000, 1, 1, 12, 0, 0, 0)


class DateTimeRequired(ModelSQL):
    'DateTime Required'
    __name__ = 'test.datetime_required'
    datetime = fields.DateTime(string='DateTime', help='Test datetime',
            required=True)


class DateTimeFormat(ModelSQL):
    'DateTime Format'
    __name__ = 'test.datetime_format'
    datetime = fields.DateTime(string='DateTime', format='%H:%M')


class Time(ModelSQL):
    'Time'
    __name__ = 'test.time'
    time = fields.Time(string='Time', help='Test time', required=False)


class TimeDefault(ModelSQL):
    'Time Default'
    __name__ = 'test.time_default'
    time = fields.Time(string='Time', help='Test time', required=False)

    @staticmethod
    def default_time():
        return datetime.time(16, 30)


class TimeRequired(ModelSQL):
    'Time'
    __name__ = 'test.time_required'
    time = fields.Time(string='Time', help='Test time', required=True)


class TimeFormat(ModelSQL):
    'Time Format'
    __name__ = 'test.time_format'
    time = fields.Time(string='Time', format='%H:%M')


class TimeDelta(ModelSQL):
    'TimeDelta'
    __name__ = 'test.timedelta'
    timedelta = fields.TimeDelta(string='TimeDelta', help='Test timedelta',
        required=False)


class TimeDeltaDefault(ModelSQL):
    'TimeDelta Default'
    __name__ = 'test.timedelta_default'
    timedelta = fields.TimeDelta(string='TimeDelta', help='Test timedelta',
        required=False)

    @staticmethod
    def default_timedelta():
        return datetime.timedelta(seconds=3600)


class TimeDeltaRequired(ModelSQL):
    'TimeDelta Required'
    __name__ = 'test.timedelta_required'
    timedelta = fields.TimeDelta(string='TimeDelta', help='Test timedelta',
        required=True)


class One2One(ModelSQL):
    'One2One'
    __name__ = 'test.one2one'
    name = fields.Char('Name', required=True)
    one2one = fields.One2One('test.one2one.relation', 'origin', 'target',
            string='One2One', help='Test one2one', required=False)


class One2OneTarget(ModelSQL):
    'One2One Target'
    __name__ = 'test.one2one.target'
    name = fields.Char('Name', required=True)


class One2OneRelation(ModelSQL):
    'One2One Relation'
    __name__ = 'test.one2one.relation'
    origin = fields.Many2One('test.one2one', 'Origin')
    target = fields.Many2One('test.one2one.target', 'Target')

    @classmethod
    def __setup__(cls):
        super(One2OneRelation, cls).__setup__()
        table = cls.__table__()
        cls._sql_constraints += [
            ('origin_unique', Unique(table, table.origin),
                'Origin must be unique'),
            ('target_unique', Unique(table, table.target),
                'Target must be unique'),
            ]


class One2OneRequired(ModelSQL):
    'One2One'
    __name__ = 'test.one2one_required'
    name = fields.Char('Name', required=True)
    one2one = fields.One2One('test.one2one_required.relation', 'origin',
        'target', string='One2One', help='Test one2one', required=True)


class One2OneRequiredRelation(ModelSQL):
    'One2One Relation'
    __name__ = 'test.one2one_required.relation'
    origin = fields.Many2One('test.one2one_required', 'Origin')
    target = fields.Many2One('test.one2one.target', 'Target')

    @classmethod
    def __setup__(cls):
        super(One2OneRequiredRelation, cls).__setup__()
        table = cls.__table__()
        cls._sql_constraints += [
            ('origin_unique', Unique(table, table.origin),
                'Origin must be unique'),
            ('target_unique', Unique(table, table.target),
                'Target must be unique'),
            ]


class One2OneDomain(ModelSQL):
    'One2One'
    __name__ = 'test.one2one_domain'
    name = fields.Char('Name', required=True)
    one2one = fields.One2One('test.one2one_domain.relation', 'origin',
        'target', string='One2One', help='Test one2one',
        domain=[('name', '=', 'domain')])


class One2OneDomainRelation(ModelSQL):
    'One2One Relation'
    __name__ = 'test.one2one_domain.relation'
    origin = fields.Many2One('test.one2one_domain', 'Origin')
    target = fields.Many2One('test.one2one.target', 'Target')

    @classmethod
    def __setup__(cls):
        super(One2OneDomainRelation, cls).__setup__()
        table = cls.__table__()
        cls._sql_constraints += [
            ('origin_unique', Unique(table, table.origin),
                'Origin must be unique'),
            ('target_unique', Unique(table, table.target),
                'Target must be unique'),
            ]


class One2Many(ModelSQL):
    'One2Many Relation'
    __name__ = 'test.one2many'
    name = fields.Char('Name', required=True)
    targets = fields.One2Many('test.one2many.target', 'origin', 'Targets')


class One2ManyTarget(ModelSQL):
    'One2Many Target'
    __name__ = 'test.one2many.target'
    name = fields.Char('Name', required=True)
    origin = fields.Many2One('test.one2many', 'Origin')


class One2ManyRequired(ModelSQL):
    'One2Many Required'
    __name__ = 'test.one2many_required'
    name = fields.Char('Name', required=True)
    targets = fields.One2Many('test.one2many_required.target', 'origin',
        'Targets', required=True)


class One2ManyRequiredTarget(ModelSQL):
    'One2Many Required Target'
    __name__ = 'test.one2many_required.target'
    name = fields.Char('Name', required=True)
    origin = fields.Many2One('test.one2many_required', 'Origin')


class One2ManyReference(ModelSQL):
    'One2Many Reference Relation'
    __name__ = 'test.one2many_reference'
    name = fields.Char('Name', required=True)
    targets = fields.One2Many('test.one2many_reference.target', 'origin',
        'Targets')


class One2ManyReferenceTarget(ModelSQL):
    'One2Many Reference Target'
    __name__ = 'test.one2many_reference.target'
    name = fields.Char('Name', required=True)
    origin = fields.Reference('Origin', [
            (None, ''),
            ('test.one2many_reference', 'One2Many Reference'),
            ])


class One2ManySize(ModelSQL):
    'One2Many Size Relation'
    __name__ = 'test.one2many_size'
    targets = fields.One2Many('test.one2many_size.target', 'origin', 'Targets',
        size=3)


class One2ManySizeTarget(ModelSQL):
    'One2Many Size Target'
    __name__ = 'test.one2many_size.target'
    origin = fields.Many2One('test.one2many_size', 'Origin')


class One2ManySizePYSON(ModelSQL):
    'One2Many Size PYSON Relation'
    __name__ = 'test.one2many_size_pyson'
    limit = fields.Integer('Limit')
    targets = fields.One2Many('test.one2many_size_pyson.target', 'origin',
        'Targets', size=Eval('limit', 0))


class One2ManySizePYSONTarget(ModelSQL):
    'One2Many Size PYSON Target'
    __name__ = 'test.one2many_size_pyson.target'
    origin = fields.Many2One('test.one2many_size_pyson', 'Origin')


class Many2Many(ModelSQL):
    'Many2Many'
    __name__ = 'test.many2many'
    name = fields.Char('Name', required=True)
    targets = fields.Many2Many('test.many2many.relation', 'origin', 'target',
        'Targets')


class Many2ManyTarget(ModelSQL):
    'Many2Many Target'
    __name__ = 'test.many2many.target'
    name = fields.Char('Name', required=True)


class Many2ManyRelation(ModelSQL):
    'Many2Many Relation'
    __name__ = 'test.many2many.relation'
    origin = fields.Many2One('test.many2many', 'Origin')
    target = fields.Many2One('test.many2many.target', 'Target')


class Many2ManyRequired(ModelSQL):
    'Many2Many Required'
    __name__ = 'test.many2many_required'
    name = fields.Char('Name', required=True)
    targets = fields.Many2Many('test.many2many_required.relation', 'origin',
        'target', 'Targets', required=True)


class Many2ManyRequiredTarget(ModelSQL):
    'Many2Many Required Target'
    __name__ = 'test.many2many_required.target'
    name = fields.Char('Name', required=True)


class Many2ManyRequiredRelation(ModelSQL):
    'Many2Many Required Relation'
    __name__ = 'test.many2many_required.relation'
    origin = fields.Many2One('test.many2many_required', 'Origin')
    target = fields.Many2One('test.many2many_required.target', 'Target')


class Many2ManyReference(ModelSQL):
    'Many2Many Reference'
    __name__ = 'test.many2many_reference'
    name = fields.Char('Name', required=True)
    targets = fields.Many2Many('test.many2many_reference.relation', 'origin',
        'target', 'Targets')


class Many2ManyReferenceTarget(ModelSQL):
    'Many2Many Reference Target'
    __name__ = 'test.many2many_reference.target'
    name = fields.Char('Name', required=True)


class Many2ManyReferenceRelation(ModelSQL):
    'Many2Many Relation'
    __name__ = 'test.many2many_reference.relation'
    origin = fields.Reference('Origin', [
            (None, ''),
            ('test.many2many_reference', 'Many2Many Reference'),
            ])
    target = fields.Many2One('test.many2many_reference.target',
        'Reference Target')


class Many2ManySize(ModelSQL):
    'Many2Many Size Relation'
    __name__ = 'test.many2many_size'
    targets = fields.Many2Many('test.many2many_size.relation', 'origin',
        'target', 'Targets', size=5)


class Many2ManySizeTarget(ModelSQL):
    'Many2Many Size Target'
    __name__ = 'test.many2many_size.target'
    name = fields.Char('Name')


class Many2ManySizeRelation(ModelSQL):
    'Many2Many Size Relation'
    __name__ = 'test.many2many_size.relation'
    origin = fields.Many2One('test.many2many_size', 'Origin')
    target = fields.Many2One('test.many2many_size.target', 'Target')


class Reference(ModelSQL):
    'Reference'
    __name__ = 'test.reference'
    name = fields.Char('Name', required=True)
    reference = fields.Reference('Reference', selection=[
            (None, ''),
            ('test.reference.target', 'Target'),
            ])


class ReferenceTarget(ModelSQL):
    'Reference Target'
    __name__ = 'test.reference.target'
    name = fields.Char('Name', required=True)


class ReferenceRequired(ModelSQL):
    'Reference Required'
    __name__ = 'test.reference_required'
    name = fields.Char('Name', required=True)
    reference = fields.Reference('Reference', selection=[
            (None, ''),
            ('test.reference.target', 'Target'),
            ], required=True)


class Property(ModelSQL):
    'Property'
    __name__ = 'test.property'
    char = fields.Property(fields.Char('Test Char'))
    many2one = fields.Property(fields.Many2One('test.char',
            'Test Many2One'))
    numeric = fields.Property(fields.Numeric('Test Numeric'))
    selection = fields.Property(fields.Selection([
                (None, ''),
                ('option_a', 'Option A'),
                ('option_b', 'Option B')
            ], 'Test Selection'))


class Selection(ModelSQL):
    'Selection'
    __name__ = 'test.selection'
    select = fields.Selection([
            ('', ''), ('arabic', 'Arabic'), ('hexa', 'Hexadecimal')],
        'Selection')
    select_string = select.translated('select')
    dyn_select = fields.Selection('get_selection',
        'Instance Dynamic Selection')
    dyn_select_static = fields.Selection('static_selection',
        'Static Selection')

    @fields.depends('select')
    def get_selection(self):
        if self.select == 'arabic':
            return [('', '')] + [(str(i), str(i)) for i in range(1, 11)]
        else:
            return [('', '')] + [(hex(i), hex(i)) for i in range(1, 11)]

    @staticmethod
    def static_selection():
        return [('', '')] + [(str(i), str(i)) for i in range(1, 11)]


class SelectionRequired(ModelSQL):
    'Selection Required'
    __name__ = 'test.selection_required'
    select = fields.Selection([('arabic', 'Arabic'), ('latin', 'Latin')],
        'Selection', required=True)


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


class Binary(ModelSQL):
    'Binary'
    __name__ = 'test.binary'
    binary = fields.Binary('Binary')


class BinaryDefault(ModelSQL):
    'Binary Default'
    __name__ = 'test.binary_default'
    binary = fields.Binary('Binary Default')

    @staticmethod
    def default_binary():
        return b'default'


class BinaryRequired(ModelSQL):
    'Binary Required'
    __name__ = 'test.binary_required'
    binary = fields.Binary('Binary Required', required=True)


class Many2OneTarget(ModelSQL):
    "Many2One Domain Validation Target"
    __name__ = 'test.many2one_target'
    _order_name = 'value'

    active = fields.Boolean('Active')
    value = fields.Integer('Value')

    @staticmethod
    def default_active():
        return True


class Many2OneDomainValidation(ModelSQL):
    "Many2One Domain Validation"
    __name__ = 'test.many2one_domainvalidation'
    many2one = fields.Many2One('test.many2one_target',
        'many2one',
        domain=[
            ('value', '>', 5),
            ])
    dummy = fields.Char('Dummy')


class Many2OneOrderBy(ModelSQL):
    "Many2One OrderBy"
    __name__ = 'test.many2one_orderby'
    many2one = fields.Many2One('test.many2one_target', 'many2one')


class Many2OneSearch(ModelSQL):
    "Many2One Search"
    __name__ = 'test.many2one_search'
    many2one = fields.Many2One('test.many2one_target', 'many2one')
