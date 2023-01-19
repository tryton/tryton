# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import (
    ModelSingleton, ModelSQL, ModelView, ValueMixin, fields)
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)
from trytond.pool import Pool
from trytond.pyson import Eval, Id

sequences = ['shipment_in_sequence', 'shipment_in_return_sequence',
    'shipment_out_sequence', 'shipment_out_return_sequence',
    'shipment_internal_sequence', 'inventory_sequence']
shipment_internal_transit = fields.Many2One(
    'stock.location', "Internal Shipment Transit", required=True,
    domain=[
        ('type', '=', 'storage'),
        ('parent', '=', None),
        ],
    help="The default location used for stock that is in transit between "
    "warehouses.")


def default_func(field_name):
    @classmethod
    def default(cls, **pattern):
        return getattr(
            cls.multivalue_model(field_name),
            'default_%s' % field_name, lambda: None)()
    return default


def default_sequence(name):
    @classmethod
    def default(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('stock', name)
        except KeyError:
            return None
    return default


class Configuration(
        ModelSingleton, ModelSQL, ModelView, CompanyMultiValueMixin):
    'Stock Configuration'
    __name__ = 'stock.configuration'
    shipment_in_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Supplier Shipment Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=',
                    Id('stock', 'sequence_type_shipment_in')),
                ],
            help="Used to generate the number given to supplier shipments."))
    shipment_in_return_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Supplier Return Shipment Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=',
                    Id('stock', 'sequence_type_shipment_in_return')),
                ],
            help="Used to generate the number given to supplier return "
            "shipments."))
    shipment_out_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Customer Shipment Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=',
                    Id('stock', 'sequence_type_shipment_out')),
                ],
            help="Used to generate the number given to customer "
            "shipments."))
    shipment_out_return_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Customer Return Shipment Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=',
                    Id('stock', 'sequence_type_shipment_out_return')),
                ],
            help="Used to generate the number given to customer return "
            "shipments."))
    shipment_internal_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Internal Shipment Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=',
                    Id('stock', 'sequence_type_shipment_internal')),
                ],
            help="Used to generate the number given to internal "
            "shipments."))
    inventory_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Inventory Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=',
                    Id('stock', 'sequence_type_inventory')),
                ],
            help="Used to generate the number given to inventories."))
    shipment_internal_transit = fields.MultiValue(shipment_internal_transit)

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in sequences:
            return pool.get('stock.configuration.sequence')
        if field == 'shipment_internal_transit':
            return pool.get('stock.configuration.location')
        return super(Configuration, cls).multivalue_model(field)

    default_shipment_in_sequence = default_func('shipment_in_sequence')
    default_shipment_in_return_sequence = default_func(
        'shipment_in_return_sequence')
    default_shipment_out_sequence = default_func('shipment_out_sequence')
    default_shipment_out_return_sequence = default_func(
        'shipment_out_return_sequence')
    default_shipment_internal_sequence = default_func(
        'shipment_internal_sequence')
    default_inventory_sequence = default_func('inventory_sequence')
    default_shipment_internal_transit = default_func(
        'shipment_internal_transit')


class ConfigurationSequence(ModelSQL, CompanyValueMixin):
    "Stock Configuration Sequence"
    __name__ = 'stock.configuration.sequence'
    shipment_in_sequence = fields.Many2One(
        'ir.sequence', "Supplier Shipment Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=',
                Id('stock', 'sequence_type_shipment_in')),
            ])
    shipment_in_return_sequence = fields.Many2One(
        'ir.sequence', "Supplier Return Shipment Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=',
                Id('stock', 'sequence_type_shipment_in_return')),
            ])
    shipment_out_sequence = fields.Many2One(
        'ir.sequence', "Customer Shipment Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=',
                Id('stock', 'sequence_type_shipment_out')),
            ])
    shipment_out_return_sequence = fields.Many2One(
        'ir.sequence', "Customer Return Shipment Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=',
                Id('stock', 'sequence_type_shipment_out_return')),
            ])
    shipment_internal_sequence = fields.Many2One(
        'ir.sequence', "Internal Shipment Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=',
                Id('stock', 'sequence_type_shipment_internal')),
            ])
    inventory_sequence = fields.Many2One(
        'ir.sequence', "Inventory Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=',
                Id('stock', 'sequence_type_inventory')),
            ])

    default_shipment_in_sequence = default_sequence('sequence_shipment_in')
    default_shipment_in_return_sequence = default_sequence(
        'sequence_shipment_in_return')
    default_shipment_out_sequence = default_sequence('sequence_shipment_out')
    default_shipment_out_return_sequence = default_sequence(
        'sequence_shipment_out_return')
    default_shipment_internal_sequence = default_sequence(
        'sequence_shipment_internal')
    default_inventory_sequence = default_sequence('sequence_inventory')


class ConfigurationLocation(ModelSQL, ValueMixin):
    "Stock Configuration Location"
    __name__ = 'stock.configuration.location'
    shipment_internal_transit = shipment_internal_transit

    @classmethod
    def default_shipment_internal_transit(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('stock', 'location_transit')
        except KeyError:
            return None
