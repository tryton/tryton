# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta


class Incoterm(metaclass=PoolMeta):
    __name__ = 'incoterm.incoterm'

    before_carrier = fields.Selection([
            ('buyer', "Buyer"),
            ('seller', "Seller"),
            ], "Before Carrier",
        help="Who contracts carriages before main carriage.")
    after_carrier = fields.Selection([
            ('buyer', "Buyer"),
            ('seller', "Seller"),
            ], "After Carrier",
        help="Who contracts carriages after main carriage.")

    @classmethod
    def __register__(cls, module_name):
        table_h = cls.__table_handler__(module_name)
        super().__register__(module_name)
        # Migration from 7.6: remove required on before/after_carrier
        # to permit to create new incoterm in incoterm module
        table_h.not_null_action('before_carrier', 'remove')
        table_h.not_null_action('after_carrier', 'remove')
