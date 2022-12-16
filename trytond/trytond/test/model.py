#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelSingleton, ModelSQL, fields


class Singleton(ModelSingleton, ModelSQL):
    'Singleton'
    _name = 'test.singleton'
    _description = __doc__

    name = fields.Char('Name')

    def default_name(self):
        return 'test'

Singleton()


class URLObject(ModelSQL):
    _name = 'test.urlobject'

    name = fields.Char('Name')


URLObject()
