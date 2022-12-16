# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Test for export_data"
from trytond.model import ModelSQL, fields
from trytond.pool import PoolMeta

__all__ = [
    'ExportDataTarget', 'ExportData', 'ExportDataTarget2',
    'ExportDataRelation']


class ExportDataTarget(ModelSQL):
    "Export Data Target"
    __name__ = 'test.export_data.target'
    name = fields.Char('Name')


class ExportData(ModelSQL):
    "Export Data"
    __name__ = 'test.export_data'
    boolean = fields.Boolean('Boolean')
    integer = fields.Integer('Integer')
    float = fields.Float('Float')
    numeric = fields.Numeric('Numeric')
    char = fields.Char('Char')
    text = fields.Text('Text')
    date = fields.Date('Date')
    datetime = fields.DateTime('DateTime')
    selection = fields.Selection([
            (None, ''),
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
            (None, ''),
            ('test.export_data.target', 'Target'),
            ])


class ExportDataTarget2(metaclass=PoolMeta):
    'Export Date Target'
    __name__ = 'test.export_data.target'
    one2many = fields.Many2One('test.export_data', 'Export Data')


class ExportDataRelation(ModelSQL):
    "Export Data Many2Many"
    __name__ = 'test.export_data.relation'
    many2many = fields.Many2One('test.export_data', 'Export Data')
    target = fields.Many2One('test.export_data.target', 'Target')
