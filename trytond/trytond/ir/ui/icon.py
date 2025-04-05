# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import os

from trytond.cache import Cache
from trytond.model import ModelSQL, ModelView, fields, sequence_ordered
from trytond.rpc import RPC
from trytond.tools import file_open
from trytond.transaction import Transaction


class Icon(
        fields.fmany2one(
            'module_ref', 'module', 'ir.module,name', "Module",
            readonly=True, required=True, ondelete='CASCADE'),
        sequence_ordered(), ModelSQL, ModelView):
    __name__ = 'ir.ui.icon'

    name = fields.Char('Name', required=True)
    module = fields.Char('Module', readonly=True, required=True)
    path = fields.Char('SVG Path', readonly=True, required=True)
    icon = fields.Function(fields.Text('Icon', depends=['path']), 'get_icon')
    _list_icons = Cache('ir.ui.icon.list_icons', context=False)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__rpc__.update({
                'list_icons': RPC(),
                })

    @staticmethod
    def default_module():
        return Transaction().context.get('module') or ''

    @staticmethod
    def default_sequence():
        return 10

    @classmethod
    def list_icons(cls):
        icons = cls._list_icons.get(None)
        if icons is not None:
            return icons
        icons = {}
        for icon in cls.browse(cls.search([],
                order=[('sequence', 'ASC'), ('id', 'ASC')])):
            if icon.name not in icons:
                icons[icon.name] = icon.id
        icons = sorted((icon_id, name) for name, icon_id in icons.items())
        cls._list_icons.set(None, icons)
        return icons

    def get_icon(self, name):
        path = os.path.join(self.module, self.path.replace('/', os.sep))
        with file_open(
                path,
                subdir='modules' if self.module not in {'ir', 'res'} else '',
                mode='r', encoding='utf-8') as fp:
            return fp.read()

    @classmethod
    def on_modification(cls, mode, records, field_names=None):
        super().on_modification(mode, records, field_names=field_names)
        cls._list_icons.clear()
