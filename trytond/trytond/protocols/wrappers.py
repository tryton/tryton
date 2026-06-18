# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import base64
import collections
import gzip
import logging
import time
import zlib
from functools import wraps

try:
    from http import HTTPStatus
except ImportError:
    from http import client as HTTPStatus

from werkzeug import exceptions
from werkzeug.datastructures import Authorization
from werkzeug.exceptions import abort
from werkzeug.utils import redirect, send_file
from werkzeug.wrappers import Request as BaseRequest
from werkzeug.wrappers import Response as BaseResponse

from trytond import backend, config, security
from trytond.exceptions import RateLimitException, UserError, UserWarning
from trytond.pool import Pool
from trytond.tools import cached_property
from trytond.transaction import Transaction, TransactionError, check_access

__all__ = [
    'HTTPStatus',
    'Request',
    'Response',
    'abort',
    'allow_null_origin',
    'exceptions',
    'redirect',
    'send_file',
    'set_max_request_size',
    'user_application',
    'with_pool',
    'with_transaction',
    'encode_session_cookie',
    'decode_session_cookie',
    'add_auth_cookies',
    'remove_auth_cookies',
    'add_cookie',
    'remove_cookie',
    'TRYTON_SESSION_COOKIE',
    ]

TRYTON_SESSION_COOKIE = 'tryton_session'
logger = logging.getLogger(__name__)


def encode_session_cookie(login, userid, token):
    return ':'.join((login, userid, token))


def decode_session_cookie(cookie):
    return cookie.rsplit(':', 2)


def add_cookie(response, database, name, value):
    response.set_cookie(name, value,
        max_age=config.getint('session', 'max_age'),
        path=f'/{database}',
        domain=config.get('session', 'cookie_domain'),
        secure=True, httponly=True, samesite='Strict')


def add_auth_cookies(response, database, username, userid, token):
    session_cookie = encode_session_cookie(username, userid, token)
    add_cookie(response, database, TRYTON_SESSION_COOKIE, session_cookie)


def remove_cookie(response, database, name):
    response.set_cookie(
        name, '', expires=0, path=f'/{database}',
        domain=config.get('session', 'cookie_domain'),
        secure=True, httponly=True, samesite='Strict')


def remove_auth_cookies(response, database):
    remove_cookie(response, database, TRYTON_SESSION_COOKIE)


class Request(BaseRequest):

    view_args = None

    def __repr__(self):
        args = []
        try:
            if self.url is None or isinstance(self.url, str):
                url = self.url
            else:
                url = self.url.decode(getattr(self, 'url_charset', 'utf-8'))
            auth = self.authorization
            if auth:
                args.append("%s@%s" % (
                        auth.get('userid', auth.username), self.remote_addr))
            else:
                args.append(self.remote_addr)
            args.append("'%s'" % url)
            args.append("[%s]" % self.method)
            if self.view_args:
                args.append("%s" % (self.rpc_method or ''))
        except Exception:
            args.append("(invalid WSGI environ)")
        return "<%s %s>" % (
            self.__class__.__name__, " ".join(filter(None, args)))

    @property
    def decoded_data(self):
        if self.content_encoding == 'gzip':
            if self.user_id:
                return gzip.decompress(self.data)
            else:
                abort(HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        else:
            return self.data

    @property
    def parsed_data(self):
        return self.data

    @property
    def rpc_method(self):
        return

    @property
    def rpc_params(self):
        return

    @cached_property
    def session(self):
        cookie = self.cookies.get(TRYTON_SESSION_COOKIE)
        if cookie:
            try:
                username, userid, token = decode_session_cookie(cookie)
                session = Session('cookie', username, int(userid), token)
            except ValueError:
                session = None
        elif self.authorization and self.authorization.type == 'session':
            session = Session(
                'authorization',
                self.authorization.username,
                int(self.authorization.get('userid')),
                self.authorization.get('session'))
        else:
            session = None
        return session

    @cached_property
    def authorization(self):
        authorization = super().authorization
        if authorization is None:
            header = self.headers.get('Authorization')
            return parse_authorization_header(header)
        elif authorization.type == 'session':
            # Werkzeug may parse the session as parameters
            # if the base64 uses the padding sign '='
            if authorization.token is None:
                header = self.headers.get('Authorization')
                return parse_authorization_header(header)
            else:
                return parse_session(authorization.token)
        return authorization

    @cached_property
    def user_id(self):
        assert self.view_args is not None
        database_name = self.view_args.get('database_name')
        if not database_name:
            return None
        auth = self.authorization
        if not self.session and not auth:
            return None
        context = {'_request': self.context}
        if self.session:
            user_id = security.check(
                database_name, self.session.userid, self.session.token,
                context=context)
        elif auth.username:
            parameters = getattr(auth, 'parameters', auth)
            try:
                user_id = security.login(
                    database_name, auth.username, parameters, cache=False,
                    context=context)
            except RateLimitException:
                abort(HTTPStatus.TOO_MANY_REQUESTS)
        else:
            user_id = None
        return user_id

    @cached_property
    def context(self):
        return {
            'remote_addr': self.remote_addr,
            'http_host': self.environ.get('HTTP_HOST'),
            'scheme': self.scheme,
            'is_secure': self.is_secure,
            'root_path': self.root_path,
            }


class Response(BaseResponse):

    def get_json(self, force=False, silent=False):
        from .jsonrpc import JSONDecoder, json

        if not (force or self.is_json):
            return None

        data = self.get_data()

        try:
            return json.loads(data, object_hook=JSONDecoder())
        except ValueError:
            if not silent:
                raise

            return None


class JSONBadRequest(exceptions.BadRequest):
    def __init__(self, e):
        super().__init__()
        self.message = e.message
        self.description = e.description

    def get_body(self, environment, scope):
        from .jsonrpc import JSONEncoder, json

        return json.dumps({
                'status': self.code,
                'message': self.message,
                'description': self.description,
                }, cls=JSONEncoder)

    def get_headers(self, environment, scope):
        return [('Content-Type', 'application/json')]


Session = collections.namedtuple('Session', 'type username userid token')


def parse_authorization_header(value):
    if not value:
        return
    if isinstance(value, bytes):
        value = value.decode('latin1')
    try:
        auth_type, auth_info = value.split(None, 1)
        auth_type = auth_type.lower()
    except ValueError:
        return
    if auth_type == 'session':
        return parse_session(auth_info)
    else:
        authorization = Authorization(auth_type)
        authorization.token = auth_info
        return authorization


def parse_session(token):
    try:
        username, userid, session = (
            base64.b64decode(token).decode().split(':', 3))
        userid = int(userid)
    except Exception:
        return
    return Authorization('session', {
            'username': username,
            'userid': userid,
            'session': session,
            })


def set_max_request_size(size):
    def decorator(func):
        func.max_request_size = size
        return func
    return decorator


def allow_null_origin(func):
    func.allow_null_origin = True
    return func


def with_pool(func):
    @wraps(func)
    def wrapper(request, database_name, *args, **kwargs):
        database_list = Pool.database_list()
        if database_name not in database_list:
            with Transaction().start(None, 0, readonly=True) as transaction:
                hostname = config.get_hostname(request.host)
                db_list = transaction.database.list(hostname=hostname)
                if database_name not in db_list:
                    abort(HTTPStatus.NOT_FOUND)
        pool = Pool(database_name)
        if database_name not in database_list:
            with Transaction().start(database_name, 0, readonly=True):
                pool.init()

        return func(request, pool, *args, **kwargs)
    return wrapper


def with_transaction(readonly=None, user=0, context=None, timeout=None):
    from trytond.worker import run_task

    def decorator(func):
        @wraps(func)
        def wrapper(request, pool, *args, **kwargs):
            readonly_ = readonly  # can not modify non local
            if readonly_ is None:
                if request.method in {'POST', 'PUT', 'DELETE', 'PATCH'}:
                    readonly_ = False
                else:
                    readonly_ = True
            if context is None:
                context_ = {}
            else:
                context_ = context.copy()
            context_['_request'] = request.context
            if user == 'request':
                user_ = request.user_id
            else:
                user_ = user
            retry = config.getint('database', 'retry')
            count = 0
            transaction_extras = {}
            while True:
                if count:
                    time.sleep(0.02 * count)
                with Transaction().start(
                        pool.database_name, user_, readonly=readonly_,
                        context=context_, timeout=timeout,
                        **transaction_extras) as transaction:
                    try:
                        result = func(request, pool, *args, **kwargs)
                    except TransactionError as e:
                        transaction.rollback()
                        transaction.tasks.clear()
                        e.fix(transaction_extras)
                        continue
                    except backend.DatabaseOperationalError:
                        if count < retry and not readonly_:
                            transaction.rollback()
                            transaction.tasks.clear()
                            count += 1
                            logger.debug("Retry: %i", count)
                            continue
                        raise
                    # Need to commit to unlock SQLite database
                    transaction.commit()
                while transaction.tasks:
                    task_id = transaction.tasks.pop()
                    run_task(pool, task_id)
                return result
        return wrapper
    return decorator


def user_application(name, json=True):
    from .jsonrpc import JSONEncoder
    from .jsonrpc import json as json_

    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            pool = Pool()
            UserApplication = pool.get('res.user.application')

            authorization = request.authorization
            if authorization is None:
                header = request.headers.get('Authorization')
                authorization = parse_authorization_header(header)
            if authorization is None:
                abort(HTTPStatus.UNAUTHORIZED)

            if authorization.type == 'bearer':
                token = getattr(authorization, 'token', '')
            elif authorization.type == 'basic':
                token = authorization.get('password')
            else:
                abort(HTTPStatus.UNAUTHORIZED)

            application = UserApplication.check(token, name)
            if not application:
                abort(HTTPStatus.UNAUTHORIZED)
            transaction = Transaction()
            # TODO language
            with transaction.set_user(application.user.id), \
                    check_access():
                try:
                    response = func(request, *args, **kwargs)
                except (UserError, UserWarning) as e:
                    raise JSONBadRequest(e)
            if not isinstance(response, BaseResponse) and json:
                response = Response(json_.dumps(response, cls=JSONEncoder),
                    content_type='application/json')
            return response
        return wrapper
    return decorator


class GzipStream:
    def __init__(self, data, compresslevel=6):
        if isinstance(data, str):
            data = [data]
        self.iterator = data
        self.compressor = zlib.compressobj(level=compresslevel, wbits=31)

    def __iter__(self):
        for chunk in self.iterator:
            data = chunk.encode('utf-8')
            compressed = self.compressor.compress(data)
            if compressed:
                yield compressed
        tail = self.compressor.flush()
        if tail:
            yield tail
