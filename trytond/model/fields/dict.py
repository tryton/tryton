# This file is part of Tryton.  The COPYRIGHT file at the toplevel of this
# repository contains the full copyright notices and license terms.
from functools import partial
import json

from sql import operators, Literal, Select, CombiningQuery, Cast, Null

from trytond import backend
from trytond.pool import Pool
from trytond.protocols.jsonrpc import JSONDecoder, JSONEncoder
from trytond.tools import grouped_slice
from trytond.transaction import Transaction
from .field import Field, SQL_OPERATORS

# Use canonical form
dumps = partial(
    json.dumps, cls=JSONEncoder, separators=(',', ':'), sort_keys=True)


class ImmutableDict(dict):

    __slots__ = ()

    def _not_allowed(cls, *args, **kwargs):
        raise TypeError("Operation not allowed on ImmutableDict")

    __setitem__ = _not_allowed
    __delitem__ = _not_allowed
    __ior__ = _not_allowed
    clear = _not_allowed
    pop = _not_allowed
    popitem = _not_allowed
    setdefault = _not_allowed
    update = _not_allowed

    del _not_allowed


class Dict(Field):
    'Define dict field.'
    _type = 'dict'
    _sql_type = 'TEXT'
    _py_type = dict

    def __init__(self, schema_model, string='', help='', required=False,
            readonly=False, domain=None, states=None, select=False,
            on_change=None, on_change_with=None, depends=None,
            context=None, loading='lazy'):
        super(Dict, self).__init__(string, help, required, readonly, domain,
            states, select, on_change, on_change_with, depends, context,
            loading)
        self.schema_model = schema_model
        self.search_unaccented = True

    def get(self, ids, model, name, values=None):
        dicts = dict((id, None) for id in ids)
        for value in values or []:
            data = value[name]
            if data:
                # If stored as JSON conversion is done on backend
                if isinstance(data, str):
                    data = json.loads(data, object_hook=JSONDecoder())
                dicts[value['id']] = ImmutableDict(data)
        return dicts

    def sql_format(self, value):
        value = super().sql_format(value)
        if isinstance(value, dict):
            d = {}
            for k, v in value.items():
                if v is None:
                    continue
                if isinstance(v, list):
                    v = list(sorted(set(v)))
                d[k] = v
            value = dumps(d)
        return value

    def __set__(self, inst, value):
        if value:
            value = ImmutableDict(value)
        super().__set__(inst, value)

    def translated(self, name=None, type_='values'):
        "Return a descriptor for the translated value of the field"
        if name is None:
            name = self.name
        if name is None:
            raise ValueError('Missing name argument')
        return TranslatedDict(name, type_)

    def _domain_column(self, operator, column, key=None):
        database = Transaction().database
        column = database.json_get(
            super()._domain_column(operator, column), key)
        if operator.endswith('like'):
            column = Cast(column, database.sql_type('VARCHAR').base)
            if self.search_unaccented and operator.endswith('ilike'):
                column = database.unaccent(column)
        return column

    def _domain_value(self, operator, value):
        if backend.name == 'sqlite' and isinstance(value, bool):
            # json_extract returns 0 for JSON false and 1 for JSON true
            value = int(value)
        if isinstance(value, (Select, CombiningQuery)):
            return value
        if isinstance(value, (list, tuple)):
            value = sorted(set(value))
        if operator.endswith('in'):
            return [dumps(v) for v in value]
        else:
            value = dumps(value)
            if self.search_unaccented and operator.endswith('ilike'):
                database = Transaction().database
                value = database.unaccent(value)
            return value

    def _domain_add_null(self, column, operator, value, expression):
        expression = super()._domain_add_null(
            column, operator, value, expression)
        if value is None and operator.endswith('='):
            if operator == '=':
                expression |= (column == Null)
            else:
                expression &= (column != Null)
        return expression

    def convert_domain(self, domain, tables, Model):
        name, operator, value = domain[:3]
        if '.' not in name:
            return super().convert_domain(domain, tables, Model)
        database = Transaction().database
        table, _ = tables[None]
        name, key = name.split('.', 1)
        Operator = SQL_OPERATORS[operator]
        raw_column = self.sql_column(table)
        column = self._domain_column(operator, raw_column, key)
        expression = Operator(column, self._domain_value(operator, value))
        if operator in {'=', '!='}:
            # Try to use custom operators in case there is indexes
            try:
                if value is None:
                    expression = database.json_key_exists(
                        raw_column, key)
                    if operator == '=':
                        expression = operators.Not(expression)
                # we compare on multi-selection by doing an equality check and
                # not a contain check
                elif not isinstance(value, (list, tuple)):
                    expression = database.json_contains(
                        raw_column, dumps({key: value}))
                    if operator == '!=':
                        expression = operators.Not(expression)
                        expression &= database.json_key_exists(
                            raw_column, key)
                return expression
            except NotImplementedError:
                pass
        elif operator.endswith('in'):
            # Try to use custom operators in case there is indexes
            if not value:
                expression = Literal(operator.startswith('not'))
            else:
                op = '!=' if operator.startswith('not') else '='
                try:
                    in_expr = Literal(False)
                    for v in value:
                        in_expr |= database.json_contains(
                            self._domain_column(op, raw_column, key),
                            dumps(v))
                    if operator.startswith('not'):
                        in_expr = ~in_expr
                    expression = in_expr
                except NotImplementedError:
                    pass
        expression = self._domain_add_null(column, operator, value, expression)
        return expression

    def convert_order(self, name, tables, Model):
        fname, _, key = name.partition('.')
        if not key:
            return super().convert_order(fname, tables, Model)
        database = Transaction().database
        table, _ = tables[None]
        column = self.sql_column(table)
        return [database.json_get(column, key)]

    def definition(self, model, language):
        definition = super().definition(model, language)
        definition['schema_model'] = self.schema_model
        return definition


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
