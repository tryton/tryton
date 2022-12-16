.. _topics-rpc:

=====================
Remote Procedure Call
=====================

There are two protocols supported by trytond: `JSON-RPC`_ (Version 1.0) and
`XML-RPC`_.
The URL of the calls must end with the database name with a trailing '/'.

The available methods are:

common.db.login
---------------

It takes as parameters: the user name and a dictionary of login parameters.
It returns in case of success the user ID and the session.
If the parameters are not valid to authenticate the user, it returns nothing.
Otherwise if it misses a key in the parameters, it raises a ``LoginException``
exception with the missing key name, type and the message to ask to the
user.

common.db.logout
----------------

It takes no parameters and it invalidate the current session.

.. TODO - other methods

.. _`JSON-RPC`: https://en.wikipedia.org/wiki/JSON-RPC
.. _`XML-RPC`: https://en.wikipedia.org/wiki/XML-RPC

Authorization
=============

Most of the calls require authorization, there are two methods:

Basic
-----

It follows the `Basic access authentication`_.

.. _`Basic access authentication`: https://en.wikipedia.org/wiki/Basic_access_authentication

Session
-------

The authorization field is constructed by the username, the user ID and the
session combined with a single colon and encoded in Base64.
The session is retrieved by calling the method ``common.db.login``.
