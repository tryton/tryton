.. _topics-models:

======
Models
======

A model represents a single business logic or concept. It contains fields and
defines the behaviors of the record. Most of the time, each model stores
records in a single database table.

The basics:

    * Each model is a Python class that subclasses one of
      :class:`~trytond.model.Model`.

    * :ref:`Fields <ref-models-fields>` are defined as model attributes.

    * Tryton generates the table definitions

    * Tryton provides an API following the `active record pattern`_ to access the records.

.. _active record pattern: http://en.wikipedia.org/wiki/Active_record

Example
=======

This example defines a ``Party`` model which has a ``name`` and a ``code``
fields::

    from trytond.model import ModelView, ModelSQL, fields

    class Party(ModelSQL, ModelView):
        "Party"
        __name__ = "party.party"
        name = fields.Char('Name')
        code = fields.Char('Code')

The class must be registered in the :class:`~trytond.pool.Pool` by the
``register()`` method of the :ref:`module <topics-modules>`.
Model classes are essentially data mappers to records and Model instances are
records.

Model attributes define meta-information of the model. They are class
attributes starting with an underscore.  Some model properties are instance
attributes allowing to update them at other places in the framework.
