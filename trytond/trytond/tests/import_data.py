# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Test for import_data"
from trytond.model import ModelSQL, fields
from trytond.pool import Pool


class ImportDataBoolean(ModelSQL):
    "Import Data Boolean"
    __name__ = 'test.import_data.boolean'
    boolean = fields.Boolean('Boolean')


class ImportDataInteger(ModelSQL):
    "Import Data Integer"
    __name__ = 'test.import_data.integer'
    integer = fields.Integer('Integer')


class ImportDataFloat(ModelSQL):
    "Import Data Float"
    __name__ = 'test.import_data.float'
    float = fields.Float('Float')


class ImportDataNumeric(ModelSQL):
    "Import Data Numeric"
    __name__ = 'test.import_data.numeric'
    numeric = fields.Numeric('Numeric')


class ImportDataChar(ModelSQL):
    "Import Data Char"
    __name__ = 'test.import_data.char'
    char = fields.Char('Char')


class ImportDataText(ModelSQL):
    "Import Data Text"
    __name__ = 'test.import_data.text'
    text = fields.Text('Text')


class ImportDataDate(ModelSQL):
    "Import Data Date"
    __name__ = 'test.import_data.date'
    date = fields.Date('Date')


class ImportDataDateTime(ModelSQL):
    "Import Data DateTime"
    __name__ = 'test.import_data.datetime'
    datetime = fields.DateTime('DateTime')


class ImportDataTimeDelta(ModelSQL):
    "Import Data TimeDelta"
    __name__ = 'test.import_data.timedelta'
    timedelta = fields.TimeDelta('TimeDelta')


class ImportDataSelection(ModelSQL):
    "Import Data Selection"
    __name__ = 'test.import_data.selection'
    selection = fields.Selection([
            (None, ''),
            ('select1', 'Select 1'),
            ('select2', 'Select 2'),
            ], 'Selection')


class ImportDataMultiSelection(ModelSQL):
    "Import Data MultiSelection"
    __name__ = 'test.import_data.multiselection'
    multiselection = fields.MultiSelection([
            ('select1', "Select 1"),
            ('select2', "Select 2"),
            ('select3', "Select 3"),
            ], "MultiSelection")


class ImportDataMany2OneTarget(ModelSQL):
    "Import Data Many2One Target"
    __name__ = 'test.import_data.many2one.target'
    name = fields.Char('Name')


class ImportDataMany2One(ModelSQL):
    "Import Data Many2One"
    __name__ = 'test.import_data.many2one'
    many2one = fields.Many2One('test.import_data.many2one.target',
            'Many2One')


class ImportDataMany2ManyTarget(ModelSQL):
    "Import Data Many2Many Target"
    __name__ = 'test.import_data.many2many.target'
    name = fields.Char('Name')


class ImportDataMany2Many(ModelSQL):
    "Import Data Many2Many"
    __name__ = 'test.import_data.many2many'
    many2many = fields.Many2Many('test.import_data.many2many.relation',
            'many2many', 'target', 'Many2Many')


class ImportDataMany2ManyRelation(ModelSQL):
    "Import Data Many2Many Relation"
    __name__ = 'test.import_data.many2many.relation'
    many2many = fields.Many2One('test.import_data.many2many', 'Many2One')
    target = fields.Many2One('test.import_data.many2many.target', 'Target')


class ImportDataOne2Many(ModelSQL):
    "Import Data One2Many"
    __name__ = 'test.import_data.one2many'
    name = fields.Char('Name')
    one2many = fields.One2Many('test.import_data.one2many.target', 'one2many',
            'One2Many')


class ImportDataOne2ManyTarget(ModelSQL):
    "Import Data One2Many Target"
    __name__ = 'test.import_data.one2many.target'
    name = fields.Char('Name')
    one2many = fields.Many2One('test.import_data.one2many', 'One2Many')


class ImportDataOne2Manies(ModelSQL):
    "Import Data One2Manies"
    __name__ = 'test.import_data.one2manies'
    name = fields.Char("Name")
    one2many1 = fields.One2Many(
        'test.import_data.one2many1.target', 'one2many', "One2Many 1")
    one2many2 = fields.One2Many(
        'test.import_data.one2many2.target', 'one2many', "One2Many 2")


class ImportDataOne2Many1Target(ModelSQL):
    "Import Data One2Many 1 Target"
    __name__ = 'test.import_data.one2many1.target'
    name = fields.Char("Name")
    one2many = fields.Many2One('test.import_data.one2manies', "One2Many")


class ImportDataOne2Many2Target(ModelSQL):
    "Import Data One2Many 2 Target"
    __name__ = 'test.import_data.one2many2.target'
    name = fields.Char("Name")
    one2many = fields.Many2One('test.import_data.one2manies', "One2Many")


class ImportDataBinary(ModelSQL):
    "Import Data Binary"
    __name__ = 'test.import_data.binary'
    data = fields.Binary("Data")


class ImportDataReferenceSelection(ModelSQL):
    "Import Data Reference Selection"
    __name__ = 'test.import_data.reference.selection'
    name = fields.Char('Name')


class ImportDataReference(ModelSQL):
    "Import Data Reference"
    __name__ = 'test.import_data.reference'
    reference = fields.Reference('Reference', [
            (None, ''),
            ('test.import_data.reference.selection', 'Test'),
            ])


class ImportDataUpdate(ModelSQL):
    "Import Data for Update"
    __name__ = 'test.import_data.update'
    name = fields.Char("Name")


def register(module):
    Pool.register(
        ImportDataBoolean,
        ImportDataInteger,
        ImportDataFloat,
        ImportDataNumeric,
        ImportDataChar,
        ImportDataText,
        ImportDataDate,
        ImportDataDateTime,
        ImportDataTimeDelta,
        ImportDataSelection,
        ImportDataMultiSelection,
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
