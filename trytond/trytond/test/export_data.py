#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Test for export_data"
from trytond.model import ModelSQL, fields


class ExportDataTarget(ModelSQL):
    "Export Data Target"
    _name = 'test.export_data.target'
    _description = __doc__
    name = fields.Char('Name')

ExportDataTarget()


class ExportData(ModelSQL):
    "Export Data"
    _name = 'test.export_data'
    _description = __doc__
    boolean = fields.Boolean('Boolean')
    integer = fields.Integer('Integer')
    float = fields.Float('Float')
    numeric = fields.Numeric('Numeric')
    char = fields.Char('Char')
    text = fields.Text('Text')
    sha = fields.Sha('Sha')
    date = fields.Date('Date')
    datetime = fields.DateTime('DateTime')
    selection = fields.Selection([
        ('select1', 'Select 1'),
        ('select2', 'Select 2'),
        ], 'Selection')
    many2one = fields.Many2One('test.export_data.target',
            'Many2One')
    many2many = fields.Many2Many('test.export_data.relation',
            'many2many', 'target', 'Many2Many')
    one2many = fields.One2Many('test.export_data.target', 'one2many',
            'One2Many')
    reference = fields.Reference('Reference', [
        ('test.export_data.target', 'Target'),
        ])

ExportData()


class ExportDataTarget(ExportDataTarget):
    one2many = fields.Many2One('test.export_data', 'Export Data')

ExportDataTarget()

class ExportDataRelation(ModelSQL):
    "Export Data Many2Many"
    _name = 'test.export_data.relation'
    _description = __doc__
    many2many = fields.Many2One('test.export_data', 'Export Data')
    target = fields.Many2One('test.export_data.target', 'Target')

ExportDataRelation()
