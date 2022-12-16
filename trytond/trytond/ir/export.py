# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Exports"
from ..model import ModelView, ModelSQL, fields
from trytond.pool import Pool
from trytond.rpc import RPC


class _ClearCache(ModelSQL):
    @classmethod
    def create(cls, vlist):
        ModelView._view_toolbar_get_cache.clear()
        return super().create(vlist)

    @classmethod
    def write(cls, *args):
        ModelView._view_toolbar_get_cache.clear()
        super().write(*args)

    @classmethod
    def delete(cls, records):
        ModelView._view_toolbar_get_cache.clear()
        super().delete(records)


class Export(_ClearCache, ModelSQL, ModelView):
    "Export"
    __name__ = "ir.export"
    name = fields.Char('Name')
    resource = fields.Char('Resource')
    export_fields = fields.One2Many('ir.export.line', 'export',
       'Fields')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__rpc__.update(
            update=RPC(instantiate=0, readonly=False))

    @classmethod
    def update(cls, exports, fields):
        pool = Pool()
        Line = pool.get('ir.export.line')
        to_delete = []
        to_save = []
        for export in exports:
            to_delete.extend(export.export_fields)
            to_save.extend(Line(export=export, name=f) for f in fields)
        Line.delete(to_delete)
        Line.save(to_save)


class ExportLine(_ClearCache, ModelSQL, ModelView):
    "Export line"
    __name__ = 'ir.export.line'
    name = fields.Char('Name')
    export = fields.Many2One('ir.export', 'Export', select=True, required=True,
        ondelete='CASCADE')
