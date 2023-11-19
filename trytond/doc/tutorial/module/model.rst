.. _tutorial-module-model:

Define model
============

The :ref:`models <ref-models>` are the base objects of a module to store and
display data.
The :class:`~trytond.model.ModelSQL` is the base class that implements the
persistence in the SQL database.
The :class:`~trytond.model.ModelView` is the base class that implements the
view layer.
And of course, a model would be useless without its :ref:`fields
<ref-models-fields>`.

Let's start with a simple model to store the opportunities with a description,
a start and end date, a link to a party and an optional comment.
Our model in :file:`opportunity.py` file currently looks like this:

.. code-block:: python

    from trytond.model import ModelSQL, fields

    class Opportunity(ModelSQL):
        "Opportunity"
        __name__ = 'training.opportunity'
        _rec_name = 'description'

        description = fields.Char("Description", required=True)
        start_date = fields.Date("Start Date", required=True)
        end_date = fields.Date("End Date")
        party = fields.Many2One('party.party', "Party", required=True)
        comment = fields.Text("Comment")

As you can see a Model must have a :attr:`~trytond.model.Model.__name__`
attribute.
This name is used to make reference to this object.
It is also used to build the name of the SQL table to store the opportunity
records in the database.

The :attr:`~trytond.model.Model._rec_name` attribute defines the field that
will be used to compute the name of the record.
The name of the record is its textual representation.

The ``party`` field is a relation field (Many2One_) to another Model of Tryton
named ``party.party``.
This model is defined by the ``party`` module.

.. _Many2One: https://en.wikipedia.org/wiki/Many-to-one

Register the model in the Pool
------------------------------

Once a Tryton model is defined, you need to register it in the
:class:`~trytond.pool.Pool`.
This is done in the :file:`__init__.py` file of your module with the following
code:

.. code-block:: python

    from trytond.pool import Pool
    from . import opportunity

    def register():
        Pool.register(
            opportunity.Opportunity,
            module='opportunity', type_='model')

Models in the pool are inspected by Tryton when activating or updating a module
in order to create or update the schema of the table in the database.

Activate the opportunity module
-------------------------------

Now that we have a basic module, we will use it to create the related table
into the :ref:`database created <tutorial-module-setup-database>`.

First we must edit the :file:`tryton.cfg` file to specify that this module
depends on the ``party`` and ``ir`` module.
We need to do this because the ``Opportunity`` model contains the ``party``
field which refers to the ``Party`` model.
And we always need the ``ir`` module which is always included in Tryton server.

Here is the content of our :file:`tryton.cfg` file:

.. code-block:: ini

   [tryton]
   version=x.y.0
   depends:
      ir
      party

As we defined a new dependency, we must refresh the installation with:

.. code-block:: console

   $ python3 -m pip install --use-pep517 --editable opportunity

Now we can activate the ``opportunity`` module and its dependencies:

.. code-block:: console

    $ trytond-admin -d test -u opportunity --activate-dependencies

This step has created the tables into your database.
You can check it with the :command:`sqlite3` command line:

.. code-block:: console

   $ sqlite3 ~/db/test.sqlite '.schema training_opportunity'
   CREATE TABLE "training_opportunity" (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      "comment" TEXT,
      "create_uid" INTEGER,
      "create_date" TIMESTAMP,
      "description" VARCHAR,
      "end_date" DATE,
      "start_date" DATE,
      "write_date" TIMESTAMP,
      "party" INTEGER,
      "write_uid" INTEGER);

The next step will be :ref:`displaying record <tutorial-module-view>`.
