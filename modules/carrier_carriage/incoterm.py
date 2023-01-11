# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta


class Incoterm(metaclass=PoolMeta):
    __name__ = 'incoterm.incoterm'

    before_carrier = fields.Selection([
            ('buyer', "Buyer"),
            ('seller', "Seller"),
            ], "Before Carrier", required=True,
        help="Who contracts carriages before main carriage.")
    after_carrier = fields.Selection([
            ('buyer', "Buyer"),
            ('seller', "Seller"),
            ], "After Carrier", required=True,
        help="Who contracts carriages after main carriage.")
