# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import base64
from http import HTTPStatus
from unittest.mock import Mock, sentinel

from werkzeug.routing import Map, Rule

from trytond import security
from trytond.exceptions import TrytonException
from trytond.pool import Pool
from trytond.protocols.wrappers import (
    TRYTON_SESSION_COOKIE, Response, decode_session_cookie,
    encode_session_cookie)
from trytond.tests.test_tryton import Client, RouteTestCase, TestCase
from trytond.transaction import Transaction
from trytond.wsgi import Base64Converter, TrytondWSGI, app


class WSGIAppTestCase(TestCase):
    'Test WSGI Application'

    class TestException(TrytonException):
        pass

    def test_base64_converter(self):
        "Test Base64 converter"
        m = Map([
                Rule('/a/<base64:a>', endpoint='a'),
                ], converters={
                'base64': Base64Converter,
                })
        a = m.bind('example.org', '/')

        self.assertEqual(a.match('/a/dGVzdA=='), ('a', {'a': 'test'}))
        self.assertEqual(a.match('/a/dGVzdA'), ('a', {'a': 'test'}))

    def test_base64_converter_build(self):
        "Test Base64 converter build"
        m = Map([
                Rule('/a/<base64:a>', endpoint='a'),
                ], converters={
                'base64': Base64Converter,
                })
        a = m.bind('example.org', '/')

        self.assertEqual(a.build('a', {'a': 'test'}), '/a/dGVzdA')

    def test_one_error_handler_called(self):
        """Test an error handler is called
        with the app, the request and the exception."""
        app = TrytondWSGI()
        spy = Mock()

        @app.error_handler
        def _handler(*args, **kwargs):
            spy(*args, **kwargs)

        exception = self.TestException('foo')

        @app.route('/willfail')
        def _route(request):
            sentinel.request = request
            raise exception

        client = Client(app, Response)
        _ = client.get('/willfail')

        spy.assert_called_once_with(app, sentinel.request, exception)

    def test_many_error_handlers_called(self):
        "Test many error handlers are called"
        app = TrytondWSGI()
        spy1 = Mock()
        spy2 = Mock()

        @app.error_handler
        def _handler1(*args, **kwargs):
            spy1(*args, **kwargs)

        @app.error_handler
        def _handler2(*args, **kwargs):
            spy2(*args, **kwargs)

        exception = self.TestException('foo')

        @app.route('/willfail')
        def _route(request):
            sentinel.request = request
            raise exception

        client = Client(app, Response)
        _ = client.get('/willfail')

        spy1.assert_called_once_with(app, sentinel.request, exception)
        spy2.assert_called_once_with(app, sentinel.request, exception)

    def test_class_error_handler_called(self):
        "Test class error handlers can be used"
        app = TrytondWSGI()
        spy = Mock()

        class ErrorHandler():
            def __call__(self, *args, **kwargs):
                spy(*args, **kwargs)

        app.error_handler(ErrorHandler())

        exception = self.TestException('foo')

        @app.route('/willfail')
        def _route(request):
            sentinel.request = request
            raise exception

        client = Client(app, Response)
        _ = client.get('/willfail')

        spy.assert_called_once_with(app, sentinel.request, exception)

    def test_error_handlers_last_response(self):
        "Test last handler response is used"
        app = TrytondWSGI()

        @app.error_handler
        def _handler1(*args, **kwargs):
            return Response(b'bar')

        @app.error_handler
        def _handler2(*args, **kwargs):
            return Response(b'baz', status=418)

        @app.route('/willfail')
        def _route(request):
            raise self.TestException('foo')

        client = Client(app, Response)
        response = client.get('/willfail')

        self.assertEqual(next(response.response), b'baz')
        self.assertEqual(response.status, "418 I'M A TEAPOT")


class TrytonWSGITestCase(RouteTestCase):
    module = 'res'

    @classmethod
    def setUpDatabase(cls):
        pool = Pool()
        User = pool.get('res.user')
        User.create([{
                    'name': 'user',
                    'login': 'user',
                    'password': '12345678',
                    }])

    def test_basic_good_auth(self):
        "Test that auth_required works with basic auth"
        @app.route('/<database_name>/auth_required')
        @app.auth_required
        def _route(request, database_name):
            return Response(b'')

        basic_auth = 'Basic ' + base64.b64encode(b"user:12345678").decode()
        response = self.client().get(
            f'/{self.db_name}/auth_required',
            headers=[('Authorization', basic_auth)])
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_basic_bad_auth(self):
        "Test that auth_required don't accept wrong password with basic auth"
        @app.route('/<database_name>/auth_required')
        @app.auth_required
        def _route(request, database_name):
            return Response(b'')

        basic_auth = 'Basic ' + base64.b64encode(b"1:Wrong Password").decode()
        response = self.client().get(
            f'/{self.db_name}/auth_required',
            headers=[('Authorization', basic_auth)])
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_session_valid_good_auth(self):
        "Test that session_valid correctly authenticates"
        app = TrytondWSGI()

        @app.route('/<database_name>/session_required')
        @app.session_valid
        def _route(request, database_name):
            return Response(b'')

        user_id, key = security.login(
            self.db_name, 'user', {'password': '12345678'})
        client = Client(app, Response)
        session_hdr = 'Session ' + base64.b64encode(
            f'user:{user_id}:{key}'.encode('utf8')).decode('utf8')
        response = client.get(
            f'/{self.db_name}/session_required',
            headers=[('Authorization', session_hdr)])
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_session_valid_no_pool(self):
        "Test that session_valid does not use the pool"
        app = TrytondWSGI()

        @app.route('/<database_name>/session_required')
        @app.session_valid
        def _route(request):
            return Response(b'')

        user_id, key = security.login(
            self.db_name, 'user', {'password': '12345678'})
        Pool.stop(self.db_name)

        client = Client(app, Response)
        session_hdr = 'Session ' + base64.b64encode(
            f'user:{user_id}:{key}'.encode('utf8')).decode('utf8')
        client.get(
            f'/{self.db_name}/session_required',
            headers=[('Authorization', session_hdr)])
        self.assertNotIn(self.db_name, Pool._pools)

    def test_session_valid_bad_auth(self):
        "Test that session_valid refuse wrong Authentication headers"

        app = TrytondWSGI()

        @app.route('/<database_name>/session_required')
        @app.session_valid
        def _route(request):
            return Response(b'')

        client = Client(app, Response)
        response = client.get(
            f'/{self.db_name}/session_required',
            headers=[('Authorization', 'Session bad token')])
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_session_valid_no_auth(self):
        "Test that session_valid refuse unauthenticated requests"

        app = TrytondWSGI()

        @app.route('/<database_name>/session_required')
        @app.session_valid
        def _route(request):
            return Response(b'')

        client = Client(app, Response)
        response = client.get(f'/{self.db_name}/session_required')
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_cookie_authentication_good_auth(self):
        "Test that session_valid authenticates with the cookie"
        @app.route('/<database_name>/session_required')
        @app.session_valid
        def _route(request, database_name):
            return Response(b'')

        user_id, key = security.login(
            self.db_name, 'user', {'password': '12345678'})

        client = self.client()
        client.set_cookie(
            TRYTON_SESSION_COOKIE,
            encode_session_cookie('user', str(user_id), key),
            path=f'/{self.db_name}')
        response = client.get(f'/{self.db_name}/session_required')
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_cookie_authentication_bad_auth(self):
        "Test that session_valid refuses wrong cookie content"
        @app.route('/<database_name>/session_required')
        @app.session_valid
        def _route(request, database_name):
            return Response(b'')

        client = self.client()
        client.set_cookie(
            TRYTON_SESSION_COOKIE,
            encode_session_cookie('user', '1', 'Wrong Token'),
            path=f'/{self.db_name}')
        response = client.get(f'/{self.db_name}/session_required')
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_cookie_login(self):
        "Test logging in through the cookie setting route"
        client = self.client()
        client.post(f'/{self.db_name}/session/login', json={
                'method': 'common.db.login',
                'params': ['user', {'password': '12345678'}, 'en'],
                })
        session_cookie = client.get_cookie(
            TRYTON_SESSION_COOKIE, path=f'/{self.db_name}').value
        _, _, token = session_cookie.rsplit(':', 2)

        with Transaction().start(self.db_name, 0):
            pool = Pool()
            Session = pool.get('ir.session')
            sessions = Session.search([('key', '=', token)])
            self.assertEqual(len(sessions), 1)

    def test_cookie_logout(self):
        "Test logging out through the cookie unsetting route"
        client = self.client()
        client.post(f'/{self.db_name}/session/login', json={
                'method': 'common.db.login',
                'params': ['user', {'password': '12345678'}, 'en'],
                })
        session_cookie = client.get_cookie(
            TRYTON_SESSION_COOKIE, path=f'/{self.db_name}').value
        _, _, token = decode_session_cookie(session_cookie)
        client.post(f'/{self.db_name}/session/logout')

        self.assertIsNone(
            client.get_cookie(TRYTON_SESSION_COOKIE, path=f'/{self.db_name}'))
        with Transaction().start(self.db_name, 0):
            pool = Pool()
            Session = pool.get('ir.session')
            sessions = Session.search([('key', '=', token)])
            self.assertEqual(len(sessions), 0)

    def test_cookie_precedence_good_auth(self):
        "Test the cookie have precedence over Authorization header"
        @app.route('/<database_name>/session_required')
        @app.session_valid
        def _route(request, database_name):
            return Response(b'')

        user_id, key = security.login(
            self.db_name, 'user', {'password': '12345678'})
        client = self.client()
        client.set_cookie(
            TRYTON_SESSION_COOKIE,
            encode_session_cookie('user', str(user_id), key),
            path=f'/{self.db_name}')
        session_hdr = 'Session ' + base64.b64encode(
            f'user:{user_id}:Wrong Key'.encode('utf8')).decode('utf8')
        response = client.get(
            f'/{self.db_name}/session_required',
            headers=[('Authorization', session_hdr)])
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_cookie_precedence_bad_auth(self):
        "Test the cookie have precedence over Authorization header"
        @app.route('/<database_name>/session_required')
        @app.session_valid
        def _route(request, database_name):
            return Response(b'')

        user_id, key = security.login(
            self.db_name, 'user', {'password': '12345678'})
        client = self.client()
        client.set_cookie(
            TRYTON_SESSION_COOKIE,
            encode_session_cookie('user', str(user_id), 'Wrong Key'),
            path=f'/{self.db_name}')
        session_hdr = 'Session ' + base64.b64encode(
            f'user:{user_id}:{key}'.encode('utf8')).decode('utf8')
        response = client.get(
            f'/{self.db_name}/session_required',
            headers=[('Authorization', session_hdr)])
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
