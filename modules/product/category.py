# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql.conditionals import NullIf
from sql.functions import CharLength
from sql.operators import Equal

from trytond.model import Exclude, ModelSQL, ModelView, fields, tree
from trytond.pool import Pool
from trytond.pyson import Eval, PYSONEncoder
from trytond.tools import is_full_text, lstrip_wildcard


class Category(tree(separator=' / '), ModelSQL, ModelView):
    __name__ = "product.category"
    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char(
        "Code",
        states={
            'readonly': Eval('code_readonly', False),
            })
    code_readonly = fields.Function(
        fields.Boolean("Code Readonly"), 'get_code_readonly')
    parent = fields.Many2One(
        'product.category', "Parent",
        help="Used to add structure above the category.")
    childs = fields.One2Many(
        'product.category', 'parent', string="Children",
        help="Used to add structure below the category.")
    templates = fields.Many2Many(
        'product.template-product.category', 'category', 'template',
        "Products")

    @classmethod
    def __setup__(cls):
        cls.code.search_unaccented = False
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_unique', Exclude(t, (NullIf(t.code, ''), Equal)),
                'product.msg_category_code_unique'),
            ]
        cls._order.insert(0, ('name', 'ASC'))
        cls._buttons.update({
                'add_products': {
                    'icon': 'tryton-add',
                    },
                })

    @classmethod
    def default_code_readonly(cls):
        pool = Pool()
        Configuration = pool.get('product.configuration')
        config = Configuration(1)
        return bool(config.category_sequence)

    def get_code_readonly(self, name):
        return self.default_code_readonly()

    @classmethod
    def order_code(cls, tables):
        table, _ = tables[None]
        if cls.default_code_readonly():
            return [CharLength(table.code), table.code]
        else:
            return [table.code]

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

    @classmethod
    @ModelView.button_action('product.act_category_product')
    def add_products(cls, categories):
        return {
            'res_id': [categories[0].id if categories else None],
            'pyson_domain': PYSONEncoder().encode(
                [('id', '=', categories[0].id if categories else None)]),
             }

    @classmethod
    def _code_sequence(cls):
        pool = Pool()
        Configuration = pool.get('product.configuration')
        config = Configuration(1)
        return config.category_sequence

    @classmethod
    def preprocess_values(cls, mode, values):
        values = super().preprocess_values(mode, values)
        if mode == 'create' and not values.get('code'):
            if sequence := cls._code_sequence():
                values['code'] = sequence.get()
        return values

    @classmethod
    def copy(cls, categories, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('templates')
        default.setdefault('code', None)
        return super().copy(categories, default=default)
