# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.model import Workflow, ModelView, fields
from trytond.model.exceptions import AccessError
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, Id
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateTransition

from .exceptions import PackWarning


class PackageType(metaclass=PoolMeta):
    __name__ = 'stock.package.type'

    length = fields.Float('Length', digits=(16, Eval('length_digits', 2)),
        depends=['length_digits'])
    length_uom = fields.Many2One('product.uom', 'Length Unit',
        domain=[
            ('category', '=', Id('product', 'uom_cat_length')),
            ],
        states={
            'required': Bool(Eval('length')),
            },
        depends=['length', 'length_digits'])
    length_digits = fields.Function(fields.Integer('Length Digits'),
        'on_change_with_length_digits')
    height = fields.Float('Height', digits=(16, Eval('height_digits', 2)),
        depends=['height_digits'])
    height_uom = fields.Many2One('product.uom', 'Height Unit',
        domain=[
            ('category', '=', Id('product', 'uom_cat_length')),
            ],
        states={
            'required': Bool(Eval('height')),
            },
        depends=['height', 'height_digits'])
    height_digits = fields.Function(fields.Integer('Height Digits'),
        'on_change_with_height_digits')
    width = fields.Float('Width', digits=(16, Eval('width_digits', 2)),
        depends=['width_digits'])
    width_uom = fields.Many2One('product.uom', 'Width Unit',
        domain=[
            ('category', '=', Id('product', 'uom_cat_length')),
            ],
        states={
            'required': Bool(Eval('width')),
            },
        depends=['width', 'width_digits'])
    width_digits = fields.Function(fields.Integer('Width Digits'),
        'on_change_with_width_digits')

    @fields.depends('length_uom')
    def on_change_with_length_digits(self, name=None):
        return (self.length_uom.digits if self.length_uom
            else self.default_length_digits())

    @fields.depends('height_uom')
    def on_change_with_height_digits(self, name=None):
        return (self.height_uom.digits if self.height_uom
            else self.default_height_digits())

    @fields.depends('width_uom')
    def on_change_with_width_digits(self, name=None):
        return (self.width_uom.digits if self.width_uom
            else self.default_width_digits())

    @classmethod
    def default_length_digits(cls):
        return 2

    @classmethod
    def default_height_digits(cls):
        return 2

    @classmethod
    def default_width_digits(cls):
        return 2


class Package(metaclass=PoolMeta):
    __name__ = 'stock.package'

    shipping_reference = fields.Char('Shipping Reference',
        states={
            'readonly': Eval('_parent_shipment', {}).get('carrier', False),
            })
    shipping_label = fields.Binary('Shipping Label', readonly=True)

    @classmethod
    def search_rec_name(cls, name, clause):
        domain = super(Package, cls).search_rec_name(name, clause)
        return ['OR', domain,
            ('shipping_reference',) + tuple(clause[1:]),
            ]

    @classmethod
    def copy(cls, packages, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('shipping_reference', None)
        default.setdefault('shipping_label', None)
        return super(Package, cls).copy(packages, default=default)


class ShipmentOut(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    shipping_description = fields.Char('Shipping Description',
        states={
            'readonly': Eval('state').in_(['done', 'packed'])
            },
        depends=['state'])

    @classmethod
    def __setup__(cls):
        super(ShipmentOut, cls).__setup__()
        # The shipment reference will be set by the shipping service
        cls.reference.readonly = True
        cls._buttons.update({
                'create_shipping': {
                    'invisible': (Eval('reference', False)
                        | ~Eval('carrier', False)),
                    'readonly': (Eval('reference', False)
                        | ~Eval('root_packages', False)
                        | ~Eval('carrier', False)
                        | ~Eval('state').in_(['packed', 'done'])),
                    'depends': ['state', 'carrier', 'reference',
                        'root_packages'],
                    },
                })

    @classmethod
    def __register__(cls, module):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        model_data = ModelData.__table__()
        cursor = Transaction().connection.cursor()
        super(ShipmentOut, cls).__register__(module)

        # Migration from 4.6: rename create_shipping xml id
        if module == 'stock_package_shipping':
            cursor.execute(*model_data.update(
                    [model_data.fs_id],
                    ['shipment_out_create_shipping_button'],
                    where=(model_data.module == module)
                    & (model_data.model == 'ir.model.button')
                    & (model_data.fs_id == 'create_shipping_button')))

    @classmethod
    def search_rec_name(cls, name, clause):
        domain = super(ShipmentOut, cls).search_rec_name(name, clause)
        return ['OR', domain,
            ('reference',) + tuple(clause[1:]),
            ]

    @classmethod
    def validate(cls, shipments):
        super(ShipmentOut, cls).validate(shipments)
        for shipment in shipments:
            if shipment.carrier and shipment.carrier.shipping_service:
                method_name = ('validate_packing_%s'
                    % shipment.carrier.shipping_service)
                validator = getattr(shipment, method_name)
                validator()

    @classmethod
    @Workflow.transition('packed')
    def pack(cls, shipments):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        super(ShipmentOut, cls).pack(shipments)
        for shipment in shipments:
            if not shipment.carrier:
                name = 'shipment_out_no_carrier_%s' % shipment.id
                if Warning.check(name):
                    raise PackWarning(name,
                        gettext('stock_package_shipping'
                            '.msg_shipment_without_carrier',
                            shipment=shipment.rec_name))

    @classmethod
    @ModelView.button_action(
        'stock_package_shipping.act_create_shipping_wizard')
    def create_shipping(cls, shipments):
        for shipment in shipments:
            if shipment.state not in {'packed', 'done'}:
                raise AccessError(
                    gettext('stock_package_shipping.msg_shipment_not_packed',
                        shipment=shipment.rec_name))


# TODO Implement ShipmentInReturn


class CreateShipping(Wizard):
    'Create Shipping'
    __name__ = 'stock.shipment.create_shipping'

    start = StateTransition()

    def transition_start(self):
        shipping_service = self.record.carrier.shipping_service
        method_name = 'validate_packing_%s' % shipping_service
        getattr(self.record, method_name)()
        return 'end'
