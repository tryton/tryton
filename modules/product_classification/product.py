# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import (ModelStorage, ModelView, DeactivableMixin, fields,
    tree)
from trytond.pool import PoolMeta, Pool


class ClassificationMixin(DeactivableMixin):
    __slots__ = ()
    name = fields.Char('Name', translate=True, required=True)
    selectable = fields.Boolean('Selectable', select=True)

    @classmethod
    def default_selectable(cls):
        return True


def classification_tree(name):
    'Return a ClassificationMixin with tree structure'

    class ClassificationTreeMixin(tree(separator=' / '), ClassificationMixin):
        __slots__ = ()
        parent = fields.Many2One(name, 'Parent', select=True)
        childs = fields.One2Many(name, 'parent', 'Children')

    return ClassificationTreeMixin


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    classification = fields.Reference('Classification',
        selection='get_classification',
        domain=[
            ('selectable', '=', True),
            ])

    @classmethod
    def _get_classification(cls):
        'Return list of Model names for classification Reference'
        return []

    @classmethod
    def get_classification(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        models = cls._get_classification()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    @classmethod
    def get_classification(cls):
        pool = Pool()
        Template = pool.get('product.template')
        return Template.get_classification()


class ClassificationDummy(ClassificationMixin, ModelStorage, ModelView):
    'Dummy Product Classification'
    __name__ = 'product.classification.dummy'


class ClassificationTreeDummy(
        classification_tree('product.classification_tree.dummy'),
        ModelStorage, ModelView):
    'Dummy Product Classification Tree'
    __name__ = 'product.classification_tree.dummy'
