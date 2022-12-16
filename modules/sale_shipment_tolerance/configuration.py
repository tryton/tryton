# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ValueMixin, fields
from trytond.pool import PoolMeta, Pool


sale_under_shipment_tolerance = fields.Float(
    "Sale Under Shipment Tolerance",
    help="The lower quantity accepted in percentage.")
sale_over_shipment_tolerance = fields.Float(
    "Sale Over Shipment Tolerance",
    help="The upper quantity accepted in percentage.")


def default_func(field_name):
    @classmethod
    def default(cls, **pattern):
        return getattr(
            cls.multivalue_model(field_name),
            'default_%s' % field_name, lambda: None)()
    return default


class Configuration(metaclass=PoolMeta):
    __name__ = 'sale.configuration'

    sale_under_shipment_tolerance = fields.MultiValue(
        sale_under_shipment_tolerance)
    sale_over_shipment_tolerance = fields.MultiValue(
        sale_over_shipment_tolerance)

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {
                'sale_under_shipment_tolerance',
                'sale_over_shipment_tolerance'}:
            return pool.get('sale.configuration.shipment_tolerance')
        return super(Configuration, cls).multivalue_model(field)

    default_sale_under_shipment_tolerance = default_func(
        'sale_under_shipment_tolerance')
    default_sale_over_shipment_tolerance = default_func(
        'sale_over_shipment_tolerance')


class ConfigurationShipmentTolerance(ModelSQL, ValueMixin):
    "Sale Configuration Shipment Tolerance"
    __name__ = 'sale.configuration.shipment_tolerance'
    sale_under_shipment_tolerance = sale_under_shipment_tolerance
    sale_over_shipment_tolerance = sale_over_shipment_tolerance

    @classmethod
    def __setup__(cls):
        super(ConfigurationShipmentTolerance, cls).__setup__()
        cls.sale_under_shipment_tolerance.domain = [
            'OR',
            ('sale_under_shipment_tolerance', '=', None),
            [
                ('sale_under_shipment_tolerance', '>=', 0),
                ('sale_under_shipment_tolerance', '<=', 1),
                ]]
        cls.sale_over_shipment_tolerance.domain = [
            'OR',
            ('sale_over_shipment_tolerance', '=', None),
            ('sale_over_shipment_tolerance', '>=', 1),
            ]

    @classmethod
    def default_sale_under_shipment_tolerance(cls):
        return 1

    @classmethod
    def default_sale_over_shipment_tolerance(cls):
        return None
