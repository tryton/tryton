# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest
from unittest.mock import Mock, sentinel

from werkzeug.wrappers import Response
from werkzeug.test import Client
from trytond.wsgi import TrytondWSGI
from trytond.exceptions import TrytonException


class WSGIAppTestCase(unittest.TestCase):
    'Test WSGI Application'

    class TestException(TrytonException):
        pass

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

        client = Client(app)
        (response, status, headers) = client.get('/willfail')

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

        client = Client(app)
        (response, status, headers) = client.get('/willfail')

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

        client = Client(app)
        (response, status, headers) = client.get('/willfail')

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

        client = Client(app)
        (response, status, headers) = client.get('/willfail')

        self.assertEqual(next(response), b'baz')
        self.assertEqual(status, "418 I'M A TEAPOT")


def suite():
    suite_ = unittest.TestSuite()
    suite_.addTests(
        unittest.TestLoader().loadTestsFromTestCase(WSGIAppTestCase))
    return suite_
