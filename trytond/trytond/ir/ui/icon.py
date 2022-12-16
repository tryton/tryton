# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import os

from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import file_open
from trytond.transaction import Transaction


class Icon(ModelSQL, ModelView):
    'Icon'
    _name = 'ir.ui.icon'
    _description = __doc__

    name = fields.Char('Name', required=True, select=1)
    module = fields.Char('Module', readonly=True, required=True)
    path = fields.Char('SVG Path', readonly=True, required=True)
    icon = fields.Function(fields.Char('Icon', depends=['path']), 'get_icon')
    sequence = fields.Integer('Sequence')

    def __init__(self):
        super(Icon, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))
        self._rpc.update({
            'list_icons': False,
        })

    def default_module(self):
        return Transaction().context.get('module') or ''

    def default_sequence(self):
        return 10

    def list_icons(self):
        icons = {}
        for icon in self.browse(self.search([],
                order=[('sequence', 'ASC'), ('id', 'ASC')])):
            if icon.name not in icons:
                icons[icon.name] = icon.id
        return sorted((icon_id, name) for name, icon_id in icons.iteritems())

    def get_icon(self, ids, name):
        result = {}
        for icon in self.browse(ids):
            path = os.path.join(icon.module, icon.path.replace('/', os.sep))
            with file_open(path, subdir='modules') as fp:
                result[icon.id] = fp.read()
        return result

Icon()
