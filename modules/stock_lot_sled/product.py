# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval

from .stock import DATE_STATE


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    shelf_life_state = fields.Selection(
        DATE_STATE, 'Shelf Life Time State', sort=False)
    shelf_life_time = fields.Integer('Shelf Life Time',
        states={
            'invisible': Eval('shelf_life_state', 'none') == 'none',
            },
        depends=['shelf_life_state'],
        help='In number of days.')
    expiration_state = fields.Selection(
        DATE_STATE, 'Expiration State', sort=False)
    expiration_time = fields.Integer('Expiration Time',
        states={
            'invisible': Eval('expiration_state', 'none') == 'none',
            },
        depends=['expiration_state'],
        help='In number of days.')

    @staticmethod
    def default_shelf_life_state():
        return 'none'

    @staticmethod
    def default_expiration_state():
        return 'none'


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
