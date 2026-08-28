# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from trytond.routing import Route, Router, Rule


class TestRouter(Router):
    __name__ = 'test'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__routes__.update({
                'hello': Route(
                    Rule('hello', methods={'GET'}),
                    Rule('hello/<name>', methods={'GET'}),
                    ),
                'redirection': Route(
                    Rule('redirection/<name>', methods={'GET'}),
                    Rule('/test/redirection/redirect/<name>', methods={'GET'},
                        redirect_to='redirection/<name>'),
                    ),
                'url_rel': Route(
                    Rule('url/<model>/<id>/<field>', methods={'GET'}),
                    Rule('url/<model>/<id>', methods={'GET'}),
                    ),
                'url_abs': Route(
                    Rule('/test/url/<model>/<id>/<field>', methods={'GET'}),
                    Rule('/test/url/<model>/<id>', methods={'GET'}),
                    ),
                })

    @classmethod
    def hello(cls, request, database_name, name='World'):
        return f'Hello, {name}!'

    @classmethod
    def redirection(cls, request, database_name, name):
        return f'{name} succeeded!'

    @classmethod
    def url_rel(cls, request, database_name, model, id):
        pass

    @classmethod
    def url_abs(cls, request, database_name, model, id):
        pass


def register(module):
    Pool.register(
        TestRouter,
        module=module, type_='router')
