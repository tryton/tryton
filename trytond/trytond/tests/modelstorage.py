# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL
from trytond.model import ModelStorage as ModelStorage_
from trytond.model import fields
from trytond.pool import Pool
from trytond.pyson import Eval, If
from trytond.transaction import Transaction


class ModelStorage(ModelSQL):
    'Model stored'
    __name__ = 'test.modelstorage'
    name = fields.Char('Name')


class ModelStorageRequired(ModelSQL):
    'Model stored'
    __name__ = 'test.modelstorage.required'
    name = fields.Char('Name', required=True)


class ModelStorageSaveMany2One(ModelSQL):
    "ModelStorage to test save with Many2One"
    __name__ = 'test.modelstorage.save_m2o'
    target = fields.Many2One('test.modelstorage.save_m2o.target', "Target")
    targets = fields.One2Many(
        'test.modelstorage.save_m2o.target', 'parent', "Targets")


class ModelStorageSaveMany2OneTarget(ModelSQL):
    "ModelStorage to test save with Many2One - Target"
    __name__ = 'test.modelstorage.save_m2o.target'

    parent = fields.Many2One('test.modelstorage.save_m2o', "Parent")
    target = fields.Many2One(
        'test.modelstorage.save_m2o.o2m_target.target', "Target")


class ModelStorageSaveMany2OneTargetTarget(ModelSQL):
    "ModelStorage to test save with Many2One - Target of Target"
    __name__ = 'test.modelstorage.save_m2o.o2m_target.target'


class ModelStorageSave2Many(ModelSQL):
    "Model Storage to test save with xxx2many"
    __name__ = 'test.modelstorage.save2many'
    targets = fields.One2Many(
        'test.modelstorage.save2many.target', 'parent', "Targets")
    m2m_targets = fields.Many2Many(
        'test.modelstorage.save2many.relation', 'parent', 'target', "Targets")


class ModelStorageSave2ManyTarget(ModelSQL):
    "Model Storage to test save with xxx2many"
    __name__ = 'test.modelstorage.save2many.target'
    parent = fields.Many2One('test.modelstorage.save2many', "Parent")


class ModelStorageSave2ManyRelation(ModelSQL):
    "Model Storage to test save with xxx2many"
    __name__ = 'test.modelstorage.save2many.relation'
    parent = fields.Many2One('test.modelstorage.save2many', "Parent")
    target = fields.Many2One('test.modelstorage.save2many.target', "Target")


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
    relation_valid = fields.Boolean("Relation Valid")
    relation_pyson = fields.Many2One(
        'test.modelstorage.relation_domain.target', "Value",
        domain=[
            If(Eval('relation_valid', True),
                ('value', '=', 'valid'),
                ('value', '!=', 'valid')),
            ],
        depends=['relation_valid'])
    relation_context = fields.Many2One(
        'test.modelstorage.relation_domain.target', "Value",
        domain=[
            ('valid', '=', True),
            ],
        context={
            'valid': Eval('relation_valid', True),
            })
    relation_pyson_context = fields.Many2One(
        'test.modelstorage.relation_domain.target', "Value",
        domain=[
            If(Eval('relation_valid', True),
                ('valid', '=', True),
                ('valid', '=', None)),
            ],
        context={
            'valid': Eval('relation_valid', True),
            },
        depends=['relation_valid'])


class ModelStorageRelationDomainTarget(ModelSQL):
    "Target of Model stored containing a relation field with a domain"
    __name__ = 'test.modelstorage.relation_domain.target'
    value = fields.Char("Value")
    valid = fields.Function(
        fields.Boolean("Valid"), 'get_valid', searcher='search_valid')

    def get_valid(self, name):
        return Transaction().context.get('valid')

    @classmethod
    def search_valid(cls, name, domain):
        if Transaction().context.get('valid') == domain[2]:
            return []
        else:
            return [('id', '=', -1)]


class ModelStorageRelationMultiDomain(ModelSQL):
    "Model stored containing a relation fields with multi domain"
    __name__ = 'test.modelstorage.relation_multi_domain'
    relation = fields.Many2One(
        'test.modelstorage.relation_multi_domain.target', "Value",
        domain=[
            ('test1', '=', True),
            ('test2', '=', True),
            ])


class ModelStorageRelationMultiDomainTarget(ModelSQL):
    "Target of Model stored containing a relation field with multi domain"
    __name__ = 'test.modelstorage.relation_multi_domain.target'
    test1 = fields.Boolean("Test 1")
    test2 = fields.Boolean("Test 2")


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


class ModelStorageEvalEnvironment(ModelStorage_):
    "Model for EvalEnvironment"
    __name__ = 'test.modelstorage.eval_environment'
    char = fields.Char("Name")
    reference = fields.Reference(
        "Reference", [
            ('test.modelstorage.eval_environment', "Reference"),
            ])
    multiselection = fields.MultiSelection([
            ('value1', "Value1"),
            ('value2', "Value2"),
            ], "MultiSelection")
    many2one = fields.Many2One(
        'test.modelstorage.eval_environment', "Many2One")
    one2many = fields.One2Many(
        'test.modelstorage.eval_environment', 'many2one', "One2Many")


class ModelStorageDomainNotRequired(ModelSQL):
    "Model for domain on not required field"
    __name__ = 'test.modelstorage.domain_not_required'

    domain_not_required = fields.Integer(
        "Domain Not Required", domain=[('domain_not_required', '>', 0)])


def register(module):
    Pool.register(
        ModelStorage,
        ModelStorageRequired,
        ModelStorageSaveMany2One,
        ModelStorageSaveMany2OneTarget,
        ModelStorageSaveMany2OneTargetTarget,
        ModelStorageSave2Many,
        ModelStorageSave2ManyTarget,
        ModelStorageSave2ManyRelation,
        ModelStorageContext,
        ModelStoragePYSONDomain,
        ModelStorageRelationDomain,
        ModelStorageRelationDomainTarget,
        ModelStorageRelationMultiDomain,
        ModelStorageRelationMultiDomainTarget,
        ModelStorageRelationDomain2,
        ModelStorageRelationDomain2Target,
        ModelStorageEvalEnvironment,
        ModelStorageDomainNotRequired,
        module=module, type_='model')
