# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql import Literal

from trytond.model import ModelView, fields
from trytond.modules.sale.sale_reporting import Abstract


class Promotion(Abstract, ModelView):
    __name__ = 'sale.reporting.promotion'

    promotion = fields.Many2One('sale.promotion', "Promotion")

    @classmethod
    def _sale_line_columns(cls, line, sale):
        return super()._sale_line_columns(line, sale) + [
            line.promotion.as_('promotion')]

    @classmethod
    def _pos_sale_line_columns(cls, line, point, sale, currency):
        try:
            columns = super()._pos_sale_line_columns(
                line, point, sale, currency)
        except AttributeError:
            columns = []
        return columns + [Literal(None).as_('promotion')]

    @classmethod
    def _columns(cls, tables, withs):
        line = tables['line']
        return super()._columns(tables, withs) + [line.promotion]

    @classmethod
    def _group_by(cls, tables, withs):
        line = tables['line']
        return super()._group_by(tables, withs) + [line.promotion]

    def get_rec_name(self, name):
        return self.promotion.rec_name if self.promotion else None

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('promotion.rec_name', *clause[1:])]
