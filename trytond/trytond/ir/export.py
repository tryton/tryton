#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Exports"
from trytond.model import ModelView, ModelSQL, fields


class Export(ModelSQL, ModelView):
    "Export"
    _name = "ir.export"
    _description = __doc__
    name = fields.Char('Name')
    resource = fields.Char('Resource')
    export_fields = fields.One2Many('ir.export.line', 'export',
       'Fields')

Export()


class ExportLine(ModelSQL, ModelView):
    "Export line"
    _name = 'ir.export.line'
    _description = __doc__
    name = fields.Char('Name')
    export = fields.Many2One('ir.export', 'Export',
       select=1)

ExportLine()
