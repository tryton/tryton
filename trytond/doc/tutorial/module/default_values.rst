.. _tutorial-module-default-values:

Set default values
==================

Default values are useful to save time for users when entering data.
On Tryton :ref:`default values <topics-fields_default_value>` are computed on
server side and they will be set by the client when creating a new record if
the field is shown on the view.
If the field is not shown on the view, the server will set this values when
storing the new records in the database.

In order to define a default value for a field you should define a class method
named ``default_<field_name>`` that returns the default value.
For example to add today as the default date of our ``Opportunity`` model the
following class method is added in :file:`opportunity.py` file:

.. code-block:: python

    from trytond.pool import Pool
    ...
    class Opportunity(ModelSQL, ModelView):
        ...
        @classmethod
        def default_start_date(cls):
            pool = Pool()
            Date = pool.get('ir.date')
            return Date.today()

.. _tutorial-module-calling-other-classes:

Call other model methods
------------------------

In the previous example we called the ``today`` method of the ``ir.date`` model
from the :class:`~trytond.pool.Pool` instance.
The :attr:`~trytond.model.Model.__name__` value is used to get the class.
It is very important to get the class from the pool instead of using a normal
Python import, because the pool ensures that all of the extensions are applied
depending on the activated modules.
For example, if we have the company module also activated the correct timezone
for the user company will be used for computing the today value.

Great, you have learned how to define default values, and how to call methods
defined on other classes in the pool.
Let's continue with :ref:`reacting on user input <tutorial-module-on-change>`.
