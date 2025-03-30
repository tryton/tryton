.. _ref-test:
.. module:: trytond.tests.test_tryton

Tests
=====

.. attribute:: DB_NAME

   The name of the database to use for testing.
   Its value is taken from the environment variable of the same name.

.. attribute:: USER

   The user id used to test the transactions

.. attribute:: CONTEXT

   The context used to test the transactions

.. attribute:: TEST_NETWORK

   If false, tests that requires network are skipped.
   Its value is taken from the environment variable of the same name.

.. function:: activate_module(name)

   Activate the named module for the tested database.

   In case database does not exist and the ``DB_CACHE`` environment variable is
   set then Tryton restores a backup found in the directory pointed by
   ``DB_CACHE``.
   ``DB_CACHE`` can also be set to the value ``postgresql://``, in that case
   Tryton create the database using the template found on the server.
   Otherwise it procees to the creation of the database and the activation of
   the module.

   ``DB_CACHE_JOBS`` environment variable defines the number of jobs used for
   dump and restore operations.
   The default value is the number of CPU.

TestCase
--------

.. class:: TestCase()

   A subclass of `unittest.TestCase`_ for testing non-module Tryton.

   It setups warning filters based on ``TEST_PYTHONWARNINGS`` environment
   variable.

ModuleTestCase
--------------

.. class:: ModuleTestCase()

   A subclass of :class:`TestCase` that tests a Tryton module.
   Some tests are included to ensure that the module works properly.

   It creates a temporary database with the module activated in setUpClass_ and
   drops it in the tearDownClass_ method.

.. attribute:: ModuleTestCase.module

   Name of the tested module.

.. attribute:: ModuleTestCase.extras

   A list of extra modules to activate

.. attribute:: ModuleTestCase.language

   The language to activate.
   Default value is ``en``.

RouteTestCase
-------------

.. class:: RouteTestCase()

   A subclass of :class:`TestCase` to test Tryton routes.

   It creates a temporary database with the module activated in setUpClass_ and
   drops it in the tearDownClass_ method.

.. attribute:: RouteTestCase.module

   Name of the tested module.

.. attribute:: RouteTestCase.extras

   A list of extra modules to activate

.. attribute:: RouteTestCase.language

   The language to activate.
   Default value is ``en``.

.. attribute:: RouteTestCase.db_name

   Returns the name of the database

.. classmethod:: RouteTestCase.setUpDatabase()

   A method called by setUpClass_ after activating the modules in a
   :class:`~trytond.transaction.Transaction`.
   It is used to setup data in the database.

.. method:: RouteTestCase.client()

   Return a client to simulate requests to the WSGI application.

ExtensionTestCase
-----------------

.. class:: ExtensionTestCase()

   A subclass of :class:`TestCase` to test a Tryton with an database extension
   activated.

.. attribute:: ExtensionTestCase.extension

   The name of the extension to activate.

.. _`unittest.TestCase`: https://docs.python.org/library/unittest.html#test-cases
.. _setUpClass: https://docs.python.org/library/unittest.html#unittest.TestCase.setUpClass
.. _tearDownClass: https://docs.python.org/library/unittest.html#unittest.TestCase.tearDownClass


Helpers
-------

.. function:: with_transaction(user=1, context=None)

   Return a decorator to run a test case inside a
   :class:`~trytond.transaction.Transaction`.
   It is rolled back and the cache cleared at the end of the test.

doctest helpers
---------------

.. function:: doctest_setup

   Prepare the run of the doctest_.
   This function should be used as the ``setUp`` parameter.

.. function:: doctest_teardown()

   Clean up after the run of the doctest_ by dropping the database.
   It should be used as ``tearDown`` parameter when creating a
   ``DocFileSuite``.

.. attribute:: doctest_checker

   A specialized doctest checker to ensure the Python compatibility.


.. function:: load_doc_tests(name, path, loader, tests, pattern[, skips])

   An helper that follows the ``load_tests`` protocol to load as
   :py:class:`~doctest.DocTest` all ``*.rst`` files in ``directory``,
   with the module ``name`` and the ``path`` to the module file from which the
   doc tests are registered.
   If a file with the same name but the extension ``.json`` exists, the test is
   registered for each globals defined in the JSON list.
   ``skips`` constains the name of the scenario to skip.

.. function:: suite()

   A function returning a subclass of ``unittest.TestSuite`` that drops the
   database if it does not exist prior to the run of the tests.

.. _doctest: https://docs.python.org/library/doctest.html

.. module:: trytond.tests.tools

Tools
-----

.. function:: activate_modules(modules, \*setup)

   Activate a list of ``modules`` for scenario based on proteus doctests.
   The following arguments are functions sequentially called at the end of the
   activation with the proteus configuration as ``config`` keyword argument.

.. function:: set_user([user[, config]])

   Set the user of the ``config`` proteus connection to ``user``.

The module exposes also all the assert methods of :py:class:`unittest.TestCase`
that can be run doctest scenario.
