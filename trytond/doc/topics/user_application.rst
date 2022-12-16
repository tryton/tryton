.. _topics-user_application:

================
User Application
================

Tryton provides a way to connect URL rules to an callable endpoint using the
decorator method ``route`` of the ``trytond.application.app`` instance. This
allows you to define a custom API based on HTTP that can be used to create a
specific user application.

The decorator takes as first parameter a string which follow the `Rule
Format`_ of Werkzeug and as second parameter sequence of HTTP methods.

Example::

    from trytond.application import app

    @app.route('/hello', methods=['GET'])
    def hello(request):
        return 'Hello world'

.. _Rule Format: http://werkzeug.pocoo.org/docs/latest/routing/#rule-format

The following converter is added by Tryton:

    - ``base64``: This converter accepts any Base64_ string and transforms it
      into its corresponding bytes value.

.. _Base64: https://en.wikipedia.org/wiki/Base64

Tryton also provides some wrappers in ``trytond.protocols.wrappers`` to ease the
creation of such route.

    - ``set_max_request_size(size)``: change the default limit of the request to
      the size in bytes.

    - ``allow_null_origin``: allow requests which have their ``Origin`` set to
      ``null``.

    - ``with_pool``: which takes the first parameter as database name and
      replace it by the corresponding instance of the :ref:`Pool <ref-pool>`.

    - ``with_transaction([readonly])``: which starts a :class:`Transaction`
      using the :ref:`Pool <ref-pool>` from ``with_pool``. If ``readonly`` is
      not set, the transaction will not be readonly for ``POST``, ``PUT``,
      ``DELETE`` and ``PATCH`` methods and readonly for all others.

    - ``user_application(name[, json])``: which set the
      :attr:`Transaction.user` from the ``Authorization`` header using the
      type ``bearer`` and a valid key for the named user application.

User Application Key
====================

Tryton also provides a easy way to manage access to user application using
keys per named application.
A key is created with a ``POST`` request on the ``URL``
``/<database_name>/user/application/`` which returns the key. The request must
contain as data a json object with the keys:

    - ``user``: the user login

    - ``application``: the name of the application

After the creation, the key must be validated by the user from the preferences
of a Tryton client.

A key can be deleted with a ``DELETE`` request on the same ``URL``. The request
must contain as data a json object with the keys:

    - ``user``: the user login

    - ``key``: the key to delete

    - ``application``: the name of the application of the key
