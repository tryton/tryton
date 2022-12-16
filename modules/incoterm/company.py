# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta


class Company(metaclass=PoolMeta):
    __name__ = 'company.company'

    incoterms = fields.Many2Many(
        'incoterm.incoterm-company.company', 'company', 'incoterm',
        "Incoterms",
        help="Incoterms available for use by the company.")
