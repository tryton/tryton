#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelSingleton, ModelSQL, fields

__all__ = [
    'Singleton', 'URLObject', 'ModelSQLRequiredField',
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


class ModelSQLRequiredField(ModelSQL):
    'model with a required field'
    __name__ = 'test.modelsql'

    integer = fields.Integer(string="integer", required=True)
    desc = fields.Char(string="desc", required=True)
