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


class ImportDataIntegerRequired(ModelSQL):
    "Import Data Integer Required"
    __name__ = 'test.import_data.integer_required'
    integer = fields.Integer('Integer', required=True)


class ImportDataFloat(ModelSQL):
    "Import Data Float"
    __name__ = 'test.import_data.float'
    float = fields.Float('Float')


class ImportDataFloatRequired(ModelSQL):
    "Import Data Float Required"
    __name__ = 'test.import_data.float_required'
    float = fields.Float('Float', required=True)


class ImportDataNumeric(ModelSQL):
    "Import Data Numeric"
    __name__ = 'test.import_data.numeric'
    numeric = fields.Numeric('Numeric')


class ImportDataNumericRequired(ModelSQL):
    "Import Data Numeric Required"
    __name__ = 'test.import_data.numeric_required'
    numeric = fields.Numeric('Numeric', required=True)


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


class ImportDataSelection(ModelSQL):
    "Import Data Selection"
    __name__ = 'test.import_data.selection'
    selection = fields.Selection([
            (None, ''),
            ('select1', 'Select 1'),
            ('select2', 'Select 2'),
            ], 'Selection')


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
        ImportDataIntegerRequired,
        ImportDataFloat,
        ImportDataFloatRequired,
        ImportDataNumeric,
        ImportDataNumericRequired,
        ImportDataChar,
        ImportDataText,
        ImportDataDate,
        ImportDataDateTime,
        ImportDataSelection,
        ImportDataMany2OneTarget,
        ImportDataMany2One,
        ImportDataMany2ManyTarget,
        ImportDataMany2Many,
        ImportDataMany2ManyRelation,
        ImportDataOne2Many,
        ImportDataOne2ManyTarget,
        ImportDataReferenceSelection,
        ImportDataReference,
        ImportDataUpdate,
        module=module, type_='model')
