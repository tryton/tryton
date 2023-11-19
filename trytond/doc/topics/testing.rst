.. _topics-testing:

=======
Testing
=======

Tryton supports both functional and unit tests.

Testing your module
~~~~~~~~~~~~~~~~~~~

Functional tests
----------------

Functional tests are written as doctests_ using proteus.

Unit tests
----------

Tryton provides the :class:`~trytond.tests.test_tryton.ModuleTestCase` class
that bundles a set of tests that are useful for every module.

Unit tests in :class:`~trytond.tests.test_tryton.ModuleTestCase` can be
decorated with :func:`~trytond.tests.test_tryton.with_transaction` to run the
test in a transaction.

To use it in your own module you just have to inherit from
:class:`~trytond.tests.test_tryton.ModuleTestCase` and set the class attribute
:attr:`~trytond.tests.test_tryton.ModuleTestCase.module` to the name of your
module.

.. code-block:: python

    from trytond.tests.test_tryton import ModuleTestCase, with_transaction

    class MyModuleTestCase(ModuleTestCase):
        "My Module Test Case"
        module = 'my_module'

        @with_transaction()
        def test_method(self):
            "Test method"
            self.assertTrue(True)

    del ModuleTestCase


.. note::
   The ``ModuleTestCase`` must be deleted to not be discovered by ``unittest``
   as it fails to run without module declaration.

.. _doctests: https://docs.python.org/library/doctest.html
.. _unittest: https://docs.python.org/library/unittest.html

Running trytond's tests
-----------------------

You can run a specific test file using ``unittest`` command line like:

.. code-block:: console

   $ python3 -m unittest trytond.tests.test_tools

To run all trytond's tests using discover of ``unittest`` with:

.. code-block:: console

   $ python3 -m unittest discover -s trytond.tests

To run all modules tests:

.. code-block:: console

   $ python3 -m unittest discover -s trytond.modules


Running your module's tests
---------------------------

You just need to replace the directory path with the one of your module:

.. code-block:: console

   $ python3 -m unittest discover -s trytond.modules.my_module.tests

Extending trytond's tests
-------------------------

Python modules extending ``trytond`` core can define additional classes to
register in ``tests`` module.
Those modules must create an entry point ``trytond.tests`` which defines a
``register`` function to be called with the module name.

Testing options
~~~~~~~~~~~~~~~

Tryton runs tests against the configured database backend.
You can specify the name of the database to use via the environment variable
``DB_NAME``.
Otherwise it generates a random name.

A configuration file can be used by setting its path to the environment
variable ``TRYTOND_CONFIG``.

The tests recreate frequently the database. You can accelerate the creation by
setting a cache directory in ``DB_CACHE`` environment which will be used to
dump and restore initial databases backups.
