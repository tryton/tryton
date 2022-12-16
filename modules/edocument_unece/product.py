# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta


class Uom(metaclass=PoolMeta):
    __name__ = 'product.uom'

    unece_code = fields.Char("UNECE Code",
        help="Standard code of "
        "the United Nations Economic Commission for Europe.")
