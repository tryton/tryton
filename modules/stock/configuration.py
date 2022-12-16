# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields
from trytond.pyson import Eval

__all__ = ['Configuration']


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Stock Configuration'
    __name__ = 'stock.configuration'
    shipment_in_sequence = fields.Property(fields.Many2One('ir.sequence',
            'Supplier Shipment Sequence', domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'stock.shipment.in'),
                ], required=True))
    shipment_in_return_sequence = fields.Property(fields.Many2One(
            'ir.sequence', 'Supplier Return Shipment Sequence', domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'stock.shipment.in.return'),
                ], required=True))
    shipment_out_sequence = fields.Property(fields.Many2One('ir.sequence',
            'Customer Shipment Sequence', domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'stock.shipment.out'),
                ], required=True))
    shipment_out_return_sequence = fields.Property(fields.Many2One(
            'ir.sequence', 'Customer Return Shipment Sequence', domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'stock.shipment.out.return'),
                ], required=True))
    shipment_internal_sequence = fields.Property(fields.Many2One(
            'ir.sequence', 'Internal Shipment Sequence', domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'stock.shipment.internal'),
                ], required=True))
    shipment_internal_transit = fields.Property(fields.Many2One(
            'stock.location', 'Internal Shipment Transit', domain=[
                ('type', '=', 'storage'),
                ], required=True))
    inventory_sequence = fields.Property(fields.Many2One(
            'ir.sequence', 'Inventory Sequence', domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'stock.inventory'),
                ], required=True))
