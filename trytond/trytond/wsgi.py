# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import base64
import http.client
import logging
import os
import posixpath
import sys
import time
import traceback
import urllib.parse
from functools import wraps

from werkzeug.routing import BaseConverter, Map, Rule

try:
    from werkzeug.middleware.proxy_fix import ProxyFix

    def NumProxyFix(app, num_proxies):
        return ProxyFix(app,
            x_for=num_proxies, x_proto=num_proxies, x_host=num_proxies,
            x_port=num_proxies, x_prefix=num_proxies)
except ImportError:
    from werkzeug.contrib.fixers import ProxyFix as NumProxyFix
try:
    from werkzeug.middleware.shared_data import SharedDataMiddleware
except ImportError:
    from werkzeug.wsgi import SharedDataMiddleware

from trytond import backend, config, security
from trytond.protocols.jsonrpc import JSONProtocol
from trytond.protocols.wrappers import (
    HTTPStatus, Request, Response, abort, exceptions)
from trytond.protocols.xmlrpc import XMLProtocol
from trytond.status import processing
from trytond.tools import resolve, safe_join

__all__ = ['TrytondWSGI', 'app']

logger = logging.getLogger(__name__)


def _do_basic_auth(request):
    headers = {}
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        headers['WWW-Authenticate'] = 'Basic realm="Tryton"'
    response = Response(None, http.client.UNAUTHORIZED, headers)
    abort(http.client.UNAUTHORIZED, response=response)


class Base64Converter(BaseConverter):

    def to_python(self, value):
        if missing_padding := len(value) % 4:
            value += '=' * (4 - missing_padding)
        return base64.urlsafe_b64decode(value).decode('utf-8')

    def to_url(self, value):
        return (
            base64.urlsafe_b64encode(value.encode('utf-8'))
            .decode('ascii')
            .rstrip('='))


class TrytondWSGI(object):

    def __init__(self):
        self.url_map = Map([], converters={
                'base64': Base64Converter,
                })
        self.protocols = [JSONProtocol, XMLProtocol]
        self.error_handlers = []

    def route(self, string, methods=None, defaults=None):
        def decorator(func):
            self.url_map.add(Rule(
                    string, endpoint=func, methods=methods, defaults=defaults))
            return func
        return decorator

    def error_handler(self, handler):
        self.error_handlers.append(handler)
        return handler

    def auth_required(self, func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if request.user_id:
                return func(request, *args, **kwargs)
            else:
                _do_basic_auth(request)
        return wrapper

    def session_valid(self, func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if (not request.authorization
                    or request.authorization.type != 'session'):
                _do_basic_auth(request)
            userid = request.authorization.get('userid')
            session = request.authorization.get('session')
            dbname = request.view_args.get('database_name')

            if not security.check_session(
                    dbname, userid, session, request.remote_addr):
                _do_basic_auth(request)

            return func(request, *args, **kwargs)

        return wrapper

    def dispatch_request(self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, request.view_args = adapter.match()
            if hasattr(endpoint, 'max_request_size'):
                max_size = endpoint.max_request_size
            elif request.user_id:
                max_size = config.getint('request', 'max_size_authenticated')
            else:
                max_size = config.getint('request', 'max_size')
            request.max_content_length = max_size
            return endpoint(request, **request.view_args)
        except exceptions.HTTPException as e:
            logger.debug(
                "Exception when processing %s", request, exc_info=True)
            return e
        except backend.DatabaseOperationalError as e:
            logger.debug(
                "Exception when processing %s", request, exc_info=True)
            return exceptions.ServiceUnavailable(description=str(e))
        except Exception as e:
            logger.debug(
                "Exception when processing %s", request, exc_info=True)
            tb_s = ''.join(traceback.format_exception(*sys.exc_info()))
            for path in sys.path:
                tb_s = tb_s.replace(path, '')
            e.__format_traceback__ = tb_s
            response = e
            for error_handler in self.error_handlers:
                rv = error_handler(self, request, e)
                if isinstance(rv, Response):
                    response = rv
            return response

    def make_response(self, request, data):
        for cls in self.protocols:
            for mimetype, _ in request.accept_mimetypes:
                if cls.content_type in mimetype:
                    response = cls.response(data, request)
                    break
            else:
                continue
            break
        else:
            for cls in self.protocols:
                if cls.content_type in request.environ.get('CONTENT_TYPE', ''):
                    response = cls.response(data, request)
                    break
            else:
                if isinstance(data, Exception):
                    try:
                        response = exceptions.InternalServerError(
                            original_exception=data)
                    except TypeError:
                        response = exceptions.InternalServerError(data)
                else:
                    response = Response(data)
        return response

    def wsgi_app(self, environ, start_response):
        def duration():
            return (time.monotonic() - started) * 1000
        started, request = time.monotonic(), None
        try:

            for cls in self.protocols:
                if cls.content_type in environ.get('CONTENT_TYPE', ''):
                    request = cls.request(environ)
                    break
            else:
                request = Request(environ)

            origin = request.headers.get('Origin')
            origin_host = (
                urllib.parse.urlparse(origin).netloc if origin else '')
            host = request.headers.get('Host')
            if origin and origin != 'null' and origin_host != host:
                cors = filter(
                    None, config.get('web', 'cors', default='').splitlines())
                if origin not in cors:
                    if (origin.startswith('moz-extension://')
                            or origin.startswith('chrome-extension://')):
                        origin = 'null'
                    else:
                        abort(HTTPStatus.FORBIDDEN)
            if origin == 'null':
                adapter = self.url_map.bind_to_environ(request.environ)
                endpoint = adapter.match()[0]
                if not getattr(endpoint, 'allow_null_origin', False):
                    abort(HTTPStatus.FORBIDDEN)

            with processing(request):
                data = self.dispatch_request(request)
                if not isinstance(data, (Response, exceptions.HTTPException)):
                    response = self.make_response(request, data)
                else:
                    response = data

            if origin and isinstance(response, Response):
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Vary'] = 'Origin'
                method = request.headers.get('Access-Control-Request-Method')
                if method:
                    response.headers['Access-Control-Allow-Methods'] = method
                headers = request.headers.get('Access-Control-Request-Headers')
                if headers:
                    response.headers['Access-Control-Allow-Headers'] = headers
                response.headers['Access-Control-Max-Age'] = config.getint(
                    'web', 'cache_timeout')
            return response(environ, start_response)
        finally:
            logger.info('%s in %i ms', request, duration())

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)


class SharedDataMiddlewareIndex(SharedDataMiddleware):
    def __call__(self, environ, start_response):
        if environ['REQUEST_METHOD'] not in {'GET', 'HEAD'}:
            return self.app(environ, start_response)
        return super().__call__(
            environ, start_response)

    def get_directory_loader(self, directory):
        def loader(path):
            if path is not None:
                path = safe_join(directory, path)
            else:
                path = directory
            if path is not None:
                if os.path.isdir(path):
                    path = posixpath.join(path, 'index.html')
                if os.path.isfile(path):
                    return os.path.basename(path), self._opener(path)
            return None, None
        return loader


app = TrytondWSGI()
if config.get('web', 'root'):
    static_files = {
        '/': config.get('web', 'root'),
        }
    app.wsgi_app = SharedDataMiddlewareIndex(
        app.wsgi_app, static_files,
        cache_timeout=config.getint('web', 'cache_timeout'))
num_proxies = config.getint('web', 'num_proxies')
if num_proxies:
    app.wsgi_app = NumProxyFix(app.wsgi_app, num_proxies)

if config.has_section('wsgi middleware'):
    for middleware in config.options('wsgi middleware'):
        Middleware = resolve(config.get('wsgi middleware', middleware))
        args, kwargs = (), {}
        section = 'wsgi %s' % middleware
        if config.has_section(section):
            if config.has_option(section, 'args'):
                args = eval(config.get(section, 'args'))
            if config.has_option(section, 'kwargs'):
                kwargs = eval(config.get(section, 'kwargs'))
        app.wsgi_app = Middleware(app.wsgi_app, *args, **kwargs)

import trytond.bus  # noqa: E402,F401
import trytond.protocols.dispatcher  # noqa: E402,F401
