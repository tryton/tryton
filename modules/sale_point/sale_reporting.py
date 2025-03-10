# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal
from sql.operators import Concat

from trytond.pool import Pool


class AbstractMixin:
    __slots__ = ()

    @classmethod
    def _pos_sale_line(cls, length, index, company_id=None):
        pool = Pool()
        Company = pool.get('company.company')
        Line = pool.get('sale.point.sale.line')
        Point = pool.get('sale.point')
        Sale = pool.get('sale.point.sale')

        line = Line.__table__()
        point = Point.__table__()
        sale = Sale.__table__()
        if company_id is not None and company_id >= 0:
            company = Company(company_id)
            currency_id = company.currency.id
        else:
            currency_id = None
        return (line
            .join(sale, condition=line.sale == sale.id)
            .join(point, condition=sale.point == point.id)
            .select(
                (line.id * length + index).as_('id'),
                *cls._pos_sale_line_columns(line, point, sale, currency_id),
                where=sale.state.in_(cls._pos_sale_states())
                & (sale.company == company_id),
                ))

    @classmethod
    def _pos_sale_line_columns(cls, line, point, sale, currency):
        try:
            columns = super()._pos_sale_line_columns(
                line, point, sale, currency)
        except AttributeError:
            columns = []
        return [
            line.product.as_('product'),
            line.quantity.as_('quantity'),
            line.unit_list_price.as_('unit_price'),
            Concat('sale.point.sale,', line.sale).as_('order'),
            sale.date.as_('date'),
            sale.company.as_('company'),
            Literal(currency).as_('currency'),
            Literal(None).as_('customer'),
            point.storage_location.as_('location'),
            point.address.as_('shipment_address'),
            ] + columns

    @classmethod
    def _lines(cls):
        return super()._lines() + [cls._pos_sale_line]

    @classmethod
    def _pos_sale_states(cls):
        return ['done', 'posted']
