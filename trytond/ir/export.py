# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Exports"
from ..model import ModelView, ModelSQL, fields

__all__ = [
    'Export', 'ExportLine',
    ]


class Export(ModelSQL, ModelView):
    "Export"
    __name__ = "ir.export"
    name = fields.Char('Name')
    resource = fields.Char('Resource')
    export_fields = fields.One2Many('ir.export.line', 'export',
       'Fields')


class ExportLine(ModelSQL, ModelView):
    "Export line"
    __name__ = 'ir.export.line'
    name = fields.Char('Name')
    export = fields.Many2One('ir.export', 'Export', select=True, required=True,
        ondelete='CASCADE')
