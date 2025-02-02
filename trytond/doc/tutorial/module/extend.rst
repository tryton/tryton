.. _tutorial-module-extend:

Extend model
============

Sometimes we want to extend an existing :class:`~trytond.model.Model` to add or
modify a :class:`~trytond.model.fields.Field` or a method.
This can be done using the extension mechanism of Tryton which can combine
classes with the same ``__name__`` that are registered in the
:class:`~trytond.pool.Pool`.

Extend the Party model
----------------------

Let's add an ``opportunities`` field on the ``party.party`` model.
The model in :file:`party.py` file of our module looks like this:

.. code-block:: python

    from trytond.model import fields
    from trytond.pool import PoolMeta

    class Party(metaclass=PoolMeta):
        __name__ = 'party.party'
        opportunities = fields.One2Many(
            'training.opportunity', 'party', "Opportunities")

This new class must be register in the :class:`~trytond.pool.Pool`.
So in :file:`__init__.py` we add:

.. code-block:: python

    from . import party

    def register():
        Pool.register(
            ...,
            party.Party,
            module='opportunity', type_='model')

Change a field of the Party model
`````````````````````````````````

To change an existing :class:`~trytond.model.fields.Field`, you need to change
its properties in the :meth:`~trytond.model.Model.__setup__` method.
Let's change the ``active`` field on the ``party.party`` model to be
``readonly`` when there are ``opportunities``.
The ``__setup__`` class method is added to the :file:`party.py` file:

.. code-block:: python

    from trytond.pyson import Bool, Eval

    class Party(metaclass=PoolMeta):
        ...

        @classmethod
        def __setup__(cls):
            super().__setup__()
            cls.active.states['readonly'] = Bool(Eval('opportunities', []))

.. note::
   You must always call the ``super()`` method when extending an existing
   method.

Extend the Party view
---------------------

Now that we added a new field to the ``party.party``
:class:`~trytond.model.Model`, we can also add it the form view.
This is done by adding a `View <model-ir.ui.view>` record that inherit the
party form view of the ``party`` module.
Here is the content of the :file:`party.xml` file:

.. code-block:: xml

   <tryton>
      <data>
         <record model="ir.ui.view" id="party_view_form">
            <field name="model">party.party</field>
            <field name="inherit" ref="party.party_view_form"/>
            <field name="name">party_form</field>
         </record>
      </data>
   </tryton>

The ``type`` is replaced by:

``inherit``
   A reference to the XML id of the view extended prefixed by the name of the
   module where the view is declared.

The content of the inheriting view must contain an XPath_ expression to define
the position from which to include the partial view XML.
Here is the content of the form view in :file:`view/party_form.xml`:

.. code-block:: xml

   <data>
      <xpath expr="/form/notebook/page[@name='identifiers']" position="after">
         <page name="opportunities" col="1">
            <field name="opportunities"/>
         </page>
      </xpath>
   </data>

.. _XPath: https://en.wikipedia.org/wiki/XPath

And finally we must declare the new XML data in the :file:`tryton.cfg` file:

.. code-block:: ini

   [tryton]
   ...
   xml:
      ...
      party.xml

Update database
---------------

As we have defined new field and XML record, we need to update the database
with:

.. code-block:: console

   $ trytond-admin -d test --all

And restart the server and reconnect with the client to see the new field on
the party.
You will also notice that the :guilabel:`Active` field become read only when
the party has opportunities.

.. code-block:: console

   $ trytond

Let's use a :ref:`wizard to convert the opportunity <tutorial-module-wizard>`.
