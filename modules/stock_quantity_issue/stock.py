# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from itertools import groupby

from trytond.i18n import gettext
from trytond.model import (
    Model, ModelSQL, ModelView, Workflow, fields, sequence_ordered)
from trytond.modules.company.model import (
    employee_field, reset_employee, set_employee)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import Button, StateAction, StateView, Wizard

from .exceptions import QuantityIssueError


class QuantityIssue(
        sequence_ordered('priority', "Priority", "ASC NULLS LAST"),
        Workflow, ModelSQL, ModelView):
    "Stock Quantity Issue"
    __name__ = 'stock.quantity.issue'

    company = fields.Many2One(
        'company.company', "Company", required=True, select=True)
    origin = fields.Reference(
        "Origin", 'get_origins', required=True,
        domain={
            'stock.shipment.out': [
                ('company', '=', Eval('company', -1)),
                ],
            'stock.shipment.in.return': [
                ('company', '=', Eval('company', -1)),
                ],
            'stock.shipment.internal': [
                ('company', '=', Eval('company', -1)),
                ],
            })
    planned_date = fields.Function(
        fields.Date("Planned Date"),
        'on_change_with_planned_date')
    best_planned_date = fields.Function(
        fields.Date("Best Planned Date"),
        'get_best_planned_date')
    warehouse = fields.Function(
        fields.Many2One('stock.location', "Warehouse"),
        'on_change_with_warehouse')

    issue_products = fields.One2Many(
        'stock.quantity.issue.product', 'issue', "Issue Products",
        readonly=True)
    products = fields.Many2Many(
        'stock.quantity.issue.product', 'issue', 'product', "Products",
        readonly=True,
        context={
            'company': Eval('company'),
            'locations': [Eval('warehouse')],
            'stock_skip_warehouse': False,
            'stock_date_end': Eval('planned_date'),
            },
        depends={'company', 'warehouse', 'planned_date'})

    processed_by = employee_field("Processed by", states=['processing'])
    solved_by = employee_field("Solved by", states=['solved'])

    state = fields.Selection([
            ('open', "Open"),
            ('processing', "Processing"),
            ('solved', "Solved"),
            ], "State", required=True, select=True, readonly=True, sort=False)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.priority.readonly = True
        cls._transitions |= {
            ('open', 'processing'),
            ('processing', 'solved'),
            ('processing', 'open'),
            }
        cls._buttons.update({
                'open': {
                    'invisible': Eval('state') != 'processing',
                    'depends': ['state'],
                    },
                'process': {
                    'invisible': Eval('state') != 'open',
                    'depends': ['state'],
                    },
                'apply_best_planned_date': {
                    'invisible': Eval('state') != 'processing',
                    'readonly': ~Eval('best_planned_date'),
                    'depends': ['state', 'best_planned_date'],
                    },
                'solve': {
                    'invisible': Eval('state') != 'processing',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def get_origins(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        get_name = Model.get_name
        models = cls._get_origins()
        return [(m, get_name(m)) for m in models]

    @classmethod
    def _get_origins(cls):
        "Return a list of Model names for origin Reference"
        return [
            'stock.shipment.out',
            'stock.shipment.in.return',
            'stock.shipment.internal',
            ]

    @fields.depends('origin')
    def on_change_with_planned_date(self, name=None):
        if (isinstance(self.origin, Model)
                and self.origin.id >= 0
                and hasattr(self.origin, 'planned_date')):
            return self.origin.planned_date

    def get_best_planned_date(self, name):
        return max(
            (p.best_planned_date for p in self.issue_products
            if p.best_planned_date), default=None)

    @classmethod
    def default_warehouse(cls):
        pool = Pool()
        Location = pool.get('stock.location')
        return Location.get_default_warehouse()

    @fields.depends('origin')
    def on_change_with_warehouse(self, name=None):
        if (isinstance(self.origin, Model) and self.origin.id >= 0
                and getattr(self.origin, 'warehouse', None)):
            return self.origin.warehouse.id

    @classmethod
    def default_state(cls):
        return 'open'

    def get_rec_name(self, name):
        return (self.origin.rec_name if isinstance(self.origin, Model)
            else '(%s)' % self.id)

    @classmethod
    @ModelView.button
    @Workflow.transition('open')
    @reset_employee('processed_by')
    def open(cls, issues):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('processing')
    @set_employee('processed_by')
    def process(cls, issues):
        pass

    @classmethod
    @ModelView.button
    def apply_best_planned_date(cls, issues):
        origins = defaultdict(list)
        for issue in issues:
            origin = issue.origin
            if hasattr(origin, 'planned_date'):
                origins[origin.__class__].append(origin)
                origin.planned_date = issue.best_planned_date
        for klass, records in origins.items():
            klass.save(records)

    @classmethod
    @ModelView.button
    @Workflow.transition('solved')
    @set_employee('solved_by')
    def solve(cls, issues):
        for issue in issues:
            for product in issue.products:
                if product.forecast_quantity < 0:
                    raise QuantityIssueError(
                        gettext('stock_quantity_issue.'
                            'msg_issue_solve_product_forecast_quantity',
                            issue=issue.rec_name,
                            product=product.rec_name))

    @classmethod
    def generate_issues(cls, warehouses=None, company=None):
        """
        For each product check each stock forecast quantity and for each
        negative day, it creates an issue for each origin on that day.

        If warehouses is specified it checks the stock only for them.
        """
        pool = Pool()
        Date = pool.get('ir.date')
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')
        Product = pool.get('product.product')
        ProductQuantitiesByWarehouse = pool.get(
            'stock.product_quantities_warehouse')
        User = pool.get('res.user')

        transaction = Transaction()
        today = Date.today()
        if warehouses is None:
            warehouses = Location.search([
                    ('type', '=', 'warehouse'),
                    ])
        if company is None:
            company = User(Transaction().user).company

        # Do not keep former open issues as they may no more be valid
        opens = cls.search([
                ('company', '=', company.id),
                ('state', '=', 'open'),
                ])
        opens = [
            i for i in opens if i.warehouse in warehouses or not i.warehouse]
        cls.delete(opens)

        issues = {}
        for issue in cls.search([
                    ('company', '=', company.id),
                    ('state', '=', 'processing'),
                    ]):
            if issue.warehouse not in warehouses:
                continue
            # Remove products from processing issues
            # as they may no more be valid
            issue.issue_products = []
            issues[issue.origin] = issue

        # Order by id to speedup reduce_ids
        products = Product.search([
                ('type', 'in', ['goods', 'assets']),
                ('consumable', '=', False),
                ],
            order=[('id', 'ASC')])

        for product in products:
            for warehouse in warehouses:
                with transaction.set_context(
                        product=product.id,
                        warehouse=warehouse.id,
                        stock_skip_warehouse=False,
                        ):
                    product_quantities = ProductQuantitiesByWarehouse.search([
                            ('date', '>=', today),
                            ('company', '=', company.id),
                            ])
                issue_products = []
                for product_quantity in product_quantities:
                    if product_quantity.quantity < 0:
                        moves = Move.search([
                                ('product', '=', product.id),
                                ('planned_date', '=', product_quantity.date),
                                ('from_location', 'child_of',
                                    [warehouse.id], 'parent'),
                                ('to_location', 'not child_of',
                                    [warehouse.id], 'parent'),
                                ('company', '=', company.id),
                                ])
                        for move in moves:
                            issue_products.append(cls._add(move, issues))
                    else:
                        for issue_product in issue_products:
                            issue_product.best_planned_date = (
                                product_quantity.date)
                        issue_products.clear()
        cls.save(issues.values())

    @classmethod
    def _get_origin(cls, move):
        if move.shipment and move.shipment.__name__ in cls._get_origins():
            return move.shipment

    @classmethod
    def _add(cls, move, issues):
        pool = Pool()
        Date = pool.get('ir.date')
        IssueProduct = pool.get('stock.quantity.issue.product')

        origin = cls._get_origin(move)

        if origin in issues:
            issue = issues[origin]
        else:
            issue = issues[origin] = cls(
                company=origin.company,
                origin=origin)
        issue_products = list(getattr(issue, 'issue_products', []))
        issue_product = IssueProduct.get_from_move(move)
        issue_products.append(issue_product)
        issue.issue_products = issue_products
        planned_date = issue.on_change_with_planned_date()
        if planned_date:
            issue.priority = (planned_date - Date.today()).days
        else:
            issue.priority = None
        return issue_product

    @classmethod
    def copy(cls, issues, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('processed_by')
        default.setdefault('solved_by')
        return super().copy(issues, default=default)


class QuantityIssueProduction(metaclass=PoolMeta):
    __name__ = 'stock.quantity.issue'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.origin.domain['production'] = [
            ('company', '=', Eval('company', -1)),
            ]

    @classmethod
    def _get_origins(cls):
        return super()._get_origins() + ['production']

    @classmethod
    def _get_origin(cls, move):
        origin = super()._get_origin(move)
        if not origin:
            origin = move.production_input
        return origin


class QuantityIssueProduct(ModelSQL):
    "Stock Quantity Issue Product"
    __name__ = 'stock.quantity.issue.product'

    issue = fields.Many2One(
        'stock.quantity.issue', "Issue",
        required=True, select=True, ondelete='CASCADE')
    product = fields.Many2One(
        'product.product', "Product",
        required=True, ondelete='CASCADE',
        domain=[
            ('type', '!=', 'service'),
            ])
    best_planned_date = fields.Date("Best Planned Date")
    forecast_quantity = fields.Function(
        fields.Float(
            "Forecast Quantity",
            help="The amount of stock expected to be in the warehouse."),
        'get_forecast_quantity')

    @classmethod
    def get_forecast_quantity(cls, records):
        quantities = {}

        def key(record):
            return record.warehouse, record.issue.planned_date
        items = cls.browse(sorted(records, key=key))
        for (warehouse, date), items in groupby(items, key=key):
            with Transaction().set_context(
                    location=[warehouse.id],
                    stock_skip_warehouse=True,
                    stock_start_end=date):
                for item in cls.browse(items):
                    quantities[item.id] = item.product.forecast_quantity
        return quantities

    def get_rec_name(self, name):
        return self.product.rec_name

    @classmethod
    def get_from_move(cls, move):
        return cls(product=move.product)


class QuantityIssueGenerate(Wizard):
    "Stock Quantity Issue Generate"
    __name__ = 'stock.quantity.issue.generate'
    start = StateView(
        'stock.quantity.issue.generate.start',
        'stock_quantity_issue.quantity_issue_generate_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Generate", 'generate', 'tryton-ok', default=True),
            ])
    generate = StateAction('stock_quantity_issue.act_quantity_issue_form')

    def transition_generate(self):
        pool = Pool()
        QuantityIssue = pool.get('stock.quantity.issue')
        QuantityIssue.generate_issues(warehouses=self.start.warehouses or None)
        return 'end'


class QuantityIssueGenerateStart(ModelView):
    "Stock Quantity Issue Generate"
    __name__ = 'stock.quantity.issue.generate.start'
    warehouses = fields.Many2Many(
        'stock.location', None, None, "Warehouses",
        domain=[
            ('type', '=', 'warehouse'),
            ],
        help="If empty all warehouses are used.")

    @classmethod
    def default_warehouses(cls):
        pool = Pool()
        Location = pool.get('stock.location')
        warehouse = Location.get_default_warehouse()
        if warehouse:
            return [warehouse]
