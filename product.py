#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import Model, ModelSQL, fields
from trytond.pyson import Eval


class Template(Model):
    _name = 'product.template'

    # TODO to replace with a Multiple Selection
    lot_required = fields.Many2Many('product.template-stock.lot.type',
        'template', 'type', 'Lot Required',
        help='The type of location for which lot is required',
        states={
            'invisible': ~Eval('type').in_(['goods', 'assets']),
            },
        depends=['type'])

Template()


class Product(Model):
    _name = 'product.product'

    def lot_is_required(self, product, from_, to):
        'Is product lot required for move with "from_" and "to" location ?'
        lot_required = [t.code for t in product.lot_required]
        for location in (from_, to):
            if location.type in lot_required:
                return True

Product()


class TemplateLotType(ModelSQL):
    'Template - Stock Lot Type'
    _name = 'product.template-stock.lot.type'

    template = fields.Many2One('product.template', 'Template', required=True,
        select=True)
    type = fields.Many2One('stock.lot.type', 'Type', required=True)

TemplateLotType()
