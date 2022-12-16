# This file is part of Tryton.  The COPYRIGHT file at the toplevel of this
# repository contains the full copyright notices and license terms.
try:
    import simplejson as json
except ImportError:
    import json

from .field import Field
from trytond.protocols.jsonrpc import object_hook


class Dict(Field):
    'Define dict field.'
    _type = 'dict'

    def __init__(self, schema_model, string='', help='', required=False,
            readonly=False, domain=None, states=None, select=False,
            on_change=None, on_change_with=None, depends=None,
            order_field=None, context=None, loading='lazy'):
        super(Dict, self).__init__(string, help, required, readonly, domain,
            states, select, on_change, on_change_with, depends, order_field,
            context, loading)
        self.schema_model = schema_model

    def get(self, ids, model, name, values=None):
        dicts = dict((id, None) for id in ids)
        for value in values or []:
            if value[name]:
                dicts[value['id']] = json.loads(value[name],
                    object_hook=object_hook)
        return dicts
