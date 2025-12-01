# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import shopify

from .shopify_retry import GraphQLException


def deep_merge(d1, d2):
    "Merge 2 fields dictionary"
    result = d1.copy()
    for key, value in d2.items():
        if result.get(key):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def selection(fields):
    "Return selection string for the fields dictionary"
    def _format(key, value):
        if not value:
            return key
        fields = '\n'.join(_format(k, v) for k, v in value.items())
        return f'{key} {{\n{fields}\n}}'
    return _format('', fields).strip()


def iterate(query, params, query_name, path=None, data=None):
    def getter(data):
        if path:
            for name in path.split('.'):
                data = data[name]
        return data

    if data is None:
        data = shopify.GraphQL().execute(
            query, {
                **params,
                'cursor': None,
                })['data'][query_name]
        if errors := data.get('userErrors'):
            raise GraphQLException({'errors': errors})

    while True:
        lst = getter(data)
        for item in lst['nodes']:
            yield item
        if not lst['pageInfo']['hasNextPage']:
            break
        data = shopify.GraphQL().execute(
            query, {
                **params,
                'cursor': lst['pageInfo']['endCursor'],
                })['data'][query_name]
        if errors := data.get('userErrors'):
            raise GraphQLException({'errors': errors})
