# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta


class User(metaclass=PoolMeta):
    __name__ = "res.user"
    dashboard_layout = fields.Selection([
        ('square', 'Square'),
        ('stack_right', 'Stack Right'),
        ('stack_left', 'Stack Left'),
        ('stack_top', 'Stack Top'),
        ('stack_bottom', 'Stack Bottom'),
        ], string='Dashboard Layout')
    dashboard_actions = fields.One2Many('dashboard.action', 'user',
            'Dashboard Actions')

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls._preferences_fields += [
            'dashboard_layout',
            'dashboard_actions',
            ]

    @staticmethod
    def default_dashboard_layout():
        return 'square'
