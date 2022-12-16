# This file is part of Tryton.  The COPYRIGHT file at the toplevel of this
# repository contains the full copyright notices and license terms.
try:
    import simplejson as json
except ImportError:
    import json
from sql import Query, Expression

from .field import Field, SQLType
from ...protocols.jsonrpc import JSONDecoder, JSONEncoder


class Dict(Field):
    'Define dict field.'
    _type = 'dict'

    def __init__(self, schema_model, string='', help='', required=False,
            readonly=False, domain=None, states=None, select=False,
            on_change=None, on_change_with=None, depends=None,
            context=None, loading='lazy'):
        super(Dict, self).__init__(string, help, required, readonly, domain,
            states, select, on_change, on_change_with, depends, context,
            loading)
        self.schema_model = schema_model

    def get(self, ids, model, name, values=None):
        dicts = dict((id, None) for id in ids)
        for value in values or []:
            if value[name]:
                dicts[value['id']] = json.loads(value[name],
                    object_hook=JSONDecoder())
        return dicts

    @staticmethod
    def sql_format(value):
        if isinstance(value, (Query, Expression)):
            return value
        if value is None:
            return None
        assert isinstance(value, dict)
        return json.dumps(value, cls=JSONEncoder)

    def sql_type(self):
        return SQLType('TEXT', 'TEXT')
