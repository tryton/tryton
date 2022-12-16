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

.. function:: activate_module(name)

   Activate the named module for the tested database.

   In case database does not exist and the ``DB_CACHE`` environment variable is
   set then Tryton restores a backup found in the directory pointed by
   ``DB_CACHE``.
   Otherwise it procees to the creation of the database and the activation of
   the module.

ModuleTestCase
--------------

.. class:: ModuleTestCase()

   A subclass of `unittest.TestCase`_ that tests a Tryton module.
   Some tests are included to ensure that the module works properly.

   It creates a temporary database with the module activated in setUpClass_ and
   drops it in the tearDownClass_ method.

.. attribute:: ModuleTestCase.module

   Name of the tested module.

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

   Prepare the run of the `doctest`_ by creating a database and dropping it
   beforehand if necessary.
   This function should be used as the ``setUp`` parameter.

   .. deprecated:: 4.2

      The ``doctest_setup`` function should not be used anymore to set up
      :py:func:`~doctest.DocFileSuite`.
      New modules should use :func:`~trytond.tests.tools.activate_modules`
      instead.

.. function:: doctest_teardown()

   Clean up after the run of the doctest_ by dropping the database.
   It should be used as ``tearDown`` parameter when creating a
   ``DocFileSuite``.

.. attribute:: doctest_checker

   A specialized doctest checker to ensure the Python compatibility.


.. function:: load_doc_tests(name, path, loader, tests, pattern)

   An helper that follows the ``load_tests`` protocol to load as
   :py:class:`~doctest.DocTest` all ``*.rst`` files in ``directory``,
   with the module ``name`` and the ``path`` to the module file from which the
   doc tests are registered.

.. function:: suite()

   A function returning a subclass of ``unittest.TestSuite`` that drops the
   database if it does not exist prior to the run of the tests.

.. _doctest: https://docs.python.org/library/doctest.html

.. module:: trytond.tests.tools

Tools
-----

.. function:: activate_modules(modules)

   Activate a list of ``modules`` for scenario based on proteus doctests.

.. function:: set_user(user, config)

   Set the user of the ``config`` proteus connection to ``user``.
