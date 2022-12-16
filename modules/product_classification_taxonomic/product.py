# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, DeactivableMixin, fields
from trytond.pool import PoolMeta

from trytond.modules.product_classification.product import (
    classification_tree, ClassificationMixin)


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    @classmethod
    def _get_classification(cls):
        return super(Template, cls)._get_classification() + [
            'product.taxon', 'product.cultivar']


class Taxon(classification_tree('product.taxon'), ModelSQL, ModelView):
    'Taxon'
    __name__ = 'product.taxon'
    rank = fields.Selection([
            ('domain', 'Domain'),
            ('kingdom', 'Kingdom'),
            ('phylum', 'Phylum'),
            ('division', 'Division'),
            ('class', 'Class'),
            ('order', 'Order'),
            ('family', 'Family'),
            ('tribe', 'Tribe'),
            ('genus', 'Genus'),
            ('section', 'Section'),
            ('series', 'Series'),
            ('species', 'Species'),
            ('variety', 'Variety'),
            ('form', 'Form'),
            ], 'Type', select=True, sort=False)


class Cultivar(ClassificationMixin, ModelSQL, ModelView):
    'Cultivar'
    __name__ = 'product.cultivar'
    taxon = fields.Many2One('product.taxon', 'Taxon', required=True)
    groups = fields.Many2Many('product.cultivar-product.cultivar.group',
        'cultivar', 'group', 'Groups')


class CultivarGroup(DeactivableMixin, ModelSQL, ModelView):
    'Cultivar Group'
    __name__ = 'product.cultivar.group'
    name = fields.Char('Name', translate=True)
    cultivars = fields.Many2Many('product.cultivar-product.cultivar.group',
        'group', 'cultivar', 'Cultivars')


class Cultivar_CultivarGroup(ModelSQL):
    'Cultivar-CultivarGroup'
    __name__ = 'product.cultivar-product.cultivar.group'
    cultivar = fields.Many2One('product.cultivar', 'Cultivar', select=True,
        required=True)
    group = fields.Many2One('product.cultivar.group', 'Group', select=True,
        required=True)

# TODO Grex
