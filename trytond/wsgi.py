# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import httplib
import logging
import sys
import traceback

from werkzeug.wrappers import Response
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import abort, HTTPException, InternalServerError
from werkzeug.contrib.fixers import ProxyFix

import wrapt

from trytond.config import config
from trytond.protocols.wrappers import Request
from trytond.protocols.jsonrpc import JSONProtocol
from trytond.protocols.xmlrpc import XMLProtocol

__all__ = ['TrytondWSGI', 'app']

logger = logging.getLogger(__name__)


class TrytondWSGI(object):

    def __init__(self):
        self.url_map = Map([])
        self.protocols = [JSONProtocol, XMLProtocol]
        self.error_handlers = []

    def route(self, string, methods=None):
        def decorator(func):
            self.url_map.add(Rule(string, endpoint=func, methods=methods))
            return func
        return decorator

    @wrapt.decorator
    def auth_required(self, wrapped, instance, args, kwargs):
        request = args[0]
        if request.user_id:
            return wrapped(*args, **kwargs)
        else:
            abort(httplib.UNAUTHORIZED)

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
                abort(httplib.LENGTH_REQUIRED)
            elif content_length > max_size:
                abort(httplib.REQUEST_ENTITY_TOO_LARGE)

    def dispatch_request(self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, request.view_args = adapter.match()
            max_request_size = getattr(endpoint, 'max_request_size', None)
            self.check_request_size(request, max_request_size)
            return endpoint(request, **request.view_args)
        except HTTPException, e:
            return e
        except Exception, e:
            tb_s = ''.join(traceback.format_exception(*sys.exc_info()))
            for path in sys.path:
                tb_s = tb_s.replace(path, '')
            e.__format_traceback__ = tb_s
            response = e
            for error_handler in self.error_handlers:
                rv = error_handler(e)
                if isinstance(rv, Response):
                    response = rv
            return response

    def wsgi_app(self, environ, start_response):
        for cls in self.protocols:
            if cls.content_type in environ.get('CONTENT_TYPE', ''):
                request = cls.request(environ)
                break
        else:
            request = Request(environ)
        data = self.dispatch_request(request)
        if not isinstance(data, (Response, HTTPException)):
            for cls in self.protocols:
                for mimetype in request.accept_mimetypes:
                    if cls.content_type in mimetype:
                        response = cls.response(data, request)
                        break
                else:
                    continue
                break
            else:
                for cls in self.protocols:
                    if cls.content_type in environ.get('CONTENT_TYPE', ''):
                        response = cls.response(data, request)
                        break
                else:
                    if isinstance(data, Exception):
                        response = InternalServerError(data)
                    else:
                        response = Response(data)
        else:
            response = data
        # TODO custom process response
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)

app = TrytondWSGI()
num_proxies = config.getint('web', 'num_proxies')
if num_proxies:
    app.wsgi_app = ProxyFix(app.wsgi_app, num_proxies=num_proxies)
import trytond.protocols.dispatcher
