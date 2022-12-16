# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class Production(metaclass=PoolMeta):
    __name__ = 'production'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'assign_manual_wizard': {
                    'invisible': Eval('state') != 'waiting',
                    'depends': ['state'],
                    },
                })

    @classmethod
    @ModelView.button_action(
        'stock_assign_manual.wizard_production_assign_manual')
    def assign_manual_wizard(cls, shipments):
        pass
