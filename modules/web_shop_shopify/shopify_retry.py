# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import json
import time
import urllib

from pyactiveresource.connection import ClientError
from shopify import Limits
from shopify.base import ShopifyConnection
from shopify.resources.graphql import GraphQL

try:
    from shopify.resources.graphql import GraphQLException
except ImportError:
    class GraphQLException(Exception):
        def __init__(self, response):
            self._response = response

        @property
        def errors(self):
            return self._response['errors']

from trytond.protocols.wrappers import HTTPStatus


def patch():
    def _open(*args, **kwargs):
        while True:
            try:
                return open_func(*args, **kwargs)
            except ClientError as e:
                if e.response.code == HTTPStatus.TOO_MANY_REQUESTS:
                    retry_after = float(
                        e.response.headers.get('Retry-After', 2))
                    time.sleep(retry_after)
                else:
                    raise
            else:
                try:
                    if Limits.credit_maxed():
                        time.sleep(0.5)
                except Exception:
                    pass

    if ShopifyConnection._open != _open:
        open_func = ShopifyConnection._open
        ShopifyConnection._open = _open

    def graphql_execute(*args, **kwargs):
        while True:
            try:
                result = graphql_execute_func(*args, **kwargs)
            except urllib.error.HTTPError as e:
                if e.code == HTTPStatus.TOO_MANY_REQUESTS:
                    retry_after = float(e.headers.get('Retry-After', 2))
                    time.sleep(retry_after)
                else:
                    raise GraphQLException(json.load(e.fp))
            if isinstance(result, str):
                result = json.loads(result)
            if result.get('errors'):
                for error in result['errors']:
                    if error.get('extensions', {}).get('code') == 'THROTTLED':
                        time.sleep(0.5)
                        continue
                raise GraphQLException(result)
            return result

    if GraphQL.execute != graphql_execute:
        graphql_execute_func = GraphQL.execute
        GraphQL.execute = graphql_execute
