# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql.functions import CharLength

from trytond.i18n import gettext
from trytond.model import DeactivableMixin, ModelSQL, ModelView, fields
from trytond.model.exceptions import RecursionError
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, If
from trytond.tools import is_full_text, lstrip_wildcard
from trytond.wizard import Button, StateView, Wizard


class BOM(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'production.bom'

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char(
        "Code",
        states={
            'readonly': Eval('code_readonly', False),
            })
    code_readonly = fields.Function(
        fields.Boolean("Code Readonly"), 'get_code_readonly')
    phantom = fields.Boolean(
        "Phantom",
        help="If checked, the BoM can be used in another BoM.")
    phantom_unit = fields.Many2One(
        'product.uom', "Unit",
        states={
            'invisible': ~Eval('phantom', False),
            'required': Eval('phantom', False),
            },
        help="The Unit of Measure of the Phantom BoM")
    phantom_quantity = fields.Float(
        "Quantity", digits='phantom_unit',
        domain=['OR',
            ('phantom_quantity', '>=', 0),
            ('phantom_quantity', '=', None),
            ],
        states={
            'invisible': ~Eval('phantom', False),
            'required': Eval('phantom', False),
            },
        help="The quantity of the Phantom BoM")
    inputs = fields.One2Many(
        'production.bom.input', 'bom', "Input Materials",
        domain=[If(Eval('phantom') & Eval('outputs', None),
                ('id', '=', None),
                ()),
            ],
        states={
            'invisible': Eval('phantom') & Bool(Eval('outputs')),
            })
    input_products = fields.Many2Many(
        'production.bom.input', 'bom', 'product', "Input Products")
    outputs = fields.One2Many(
        'production.bom.output', 'bom', "Output Materials",
        domain=[If(Eval('phantom') & Eval('inputs', None),
                ('id', '=', None),
                ()),
            ],
        states={
            'invisible': Eval('phantom') & Bool(Eval('inputs')),
            })
    output_products = fields.Many2Many('production.bom.output',
        'bom', 'product', 'Output Products')

    @classmethod
    def order_code(cls, tables):
        table, _ = tables[None]
        if cls.default_code_readonly():
            return [CharLength(table.code), table.code]
        else:
            return [table.code]

    @classmethod
    def default_code_readonly(cls):
        pool = Pool()
        Configuration = pool.get('production.configuration')
        config = Configuration(1)
        return bool(config.bom_sequence)

    def get_code_readonly(self, name):
        return self.default_code_readonly()

    @classmethod
    def order_rec_name(cls, tables):
        table, _ = tables[None]
        return cls.order_code(tables) + [table.name]

    def get_rec_name(self, name):
        if self.code:
            return '[' + self.code + '] ' + self.name
        else:
            return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, operand, *extra = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        code_value = operand
        if operator.endswith('like') and is_full_text(operand):
            code_value = lstrip_wildcard(operand)
        return [bool_op,
            ('name', operator, operand, *extra),
            ('code', operator, code_value, *extra),
            ]

    def compute_factor(self, product, quantity, unit, type='outputs'):
        pool = Pool()
        Uom = pool.get('product.uom')
        assert type in {'inputs', 'outputs'}, f"Invalid {type}"
        total = 0
        if self.phantom:
            total = Uom.compute_qty(
                self.phantom_unit, self.phantom_quantity, unit, round=False)
        else:
            for line in getattr(self, type):
                if line.product == product:
                    total += Uom.compute_qty(
                        line.unit, line.quantity, unit, round=False)
        if total:
            return quantity / total
        else:
            return 0

    @classmethod
    def _code_sequence(cls):
        pool = Pool()
        Configuration = pool.get('production.configuration')
        config = Configuration(1)
        return config.bom_sequence

    @classmethod
    def preprocess_values(cls, mode, values):
        values = super().preprocess_values(mode, values)
        if mode == 'create' and not values.get('code'):
            if sequence := cls._code_sequence():
                values['code'] = sequence.get()
        return values

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('code', None)
        default.setdefault('input_products', None)
        default.setdefault('output_products', None)
        return super().copy(records, default=default)


class BOMInput(ModelSQL, ModelView):
    __name__ = 'production.bom.input'

    bom = fields.Many2One(
        'production.bom', "BOM", required=True, ondelete='CASCADE')
    product = fields.Many2One(
        'product.product', "Product",
        domain=[If(Eval('phantom_bom', None),
                ('id', '=', None),
                ()),
            ],
        states={
            'invisible': Bool(Eval('phantom_bom')),
            'required': ~Bool(Eval('phantom_bom')),
            })
    phantom_bom = fields.Many2One(
        'production.bom', "Phantom BOM",
        domain=[If(Eval('product', None),
                ('id', '=', None),
                ()),
            ],
        states={
            'invisible': Bool(Eval('product')),
            'required': ~Bool(Eval('product')),
            })
    uom_category = fields.Function(fields.Many2One(
        'product.uom.category', 'Uom Category'), 'on_change_with_uom_category')
    unit = fields.Many2One(
        'product.uom', "Unit", required=True,
        domain=[
            ('category', '=', Eval('uom_category', -1)),
            ])
    quantity = fields.Float(
        "Quantity", digits='unit', required=True,
        domain=['OR',
            ('quantity', '>=', 0),
            ('quantity', '=', None),
            ])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.phantom_bom.domain = [
            ('phantom', '=', True),
            ('inputs', '!=', None),
            ]
        cls.product.domain = [('type', 'in', cls.get_product_types())]
        cls.__access__.add('bom')

    @classmethod
    def __register__(cls, module):
        table_h = cls.__table_handler__(module)

        # Migration from 6.8: rename uom to unit
        if (table_h.column_exist('uom')
                and not table_h.column_exist('unit')):
            table_h.column_rename('uom', 'unit')

        super().__register__(module)
        table_h = cls.__table_handler__(module)

        # Migration from 6.0: remove unique constraint
        table_h.drop_constraint('product_bom_uniq')
        # Migration from 7.6: remove required on product
        table_h.not_null_action('product', 'remove')

    @classmethod
    def get_product_types(cls):
        return ['goods', 'assets']

    @fields.depends('phantom_bom', 'unit')
    def on_change_phantom_bom(self):
        if self.phantom_bom:
            category = self.phantom_bom.phantom_unit.category
            if not self.unit or self.unit.category != category:
                self.unit = self.phantom_bom.phantom_unit
        else:
            self.unit = None

    @fields.depends('product', 'unit')
    def on_change_product(self):
        if self.product:
            category = self.product.default_uom.category
            if not self.unit or self.unit.category != category:
                self.unit = self.product.default_uom
        else:
            self.unit = None

    @fields.depends('product', 'phantom_bom')
    def on_change_with_uom_category(self, name=None):
        uom_category = None
        if self.product:
            uom_category = self.product.default_uom.category
        elif self.phantom_bom:
            uom_category = self.phantom_bom.phantom_unit.category
        return uom_category

    def get_rec_name(self, name):
        if self.product:
            return self.product.rec_name
        elif self.phantom_bom:
            return self.phantom_bom.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, value = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'

        return [bool_op,
            ('product.rec_name', operator, value),
            ('phantom_bom.rec_name', operator, value),
            ]

    @classmethod
    def validate(cls, boms):
        super().validate(boms)
        for bom in boms:
            bom.check_bom_recursion()

    def check_bom_recursion(self, bom=None):
        '''
        Check BOM recursion
        '''
        if bom is None:
            bom = self.bom
        if self.product:
            self.product.check_bom_recursion()
        else:
            for line_ in self._phantom_lines:
                if line_.phantom_bom and (line_.phantom_bom == bom
                        or line_.check_bom_recursion(bom=bom)):
                    raise RecursionError(gettext(
                            'production.msg_recursive_bom_bom',
                            bom=bom.rec_name))

    def compute_quantity(self, factor):
        return self.unit.ceil(self.quantity * factor)

    def prepare_move(self, production, move):
        "Update stock move for the production"
        return move

    @property
    def _phantom_lines(self):
        if self.phantom_bom:
            return self.phantom_bom.inputs

    def lines_for_quantity(self, quantity):
        if self.phantom_bom:
            factor = self.phantom_bom.compute_factor(
                None, quantity, self.unit)
            for line in self._phantom_lines:
                yield line, line.compute_quantity(factor)
        else:
            yield self, quantity


class BOMOutput(BOMInput):
    __name__ = 'production.bom.output'
    __string__ = None
    _table = None  # Needed to override BOMInput._table

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.phantom_bom.domain = [
            ('phantom', '=', True),
            ('outputs', '!=', None),
            ]

    def compute_quantity(self, factor):
        return self.unit.floor(self.quantity * factor)

    @property
    def _phantom_lines(self):
        if self.phantom_bom:
            return self.phantom_bom.outputs

    @classmethod
    def on_delete(cls, outputs):
        pool = Pool()
        ProductBOM = pool.get('product.product-production.bom')

        callback = super().on_delete(outputs)

        bom_products = [b for o in outputs for b in o.product.boms]
        # Validate that output_products domain on bom is still valid
        callback.append(lambda: ProductBOM._validate(bom_products, ['bom']))
        return callback

    @classmethod
    def on_write(cls, outputs, values):
        pool = Pool()
        ProductBOM = pool.get('product.product-production.bom')

        callback = super().on_write(outputs, values)

        bom_products = [b for o in outputs for b in o.product.boms]
        # Validate that output_products domain on bom is still valid
        callback.append(lambda: ProductBOM._validate(bom_products, ['bom']))
        return callback


class BOMTree(ModelView):
    __name__ = 'production.bom.tree'

    product = fields.Many2One('product.product', 'Product')
    quantity = fields.Float('Quantity', digits='unit')
    unit = fields.Many2One('product.uom', "Unit")
    childs = fields.One2Many('production.bom.tree', None, 'Childs')

    @classmethod
    def tree(cls, product, quantity, unit, bom=None):
        Input = Pool().get('production.bom.input')

        result = []
        if bom is None:
            pbom = product.get_bom()
            if pbom is None:
                return result
            bom = pbom.bom

        factor = bom.compute_factor(product, quantity, unit)
        for input_ in bom.inputs:
            quantity = Input.compute_quantity(input_, factor)
            childs = cls.tree(input_.product, quantity, input_.unit)
            values = {
                'product': input_.product.id,
                'product.': {
                    'rec_name': input_.product.rec_name,
                    },
                'quantity': quantity,
                'unit': input_.unit.id,
                'unit.': {
                    'rec_name': input_.unit.rec_name,
                    },
                'childs': childs,
            }
            result.append(values)
        return result


class OpenBOMTreeStart(ModelView):
    __name__ = 'production.bom.tree.open.start'

    quantity = fields.Float('Quantity', digits='unit', required=True)
    unit = fields.Many2One(
        'product.uom', "Unit", required=True,
        domain=[
            ('category', '=', Eval('category', -1)),
            ])
    category = fields.Many2One('product.uom.category', 'Category',
        readonly=True)
    bom = fields.Many2One('product.product-production.bom',
        'BOM', required=True, domain=[
            ('product', '=', Eval('product', -1)),
            ])
    product = fields.Many2One('product.product', 'Product', readonly=True)


class OpenBOMTreeTree(ModelView):
    __name__ = 'production.bom.tree.open.tree'

    bom_tree = fields.One2Many('production.bom.tree', None, 'BOM Tree',
        readonly=True)

    @classmethod
    def tree(cls, bom, product, quantity, unit):
        pool = Pool()
        Tree = pool.get('production.bom.tree')

        childs = Tree.tree(product, quantity, unit, bom=bom)
        bom_tree = [{
                'product': product.id,
                'product.': {
                    'rec_name': product.rec_name,
                    },
                'quantity': quantity,
                'unit': unit.id,
                'unit.': {
                    'rec_name': unit.rec_name,
                    },
                'childs': childs,
                }]
        return {
            'bom_tree': bom_tree,
            }


class OpenBOMTree(Wizard):
    __name__ = 'production.bom.tree.open'
    _readonly = True

    start = StateView('production.bom.tree.open.start',
        'production.bom_tree_open_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'tree', 'tryton-ok', True),
            ])
    tree = StateView('production.bom.tree.open.tree',
        'production.bom_tree_open_tree_view_form', [
            Button('Change', 'start', 'tryton-back'),
            Button('Close', 'end', 'tryton-close'),
            ])

    def default_start(self, fields):
        defaults = {}
        product = self.record
        defaults['category'] = product.default_uom.category.id
        if self.start.unit:
            defaults['unit'] = self.start.unit.id
        else:
            defaults['unit'] = product.default_uom.id
        defaults['product'] = product.id
        if self.start.bom:
            defaults['bom'] = self.start.bom.id
        else:
            bom = product.get_bom()
            if bom:
                defaults['bom'] = bom.id
        defaults['quantity'] = self.start.quantity
        return defaults

    def default_tree(self, fields):
        pool = Pool()
        BomTree = pool.get('production.bom.tree.open.tree')
        return BomTree.tree(self.start.bom.bom, self.start.product,
            self.start.quantity, self.start.unit)
