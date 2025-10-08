# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt
from functools import wraps
from random import Random

from sql.functions import CharLength

from trytond.i18n import gettext, lazy_gettext
from trytond.model import (
    DeactivableMixin, DictSchemaMixin, MatchMixin, ModelSingleton, ModelSQL,
    ModelStorage, ModelView, Unique, Workflow, dualmethod, fields)
from trytond.model.exceptions import AccessError, ButtonActionException
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin, employee_field, reset_employee,
    set_employee)
from trytond.pool import Pool
from trytond.pyson import Eval, Id, If
from trytond.transaction import Transaction
from trytond.wizard import Button, StateTransition, StateView, Wizard

from .exceptions import InspectionError, InspectionValidationError


class Configuration(
        ModelSingleton, CompanyMultiValueMixin, ModelSQL, ModelView):
    __name__ = 'quality.configuration'

    inspection_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Inspection Sequence", required=True,
            domain=[
                ('company', 'in', [
                        Eval('context', {}).get('company', -1),
                        None]),
                ('sequence_type', '=',
                    Id('quality', 'sequence_type_quality_inspection')),
                ]))
    alert_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Alert Sequence", required=True,
            domain=[
                ('company', 'in', [
                        Eval('context', {}).get('company', -1),
                        None]),
                ('sequence_type', '=',
                    Id('quality', 'sequence_type_quality_alert')),
                ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'inspection_sequence', 'alert_sequence'}:
            return pool.get('quality.configuration.sequence')
        return super().multivalue_model(field)

    @classmethod
    def default_inspection_sequence(cls, **pattern):
        return (
            cls.multivalue_model('inspection_sequence')
            .default_inspection_sequence())

    @classmethod
    def default_alert_sequence(cls, **pattern):
        return (
            cls.multivalue_model('alert_sequence')
            .default_alert_sequence())


class ConfigurationSequence(CompanyValueMixin, ModelSQL):
    __name__ = 'quality.configuration.sequence'
    inspection_sequence = fields.Many2One(
        'ir.sequence', "Inspection Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=',
                Id('quality', 'sequence_type_quality_inspection')),
            ])
    alert_sequence = fields.Many2One(
        'ir.sequence', "Alert Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=',
                Id('quality', 'sequence_type_quality_alert')),
            ])

    @classmethod
    def default_inspection_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('quality', 'sequence_quality_inspection')
        except KeyError:
            return None

    @classmethod
    def default_alert_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('quality', 'sequence_quality_alert')
        except KeyError:
            return None


class ControlledMixin(ModelStorage):
    __slots__ = ()

    quality_inspections = fields.One2Many(
        'quality.inspection', 'origin',
        lazy_gettext('quality.msg_quality_inspections'), readonly=True)

    @classmethod
    def copy(cls, records, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('quality_inspections')
        return super().copy(records, default=default)

    def quality_control_pattern(self, operation):
        return {}

    @dualmethod
    def quality_control_needed(cls, records, operation):
        pool = Pool()
        Control = pool.get('quality.control')
        return bool(Control.get_inspections(records, operation))

    def quality_controlled_for(self, operation):
        operation = f'{self.__name__}:{operation}'
        return any(
            i for i in self.quality_inspections
            if operation in i.control.operations)

    def quality_inspections_pending(self):
        return [i for i in self.quality_inspections if i.state == 'pending']

    def quality_inspections_failed(self):
        return [
            i for i in self.quality_inspections
            if i.state == 'failed'
            and (any(a.state in {'open', 'processing'} for a in i.alerts)
                or not i.alerts)]

    @staticmethod
    def control(operation, wizard):
        def decorator(func):
            @wraps(func)
            def wrapper(cls, records):
                if (cls.quality_control_needed(records, operation)
                        or any(
                            r.quality_inspections_pending() for r in records)):
                    raise ButtonActionException(wizard)
                if any(r.quality_inspections_failed() for r in records):
                    raise InspectionError(gettext(
                            'quality.msg_quality_inspection_failed'))
                return func(cls, records)
            return wrapper
        return decorator


class Control(DeactivableMixin, MatchMixin, ModelSQL, ModelView):
    __name__ = 'quality.control'

    name = fields.Char("Name", required=True, translate=True)

    operations = fields.MultiSelection([
            ('stock.shipment.in:receive', "Supplier Shipment Received"),
            ('stock.shipment.in:do', "Supplier Shipment Done"),
            ('stock.shipment.out:pick', "Customer Shipment Picked"),
            ('stock.shipment.out:pack', "Customer Shipment Packed"),
            ('stock.shipment.out.return:receive',
                "Customer Shipment Return Received"),
            ('stock.shipment.out.return:do',
                "Customer Shipment Return Done"),
            ('stock.shipment.internal:ship', "Internal Shipment Shipped"),
            ('stock.shipment.internal:do', "Internal Shipment Done"),
            ('production:run', "Production Run"),
            ('production:do', "Production Done"),
            ], "Operations",
        help="The operations for which the control is performed.")
    frequency = fields.Float(
        "Frequency", digits=(1, 4), required=True,
        domain=[
            ('frequency', '>=', 0),
            ('frequency', '<=', 1),
            ],
        help="How often the control must be done.")
    company = fields.Many2One(
        'company.company', "Company", ondelete='RESTRICT',
        help="The company to which the control applies.")
    product_category = fields.Many2One(
        'product.category', "Product Category", ondelete='RESTRICT',
        help="The product category to which the control applies.")
    product = fields.Many2One(
        'product.product', 'Product', ondelete='RESTRICT',
        context={
            'company': Eval('company', Eval('context', {}).get('company')),
            },
        help="The product to which the control applies.")

    points = fields.One2Many(
        'quality.control.point', 'control', "Points", required=True)

    @classmethod
    def __register__(cls, module):
        table = cls.__table__()
        transaction = Transaction()
        database = transaction.database
        cursor = transaction.connection.cursor()
        update = transaction.connection.cursor()

        super().__register__(module)

        # Migration from 7.0: rename done button to do
        for old, new in [
                ('stock.shipment.in:done', 'stock.shipment.in:do'),
                ('stock.shipment.out.return:done',
                    'stock.shipment.out.return:do'),
                ('stock.shipment.internal:done',
                    'stock.shipment.internal:do'),
                ('production:done', 'production:do'),
                ]:
            try:
                where = database.json_key_exists(table.operations, old)
            except NotImplementedError:
                where = table.operations.like(f'%{old}%')
            cursor.execute(*table.select(
                    table.id, table.operations, where=where))
            for id_, operations in cursor:
                if isinstance(operations, (list, tuple)):
                    value = cls.operations.sql_format(
                        [x.replace(old, new) for x in operations])
                else:
                    value = operations.replace(old, new)
                update.execute(*table.update(
                        [table.operations],
                        [value],
                        where=table.id == id_))

    @classmethod
    def default_frequency(cls):
        return 1

    @classmethod
    def get_inspections(cls, records, operation):
        pool = Pool()
        Inspection = pool.get('quality.inspection')

        records = [
            r for r in records if not r.quality_controlled_for(operation)]
        inspections = []
        if records:
            name = records[0].__name__
            assert len({r.__name__ for r in records}) == 1

            controls = cls.search([
                    ('operations', 'in', f'{name}:{operation}'),
                    ])
            for control in controls:
                for record in records:
                    pattern = record.quality_control_pattern(operation)
                    if control.match(pattern) and control.choose(record):
                        inspections.append(
                            Inspection.get_from_control(control, record))
        return inspections

    def match(self, pattern, match_none=False):
        pool = Pool()
        Product = pool.get('product.product')
        pattern = pattern.copy()

        def parents(categories):
            for category in categories:
                while category:
                    yield category
                    category = category.parent

        products = set(pattern.pop('products', []))
        if pattern.get('product'):
            products.add(pattern.pop('product'))
        if products:
            products = Product.browse(products)
            if self.product and self.product not in products:
                return False
            if self.product_category:
                categories = {
                    c for p in products for c in parents(p.categories_all)}
                if self.product_category not in categories:
                    return False
        return super().match(pattern, match_none=match_none)

    def choose(self, record):
        random = Random(record.id)
        return random.random() <= self.frequency


class ControlPoint(DictSchemaMixin, ModelSQL, ModelView):
    __name__ = 'quality.control.point'

    control = fields.Many2One(
        'quality.control', "Control", required=True, ondelete='CASCADE')
    tolerance_lower = fields.Float(
        "Tolerance Lower",
        states={
            'invisible': ~Eval('type_').in_(['integer', 'float', 'numeric']),
            })
    tolerance_upper = fields.Float(
        "Tolerance Upper",
        states={
            'invisible': ~Eval('type_').in_(['integer', 'float', 'numeric']),
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('control_point_unique', Unique(t, t.control, t.name),
                'quality.msg_control_point_unique'),
            ]
        cls.__access__.add('control')
        cls.type_.selection = [
            ('boolean', lazy_gettext('ir.msg_dict_schema_boolean')),
            ('integer', lazy_gettext('ir.msg_dict_schema_integer')),
            ('float', lazy_gettext('ir.msg_dict_schema_float')),
            ('numeric', lazy_gettext('ir.msg_dict_schema_numeric')),
            ]

    def check(self, value):
        if self.type_ == 'boolean':
            return value
        elif self.type_ in {'integer', 'float', 'numeric'}:
            result = True
            if value is None:
                result = False
            elif (self.tolerance_lower is not None
                    and self.tolerance_lower > value):
                result = False
            elif (self.tolerance_upper is not None
                    and self.tolerance_upper < value):
                result = False
            return result


class Inspection(Workflow, ModelSQL, ModelView):
    __name__ = 'quality.inspection'
    _rec_name = 'number'

    _states = {
        'readonly': Eval('state') != 'pending',
        }

    number = fields.Char("Number", required=True, readonly=True)
    company = fields.Many2One(
        'company.company', "Company", required=True, states=_states)
    origin = fields.Reference(
        "Origin", 'get_origins', states=_states,
        domain={
            'stock.shipment.in': [
                ('company', '=', Eval('company', -1)),
                ],
            'stock.shipment.out': [
                ('company', '=', Eval('company', -1)),
                ],
            'stock.shipment.out.return': [
                ('company', '=', Eval('company', -1)),
                ],
            'stock.shipment.internal': [
                ('company', '=', Eval('company', -1)),
                ],
            'production': [
                ('company', '=', Eval('company', -1)),
                ],
            })
    control = fields.Many2One(
        'quality.control', "Control", required=True, states=_states,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ])

    points = fields.Dict(
        'quality.control.point', "Points",
        domain=[
            ('control', '=', Eval('control', -1)),
            ],
        states=_states)

    alerts = fields.One2Many(
        'quality.alert', 'origin', "Alerts",
        states={
            'invisible': (
                (Eval('state') != 'failed')
                | ~Eval('alerts')),
            })

    processed_by = employee_field("Processed by", states=['passed', 'failed'])
    processed_at = fields.DateTime("Processed at", states=_states)
    passed_by = employee_field("Passed by", states=['passed'])
    failed_by = employee_field("Failed by", states=['failed'])

    state = fields.Selection([
            ('pending', "Pending"),
            ('passed', "Passed"),
            ('failed', "Failed"),
            ], "State", required=True, readonly=True, sort=False)

    @classmethod
    def __setup__(cls):
        cls.number.search_unaccented = False
        super().__setup__()
        cls._transitions |= {
            ('pending', 'passed'),
            ('pending', 'failed'),
            ('passed', 'failed'),
            ('passed', 'pending'),
            ('failed', 'passed'),
            ('failed', 'pending'),
            }
        cls._buttons.update({
                'pending': {
                    'invisible': ~Eval('state').in_(['passed', 'failed']),
                    'icon': 'tryton-back',
                    'depends': ['state'],
                    },
                'process': {
                    'invisible': Eval('state') != 'pending',
                    'icon': 'tryton-forward',
                    'depends': ['state'],
                    },
                'pass_': {
                    'invisible': Eval('state') != 'failed',
                    'icon': 'tryton-ok',
                    'depends': ['state'],
                    },
                'fail': {
                    'invisible': Eval('state') != 'passed',
                    'icon': 'tryton-cancel',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def order_number(cls, tables):
        table, _ = tables[None]
        return [CharLength(table.number), table.number]

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_state(cls):
        return 'pending'

    @classmethod
    def _get_origins(cls):
        return [
            'stock.shipment.in',
            'stock.shipment.out',
            'stock.shipment.out.return',
            'stock.shipment.internal',
            'production',
            ]

    @classmethod
    def get_origins(cls):
        pool = Pool()
        IrModel = pool.get('ir.model')
        models = cls._get_origins()
        models = IrModel.search([
                ('name', 'in', models),
                ])
        return [(None, '')] + [(m.name, m.string) for m in models]

    @fields.depends('control', 'points')
    def on_change_control(self):
        if self.control:
            points = dict(self.points) if self.points is not None else {}
            points.update(
                (p.name, None) for p in self.control.points)
            self.points = points

    def validate_points(self):
        points = {p.name: p.string for p in self.control.points}
        missing = points.keys() - (self.points or {}).keys()
        if missing:
            raise InspectionValidationError(
                gettext('quality.msg_quality_inspection_missing_point',
                    inspection=self.rec_name,
                    points=', '.join(points[m] for m in missing),
                    ))

    def check(self):
        for point in self.control.points:
            if not point.check(self.points.get(point.name)):
                return False
        return True

    @classmethod
    def view_attributes(cls):
        attributes = super().view_attributes() + [
            ('/tree', 'visual', If(Eval('state') == 'failed', 'danger', '')),
            ]
        if Transaction().context.get('inspect'):
            attributes.extend([
                    ('//field[@name="control"]', 'readonly', 1),
                    ('//*[@name="origin"]', 'invisible', 1),
                    ('//page[@id="other"]', 'invisible', 1),
                    ('//*[@name="state"]', 'invisible', 1),
                    ('//group[@id="buttons"]', 'states', {'invisible': True}),
                    ])

        return attributes

    @classmethod
    @ModelView.button
    @Workflow.transition('pending')
    @reset_employee('processed_by', 'passed_by', 'failed_by')
    def pending(cls, inspections):
        cls.write(inspections, {
                'processed_at': None,
                })

    @dualmethod
    @ModelView.button
    @set_employee('processed_by')
    def process(cls, inspections):
        for inspection in inspections:
            inspection.validate_points()
        cls.write([i for i in inspections if not i.processed_at], {
                'processed_at': dt.datetime.now(),
                })
        to_pass, to_fail = [], []
        for inspection in inspections:
            if inspection.check():
                to_pass.append(inspection)
            else:
                to_fail.append(inspection)
        cls.pass_(to_pass)
        cls.fail(to_fail)

    @classmethod
    @ModelView.button
    @Workflow.transition('passed')
    @reset_employee('failed_by')
    @set_employee('passed_by')
    def pass_(cls, inspections):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('failed')
    @reset_employee('passed_by')
    @set_employee('failed_by')
    def fail(cls, inspections):
        pool = Pool()
        Alert = pool.get('quality.alert')
        alerts = []
        for inspection in inspections:
            if not inspection.alerts:
                alerts.append(inspection.get_alert())
        Alert.save(alerts)

    def get_alert(self):
        pool = Pool()
        Alert = pool.get('quality.alert')
        return Alert(
            company=self.company,
            origin=self)

    @classmethod
    def preprocess_values(cls, mode, values):
        pool = Pool()
        Configuration = pool.get('quality.configuration')
        values = super().preprocess_values(mode, values)
        if mode == 'create' and not values.get('number'):
            company_id = values.get('company', cls.default_company())
            if company_id is not None:
                configuration = Configuration(1)
                if sequence := configuration.get_multivalue(
                        'inspection_sequence', company=company_id):
                    values['number'] = sequence.get()
        return values

    @classmethod
    def check_modification(
            cls, mode, inspections, values=None, external=False):
        super().check_modification(
            mode, inspections, values=values, external=external)
        if mode == 'delete':
            for inspection in inspections:
                if inspection.state != 'pending':
                    raise AccessError(gettext(
                            'quality.msg_inspection_delete_non_pending',
                            inspection=inspection.rec_name))

    @classmethod
    def copy(cls, inspections, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('number')
        default.setdefault('processed_by')
        default.setdefault('processed_at')
        default.setdefault('passed_by')
        default.setdefault('failed_by')
        return super().copy(inspections, default=default)

    @classmethod
    def get_from_control(cls, control, origin=None):
        return cls(control=control, origin=origin)


class Alert(Workflow, ModelSQL, ModelView):
    __name__ = 'quality.alert'
    _rec_name = 'number'

    _states = {
        'readonly': ~Eval('state').in_(['open', 'processing']),
        }

    number = fields.Char("Number", required=True, readonly=True)
    company = fields.Many2One(
        'company.company', "Company", required=True, states=_states)
    title = fields.Char("Title")
    origin = fields.Reference(
        "Origin", 'get_origins', required=True,
        domain={
            'quality.inspection': [
                ('company', '=', Eval('company', -1)),
                ],
            })
    description = fields.Text("Description")

    processed_by = employee_field(
        "Processed by", states=['processing', 'resolved', 'deferred'])
    deferred_by = employee_field(
        "Deferred by", states=['deferred', 'resolved'])
    resolved_by = employee_field("Resolved by", states=['resolved'])

    state = fields.Selection([
            ('open', "Open"),
            ('processing', "Processing"),
            ('deferred', "Deferred"),
            ('resolved', "Resolved"),
            ], "State", required=True, readonly=True, sort=False)

    @classmethod
    def __setup__(cls):
        cls.number.search_unaccented = False
        super().__setup__()
        cls._transitions |= {
            ('open', 'processing'),
            ('processing', 'resolved'),
            ('processing', 'deferred'),
            ('deferred', 'processing'),
            ('resolved', 'open'),
            }
        cls._buttons.update({
                'open': {
                    'invisible': Eval('state') != 'resolved',
                    'icon': 'tryton-back',
                    'depends': ['state'],
                    },
                'process': {
                    'invisible': ~Eval('state').in_(['open', 'deferred']),
                    'icon': 'tryton-forward',
                    'depends': ['state'],
                    },
                'defer': {
                    'invisible': Eval('state') != 'processing',
                    'icon': 'tryton-archive',
                    'depends': ['state'],
                    },
                'resolve': {
                    'invisible': Eval('state') != 'processing',
                    'icon': 'tryton-ok',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_state(cls):
        return 'open'

    @classmethod
    def _get_origins(cls):
        return ['quality.inspection']

    @classmethod
    def get_origins(cls):
        pool = Pool()
        IrModel = pool.get('ir.model')
        models = cls._get_origins()
        models = IrModel.search([
                ('name', 'in', models),
                ])
        return [(None, '')] + [(m.name, m.string) for m in models]

    @classmethod
    @ModelView.button
    @Workflow.transition('open')
    @reset_employee('processed_by', 'deferred_by', 'resolved_by')
    def open(cls, alerts):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('processing')
    @set_employee('processed_by')
    def process(cls, alerts):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('deferred')
    @reset_employee('processed_by')
    @set_employee('deferred_by')
    def defer(cls, alerts):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('resolved')
    @set_employee('resolved_by')
    def resolve(cls, alerts):
        pass

    @classmethod
    def preprocess_values(cls, mode, values):
        pool = Pool()
        Configuration = pool.get('quality.configuration')
        values = super().preprocess_values(mode, values)
        if mode == 'create' and not values.get('number'):
            company_id = values.get('company', cls.default_company())
            if company_id is not None:
                configuration = Configuration(1)
                if sequence := configuration.get_multivalue(
                        'alert_sequence', company=company_id):
                    values['number'] = sequence.get()
        return values

    @classmethod
    def copy(cls, inspections, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('number')
        default.setdefault('processed_by')
        default.setdefault('deferred_by')
        default.setdefault('resolved_by')
        return super().copy(inspections, default=default)


class InspectStateView(StateView):
    def get_view(self, wizard, state_name):
        with Transaction().set_context(inspect=True):
            return super().get_view(wizard, state_name)

    def get_defaults(self, wizard, state_name, fields):
        return {}


class Inspect(Wizard):
    __name__ = 'quality.inspect'

    start = StateTransition()
    store = StateView('quality.inspect.store', None, [])
    next_ = StateTransition()
    inspection = InspectStateView(
        'quality.inspection', 'quality.quality_inspection_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Skip", 'next_', 'tryton-forward', validate=False),
            Button("Save", 'save', 'tryton-ok', default=True),
            ])
    save = StateTransition()

    def transition_start(self):
        pool = Pool()
        Control = pool.get('quality.control')
        Inspection = pool.get('quality.inspection')
        Store = pool.get('quality.inspect.store')

        context = Transaction().context
        operation = self.operation(context.get('action_id'))

        inspections = Control.get_inspections(self.records, operation)
        Inspection.save(inspections)

        inspections = []
        for record in self.records:
            inspections.extend(record.quality_inspections_pending())
        self.store = Store(inspections=inspections)
        return 'inspection' if self.store.inspections else 'end'

    @property
    def _operations(self):
        return {
            'quality.wizard_stock_shipment_in_inspect_receive': 'receive',
            'quality.wizard_stock_shipment_in_inspect_done': 'done',
            'quality.wizard_stock_shipment_out_inspect_pick': 'pick',
            'quality.wizard_stock_shipment_out_inspect_pack': 'pack',
            'quality.wizard_stock_shipment_out_return_inspect_receive':
            'receive',
            'quality.wizard_stock_shipment_out_return_inspect_done': 'done',
            'quality.wizard_stock_shipment_internal_inspect_ship': 'ship',
            'quality.wizard_stock_shipment_internal_inspect_done': 'done',
            'quality.wizard_production_inspect_run': 'run',
            'quality.wizard_production_inspect_done': 'done',
            }

    def operation(self, action_id):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        for xml_id, operation in self._operations.items():
            try:
                if action_id == ModelData.get_id(xml_id):
                    return operation
            except KeyError:
                continue

    def transition_next_(self):
        self.store.inspections = self.store.inspections[1:]
        return 'inspection' if self.store.inspections else 'end'

    def value_inspection(self, fields):
        inspection = self.store.inspections[0]
        values = {}
        for fieldname in fields:
            values[fieldname] = getattr(inspection, fieldname)

        if 'points' in fields:
            # Convert ImmutableDict to dict
            values['points'] = dict(values['points'] or {})
            for point in inspection.control.points:
                values['points'].setdefault(point.name)
        return values

    def transition_save(self):
        pool = Pool()
        Inspection = pool.get('quality.inspection')
        inspection = self.store.inspections[0]
        Inspection.write([inspection], self.inspection._save_values())
        inspection.process()
        return 'next_'


class InspectStore(ModelView):
    __name__ = 'quality.inspect.store'

    inspections = fields.Many2Many(
        'quality.inspection', None, None, "Inspections")
