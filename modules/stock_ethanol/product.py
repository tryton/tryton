# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from sql.conditionals import Coalesce

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Id, If


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    contain_ethanol = fields.Boolean(
        "Contain Alcohol",
        states={
            'invisible': Eval('type', 'goods') != 'goods',
            },
        help="Check if goods contain ethanol/alcohol.")
    ethanol_by_volume = fields.Float(
        "Alcohol By Volume", digits=(1, 4),
        domain=[If(Eval('contain_ethanol'),
                ['OR',
                    [
                        ('ethanol_by_volume', '>=', 0),
                        ('ethanol_by_volume', '<=', 1),
                        ],
                    ('ethanol_by_volume', '=', None),
                    ],
                [('ethanol_by_volume', '=', None)])],
        states={
            'invisible': ~Eval('contain_ethanol'),
            },
        help="How much ethanol/alcohol is contained "
        "in a given volume at 20°C.")
    ethanol_volume = fields.Function(
        fields.Float(
            "Alcohol Volume", digits='ethanol_volume_unit',
            help="The volume of ethanol/alcohol in the location."),
        'sum_product')
    ethanol_volume_unit = fields.Function(
        fields.Many2One(
            'product.uom', "Alcohol Volume UoM",
            states={
                'invisible': ~Eval('ethanol_volume'),
                }),
        'get_ethanol_volume_unit')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._modify_no_move += [
            ('contain_ethanol',
                'stock_ethanol.msg_product_change_contain_ethanol'),
            ('ethanol_by_volume',
                'stock_ethanol.msg_product_change_ethanol_by_volume'),
            ]

    @classmethod
    def get_ethanol_volume_unit(cls, templates, name):
        pool = Pool()
        Configuration = pool.get('stock.configuration')
        configuration = Configuration(1)
        uom = configuration.get_multivalue('ethanol_volume_uom')
        return dict.fromkeys(map(int, templates), uom.id)

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//page[@id="ethanol"]', 'states', {
                    'invisible': ~Eval('contain_ethanol'),
                    }),
            ]


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    ethanol_by_volume = fields.Float(
        "Alcohol By Volume", digits=(1, 4),
        domain=[If(Eval('contain_ethanol'),
                ['OR',
                    [
                        ('ethanol_by_volume', '>=', 0),
                        ('ethanol_by_volume', '<=', 1),
                        ],
                    ('ethanol_by_volume', '=', None),
                    ],
                [('ethanol_by_volume', '=', None)])],
        states={
            'invisible': ~Eval('contain_ethanol'),
            },
        help="How much ethanol/alcohol is contained "
        "in a given volume at 20°C.\n"
        "Leave empty to use the template value.")
    ethanol_by_volume_used = fields.Function(fields.Float(
            "Alcohol By Volume", digits=(1, 4),
            states={
                'invisible': ~Eval('contain_ethanol'),
                },
            help="How much ethanol/alcohol is contained "
            "in a given volume at 20°C."),
        'get_ethanol_by_volume_used',
        searcher='search_ethanol_by_volume_used')

    ethanol_volume = fields.Function(
        fields.Float(
            "Alcohol Volume", digits='ethanol_volume_unit',
            help="The volume of ethanol/alcohol in the location."),
        'get_ethanol_volume')

    def get_ethanol_by_volume_used(self, name):
        if self.contain_ethanol:
            if self.ethanol_by_volume is not None:
                return self.ethanol_by_volume
            else:
                return self.template.ethanol_by_volume

    @classmethod
    def search_ethanol_by_volume_used(cls, name, clause):
        operator = clause[1]
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op, [
                ('ethanol_by_volume', '!=', None),
                ('ethanol_by_volume', *clause[1:]),
                ], [
                ('ethanol_by_volume', '=', None),
                ('template.ethanol_by_volume', *clause[1:]),
                ]]

    @classmethod
    def order_ethanol_by_volume_used(cls, tables):
        pool = Pool()
        Template = pool.get('product.template')
        product, _ = tables[None]
        if 'template' not in tables:
            template = Template.__table__()
            tables['template'] = {
                None: (template, product.template == template.id),
                }
        else:
            template, _ = tables['template'][None]
        return [
            Coalesce(product.ethanol_by_volume, template.ethanol_by_volume)]

    def get_ethanol_volume(self, name):
        pool = Pool()
        UoM = pool.get('product.uom')

        if unit := self.ethanol_volume_unit:
            ethanol_by_volume = self.ethanol_by_volume_used
            if ethanol_by_volume is not None and self.quantity is not None:
                if self.default_uom.category == unit.category:
                    quantity = self.quantity * ethanol_by_volume
                    return UoM.compute_qty(self.default_uom, quantity, unit)
                elif getattr(self, 'volume', None) is not None:
                    quantity = (
                        self.quantity * self.volume * ethanol_by_volume)
                    return UoM.compute_qty(self.volume_uom, quantity, unit)

    def compute_ethanol_volume(self, quantity, unit, unit_volume, round=True):
        pool = Pool()
        UoM = pool.get('product.uom')
        assert unit.category == self.default_uom.category
        if (ethanol_by_volume := self.ethanol_by_volume_used) is not None:
            if unit.category == unit_volume.category:
                volume = quantity * ethanol_by_volume
            else:
                if getattr(self, 'volume', None) is not None:
                    volume = quantity * self.volume * ethanol_by_volume
                    unit = self.volume_uom
            return UoM.compute_qty(unit, volume, unit_volume, round=round)


class PriceList(metaclass=PoolMeta):
    __name__ = 'product.price_list'

    def get_context_formula(self, product, quantity, uom, pattern=None):
        pool = Pool()
        UoM = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')

        liter = UoM(ModelData.get_id('product', 'uom_liter'))

        context = super().get_context_formula(
            product, quantity, uom, pattern=pattern)
        ethanol_volume = None
        if product:
            ethanol_volume = product.compute_ethanol_volume(
                1, product.default_uom, liter, round=False)
        if ethanol_volume is None:
            ethanol_volume = 0
        context['names']['ethanol_volume'] = Decimal(str(ethanol_volume))
        return context


class PriceListLine(metaclass=PoolMeta):
    __name__ = 'product.price_list.line'

    ethanol_volume_uom = fields.Many2One(
        'product.uom', "AlcoholVolume UoM",
        domain=[('category', '=', Id('product', 'uom_cat_volume'))],
        help="Leave empty for liter.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.formula.help += ("\n"
            "-ethanol_volume: the volume of alcohol in 1 unit of product")

    def get_unit_price(self, **context):
        pool = Pool()
        UoM = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')

        if self.ethanol_volume_uom:
            context['names'] = context['names'].copy()
            liter = UoM(ModelData.get_id('product', 'uom_liter'))
            ethanol_volume = UoM.compute_qty(
                liter, float(context['names']['ethanol_volume']),
                self.ethanol_volume_uom, round=False)
            context['names']['ethanol_volume'] = Decimal(str(ethanol_volume))
        return super().get_unit_price(**context)
