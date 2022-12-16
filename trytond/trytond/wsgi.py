# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import base64
import http.client
import logging
import os
import sys
import traceback
import urllib.parse
try:
    from http import HTTPStatus
except ImportError:
    from http import client as HTTPStatus

from werkzeug.wrappers import Response
from werkzeug.routing import Map, Rule, BaseConverter
from werkzeug.exceptions import abort, HTTPException, InternalServerError
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

import wrapt

from trytond.config import config
from trytond.protocols.wrappers import Request
from trytond.protocols.jsonrpc import JSONProtocol
from trytond.protocols.xmlrpc import XMLProtocol

__all__ = ['TrytondWSGI', 'app']

logger = logging.getLogger(__name__)


class Base64Converter(BaseConverter):

    def to_python(self, value):
        return base64.urlsafe_b64decode(value).decode('utf-8')

    def to_url(self, value):
        return base64.urlsafe_b64encode(value.encode('utf-8'))


class TrytondWSGI(object):

    def __init__(self):
        self.url_map = Map([], converters={
                'base64': Base64Converter,
                })
        self.protocols = [JSONProtocol, XMLProtocol]
        self.error_handlers = []

    def route(self, string, methods=None):
        def decorator(func):
            self.url_map.add(Rule(string, endpoint=func, methods=methods))
            return func
        return decorator

    def error_handler(self, handler):
        self.error_handlers.append(handler)
        return handler

    @wrapt.decorator
    def auth_required(self, wrapped, instance, args, kwargs):
        request = args[0]
        if request.user_id:
            return wrapped(*args, **kwargs)
        else:
            headers = {}
            if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
                headers['WWW-Authenticate'] = 'Basic realm="Tryton"'
            response = Response(None, http.client.UNAUTHORIZED, headers)
            abort(http.client.UNAUTHORIZED, response=response)

    def check_request_size(self, request, size=None):
        if request.method not in {'POST', 'PUT', 'PATCH'}:
            return
        if size is None:
            if request.user_id:
                max_size = config.getint(
                    'request', 'max_size_authenticated')
            else:
                max_size = config.getint(
                    'request', 'max_size')
        else:
            max_size = size
        if max_size:
            content_length = request.content_length
            if content_length is None:
                abort(http.client.LENGTH_REQUIRED)
            elif content_length > max_size:
                abort(http.client.REQUEST_ENTITY_TOO_LARGE)

    def dispatch_request(self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, request.view_args = adapter.match()
            max_request_size = getattr(endpoint, 'max_request_size', None)
            self.check_request_size(request, max_request_size)
            return endpoint(request, **request.view_args)
        except HTTPException as e:
            return e
        except Exception as e:
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
                    response = InternalServerError(data)
                else:
                    response = Response(data)
        return response

    def wsgi_app(self, environ, start_response):
        for cls in self.protocols:
            if cls.content_type in environ.get('CONTENT_TYPE', ''):
                request = cls.request(environ)
                break
        else:
            request = Request(environ)

        origin = request.headers.get('Origin')
        origin_host = urllib.parse.urlparse(origin).netloc if origin else ''
        host = request.headers.get('Host')
        if origin and origin_host != host:
            cors = filter(
                None, config.get('web', 'cors', default='').splitlines())
            if origin not in cors:
                abort(HTTPStatus.FORBIDDEN)

        data = self.dispatch_request(request)
        if not isinstance(data, (Response, HTTPException)):
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

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)


class SharedDataMiddlewareIndex(SharedDataMiddleware):
    def __call__(self, environ, start_response):
        if environ['REQUEST_METHOD'] not in {'GET', 'HEAD'}:
            return self.app(environ, start_response)
        return super(SharedDataMiddlewareIndex, self).__call__(
            environ, start_response)

    def get_directory_loader(self, directory):
        def loader(path):
            if path is not None:
                path = os.path.join(directory, path)
            else:
                path = directory
            if os.path.isdir(path):
                path = os.path.join(path, 'index.html')
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
import trytond.protocols.dispatcher
import trytond.bus
