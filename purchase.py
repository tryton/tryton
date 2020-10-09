# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from itertools import chain

from trytond import backend
from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool, If
from trytond.model import Workflow, ModelView, fields, ModelSQL, \
        sequence_ordered
from trytond.model.exceptions import RequiredValidationError, AccessError
from trytond.wizard import Wizard
from trytond.transaction import Transaction
from trytond.tools import grouped_slice

from trytond.modules.company.model import (
    employee_field, set_employee, reset_employee)
from trytond.modules.product import price_digits


class Configuration(metaclass=PoolMeta):
    __name__ = 'purchase.configuration'
    purchase_requisition_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Purchase Requisition Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'purchase.requisition'),
                ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'purchase_requisition_sequence':
            return pool.get('purchase.configuration.sequence')
        return super(Configuration, cls).multivalue_model(field)

    @classmethod
    def default_purchase_requisition_sequence(cls, **pattern):
        return cls.multivalue_model('purchase_requisition_sequence'
            ).default_purchase_requisition_sequence()


class ConfigurationSequence(metaclass=PoolMeta):
    __name__ = 'purchase.configuration.sequence'
    purchase_requisition_sequence = fields.Many2One(
        'ir.sequence', "Purchase Requisition Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('code', '=', 'purchase.requisition'),
            ],
        depends=['company'])

    @classmethod
    def __register__(cls, module_name):
        exist = backend.TableHandler.table_exist(cls._table)
        if exist:
            table = cls.__table_handler__(module_name)
            exist &= table.column_exist('purchase_requisition_sequence')

        super(ConfigurationSequence, cls).__register__(module_name)

        if not exist:
            cls._migrate_property([], [], [])

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('purchase_requisition_sequence')
        value_names.append('purchase_requisition_sequence')
        super(ConfigurationSequence, cls)._migrate_property(
            field_names, value_names, fields)

    @classmethod
    def default_purchase_requisition_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id(
                'purchase_requisition', 'sequence_purchase_requisition')
        except KeyError:
            return None


class PurchaseRequisition(Workflow, ModelSQL, ModelView):
    "Purchase Requisition"
    __name__ = 'purchase.requisition'
    _rec_name = 'number'
    _states = {
        'readonly': Eval('state') != 'draft',
        }
    _depends = ['state']

    company = fields.Many2One(
        'company.company', 'Company', required=True,
        states={
            'readonly': (Eval('state') != 'draft') | Eval('lines', [0]),
            },
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        depends=['lines'] + _depends, select=True)
    number = fields.Char('Number', readonly=True, select=True)
    description = fields.Char(
        'Description', states=_states, depends=_depends)
    employee = fields.Many2One(
        'company.employee', 'Employee', required=True,
        states=_states, depends=_depends)
    supply_date = fields.Date(
        'Supply Date',
        states={
            'required': ~Eval('state').in_(['draft', 'cancelled']),
            'readonly': _states['readonly'],
            },
        depends=_depends)
    warehouse = fields.Many2One(
        'stock.location', 'Warehouse',
        domain=[
            ('type', '=', 'warehouse'),
            ],
        states=_states, depends=_depends)
    currency = fields.Many2One(
        'currency.currency', 'Currency',
        states={
            'readonly': (_states['readonly']
                | (Eval('lines', [0]) & Eval('currency'))),
            },
        depends=_depends)
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'), 'on_change_with_currency_digits')
    total_amount = fields.Function(
        fields.Numeric('Total', digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_amount')
    total_amount_cache = fields.Numeric(
        'Total Cache', digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    lines = fields.One2Many(
        'purchase.requisition.line', 'requisition', 'Lines',
        states=_states, depends=_depends)

    approved_by = employee_field(
        "Approved By", states=['approved', 'processing', 'done', 'cancelled'])
    rejected_by = employee_field(
        "Rejected By", states=['rejected', 'processing', 'done', 'cancelled'])
    state = fields.Selection([
            ('draft', "Draft"),
            ('waiting', "Waiting"),
            ('rejected', "Rejected"),
            ('approved', "Approved"),
            ('processing', "Processing"),
            ('done', "Done"),
            ('cancelled', "Cancelled"),
            ], "State", readonly=True, required=True)

    del _states

    @classmethod
    def __setup__(cls):
        super(PurchaseRequisition, cls).__setup__()
        cls._transitions |= set((
                ('cancelled', 'draft'),
                ('rejected', 'draft'),
                ('draft', 'cancelled'),
                ('draft', 'waiting'),
                ('waiting', 'draft'),
                ('waiting', 'rejected'),
                ('waiting', 'approved'),
                ('approved', 'processing'),
                ('approved', 'draft'),
                ('processing', 'done'),
                ('done', 'processing'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(
                        ['cancelled', 'waiting', 'approved', 'rejected']),
                    'icon': If(Eval('state').in_(['cancelled', 'rejected']),
                        'tryton-undo',
                        'tryton-back'),
                    'depends': ['state'],
                    },
                'wait': {
                    'pre_validate': [('supply_date', '!=', None)],
                    'invisible': ((Eval('state') != 'draft')
                        | ~Eval('lines', [])),
                    'readonly': ~Eval('lines', []),
                    'depends': ['state'],
                    },
                'approve': {
                    'invisible': Eval('state') != 'waiting',
                    'depends': ['state'],
                    },
                'process': {
                    'invisible': ~Eval('state').in_(
                        ['approved', 'processing']),
                    'icon': If(Eval('state') == 'approved',
                        'tryton-forward', 'tryton-refresh'),
                    'depends': ['state'],
                    },
                'reject': {
                    'invisible': Eval('state') != 'waiting',
                    'depends': ['state'],
                    },
                })
        # The states where amounts are cached
        cls._states_cached = ['approved', 'done', 'rejected',
            'processing', 'cancelled']

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table = cls.__table__()

        super().__register__(module_name)

        # Migration from 5.6: rename state cancel to cancelled
        cursor.execute(*table.update(
                [table.state], ['cancelled'],
                where=table.state == 'cancel'))

    @classmethod
    def default_state(cls):
        return 'draft'

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_employee(cls):
        return Transaction().context.get('employee')

    @classmethod
    def default_warehouse(cls):
        Location = Pool().get('stock.location')
        return Location.get_default_warehouse()

    @classmethod
    def default_currency(cls):
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            return Company(company).currency.id

    @classmethod
    def default_currency_digits(cls):
        Company = Pool().get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = Company(company)
            return company.currency.digits
        return 2

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    @fields.depends('lines', 'currency')
    def on_change_with_total_amount(self):
        self.total_amount = Decimal('0.0')
        if self.lines:
            for line in self.lines:
                self.total_amount += getattr(line, 'amount', None) or 0
        if self.currency:
            self.total_amount = self.currency.round(self.total_amount)
        return self.total_amount

    @classmethod
    def store_cache(cls, requisitions):
        for requisition in requisitions:
            requisition.total_amount_cache = requisition.total_amount
        cls.save(requisitions)

    @classmethod
    def get_amount(cls, requisitions, name):
        total_amount = {}

        # Sort cached first and re-instantiate to optimize cache management
        requisitions = sorted(requisitions,
            key=lambda r: r.state in cls._states_cached, reverse=True)
        requisitions = cls.browse(requisitions)
        for requisition in requisitions:
            if (requisition.state in cls._states_cached
                    and requisition.total_amount_cache is not None):
                total_amount[requisition.id] = requisition.total_amount_cache
            else:
                total_amount[requisition.id] = (
                    requisition.on_change_with_total_amount())
        return total_amount

    @classmethod
    def create_requests(cls, requisitions):
        pool = Pool()
        Request = pool.get('purchase.request')
        requests = []
        for requisition in requisitions:
            for line in requisition.lines:
                request = line.compute_request()
                if request:
                    requests.append(request)
        if requests:
            Request.save(requests)

    @classmethod
    def view_attributes(cls):
        return [
            ('/tree', 'visual',
                If(Eval('state') == 'cancelled', 'muted', '')),
            ]

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('purchase.configuration')

        config = Config(1)
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            if values.get('number') is None:
                values['number'] = Sequence.get_id(
                    config.purchase_requisition_sequence.id)
        return super(PurchaseRequisition, cls).create(vlist)

    @classmethod
    def delete(cls, requisitions):
        # Cancel before delete
        cls.cancel(requisitions)
        for requisition in requisitions:
            if requisition.state != 'cancelled':
                raise AccessError(
                    gettext('purchase_requisition.msg_delete_cancel',
                        requisition=requisition.rec_name))
        super(PurchaseRequisition, cls).delete(requisitions)

    def check_for_waiting(self):
        if not self.warehouse:
            for line in self.lines:
                if line.product and line.product.type in {'goods', 'assets'}:
                    raise RequiredValidationError(
                        gettext('purchase_requisition.msg_warehouse_required',
                            requisition=self.rec_name))

    @classmethod
    def copy(cls, requisitions, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('number', None)
        default.setdefault('supply_date', None)
        return super(PurchaseRequisition, cls).copy(
            requisitions, default=default)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, requisitions):
        cls.store_cache(requisitions)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    @reset_employee('approved_by', 'rejected_by')
    def draft(cls, requisitions):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('waiting')
    def wait(cls, requisitions):
        for requisition in requisitions:
            requisition.check_for_waiting()

    @classmethod
    @ModelView.button
    @Workflow.transition('rejected')
    @set_employee('rejected_by')
    def reject(cls, requisitions):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('approved')
    @set_employee('approved_by')
    def approve(cls, requisitions):
        pool = Pool()
        Configuration = pool.get('purchase.configuration')
        cls.store_cache(requisitions)
        config = Configuration(1)
        with Transaction().set_context(
                queue_name='purchase',
                queue_scheduled_at=config.purchase_process_after):
            cls.__queue__.process(requisitions)

    @classmethod
    @Workflow.transition('processing')
    def proceed(cls, requisitions):
        pass

    @classmethod
    @Workflow.transition('done')
    def do(cls, requisitions):
        pass

    @classmethod
    @ModelView.button
    def process(cls, requisitions):
        done = []
        process = []
        requisitions = [r for r in requisitions
            if r.state in {'approved', 'processing', 'done'}]
        cls.create_requests(requisitions)
        for requisition in requisitions:
            if requisition.is_done():
                if requisition.state != 'done':
                    done.append(requisition)
            elif requisition.state != 'processing':
                process.append(requisition)
        if process:
            cls.proceed(process)
        if done:
            cls.do(done)

    def is_done(self):
        return all(
            r.purchase and r.purchase.state in {'cancelled', 'confirmed'}
            for l in self.lines for r in l.purchase_requests)


class PurchaseRequisitionLine(sequence_ordered(), ModelSQL, ModelView):
    "Purchase Requisition Line"
    __name__ = 'purchase.requisition.line'
    _states = {
        'readonly': Eval('purchase_requisition_state') != 'draft',
        }
    _depends = ['purchase_requisition_state']

    requisition = fields.Many2One(
        'purchase.requisition', 'Requisition',
        ondelete='CASCADE', select=True, required=True)
    supplier = fields.Many2One(
        'party.party', 'Supplier', states=_states, depends=_depends)
    product = fields.Many2One(
        'product.product', 'Product',
        ondelete='RESTRICT',
        domain=[
            ('purchasable', '=', True),
            ],
        states=_states, depends=_depends)
    product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', "Product UOM Category"),
        'on_change_with_product_uom_category')
    description = fields.Text("Description", states=_states, depends=_depends)
    quantity = fields.Float(
        'Quantity', digits=(16, Eval('unit_digits', 2)), required=True,
        states=_states, depends=['unit_digits'] + _depends)
    unit = fields.Many2One(
        'product.uom', 'Unit', ondelete='RESTRICT',
        states={
            'required': Bool(Eval('product')),
            'readonly': _states['readonly'],
            },
        depends=['product'] + _depends)
    unit_digits = fields.Function(
        fields.Integer('Unit Digits'), 'on_change_with_unit_digits')
    unit_price = fields.Numeric(
        'Unit Price', digits=price_digits, states=_states, depends=_depends)
    currency = fields.Function(fields.Many2One('currency.currency',
        'Currency'), 'on_change_with_currency')
    amount = fields.Function(
        fields.Numeric('Amount',
            digits=(
                16, Eval('_parent_requisition', {}).get('currency_digits', 2)),
            depends=_depends), 'on_change_with_amount')
    purchase_requests = fields.One2Many(
        'purchase.request', 'origin', 'Purchase Request', readonly=True)
    purchase_requisition_state = fields.Function(fields.Selection(
            'get_purchase_requisition_states', "Purchase Requisition State"),
        'on_change_with_purchase_requisition_state')

    del _states

    @classmethod
    def __setup__(cls):
        super().__setup__()
        unit_categories = cls._unit_categories()
        cls.unit.domain = [
            If(Bool(Eval('product_uom_category')),
                ('category', 'in', [Eval(c) for c in unit_categories]),
                ('category', '!=', -1)),
            ]
        cls.unit.depends.extend(unit_categories)

    @classmethod
    def _unit_categories(cls):
        return ['product_uom_category']

    @fields.depends('product')
    def on_change_with_product_uom_category(self, name=None):
        if self.product:
            return self.product.default_uom_category.id

    @fields.depends('requisition', '_parent_requisition.currency')
    def on_change_with_currency(self, name=None):
        if self.requisition:
            return self.requisition.currency.id

    @classmethod
    def get_purchase_requisition_states(cls):
        pool = Pool()
        Requisition = pool.get('purchase.requisition')
        return Requisition.fields_get(['state'])['state']['selection']

    @fields.depends('requisition', '_parent_requisition.state')
    def on_change_with_purchase_requisition_state(self, name=None):
        if self.requisition:
            return self.requisition.state

    @fields.depends('product', 'unit', 'quantity', 'supplier')
    def on_change_product(self):
        if not self.product:
            return

        category = self.product.purchase_uom.category
        if not self.unit or self.unit.category != category:
            self.unit = self.product.purchase_uom
            self.unit_digits = self.product.purchase_uom.digits

    @fields.depends('quantity', 'unit_price', 'unit', 'requisition',
        '_parent_requisition.currency')
    def on_change_with_amount(self, name=None):
        if (self.unit_price is None) or (self.quantity is None):
            return None
        amount = Decimal(str(self.quantity)) * self.unit_price
        if self.requisition.currency:
            amount = self.requisition.currency.round(amount)
        return amount

    @fields.depends('unit')
    def on_change_with_unit_digits(self, name=None):
        if self.unit:
            return self.unit.digits
        return 2

    def get_rec_name(self, name):
        pool = Pool()
        Lang = pool.get('ir.lang')
        if self.product:
            lang = Lang.get()
            return (lang.format(
                    '%.*f', (self.unit.digits, self.quantity or 0))
                + '%s %s @ %s' % (
                    self.unit.symbol, self.product.rec_name,
                    self.requisition.rec_name))
        else:
            return self.requisition.rec_name

    def _get_purchase_request_product_supplier_pattern(self):
        return {
            'company': self.requisition.company.id,
            }

    def compute_request(self):
        """
        Return the value of the purchase request which will answer to
        the needed quantity at the given date.
        """
        pool = Pool()
        Uom = pool.get('product.uom')
        Request = pool.get('purchase.request')

        if self.purchase_requests:
            return

        supply_date = self.requisition.supply_date
        purchase_date = supply_date

        if not self.supplier and self.product:
            supplier, purchase_date = Request.find_best_supplier(
                self.product, supply_date,
                **self._get_purchase_request_product_supplier_pattern())
        else:
            supplier = self.supplier
            # TODO compute purchase_date for product_supplier

        uom = self.unit
        quantity = self.quantity
        if (self.product
                and self.product.purchase_uom.category == self.unit.category):
            uom = self.product.purchase_uom
            quantity = Uom.compute_qty(self.unit, self.quantity,
                uom, round=True)

        return Request(
            product=self.product,
            description=self.description,
            party=supplier,
            quantity=quantity,
            uom=uom,
            computed_quantity=self.quantity,
            computed_uom=self.unit,
            purchase_date=purchase_date,
            supply_date=supply_date,
            company=self.requisition.company,
            warehouse=self.requisition.warehouse,
            origin=self,
            )

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('purchase_requests')
        return super(PurchaseRequisitionLine, cls).copy(lines, default=default)


class PurchaseRequest(metaclass=PoolMeta):
    __name__ = 'purchase.request'

    @classmethod
    def _get_origin(cls):
        return (super(PurchaseRequest, cls)._get_origin()
            | {'purchase.requisition.line'})

    @property
    def currency(self):
        pool = Pool()
        RequisitionLine = pool.get('purchase.requisition.line')
        currency = super(PurchaseRequest, self).currency
        if (isinstance(self.origin, RequisitionLine)
                and self.origin.requisition.currency):
            return self.origin.requisition.currency
        return currency


class HandlePurchaseCancellationException(metaclass=PoolMeta):
    __name__ = 'purchase.request.handle.purchase.cancellation'

    def transition_reset(self):
        pool = Pool()
        Requisition = pool.get('purchase.requisition')
        RequisitionLine = pool.get('purchase.requisition.line')

        state = super(
            HandlePurchaseCancellationException, self).transition_reset()

        requests = self.records
        requisition_ids = list({r.origin.requisition.id for r in requests
                if isinstance(r.origin, RequisitionLine)})
        Requisition.process(Requisition.browse(requisition_ids))
        return state


class CreatePurchase(Wizard):
    'Create Purchase'
    __name__ = 'purchase.request.create_purchase'

    def _group_purchase_line_key(self, request):
        pool = Pool()
        RequisitionLine = pool.get('purchase.requisition.line')
        key = super(CreatePurchase, self)._group_purchase_line_key(request)
        if isinstance(request.origin, RequisitionLine):
            if request.origin.unit_price:
                key += (('unit_price', request.origin.unit_price),)
        return key


class Purchase(metaclass=PoolMeta):
    __name__ = 'purchase.purchase'

    @classmethod
    def _process_requisition(cls, purchases):
        pool = Pool()
        Request = pool.get('purchase.request')
        Requisition = pool.get('purchase.requisition')

        requests = []
        for sub_purchases in grouped_slice(purchases):
            requests.append(Request.search([
                        ('purchase_line.purchase.id', 'in',
                            [x.id for x in sub_purchases]),
                        ('origin', 'like', 'purchase.requisition.line,%'),
                        ]))
        requests = list(chain(*requests))

        if requests:
            requisition_ids = list(set(req.origin.requisition
                for req in requests))
            Requisition.process(Requisition.browse(requisition_ids))

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, purchases):
        super(Purchase, cls).confirm(purchases)
        cls._process_requisition(purchases)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, purchases):
        super(Purchase, cls).cancel(purchases)
        cls._process_requisition(purchases)
