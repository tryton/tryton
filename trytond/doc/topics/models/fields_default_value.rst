.. _topics-fields_default_value:

=======================
Default value of fields
=======================

When a record is created, each field, which doesn't have a value specified,
is set with the default value if exists.

The following class method:

.. rstcheck: ignore-next-code-block
.. code-block:: python

    Model.default_<field name>()

Return the default value for ``field name``.

This example defines an ``Item`` model which has a default ``since``:


.. code-block:: python

    import datetime

    from trytond.model import ModelView, ModelSQL, fields


    class Item(ModelSQL, ModelView):
        "Item"
        __name__ = 'item'
        since = fields.Date('since')

        @classmethod
        def default_since(cls):
            return datetime.date.today()

See also method :meth:`~trytond.model.Model.default_get`.
