.. _topics-url_routing:

===========
URL Routing
===========

Tryton provides two ways to connect URL rules to a callable endpoint.

A decorator for small functions that won't be modified by further modules.

A :class:`~trytond.routing.Router` living in the :class:`~trytond.pool.Pool`
when the endpoint might be extended by another module.

The ``route`` decorator
-----------------------

The simplest way to define a route is by using the decorator method ``route``
of the ``trytond.wsgi.app`` instance. This allows you to define a custom API
based on HTTP that can be used to create specific user applications.

The decorator takes as first parameter a string which follow the `Rule
Format`_ of Werkzeug and as second parameter sequence of HTTP methods.

Example::

    from trytond.wsgi import app

    @app.route('/hello', methods=['GET'])
    def hello(request):
        return 'Hello world'

.. _Rule Format: http://werkzeug.pocoo.org/docs/latest/routing/#rule-format


``Router`` classes
------------------

A more versatile way to expose entrypoints is by using a
:class:`~trytond.routing.Router`.
A Router is a class registered in the :class:`~trytond.pool.Pool` that contains
a mapping between some :class:`~trytond.routing.Route` and a method of the
Router.
A Route must contain at least one :class:`~trytond.routing.Rule` which also
follows the `Rule Format`_ of Werkzeug in order to map the ``path`` part of the
URL to the endpoint parameters.
A Route can also define a list of decorators that are applied to the
corresponding endpoint.

Example::

    from trytond.routing import Route, Router, Rule

    class Example(Router):
        __name__ = 'example'

        @classmethod
        def __setup__(cls):
            super().__setup__()
            cls.__routes__.update({
                    'hello': Route(
                        Rule('hello', methods={'GET'}),
                        Rule('hello/<name>', methods={'GET'}),
                        decorators=[
                            with_pool,
                            with_transaction(),
                            ],
                        ),
                    })

        @classmethod
        def hello(cls, request, pool, name='World'):
            return f'Hello, {name}!'

.. note::
   As the router are registered in the Pool, they can be extended.

Routing helpers
---------------

The following converter is available:

``base64``
   This converter accepts any Base64_ string and transforms it into its
   corresponding bytes value.

.. _Base64: https://en.wikipedia.org/wiki/Base64

Some decorators are provided in ``trytond.protocols.wrappers`` to ease the
creation of routes:

``set_max_request_size(size)``
   Changes the default limit size of the request.

``allow_null_origin``
   Allows requests that have their ``Origin`` set to ``null``.

``with_pool``
   Takes the first parameter as database name and replaces it by the
   corresponding instance of the :class:`~trytond.pool.Pool`.

``with_transaction([readonly[, user[, context[, timeout]]]])``
   Starts a :class:`~trytond.transaction.Transaction` using the
   :class:`~trytond.pool.Pool` from ``with_pool``.
   If ``readonly`` is not set, the transaction will not be readonly for
   ``POST``, ``PUT``, ``DELETE`` and ``PATCH`` methods and readonly for all
   others.

.. _topics-user_application_decorator:

``user_application(name[, json])``
   Set the :attr:`~trytond.transaction.Transaction.user` from the
   ``Authorization`` header using the ``bearer`` type with the user application
   key, or the ``basic`` type without a username and with the user application
   key as the password.
