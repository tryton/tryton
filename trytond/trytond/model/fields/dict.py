# This file is part of Tryton.  The COPYRIGHT file at the toplevel of this
# repository contains the full copyright notices and license terms.
import json

from .field import Field
from ...protocols.jsonrpc import JSONDecoder, JSONEncoder
from ...pool import Pool
from ...tools import grouped_slice


class Dict(Field):
    'Define dict field.'
    _type = 'dict'
    _sql_type = 'TEXT'

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
            data = value[name]
            if data:
                # If stored as JSON conversion is done on backend
                if isinstance(data, str):
                    data = json.loads(data, object_hook=JSONDecoder())
                dicts[value['id']] = data
        return dicts

    def sql_format(self, value):
        if value is None:
            return None
        assert isinstance(value, dict)
        # Use canonical form
        return json.dumps(
            value, cls=JSONEncoder, separators=(',', ':'), sort_keys=True)

    def translated(self, name=None, type_='values'):
        "Return a descriptor for the translated value of the field"
        if name is None:
            name = self.name
        if name is None:
            raise ValueError('Missing name argument')
        return TranslatedDict(name, type_)


class TranslatedDict(object):
    'A descriptor for translated values of Dict field'

    def __init__(self, name, type_):
        assert type_ in ['keys', 'values']
        self.name = name
        self.type_ = type_

    def __get__(self, inst, cls):
        if inst is None:
            return self
        pool = Pool()
        schema_model = getattr(cls, self.name).schema_model
        SchemaModel = pool.get(schema_model)

        value = getattr(inst, self.name)
        if not value:
            return value

        domain = []
        if self.type_ == 'values':
            domain = [('type_', '=', 'selection')]

        records = []
        for key_names in grouped_slice(value.keys()):
            records += SchemaModel.search([
                    ('name', 'in', key_names),
                    ] + domain)
        keys = SchemaModel.get_keys(records)

        if self.type_ == 'keys':
            return {k['name']: k['string'] for k in keys}

        elif self.type_ == 'values':
            trans = {k['name']: dict(k['selection']) for k in keys}
            return {k: v if k not in trans else trans[k].get(v, v)
                for k, v in value.items()}
