# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta


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
        super().__setup__()
        cls._preferences_fields += [
            'dashboard_layout',
            'dashboard_actions',
            ]

    @staticmethod
    def default_dashboard_layout():
        return 'square'

    @classmethod
    def on_modification(cls, mode, users, field_names=None):
        pool = Pool()
        View = pool.get('ir.ui.view')
        super().on_modification(mode, users, field_names=field_names)
        if (mode == 'write'
                and field_names & {'dashboard_layout', 'dashboard_actions'}):
            View._view_get_cache.clear()
            ModelView._fields_view_get_cache.clear()
