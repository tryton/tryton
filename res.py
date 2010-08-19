#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import Model, fields
from trytond.backend import TableHandler
from trytond.transaction import Transaction


class User(Model):
    _name = "res.user"

    dashboard_layout = fields.Selection([
        ('square', 'Square'),
        ('stack_right', 'Stack Right'),
        ('stack_left', 'Stack Left'),
        ('stack_top', 'Stack Top'),
        ('stack_bottom', 'Stack Bottom'),
        ], string='Dashboard Layout')
    dashboard_actions = fields.One2Many('dashboard.action', 'user',
            'Dashboard Actions')

    def __init__(self):
        super(User, self).__init__()
        self._preferences_fields += [
            'dashboard_layout',
            'dashboard_actions',
        ]

    def init(self, module_name):
        super(User, self).init(module_name)
        cursor = Transaction().cursor
        table = TableHandler(cursor, self, module_name)

        # Migration from 1.6
        table.not_null_action('dashboard_layout', action='remove')

    def default_dashboard_layout(self):
        return 'square'

User()
