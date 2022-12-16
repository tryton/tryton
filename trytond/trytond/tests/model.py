#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelSingleton, ModelSQL, ModelView, fields


class Singleton(ModelSingleton, ModelSQL, ModelView):
    'Singleton'
    _name = 'tests.singleton'
    _description = __doc__

    name = fields.Char('Name')

    def default_name(self, cursor, user, context=None):
        return 'test'

Singleton()
