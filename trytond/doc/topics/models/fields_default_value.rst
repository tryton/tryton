.. _topics-fields_default_value:

=======================
Default value of fields
=======================

When a record is created, each field, which doesn't have a value specified,
is set with the default value if exists.

The following method::

    Model.default_<field name>()

Return the default value for ``field name``.

This example defines an ``Item`` model which has a default ``since``::

    import datetime

    from trytond.model import ModelView, ModelSQL, fields

    class Item(ModelSQL, ModelView):
        "Item"
        _description = __doc__
        _name = "item.item"
        since = fields.Date('since')

        def default_since(self):
            return datetime.date.today()

    Item()

See also method ``Model.default_get``: :attr:`~trytond.model.Model.default_get`

