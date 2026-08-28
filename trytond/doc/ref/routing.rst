.. _ref-routing:
.. module:: trytond.routing

=======
Routing
=======

.. contents::
   :local:
   :backlinks: entry
   :depth: 2

Router
======

.. class:: Router()

This is the base class that every :ref:`router <topics-url_routing>` inherits.

Class attributes are:

.. attribute:: Router.__name__

   The unique name to reference the router throughout the platform.

.. attribute:: Router.__routes__

   A mapping between the name of the callable endpoint and a
   :class:`~trytond.routing.Route` object.

.. attribute:: Router.rules

   A mapping between the name of callable endpoint and the list of rules.

Class methods:

.. classmethod:: Router.url_for(endpoint[, _method[, _request[, \*\*values]]])

   Generate a URL to the given ``endpoint`` with the given ``values``.

   ``endpoint`` is the name of the callable endpoint.

   ``values`` is used for the variable parts of the URL rule. Unknown keys are
   appended as query string arguments.

   ``_method`` if given, generate the URL associated with this method for the
   endpoint.

   ``_request`` if given, the request context to use to generate the base of
   the URL.

Route
=====

.. class:: Route(\*rules[, decorators])

This class is used to define a set of :class:`Rule` that maps variable
placeholders to their value in the URL.

Route allows also to set decorators that are applied to the endpoint method
following the declaration order.

Class attributes are:

.. attribute:: Route.rules

   A :py:class:`list` of :class:`Rule`.

.. attribute:: Route.decorators

   A :py:class:`list` of callables.

Instance method:

.. method:: Route.start(database, router, name)

   This method registers the URL rules for the database.

   ``database`` is the database name.

   ``router`` is the :class:`Router` on which the route is defined.

   ``name`` is the name of the endpoint which is a class method on the
   :class:`Router`.

Rule
====

.. class:: Rule(path[, methods[, defaults[, redirect_to]]])

This class is a named tuple defining the path, methods, default values and
redirect URL of a rule. Those parameters have the same meaning as those of a
`Werkzeug Rule`_ with the exception of ``redirect_to`` which must be a string.

There are two kinds of rule:

* *relative rule* is a rule for which the path does not start with a ``/``.
  The path will be prefixed by ``/<database>/r/<router>/`` where ``database``
  and ``router`` are expended to the database name and the router's
  :attr:`Router.__name__` respectively to create the database rule.

* *absolute rule* is a rule for which the path starts with a ``/``.
  The path is used as-is to create the Werkzeug rule in this case.

.. _`Werkzeug Rule`: https://werkzeug.palletsprojects.com/en/stable/routing/#werkzeug.routing.Rule
