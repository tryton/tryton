# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.model import (ModelView, ModelSQL, ModelSingleton, ValueMixin,
    fields)
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.tools.multivalue import migrate_property
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)

sequences = ['shipment_in_sequence', 'shipment_in_return_sequence',
    'shipment_out_sequence', 'shipment_out_return_sequence',
    'shipment_internal_sequence', 'inventory_sequence']
shipment_internal_transit = fields.Many2One(
    'stock.location', "Internal Shipment Transit", required=True,
    domain=[
        ('type', '=', 'storage'),
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
                ('code', '=', 'stock.shipment.in'),
                ],
            help="Used to generate the number given to supplier shipments."))
    shipment_in_return_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Supplier Return Shipment Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'stock.shipment.in.return'),
                ],
            help="Used to generate the number given to supplier return "
            "shipments."))
    shipment_out_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Customer Shipment Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'stock.shipment.out'),
                ],
            help="Used to generate the number given to customer "
            "shipments."))
    shipment_out_return_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Customer Return Shipment Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'stock.shipment.out.return'),
                ],
            help="Used to generate the number given to customer return "
            "shipments."))
    shipment_internal_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Internal Shipment Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'stock.shipment.internal'),
                ],
            help="Used to generate the number given to internal "
            "shipments."))
    inventory_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Inventory Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'stock.inventory'),
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
            ('code', '=', 'stock.shipment.in'),
            ],
        depends=['company'])
    shipment_in_return_sequence = fields.Many2One(
        'ir.sequence', "Supplier Return Shipment Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('code', '=', 'stock.shipment.in.return'),
            ],
        depends=['company'])
    shipment_out_sequence = fields.Many2One(
        'ir.sequence', "Customer Shipment Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('code', '=', 'stock.shipment.out'),
            ],
        depends=['company'])
    shipment_out_return_sequence = fields.Many2One(
        'ir.sequence', "Customer Return Shipment Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('code', '=', 'stock.shipment.out.return'),
            ],
        depends=['company'])
    shipment_internal_sequence = fields.Many2One(
        'ir.sequence', "Internal Shipment Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('code', '=', 'stock.shipment.internal'),
            ],
        depends=['company'])
    inventory_sequence = fields.Many2One(
        'ir.sequence', "Inventory Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('code', '=', 'stock.inventory'),
            ],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)

        super(ConfigurationSequence, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.extend(sequences)
        value_names.extend(sequences)
        fields.append('company')
        migrate_property(
            'stock.configuration', field_names, cls, value_names,
            fields=fields)

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
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)

        super(ConfigurationLocation, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('shipment_internal_transit')
        value_names.append('shipment_internal_transit')
        migrate_property(
            'stock.configuration', field_names, cls, value_names,
            fields=fields)

    @classmethod
    def default_shipment_internal_transit(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('stock', 'location_transit')
        except KeyError:
            return None
