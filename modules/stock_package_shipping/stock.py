# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import mimetypes

from sql import Column

from trytond.config import config
from trytond.i18n import gettext
from trytond.model import ModelView, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.report import Report
from trytond.transaction import Transaction
from trytond.wizard import StateAction, StateTransition, Wizard

from .exceptions import PackWarning

if config.getboolean('stock_package_shipping', 'filestore', default=False):
    file_id = 'shipping_label_id'
    store_prefix = config.get(
        'stock_package_shipping', 'store_prefix', default=None)
else:
    file_id = store_prefix = None


class Package(metaclass=PoolMeta):
    __name__ = 'stock.package'

    shipping_reference = fields.Char('Shipping Reference',
        states={
            'readonly': Eval('has_shipping_service', False),
            })
    shipping_label = fields.Binary(
        "Shipping Label", readonly=True,
        file_id=file_id, store_prefix=store_prefix)
    shipping_label_id = fields.Char(
        "Shipping Label ID", readonly=True, strip=False)
    shipping_label_mimetype = fields.Char(
        "Shipping Label MIME Type", readonly=True)
    shipping_tracking_url = fields.Function(
        fields.Char(
            "Shipping Tracking URL",
            states={
                'invisible': ~Eval('shipping_tracking_url'),
                }),
        'get_shipping_tracking_url')
    has_shipping_service = fields.Function(
        fields.Boolean("Has Shipping Service"),
        'on_change_with_has_shipping_service')

    def get_shipping_tracking_url(self, name):
        return

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.shipping_reference.search_unaccented = False
        cls._buttons.update(
            print_shipping_label={
                'invisible': ~Eval('shipping_label'),
                'depends': ['shipping_label'],
                })

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        PackageType = pool.get('stock.package.type')
        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        package_type = PackageType.__table__()
        table_h = cls.__table_handler__(module_name)
        dimension_columns = [
            'length', 'length_uom',
            'height', 'height_uom',
            'width', 'width_uom']
        dimension_exists = any(
            table_h.column_exist(c) for c in dimension_columns)

        super().__register__(module_name)

        # Migration from 5.8: Update dimensions on package from package_type
        if not dimension_exists:
            columns = []
            values = []
            for c in dimension_columns:
                columns.append(Column(table, c))
                values.append(package_type.select(
                        Column(package_type, c),
                        where=package_type.id == table.type))
            cursor.execute(*table.update(
                    columns=columns,
                    values=values))

    @fields.depends('shipment')
    def on_change_with_has_shipping_service(self, name=None):
        return bool(
            self.shipment
            and getattr(self.shipment, 'carrier', None)
            and getattr(self.shipment.carrier, 'shipping_service', None))

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, value = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        domain = super(Package, cls).search_rec_name(name, clause)
        return [bool_op,
            domain,
            ('shipping_reference', *clause[1:]),
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

    @classmethod
    @ModelView.button_action('stock_package_shipping.report_shipping_label')
    def print_shipping_label(cls, packages):
        pass


class ShippingMixin:
    __slots__ = ()

    shipping_reference = fields.Char(
        "Shipping Reference",
        states={
            'readonly': Eval('has_shipping_service', False),
            })
    shipping_description = fields.Char('Shipping Description',
        states={
            'readonly': Eval('state').in_(['done', 'packed'])
            })
    has_shipping_service = fields.Function(
        fields.Boolean("Has Shipping Service"),
        'on_change_with_has_shipping_service')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.shipping_reference.search_unaccented = False
        cls._buttons.update({
                'create_shipping': {
                    'invisible': (Eval('shipping_reference', False)
                        | ~Eval('carrier', False)),
                    'readonly': (Eval('shipping_reference', False)
                        | ~Eval('root_packages', False)
                        | ~Eval('carrier', False)
                        | ~Eval('state').in_(['packed', 'done'])),
                    'depends': [
                        'state', 'carrier', 'shipping_reference',
                        'root_packages'],
                    },
                })

    @classmethod
    def __register__(cls, module):
        table = cls.__table__()
        table_h = cls.__table_handler__(module)
        cursor = Transaction().connection.cursor()

        fill_shiping_reference = (
            table_h.column_exist('reference')
            and not table_h.column_exist('shipping_reference'))

        super().__register__(module)

        # Migration from 6.8: fill shipping_reference
        if fill_shiping_reference:
            cursor.execute(*table.update(
                    [table.shipping_reference],
                    [table.reference]))

    @fields.depends('carrier')
    def on_change_with_has_shipping_service(self, name=None):
        return bool(self.carrier and self.carrier.shipping_service)

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, value = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        domain = super().search_rec_name(name, clause)
        return [bool_op,
            domain,
            ('shipping_reference', *clause[1:]),
            ]

    @classmethod
    def validate(cls, shipments):
        super().validate(shipments)
        for shipment in shipments:
            if shipment.has_shipping_service:
                method_name = ('validate_packing_%s'
                    % shipment.carrier.shipping_service)
                validator = getattr(shipment, method_name)
                validator()

    @classmethod
    def check_no_carrier(cls, shipments):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        for shipment in shipments:
            if (not shipment.carrier
                    and shipment.delivery_address
                    and shipment.warehouse not in
                    shipment.delivery_address.warehouses):
                name = 'shipment_out_no_carrier_%s' % shipment
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
            if shipment.state not in shipment.shipping_allowed:
                raise AccessError(
                    gettext('stock_package_shipping.msg_shipment_not_packed',
                        shipment=shipment.rec_name))

    @property
    def shipping_allowed(self):
        raise NotImplementedError

    @property
    def shipping_warehouse(self):
        raise NotImplementedError

    @property
    def shipping_to(self):
        raise NotImplementedError

    @property
    def shipping_to_address(self):
        raise NotImplementedError


class ShipmentOut(ShippingMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    @classmethod
    @ModelView.button
    @Workflow.transition('packed')
    def pack(cls, shipments):
        super().pack(shipments)
        cls.check_no_carrier(shipments)

    @property
    def shipping_allowed(self):
        return {'packed', 'done'}

    @property
    def shipping_warehouse(self):
        return self.warehouse

    @property
    def shipping_to(self):
        return self.customer

    @property
    def shipping_to_address(self):
        return self.delivery_address


class ShipmentInReturn(ShippingMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'

    carrier = fields.Many2One(
        'carrier', "Carrier",
        states={
            'readonly': ~Eval('state').in_(['draft', 'waiting', 'assigned']),
            })

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, shipments):
        super().done(shipments)
        cls.check_no_carrier(shipments)

    @property
    def shipping_allowed(self):
        return {'assigned', 'done'}

    @property
    def shipping_warehouse(self):
        return self.from_location.warehouse

    @property
    def shipping_to(self):
        return self.supplier

    @property
    def shipping_to_address(self):
        return self.delivery_address


class CreateShipping(Wizard):
    'Create Shipping'
    __name__ = 'stock.shipment.create_shipping'

    start = StateTransition()

    def transition_start(self):
        if self.record.has_shipping_service:
            shipping_service = self.record.carrier.shipping_service
            method_name = 'validate_packing_%s' % shipping_service
            getattr(self.record, method_name)()
        return 'end'


class ShippingLabel(Report):
    __name__ = 'stock.package.shipping_label'

    @classmethod
    def render(cls, report, report_context):
        package = report_context['record']
        if not package:
            return '.bin', b''
        extension = mimetypes.guess_extension(
            package.shipping_label_mimetype or 'application/octet-stream')
        # Return with extension so convert has it
        return extension, package.shipping_label or b''

    @classmethod
    def convert(cls, report, data, **kwargs):
        return data


class PrintShippingLabel(Wizard):
    "Print Shipping Label"
    __name__ = 'stock.shipment.print_shipping_label'
    start_state = 'print_'
    print_ = StateAction('stock_package_shipping.report_shipping_label')

    def do_print_(self, action):
        package_ids = []
        labels = set()
        for shipment in self.records:
            for package in shipment.packages:
                if (package.shipping_label
                        and package.shipping_label not in labels):
                    package_ids.append(package.id)
                    labels.add(package.shipping_label)
        return action, {'ids': package_ids}
