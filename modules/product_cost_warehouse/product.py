# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.modules.company.model import CompanyValueMixin
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

cost_price_warehouse = fields.Boolean(
    "Cost Price per Warehouse",
    help="Compute product cost price for each warehouse.")


class Configuration(metaclass=PoolMeta):
    __name__ = 'product.configuration'
    cost_price_warehouse = fields.MultiValue(cost_price_warehouse)

    @classmethod
    def default_cost_price_warehouse(cls, **pattern):
        return cls.multivalue_model(
            'cost_price_warehouse').default_cost_price_warehouse()


class ConfigurationCostPriceWarehouse(ModelSQL, CompanyValueMixin):
    "Product Configuration Cost Price per Warehouse"
    __name__ = 'product.configuration.cost_price_warehouse'
    cost_price_warehouse = cost_price_warehouse

    @classmethod
    def default_cost_price_warehouse(cls):
        return False


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        readonly = (
            Eval('context', {}).get('cost_price_warehouse', False)
            & ~Eval('context', {}).get('warehouse'))
        if cls.cost_price.states['readonly']:
            cls.cost_price.states['readonly'] |= readonly
        else:
            cls.cost_price.states['readonly'] = readonly

    def multivalue_records(self, field):
        Value = self.multivalue_model(field)
        records = super().multivalue_records(field)
        if issubclass(Value, CostPrice):
            # Sort to get record with empty warehouse at the end
            records = sorted(records, key=lambda r: r.warehouse is None)
        return records

    def get_multivalue(self, name, **pattern):
        pool = Pool()
        Company = pool.get('company.company')
        context = Transaction().context
        Value = self.multivalue_model(name)
        if issubclass(Value, CostPrice) and context.get('company'):
            company = Company(context['company'])
            if company.cost_price_warehouse:
                pattern.setdefault('warehouse', context.get('warehouse'))
        return super().get_multivalue(name, **pattern)

    def set_multivalue(self, name, value, save=True, **pattern):
        pool = Pool()
        Company = pool.get('company.company')
        context = Transaction().context
        Value = self.multivalue_model(name)
        if issubclass(Value, CostPrice) and context.get('company'):
            company = Company(context['company'])
            if company.cost_price_warehouse:
                pattern.setdefault('warehouse', context.get('warehouse'))
            if not value and not pattern.get('warehouse'):
                return []
        return super().set_multivalue(name, value, save=save, **pattern)

    @classmethod
    def _domain_moves_cost(cls):
        pool = Pool()
        Company = pool.get('company.company')
        context = Transaction().context
        domain = super()._domain_moves_cost()
        if context.get('company'):
            company = Company(context['company'])
            if company.cost_price_warehouse:
                warehouse = context.get('warehouse')
                domain = [
                    domain,
                    ['OR',
                        ('from_location', 'child_of', warehouse, 'parent'),
                        ('from_location.cost_warehouse', '=', warehouse),
                        ('to_location', 'child_of', warehouse, 'parent'),
                        ('to_location.cost_warehouse', '=', warehouse),
                        ],
                    ]
        return domain

    @classmethod
    def _domain_in_moves_cost(cls):
        pool = Pool()
        Company = pool.get('company.company')
        context = Transaction().context
        domain = super()._domain_in_moves_cost()
        if context.get('company'):
            company = Company(context['company'])
            if company.cost_price_warehouse:
                warehouse = context.get('warehouse')
                domain = ['OR',
                    domain,
                    [
                        ('from_location.type', '=', 'storage'),
                        ('to_location.type', '=', 'storage'),
                        ('from_location', 'not child_of', warehouse, 'parent'),
                        ['OR',
                            ('from_location.cost_warehouse', '!=', warehouse),
                            ('from_location.cost_warehouse', '=', None),
                            ],
                        ['OR',
                            ('to_location', 'child_of', warehouse, 'parent'),
                            ('to_location.cost_warehouse', '=', warehouse),
                            ],
                        ]
                    ]
        return domain

    @classmethod
    def _domain_out_moves_cost(cls):
        pool = Pool()
        Company = pool.get('company.company')
        context = Transaction().context
        domain = super()._domain_out_moves_cost()
        if context.get('company'):
            company = Company(context['company'])
            if company.cost_price_warehouse:
                warehouse = context.get('warehouse')
                domain = ['OR',
                    domain,
                    [
                        ('from_location.type', '=', 'storage'),
                        ('to_location.type', '=', 'storage'),
                        ('to_location', 'not child_of', warehouse, 'parent'),
                        ['OR',
                            ('to_location.cost_warehouse', '!=', warehouse),
                            ('to_location.cost_warehouse', '=', None),
                            ],
                        ['OR',
                            ('from_location', 'child_of', warehouse, 'parent'),
                            ('from_location.cost_warehouse', '=', warehouse),
                            ],
                        ]
                    ]
        return domain

    @classmethod
    def _domain_storage_quantity(cls):
        pool = Pool()
        Company = pool.get('company.company')
        context = Transaction().context
        domain = super()._domain_storage_quantity()
        if context.get('company'):
            company = Company(context['company'])
            if company.cost_price_warehouse:
                warehouse = context.get('warehouse')
                domain = [
                    domain,
                    ['OR',
                        ('parent', 'child_of', warehouse),
                        ('cost_warehouse', '=', warehouse),
                        ],
                    ]
        return domain

    @classmethod
    def default_cost_price(cls, **pattern):
        context = Transaction().context
        default = super().default_cost_price()
        if (context.get('cost_price_warehouse')
                and not pattern.get('warehouse', context.get('warehouse'))):
            default = None
        return default


class CostPrice(metaclass=PoolMeta):
    __name__ = 'product.cost_price'
    warehouse = fields.Many2One(
        'stock.location', "Warehouse", ondelete='RESTRICT',
        domain=[
            ('type', '=', 'warehouse'),
            ],
        states={
            'required': Eval('warehouse_required', False),
            })
    warehouse_required = fields.Function(fields.Boolean(
            "Warehouse Required"), 'get_warehouse_required')

    @classmethod
    def get_warehouse_required(cls, records, name):
        return {r.id: r.company.cost_price_warehouse for r in records}


class CostPriceRevision(metaclass=PoolMeta):
    __name__ = 'product.cost_price.revision'
    warehouse = fields.Many2One(
        'stock.location', "Warehouse", ondelete='RESTRICT',
        domain=[
            ('type', '=', 'warehouse'),
            ],
        states={
            'required': Eval('warehouse_required', False),
            })
    warehouse_required = fields.Function(fields.Boolean(
            "Warehouse Required"), 'get_warehouse_required')

    @classmethod
    def default_warehouse(cls):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = cls.default_company()
        if company_id:
            company = Company(company_id)
            if company.cost_price_warehouse:
                return Transaction().context.get('warehouse')

    @classmethod
    def get_warehouse_required(cls, records, name):
        return {r.id: r.company.cost_price_warehouse for r in records}

    @classmethod
    def _get_for_product_domain(cls):
        pool = Pool()
        Company = pool.get('company.company')
        domain = super()._get_for_product_domain()
        context = Transaction().context
        if context.get('company'):
            company = Company(context['company'])
            if company.cost_price_warehouse:
                domain = [
                    domain,
                    ('warehouse', '=', context.get('warehouse')),
                    ]
        return domain


class ModifyCostPrice(metaclass=PoolMeta):
    __name__ = 'product.modify_cost_price'

    def get_revision(self, Revision):
        revision = super().get_revision(Revision)
        if revision.company.cost_price_warehouse:
            revision.warehouse = Transaction().context.get('warehouse')
        return revision


class ProductCostHistory(metaclass=PoolMeta):
    __name__ = 'product.product.cost_history'

    @classmethod
    def _non_moves_clause(cls, history_table, user):
        clause = super()._non_moves_clause(history_table, user)
        if user.company and user.company.cost_price_warehouse:
            warehouse_id = user.warehouse.id if user.warehouse else None
            clause &= history_table.warehouse == warehouse_id
        return clause
