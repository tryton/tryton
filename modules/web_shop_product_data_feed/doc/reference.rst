*************
API Reference
*************

.. _Fetch Product Data Feed:

Fetch Product Data Feed
=======================

The *Web Shop Product Data Feed Module* define a route to fetch the product
data feed of a *Web Shop*:

   - ``GET`` ``/<database_name>/web_shop/<shop>/<format>/<language>/products.csv``:

      ``shop`` is the name of the *Web Shop*.
      ``format`` is the name of the target like ``google`` or ``facebook``.
      ``language`` is the :rfc:`4646` code of the language. It can be omitted
      to use the default database language.
