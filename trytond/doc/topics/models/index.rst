.. _topics-models:

======
Models
======

A model represents a single business logic or concept. It contains fields and
defines the behaviors of the data. Most of the time, each model stores data in
a single database table.

The basics:

    * Each model is a Python class that subclasses one of
      :class:`trytond.model.model.Model`.

    * :ref:`Fields <ref-models-fields>` are defined as model attributes.

    * Tryton generates the table definitions and provides an API to access the
      data.

Example
=======

This example defines a ``Party`` model which has a ``name`` and a ``code``
fields::

    from trytond.model import ModelView, ModelSQL, fields

    class Party(ModelSQL, ModelView):
        "Party"
        _description = __doc__
        _name = "party.party"
        name = fields.Char('Name')
        code = fields.Char('Code')

    Party()

Instantiating the class registers the model class in the framework.  Later the
class will be instantiated once per database and stored in the
:ref:`Pool <topics-pool>`.  Model instances are essentially accessors to
records.

Model attributes define meta-information of the model. They are class
attributes starting with an underscore.  Some model properties are instance
attributes allowing to update them at other places in the framework.
