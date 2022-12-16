#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelSingleton, ModelSQL, fields

__all__ = [
    'Singleton', 'URLObject', 'ModelInherits', 'ModelInheritsSubModel',
    'ModelInheritsSubSubModel', 'ModelInheritsSubSubSubModel',
    'ModelInheritsOverriddenFieldModel', 'ModelSQLRequiredField'
    ]


class Singleton(ModelSingleton, ModelSQL):
    'Singleton'
    __name__ = 'test.singleton'
    name = fields.Char('Name')

    @staticmethod
    def default_name():
        return 'test'


class URLObject(ModelSQL):
    'URLObject'
    __name__ = 'test.urlobject'
    name = fields.Char('Name')


class ModelInherits(ModelSQL):
    'Model Inherits'
    __name__ = 'test.model_inherits'

    name = fields.Char('Name')


class ModelInheritsSubModel(ModelSQL):
    'Model Inherits Sub-Model'
    __name__ = 'test.submodel'
    _inherits = {'test.model_inherits': 'parent_model'}

    subfield = fields.Char('SubField')
    parent_model = fields.Many2One('test.model_inherits', 'Parent model',
        required=True)


class ModelInheritsSubSubModel(ModelSQL):
    'Model Inherits Sub-Sub-Model'
    __name__ = 'test.subsubmodel'
    _inherits = {'test.submodel': 'parent_model'}

    subsubfield = fields.Char('SubField')
    parent_model = fields.Many2One('test.submodel', 'Parent model',
        required=True)


class ModelInheritsSubSubSubModel(ModelSQL):
    'Model Inherits Sub-Sub-Sub-Model'
    __name__ = 'test.subsubsubmodel'
    _inherits = {'test.subsubmodel': 'parent_model'}

    subsubsubfield = fields.Char('SubField')
    parent_model = fields.Many2One('test.subsubmodel', 'Parent model',
        required=True)


class ModelInheritsOverriddenFieldModel(ModelSQL):
    'Model Inherits Overridden Field Model'
    __name__ = 'test.overriddeninheritedfieldmodel'
    _inherits = {'test.subsubmodel': 'parent_model'}

    subfield = fields.Integer('Overridden field')
    parent_model = fields.Many2One('test.subsubmodel', 'Parent model',
        required=True)


class ModelSQLRequiredField(ModelSQL):
    'model with a required field'
    __name__ = 'test.modelsql'

    integer = fields.Integer(string="integer", required=True)
    desc = fields.Char(string="desc", required=True)
