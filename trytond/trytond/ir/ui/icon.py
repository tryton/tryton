# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import os

from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import file_open
from trytond.transaction import Transaction
from trytond.rpc import RPC

__all__ = [
    'Icon',
    ]


class Icon(ModelSQL, ModelView):
    'Icon'
    __name__ = 'ir.ui.icon'

    name = fields.Char('Name', required=True, select=True)
    module = fields.Char('Module', readonly=True, required=True)
    path = fields.Char('SVG Path', readonly=True, required=True)
    icon = fields.Function(fields.Char('Icon', depends=['path']), 'get_icon')
    sequence = fields.Integer('Sequence', required=True)

    @classmethod
    def __setup__(cls):
        super(Icon, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))
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
        icons = {}
        for icon in cls.browse(cls.search([],
                order=[('sequence', 'ASC'), ('id', 'ASC')])):
            if icon.name not in icons:
                icons[icon.name] = icon.id
        return sorted((icon_id, name) for name, icon_id in icons.items())

    def get_icon(self, name):
        path = os.path.join(self.module, self.path.replace('/', os.sep))
        with file_open(path,
                subdir='modules', mode='r', encoding='utf-8') as fp:
            return fp.read()
