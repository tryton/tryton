# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Test for import_data"
from trytond.model import ModelSQL, fields
from trytond.pool import Pool


class ImportData(ModelSQL):
    __name__ = 'test.import_data'
    name = fields.Char("Name")
    value = fields.Integer("Value")


class ImportDataBoolean(ModelSQL):
    __name__ = 'test.import_data.boolean'
    boolean = fields.Boolean('Boolean')


class ImportDataInteger(ModelSQL):
    __name__ = 'test.import_data.integer'
    integer = fields.Integer('Integer')


class ImportDataFloat(ModelSQL):
    __name__ = 'test.import_data.float'
    float = fields.Float('Float')


class ImportDataNumeric(ModelSQL):
    __name__ = 'test.import_data.numeric'
    numeric = fields.Numeric('Numeric')


class ImportDataChar(ModelSQL):
    __name__ = 'test.import_data.char'
    char = fields.Char('Char')


class ImportDataTranslate(ModelSQL):
    __name__ = 'test.import_data.translate'
    translate = fields.Char("Translate", translate=True)


class ImportDataText(ModelSQL):
    __name__ = 'test.import_data.text'
    text = fields.Text('Text')


class ImportDataDate(ModelSQL):
    __name__ = 'test.import_data.date'
    date = fields.Date('Date')


class ImportDataDateTime(ModelSQL):
    __name__ = 'test.import_data.datetime'
    datetime = fields.DateTime('DateTime')


class ImportDataTimeDelta(ModelSQL):
    __name__ = 'test.import_data.timedelta'
    timedelta = fields.TimeDelta('TimeDelta')


class ImportDataSelection(ModelSQL):
    __name__ = 'test.import_data.selection'
    selection = fields.Selection([
            (None, ''),
            ('select1', 'Select 1'),
            ('select2', 'Select 2'),
            ], 'Selection')


class ImportDataMany2OneTarget(ModelSQL):
    __name__ = 'test.import_data.many2one.target'
    name = fields.Char('Name')


class ImportDataMany2One(ModelSQL):
    __name__ = 'test.import_data.many2one'
    many2one = fields.Many2One('test.import_data.many2one.target',
            'Many2One')


class ImportDataMany2ManyTarget(ModelSQL):
    __name__ = 'test.import_data.many2many.target'
    name = fields.Char('Name')


class ImportDataMany2Many(ModelSQL):
    __name__ = 'test.import_data.many2many'
    many2many = fields.Many2Many('test.import_data.many2many.relation',
            'many2many', 'target', 'Many2Many')


class ImportDataMany2ManyRelation(ModelSQL):
    __name__ = 'test.import_data.many2many.relation'
    many2many = fields.Many2One('test.import_data.many2many', 'Many2One')
    target = fields.Many2One('test.import_data.many2many.target', 'Target')


class ImportDataOne2Many(ModelSQL):
    __name__ = 'test.import_data.one2many'
    name = fields.Char('Name')
    one2many = fields.One2Many('test.import_data.one2many.target', 'one2many',
            'One2Many')


class ImportDataOne2ManyTarget(ModelSQL):
    __name__ = 'test.import_data.one2many.target'
    name = fields.Char('Name')
    one2many = fields.Many2One('test.import_data.one2many', 'One2Many')


class ImportDataOne2Manies(ModelSQL):
    __name__ = 'test.import_data.one2manies'
    name = fields.Char("Name")
    one2many1 = fields.One2Many(
        'test.import_data.one2many1.target', 'one2many', "One2Many 1")
    one2many2 = fields.One2Many(
        'test.import_data.one2many2.target', 'one2many', "One2Many 2")


class ImportDataOne2Many1Target(ModelSQL):
    __name__ = 'test.import_data.one2many1.target'
    name = fields.Char("Name")
    one2many = fields.Many2One('test.import_data.one2manies', "One2Many")


class ImportDataOne2Many2Target(ModelSQL):
    __name__ = 'test.import_data.one2many2.target'
    name = fields.Char("Name")
    one2many = fields.Many2One('test.import_data.one2manies', "One2Many")


class ImportDataBinary(ModelSQL):
    __name__ = 'test.import_data.binary'
    data = fields.Binary("Data")


class ImportDataReferenceSelection(ModelSQL):
    __name__ = 'test.import_data.reference.selection'
    name = fields.Char('Name')


class ImportDataReference(ModelSQL):
    __name__ = 'test.import_data.reference'
    reference = fields.Reference('Reference', [
            (None, ''),
            ('test.import_data.reference.selection', 'Test'),
            ])


class ImportDataUpdate(ModelSQL):
    __name__ = 'test.import_data.update'
    name = fields.Char("Name")


def register(module):
    Pool.register(
        ImportData,
        ImportDataBoolean,
        ImportDataInteger,
        ImportDataFloat,
        ImportDataNumeric,
        ImportDataChar,
        ImportDataTranslate,
        ImportDataText,
        ImportDataDate,
        ImportDataDateTime,
        ImportDataTimeDelta,
        ImportDataSelection,
        ImportDataMany2OneTarget,
        ImportDataMany2One,
        ImportDataMany2ManyTarget,
        ImportDataMany2Many,
        ImportDataMany2ManyRelation,
        ImportDataOne2Many,
        ImportDataOne2ManyTarget,
        ImportDataOne2Manies,
        ImportDataOne2Many1Target,
        ImportDataOne2Many2Target,
        ImportDataReferenceSelection,
        ImportDataReference,
        ImportDataBinary,
        ImportDataUpdate,
        module=module, type_='model')
