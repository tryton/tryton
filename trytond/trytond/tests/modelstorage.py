# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool


class ModelStorage(ModelSQL):
    'Model stored'
    __name__ = 'test.modelstorage'
    name = fields.Char('Name')


class ModelStorageRequired(ModelSQL):
    'Model stored'
    __name__ = 'test.modelstorage.required'
    name = fields.Char('Name', required=True)


class ModelStorageContext(ModelSQL):
    'Model Storage to test Context'
    __name__ = 'test.modelstorage.context'
    context = fields.Function(fields.Binary('Context'), 'get_context')

    def get_context(self, name):
        return Transaction().context


class ModelStoragePYSONDomain(ModelSQL):
    "Model stored with PYSON domain"
    __name__ = 'test.modelstorage.pyson_domain'
    constraint = fields.Char("Constraint")
    value = fields.Char(
        "Value",
        domain=[
            ('value', '=', Eval('constraint')),
            ],
        depends=['constraint'])


class ModelStorageRelationDomain(ModelSQL):
    "Model stored containing a relation field with a domain"
    __name__ = 'test.modelstorage.relation_domain'
    relation = fields.Many2One(
        'test.modelstorage.relation_domain.target', "Value",
        domain=[
            ('value', '=', 'valid'),
            ])


class ModelStorageRelationDomainTarget(ModelSQL):
    "Target of Model stored containing a relation field with a domain"
    __name__ = 'test.modelstorage.relation_domain.target'
    value = fields.Char("Value")


class ModelStorageRelationDomain2(ModelSQL):
    "Model stored containing a relation field with a domain with 2 level"
    __name__ = 'test.modelstorage.relation_domain2'
    relation = fields.Many2One(
        'test.modelstorage.relation_domain2.target', "Relation",
        domain=[
            ('relation2.value', '=', 'valid'),
            ])


class ModelStorageRelationDomain2Target(ModelSQL):
    "First Target of Model stored containing a relation field with a domain"
    __name__ = 'test.modelstorage.relation_domain2.target'
    relation2 = fields.Many2One(
        'test.modelstorage.relation_domain.target', "Relation 2")


def register(module):
    Pool.register(
        ModelStorage,
        ModelStorageRequired,
        ModelStorageContext,
        ModelStoragePYSONDomain,
        ModelStorageRelationDomain,
        ModelStorageRelationDomainTarget,
        ModelStorageRelationDomain2,
        ModelStorageRelationDomain2Target,
        module=module, type_='model')
