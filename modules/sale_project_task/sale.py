# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from collections import defaultdict

from trytond.i18n import gettext
from trytond.model import Index, ModelView, fields
from trytond.modules.currency.fields import Monetary
from trytond.modules.sale.exceptions import SaleValidationError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.transaction import Transaction

sale_task_creation_method = fields.Selection(
    'get_sale_task_creation_methods', "Sale Task Creation Method")


def get_sale_methods(field_name):
    @classmethod
    def func(cls):
        pool = Pool()
        Sale = pool.get('sale.sale')
        return Sale.fields_get([field_name])[field_name]['selection']
    return func


def default_func(field_name):
    @classmethod
    def default(cls, **pattern):
        return getattr(
            cls.multivalue_model(field_name),
            'default_%s' % field_name, lambda: None)()
    return default


class Configuration(metaclass=PoolMeta):
    __name__ = 'sale.configuration'

    sale_task_creation_method = fields.MultiValue(sale_task_creation_method)
    get_sale_task_creation_methods = get_sale_methods('task_creation_method')

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'sale_task_creation_method':
            return pool.get('sale.configuration.sale_method')
        return super().multivalue_model(field)

    default_sale_task_creation_method = default_func(
        'sale_task_creation_method')


class ConfigurationSaleMethod(metaclass=PoolMeta):
    __name__ = 'sale.configuration.sale_method'

    sale_task_creation_method = sale_task_creation_method
    get_sale_task_creation_methods = get_sale_methods('task_creation_method')

    @classmethod
    def default_sale_task_creation_method(cls):
        return 'order'


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    task_creation_method = fields.Selection([
            ('manual', "Manual"),
            ('order', "On Order Processed"),
            ('invoice', "On Invoice Paid"),
            ],
        "Task Creation Method", required=True,
        states={
            'readonly': Eval('state') != 'draft',
            })
    task_creation_method_string = task_creation_method.translated(
        'task_creation_method')
    tasks_state = fields.Selection([
            (None, "None"),
            ('waiting', "Waiting"),
            ('partially', "Partially fulfilled"),
            ('fulfilled', "fulfilled"),
            ],
        "Tasks State", readonly=True, sort=False)
    tasks_to_create = fields.Boolean("Tasks to Create", readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_indexes.update({
                Index(
                    t,
                    (t.tasks_state, Index.Equality(cardinality='low')),
                    where=t.tasks_state.in_(['none', 'waiting'])),
                })
        cls._buttons.update({
                'manual_task_creation': {
                    'invisible': (
                        ~Eval('tasks_to_create', False)
                        | (Eval('task_creation_method') != 'manual')
                        | ~Eval('state').in_(['processing', 'done'])),
                    'depends': [
                        'tasks_to_create', 'task_creation_method', 'state'],
                    },
                'manual_task_invoice': {
                    'invisible': (
                        ~Eval('to_invoice', False)
                        | (Eval('invoice_method') != 'fulfillment')
                        | ~Eval('state').in_(['processing', 'done'])),
                    'depends': ['invoice_method', 'state'],
                    },
                })

    @fields.depends('company')
    def on_change_company(self):
        try:
            super().on_change_company()
        except AttributeError:
            pass
        self.task_creation_method = self.default_task_creation_method(
            company=self.company.id if self.company else None)

    @classmethod
    def default_task_creation_method(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('sale.configuration')
        return Configuration(1).get_multivalue(
            'sale_task_creation_method', **pattern)

    @classmethod
    def check_method(cls, sales, field_names=None):
        super().check_method(sales, field_names=field_names)
        if field_names and not (field_names & {
                    'task_creation_method', 'invoice_method'}):
            return
        for sale in sales:
            if (sale.task_creation_method == 'invoice'
                    and sale.invoice_method == 'fulfillment'):
                raise SaleValidationError(
                    gettext('sale_project_task.'
                        'msg_sale_invalid_method',
                        invoice_method=sale.invoice_method_string,
                        task_creation_method=sale.task_creation_method_string,
                        sale=sale.rec_name))

    @classmethod
    def copy(cls, sales, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('tasks_state')
        default.setdefault('tasks_to_create')
        return super().copy(sales, default=default)

    @classmethod
    @ModelView.button
    def manual_task_creation(cls, sales):
        sales = [s for s in sales if s.task_creation_method == 'manual']
        with Transaction().set_context(_sale_manual_task_creation=True):
            cls.process(sales)

    @classmethod
    @ModelView.button
    def manual_task_invoice(cls, sales):
        sales = [s for s in sales if s.invoice_method == 'fulfillment']
        with Transaction().set_context(_sale_manual_task_invoice=True):
            cls.process(sales)

    @classmethod
    def _process_fulfillment(cls, sales):
        pool = Pool()
        Work = pool.get('project.work')
        context = Transaction().context
        works = []
        super()._process_fulfillment(sales)
        for sale in sales:
            if (sale.task_creation_method == 'manual'
                    and not context.get('_sale_manual_task_creation', False)):
                continue
            for line in sale.line_lines:
                works.extend(line.get_works())
        Work.save(works)

    @classmethod
    def _process_invoice_fulfillment_states(cls, sales):
        super()._process_invoice_fulfillment_states(sales)
        sales_tasks_to_create = defaultdict(list)
        tasks_states = defaultdict(list)
        for sale in sales:
            tasks_state = sale.get_tasks_state()
            if sale.tasks_state != tasks_state:
                tasks_states[tasks_state].append(sale)

            tasks_to_create = any(
                l.quantity_task_to_create for l in sale.lines)
            if sale.tasks_to_create != tasks_to_create:
                sales_tasks_to_create[tasks_to_create].append(sale)
        for tasks_to_create, sales in sales_tasks_to_create.items():
            cls.write(sales, {'tasks_to_create': tasks_to_create})
        for tasks_state, sales in tasks_states.items():
            cls.write(sales, {'tasks_state': tasks_state})
            cls.log(sales, 'transition', f'tasks_state:{tasks_state}')

    def get_tasks_state(self):
        tasks = sum((l.tasks for l in self.line_lines), ())

        def is_complete(task):
            return (task.progress or 0) >= 1

        if tasks:
            if all(is_complete(t) for t in tasks):
                return 'fulfilled'
            elif any(is_complete(t) for t in tasks):
                return 'partially'
            else:
                return 'waiting'
        return None

    def is_done(self):
        return (super().is_done()
            and (self.tasks_state == 'fulfilled'
                or (self.tasks_state is None
                    and all(
                        l.tasks_progress >= 1
                        for l in self.line_lines
                        if l.tasks_progress is not None))))


class Line(metaclass=PoolMeta):
    __name__ = 'sale.line'

    quantity_task_to_create = fields.Float(
        "Quantity Task to Create", digits='unit', readonly=True,
        states={
            'invisible': ~Eval('quantity_task_to_create'),
            })
    tasks = fields.One2Many(
        'project.work', 'origin', "Tasks", readonly=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ('type', '=', 'task'),
            ],
        states={
            'invisible': ~Eval('tasks'),
            })
    tasks_progress = fields.Function(fields.Float(
            "Tasks Progress", digits=(1, 4),
            states={
                'invisible': ~Eval('tasks'),
                }),
        'get_tasks_progress')

    def get_tasks_progress(self, name):
        progress = None
        if self.tasks:
            progress = round(
                sum(t.progress or 0 for t in self.tasks) / len(self.tasks), 4)
            progress = max(0., min(1., progress))
        return progress

    def get_works(self):
        if self.type != 'line':
            return
        if not self.product:
            return
        if (self.product.type != 'service'
                or not self.product.taskable):
            return
        if self.quantity <= 0:
            return
        if self.tasks:
            return

        quantity = self.unit.round(
            self._get_work_quantity() - self._get_work_quantity_created())
        if quantity < self.quantity:
            return

        for task in self.product.tasks_used:
            yield from task.get_sold_works(self)

    def _get_work_quantity(self):
        pool = Pool()
        UoM = pool.get('product.uom')

        quantity = 0.
        if self.sale.task_creation_method in {'order', 'manual'}:
            quantity = self.quantity
        elif self.sale.task_creation_method == 'invoice':
            for invoice_line in self.invoice_lines:
                if (invoice_line.invoice
                        and invoice_line.invoice.state == 'paid'):
                    quantity += UoM.compute_qty(
                        invoice_line.unit or self.unit, invoice_line.quantity,
                        self.unit)
        return quantity

    def _get_work_quantity_created(self):
        quantity = 0
        if self.tasks:
            quantity = self.quantity
        return quantity

    def get_invoice_line(self):
        context = Transaction().context
        lines = super().get_invoice_line()
        if (self.product
                and self.product.type == 'service'
                and self.product.taskable
                and self.sale.invoice_method == 'fulfillment'
                and not context.get('_sale_manual_task_invoice', False)):
            lines = []
        return lines

    def _get_invoice_line_quantity(self):
        quantity = super()._get_invoice_line_quantity()
        if (self.product
                and self.product.type == 'service'
                and self.product.taskable
                and self.sale.invoice_method == 'fulfillment'):
            quantity = 0
            if (self.tasks_progress or 0) >= 1:
                quantity = self.quantity
            else:
                quantity = 0
        return quantity

    def set_quantities(self):
        super().set_quantities()
        if (self.product
                and self.product.type == 'service'
                and self.product.taskable):
            quantity_task_to_create = self.unit.round(
                self._get_work_quantity() - self._get_work_quantity_created())
        else:
            quantity_task_to_create = None
        if self.quantity_task_to_create != quantity_task_to_create:
            self.quantity_task_to_create = quantity_task_to_create

    @classmethod
    def copy(cls, lines, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('tasks')
        default.setdefault('quantity_task_to_create')
        return super().copy(lines, default=default)


class Line_Revenue(metaclass=PoolMeta):
    __name__ = 'sale.line'

    tasks_revenue = fields.Function(Monetary(
            "Tasks Revenue", currency='currency', digits='currency',
            states={
                'invisible': ~Eval('tasks', None),
                }),
        'get_tasks_revenue')

    def get_tasks_revenue(self, name):
        pool = Pool()
        Work = pool.get('project.work')
        return self.currency.round(sum(Work._get_revenue(self.tasks).values()))

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/tree/field[@name="tasks_revenue"]', 'visual',
                If(Eval('amount', 0) < Eval('tasks_revenue', 0), 'danger',
                    If(Eval('amount', 0) > Eval('tasks_revenue', 0), 'warning',
                        ''))),
            ]
