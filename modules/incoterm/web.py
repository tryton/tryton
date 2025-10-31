# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class Shop(metaclass=PoolMeta):
    __name__ = 'web.shop'

    default_incoterm = fields.Many2One(
        'incoterm.incoterm', "Default Incoterm",
        domain=[
            ('carrier', '=', 'seller'),
            ('id', 'in', Eval('available_incoterms', [])),
            ],
        help="Used to fill incoterm on sales that require it.")
    available_incoterms = fields.Function(fields.Many2Many(
            'incoterm.incoterm', None, None, "Available Incoterms"),
        'on_change_with_available_incoterms')

    @fields.depends('company', methods=['_get_incoterm_pattern'])
    def on_change_with_available_incoterms(self, name=None):
        pool = Pool()
        Incoterm = pool.get('incoterm.incoterm')
        pattern = self._get_incoterm_pattern()
        return Incoterm.get_incoterms(self.company, pattern)

    @fields.depends()
    def _get_incoterm_pattern(self):
        return {}
