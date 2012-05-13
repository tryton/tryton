#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, Button
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.pool import Pool


class BOM(ModelSQL, ModelView):
    "Bill of Material"
    _name = 'production.bom'
    _description = __doc__

    name = fields.Char('Name', required=True, translate=True)
    active = fields.Boolean('Active', select=1)
    inputs = fields.One2Many('production.bom.input', 'bom', 'Inputs')
    outputs = fields.One2Many('production.bom.output', 'bom', 'Outputs')
    output_products = fields.Many2Many('production.bom.output',
        'bom', 'product', 'Output Products')

    def default_active(self):
        return True

    def compute_factor(self, bom, product, quantity, uom):
        '''
        Compute factor for an output product
        '''
        uom_obj = Pool().get('product.uom')
        for output in bom.outputs:
            if output.product == product:
                quantity = uom_obj.compute_qty(uom, quantity,
                    output.uom, round=False)
                return quantity / output.quantity

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default['output_products'] = False
        return super(BOM, self).copy(ids, default=default)

BOM()


class BOMInput(ModelSQL, ModelView):
    "Bill of Material Input"
    _name = 'production.bom.input'
    _description = __doc__
    _rec_name = 'product'

    bom = fields.Many2One('production.bom', 'BOM', required=True,
        select=1)
    product = fields.Many2One('product.product', 'Product',
        required=True, domain=[
            ('type', '!=', 'service'),
        ], on_change=['product', 'uom'])
    uom_category = fields.Function(fields.Many2One(
        'product.uom.category', 'Uom Category',
        on_change_with=['product']), 'get_uom_category')
    uom = fields.Many2One('product.uom', 'Uom', required=True,
        domain=[
            ('category', '=', Eval('uom_category')),
        ], depends=['uom_category'])
    unit_digits = fields.Function(fields.Integer('Unit Digits',
        on_change_with=['uom']), 'get_unit_digits')
    quantity = fields.Float('Quantity', required=True,
        digits=(16, Eval('unit_digits', 2)),
        depends=['unit_digits'])

    def __init__(self):
        super(BOMInput, self).__init__()
        self._sql_constraints = [
            ('product_bom_uniq', 'UNIQUE(product, bom)',
                'product_bom_uniq'),
        ]
        self._constraints += [
            ('check_bom_recursion', 'recursive_bom'),
        ]
        self._error_messages.update({
            'product_bom_uniq': 'Product must be unique per BOM!',
            'recursive_bom': 'You can not create recursive BOMs!',
        })

    def on_change_product(self, vals):
        product_obj = Pool().get('product.product')

        res = {}
        if vals.get('product'):
            product = product_obj.browse(vals['product'])
            uom_ids = [x.id for x in product.default_uom.category.uoms]
            if (not vals.get('uom')
                    or vals.get('uom') not in uom_ids):
                res['uom'] = product.default_uom.id
                res['uom.rec_name'] = product.default_uom.rec_name
                res['unit_digits'] = product.default_uom.digits
        else:
            res['uom'] = False
            res['uom.rec_name'] = ''
            res['unit_digits'] = 2
        return res

    def on_change_with_uom_category(self, vals):
        product_obj = Pool().get('product.product')
        if vals.get('product'):
            product = product_obj.browse(vals['product'])
            return product.default_uom.category.id
        return False

    def get_uom_category(self, ids, name):
        res = {}
        for input in self.browse(ids):
            res[input.id] = input.product.default_uom.category.id
        return res

    def on_change_with_unit_digits(self, vals):
        uom_obj = Pool().get('product.uom')
        if vals.get('uom'):
            uom = uom_obj.browse(vals['uom'])
            return uom.digits
        return 2

    def get_unit_digits(self, ids, name):
        res = {}
        for input in self.browse(ids):
            res[input.id] = input.uom.digits
        return res

    def check_bom_recursion(self, ids):
        '''
        Check BOM recursion
        '''
        product_obj = Pool().get('product.product')

        inputs = self.browse(ids)
        product_ids = [input.product.id for input in inputs]
        return product_obj.check_bom_recursion(product_ids)

    def compute_quantity(self, line, factor):
        uom_obj = Pool().get('product.uom')
        return uom_obj.round(line.quantity * factor, line.uom.rounding)

BOMInput()


class BOMOutput(BOMInput):
    "Bill of Material Output"
    _name = 'production.bom.output'
    _description = __doc__

BOMOutput()


class BOMTree(ModelView):
    'BOM Tree'
    _name = 'production.bom.tree'
    _description = __doc__

    product = fields.Many2One('product.product', 'Product')
    quantity = fields.Float('Quantity', digits=(16, Eval('unit_digits', 2)),
        depends=['unit_digits'])
    uom = fields.Many2One('product.uom', 'Uom')
    unit_digits = fields.Integer('Unit Digits')
    childs = fields.One2Many('production.bom.tree', None, 'Childs')

    def tree(self, product, quantity, uom, bom=None):
        bom_obj = Pool().get('production.bom')
        input_obj = Pool().get('production.bom.input')

        result = []
        if bom is None:
            if not product.boms:
                return result
            bom = product.boms[0].bom

        factor = bom_obj.compute_factor(bom, product, quantity, uom)
        for input in bom.inputs:
            quantity = input_obj.compute_quantity(input, factor)
            childs = self.tree(input.product, quantity, input.uom)
            values = {
                'product': input.product.id,
                'quantity': quantity,
                'uom': input.uom.id,
                'unit_digits': input.uom.digits,
                'childs': childs,
            }
            result.append(values)
        return result

BOMTree()


class OpenBOMTreeStart(ModelView):
    'Open BOM Tree'
    _name = 'production.bom.tree.open.start'

    quantity = fields.Float('Quantity', required=True,
        digits=(16, Eval('unit_digits', 2)), depends=['unit_digits'])
    uom = fields.Many2One('product.uom', 'Unit', required=True,
        domain=[
            ('category', '=', Eval('category')),
        ], depends=['category'])
    unit_digits = fields.Integer('Unit Digits', readonly=True,
        on_change_with=['uom'])
    category = fields.Many2One('product.uom.category', 'Category',
        readonly=True)
    bom = fields.Many2One('product.product-production.bom',
        'BOM', required=True, domain=[
            ('product', '=', Eval('product')),
        ], depends=['product'])
    product = fields.Many2One('product.product', 'Product', readonly=True)

    def on_change_with_unit_digits(self, values):
        uom_obj = Pool().get('product.uom')
        if values.get('uom'):
            uom = uom_obj.browse(values['uom'])
            return uom.digits
        return 2

OpenBOMTreeStart()


class OpenBOMTreeTree(ModelView):
    'Open BOM Tree'
    _name = 'production.bom.tree.open.tree'

    bom_tree = fields.One2Many('production.bom.tree', None, 'BOM Tree')

    def tree(self, bom, product, quantity, uom):
        pool = Pool()
        tree_obj = pool.get('production.bom.tree')

        childs = tree_obj.tree(product, quantity, uom, bom=bom)
        bom_tree = [{
            'product': product.id,
            'quantity': quantity,
            'uom': uom.id,
            'unit_digits': uom.digits,
            'childs': childs,
        }]
        return {
            'bom_tree': bom_tree,
        }

OpenBOMTreeTree()


class OpenBOMTree(Wizard):
    'Open BOM Tree'
    _name = 'production.bom.tree.open'

    start = StateView('production.bom.tree.open.start',
        'production.bom_tree_open_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'tree', 'tryton-ok', True),
            ])
    tree = StateView('production.bom.tree.open.tree',
        'production.bom_tree_open_tree_view_form', [
            Button('Change', 'start', 'tryton-go-previous'),
            Button('Close', 'end', 'tryton-close'),
            ])

    def default_start(self, session, fields):
        product_obj = Pool().get('product.product')
        defaults = {}
        product = product_obj.browse(Transaction().context['active_id'])
        defaults['category'] = product.default_uom.category.id
        if session.start.uom:
            defaults['uom'] = session.start.uom.id
            defaults['unit_digits'] = session.start.unit_digits
        else:
            defaults['uom'] = product.default_uom.id
            defaults['unit_digits'] = product.default_uom.digits
        defaults['product'] = product.id
        if session.start.bom:
            defaults['bom'] = session.start.bom.id
        elif product.boms:
            defaults['bom'] = product.boms[0].id
        defaults['quantity'] = session.start.quantity
        return defaults

    def default_tree(self, session, fields):
        pool = Pool()
        bom_tree_obj = pool.get('production.bom.tree.open.tree')
        return bom_tree_obj.tree(session.start.bom.bom, session.start.product,
            session.start.quantity, session.start.uom)

OpenBOMTree()
