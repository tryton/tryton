# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelStorage, ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

__all__ = ['ClassificationMixin', 'classification_tree',
    'Template', 'Product', 'ClassificationDummy', 'ClassificationTreeDummy']


class ClassificationMixin(object):
    name = fields.Char('Name', translate=True, required=True)
    active = fields.Boolean('Active', select=True)
    selectable = fields.Boolean('Selectable', select=True)

    @classmethod
    def default_active(cls):
        return True

    @classmethod
    def default_selectable(cls):
        return True


def classification_tree(name):
    'Return a ClassificationMixin with tree structure'

    class ClassificationTreeMixin(ClassificationMixin):
        parent = fields.Many2One(name, 'Parent', select=True)
        childs = fields.One2Many(name, 'parent', 'Children')

        @classmethod
        def validate(cls, records):
            super(ClassificationMixin, cls).validate(records)
            cls.check_recursion(records, rec_name='name')

        def get_rec_name(self, name):
            if self.parent:
                return self.parent.get_rec_name(name) + ' / ' + self.name
            else:
                return self.name

    return ClassificationTreeMixin


class Template:
    __metaclass__ = PoolMeta
    __name__ = 'product.template'

    classification = fields.Reference('Classification',
        selection='get_classification',
        domain=[
            ('selectable', '=', True),
            ],
        states={
            'readonly': ~Eval('active', True),
            },
        depends=['active'])

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


class Product:
    __metaclass__ = PoolMeta
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
