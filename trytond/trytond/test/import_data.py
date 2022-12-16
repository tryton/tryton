#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Test for import_data"
from trytond.model import ModelSQL, fields


class ImportDataBoolean(ModelSQL):
    "Import Data Boolean"
    _name = 'test.import_data.boolean'
    _description = __doc__
    boolean = fields.Boolean('Boolean')

ImportDataBoolean()


class ImportDataInteger(ModelSQL):
    "Import Data Integer"
    _name = 'test.import_data.integer'
    _description = __doc__
    integer = fields.Integer('Integer')

ImportDataInteger()


class ImportDataFloat(ModelSQL):
    "Import Data Float"
    _name = 'test.import_data.float'
    _description = __doc__
    float = fields.Float('Float')

ImportDataFloat()


class ImportDataNumeric(ModelSQL):
    "Import Data Numeric"
    _name = 'test.import_data.numeric'
    _description = __doc__
    numeric = fields.Numeric('Numeric')

ImportDataNumeric()


class ImportDataChar(ModelSQL):
    "Import Data Char"
    _name = 'test.import_data.char'
    _description = __doc__
    char = fields.Char('Char')

ImportDataChar()


class ImportDataText(ModelSQL):
    "Import Data Text"
    _name = 'test.import_data.text'
    _description = __doc__
    text = fields.Text('Text')

ImportDataText()


class ImportDataSha(ModelSQL):
    "Import Data Sha"
    _name = 'test.import_data.sha'
    _description = __doc__
    sha = fields.Sha('Sha')

ImportDataSha()


class ImportDataDate(ModelSQL):
    "Import Data Date"
    _name = 'test.import_data.date'
    _description = __doc__
    date = fields.Date('Date')

ImportDataDate()


class ImportDataDateTime(ModelSQL):
    "Import Data DateTime"
    _name = 'test.import_data.datetime'
    _description = __doc__
    datetime = fields.DateTime('DateTime')

ImportDataDateTime()


class ImportDataSelection(ModelSQL):
    "Import Data Selection"
    _name = 'test.import_data.selection'
    _description = __doc__
    selection = fields.Selection([
        ('select1', 'Select 1'),
        ('select2', 'Select 2'),
        ], 'Selection')

ImportDataSelection()



class ImportDataMany2OneTarget(ModelSQL):
    "Import Data Many2One Target"
    _name = 'test.import_data.many2one.target'
    _description = __doc__
    name = fields.Char('Name')

ImportDataMany2OneTarget()


class ImportDataMany2One(ModelSQL):
    "Import Data Many2One"
    _name = 'test.import_data.many2one'
    _description = __doc__
    many2one = fields.Many2One('test.import_data.many2one.target',
            'Many2One')

ImportDataMany2One()


class ImportDataMany2ManyTarget(ModelSQL):
    "Import Data Many2Many Target"
    _name = 'test.import_data.many2many.target'
    _description = __doc__
    name = fields.Char('Name')

ImportDataMany2ManyTarget()


class ImportDataMany2Many(ModelSQL):
    "Import Data Many2Many"
    _name = 'test.import_data.many2many'
    _description = __doc__
    many2many = fields.Many2Many('test.import_data.many2many.relation',
            'many2many', 'target', 'Many2Many')

ImportDataMany2Many()


class ImportDataMany2ManyRelation(ModelSQL):
    "Import Data Many2Many Relation"
    _name = 'test.import_data.many2many.relation'
    many2many = fields.Many2One('test.import_data.many2many', 'Many2One')
    target = fields.Many2One('test.import_data.many2many.target', 'Target')

ImportDataMany2ManyRelation()


class ImportDataOne2Many(ModelSQL):
    "Import Data One2Many"
    _name = 'test.import_data.one2many'
    _description = __doc__
    name = fields.Char('Name')
    one2many = fields.One2Many('test.import_data.one2many.target', 'one2many',
            'One2Many')

ImportDataOne2Many()


class ImportDataOne2ManyTarget(ModelSQL):
    "Import Data One2Many Target"
    _name = 'test.import_data.one2many.target'
    _description = __doc__
    name = fields.Char('Name')
    one2many = fields.Many2One('test.import_data.one2many', 'One2Many')

ImportDataOne2ManyTarget()


class ImportDataReferenceSelection(ModelSQL):
    "Import Data Reference Selection"
    _name = 'test.import_data.reference.selection'
    _description = __doc__
    name = fields.Char('Name')

ImportDataReferenceSelection()


class ImportDataReference(ModelSQL):
    "Import Data Reference"
    _name = 'test.import_data.reference'
    reference = fields.Reference('Reference', [
        ('test.import_data.reference.selection', 'Test'),
        ])

ImportDataReference()
