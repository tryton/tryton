# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import urllib.parse
from collections import defaultdict, namedtuple

from werkzeug.routing import Rule as WkzgRule

from trytond.pool import PoolBase
from trytond.url import http_base
from trytond.wsgi import app


class BuildURLError(Exception):
    pass


Rule = namedtuple(
    'Rule',
    ('path', 'methods', 'defaults', 'redirect_to'),
    defaults=(None, None, None))


class Router(PoolBase):
    __slots__ = ('__routes__', 'rules')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__routes__ = {}
        cls.rules = defaultdict(list)

    @classmethod
    def url_for(cls, endpoint, *, _method='GET', _request=None, **values):
        for r in cls.rules[endpoint]:
            if r.redirect_to:
                continue
            if r.suitable_for(values, _method):
                build_rv = r.build(values)
                if build_rv is not None:
                    _, path = build_rv
                    break
        else:
            path = None
        if path is None:
            raise BuildURLError(
                f"Can not build URL for {endpoint!r} with {values=}")
        return urllib.parse.urljoin(http_base(request=_request), path)


class Route:
    __slots__ = ('rules', 'decorators')

    def __init__(self, *rules, decorators=None):
        if not rules:
            raise ValueError("missing rules")
        self.rules = list(rules)
        self.decorators = list(decorators) if decorators else []

    def start(self, database, router, name):
        endpoint = getattr(router, name)
        for func in reversed(self.decorators):
            endpoint = func(endpoint)

        router_prefix = f'/{database}/r/{router.__name__}'
        for rule in self.rules:
            defaults = (rule.defaults.copy()
                if rule.defaults is not None else {})
            if rule.path.startswith('/'):
                path = rule.path
            else:
                if rule.path:
                    path = f'{router_prefix}/{rule.path}'
                else:
                    path = router_prefix
                defaults['database_name'] = database

            if rule.redirect_to and not rule.redirect_to.startswith('/'):
                redirect_to = f'{router_prefix}/{rule.redirect_to}'
            else:
                redirect_to = rule.redirect_to
            if redirect_to:
                endpoint = None
            rule = WkzgRule(
                path, endpoint=endpoint, methods=rule.methods,
                defaults=defaults, redirect_to=redirect_to)
            router.rules[name].append(rule)
            app.url_map.add(rule)
