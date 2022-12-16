#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import Model, fields


class User(Model):
    _name = "res.user"

    dashboard_layout = fields.Selection([
        ('square', 'Square'),
        ('stack_right', 'Stack Right'),
        ('stack_left', 'Stack Left'),
        ('stack_top', 'Stack Top'),
        ('stack_bottom', 'Stack Bottom'),
        ], string='Dashboard Layout', required=True)
    dashboard_actions = fields.One2Many('dashboard.action', 'user',
            'Dashboard Actions')

    def __init__(self):
        super(User, self).__init__()
        self._preferences_fields += [
            'dashboard_layout',
            'dashboard_actions',
        ]

    def default_dashboard_layout(self, cursor, user, context=None):
        return 'square'

User()
