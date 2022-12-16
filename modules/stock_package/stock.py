# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, ModelView, Workflow, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.report import Report

__all__ = ['Configuration', 'Package', 'Type', 'Move',
    'ShipmentOut', 'ShipmentInReturn', 'PackageLabel']


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'stock.configuration'
    package_sequence = fields.Property(fields.Many2One('ir.sequence',
            'Package Sequence', domain=[
                ('company', 'in', [Eval('context', {}).get('company'), None]),
                ('code', '=', 'stock.package'),
                ], required=True))


class Package(ModelSQL, ModelView):
    'Stock Package'
    __name__ = 'stock.package'
    _rec_name = 'code'
    code = fields.Char('Code', select=True, readonly=True, required=True)
    type = fields.Many2One('stock.package.type', 'Type', required=True)
    shipment = fields.Reference('Shipment', selection='get_shipment',
        select=True)
    moves = fields.One2Many('stock.move', 'package', 'Moves',
        domain=[
            ('shipment', '=', Eval('shipment')),
            ('to_location.type', 'in', ['customer', 'supplier']),
            ],
        add_remove=[
            ('package', '=', None),
            ],
        depends=['shipment'])
    parent = fields.Many2One('stock.package', 'Parent', select=True,
        ondelete='CASCADE', domain=[('shipment', '=', Eval('shipment'))],
        depends=['shipment'])
    children = fields.One2Many('stock.package', 'parent', 'Children',
        domain=[('shipment', '=', Eval('shipment'))],
        depends=['shipment'])

    @staticmethod
    def _get_shipment():
        'Return list of Model names for shipment Reference'
        return [
            'stock.shipment.out',
            'stock.shipment.in.return',
            ]

    @classmethod
    def get_shipment(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        models = cls._get_shipment()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('stock.configuration')

        vlist = [v.copy() for v in vlist]
        config = Config(1)
        for values in vlist:
            values['code'] = Sequence.get_id(config.package_sequence)
        return super(Package, cls).create(vlist)

    @classmethod
    def validate(cls, packages):
        super(Package, cls).validate(packages)
        cls.check_recursion(packages)


class Type(ModelSQL, ModelView):
    'Stock Package Type'
    __name__ = 'stock.package.type'
    name = fields.Char('Name', required=True)


class Move:
    __metaclass__ = PoolMeta
    __name__ = 'stock.move'
    package = fields.Many2One('stock.package', 'Package', select=True)


class PackageMixin(object):
    packages = fields.One2Many('stock.package', 'shipment', 'Packages',
        states={
            'readonly': Eval('state').in_(['done', 'cancel']),
            })
    root_packages = fields.Function(fields.One2Many('stock.package',
            'shipment', 'Packages',
            domain=[('parent', '=', None)],
            states={
                'readonly': Eval('state').in_(['done', 'cancel']),
                }), 'get_root_packages', setter='set_root_packages')

    def get_root_packages(self, name):
        return [p.id for p in self.packages if not p.parent]

    @classmethod
    def set_root_packages(cls, shipments, name, value):
        if not value:
            return
        cls.write(shipments, {
                'packages': value,
                })


class ShipmentOut(PackageMixin, object):
    __metaclass__ = PoolMeta
    __name__ = 'stock.shipment.out'

    @classmethod
    def __setup__(cls):
        super(ShipmentOut, cls).__setup__()
        cls._error_messages.update({
                'package_mismatch': ('Not all Outgoing Moves of '
                    'Customer Shipment "%s" are packaged.'),
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, shipments):
        super(ShipmentOut, cls).done(shipments)
        for shipment in shipments:
            if not shipment.packages:
                continue
            if (len(shipment.outgoing_moves)
                    != sum(len(p.moves) for p in shipment.packages)):
                cls.raise_user_error('package_mismatch', shipment.rec_name)


class ShipmentInReturn(PackageMixin, object):
    __metaclass__ = PoolMeta
    __name__ = 'stock.shipment.in.return'

    @classmethod
    def __setup__(cls):
        super(ShipmentInReturn, cls).__setup__()
        cls._error_messages.update({
                'package_mismatch': ('Not all Outgoing Moves of '
                    'Supplier Return Shipment "%s" are packaged.'),
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, shipments):
        super(ShipmentInReturn, cls).done(shipments)
        for shipment in shipments:
            if not shipment.packages:
                continue
            if (len(shipment.moves)
                    != sum(len(p.moves) for p in shipment.packages)):
                cls.raise_user_error('package_mismatch', shipment.rec_name)


class PackageLabel(Report):
    'Package Label'
    __name__ = 'stock.package.label'
