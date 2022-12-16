.. _ref-test:
.. module:: trytond.tests.test_tryton

====
Test
====

.. attribute:: DB_NAME

    The name of the database to use for testing. Its value is taken from the
    environment variable of the same name.

.. attribute:: USER

    The user id used to test the transactions

.. attribute:: CONTEXT

    The context used to test the transactions

.. function:: activate_module(name)

Activates the module `name` for the tested database.

In case database does not exist and the `DB_CACHE` environment variable is set
then Tryton will restore a backup found in the directory pointed by `DB_CACHE`.
Otherwise it will proceed to the creation of the database and the activation of
the module.

==============
ModuleTestCase
==============

.. class:: ModuleTestCase()

A subclass of `unittest.TestCase`_ that tests a Tryton module. Some tests are
included to ensure that the module works properly.

This class creates a temporary database with the module activated in
`setUpClass`_ and drops it in the `tearDownClass` method.

.. attribute:: ModuleTestCase.module

    Name of the tested module.

.. _`unittest.TestCase`: https://docs.python.org/library/unittest.html#test-cases
.. _setUpClass: https://docs.python.org/library/unittest.html#unittest.TestCase.setUpClass
.. _tearDownClass: https://docs.python.org/library/unittest.html#unittest.TestCase.tearDownClass

=======
Helpers
=======

.. function:: with_transaction(user=1, context=None)

This function returns a decorator to run a test case inside a transaction. The
transaction is rolled back and the cache cleared at the end of the test.

doctest helpers
---------------

.. function:: doctest_setup

A function that prepares the run of the `doctest`_ by creating a database and
dropping it beforehand if necessary. This function should be used as the
`setUp` parameter 

.. deprecated::
    The `doctest_setup` function should not be used anymore to set up
    `DocFileSuite`. New modules should use :func:`activate_modules` instead.

.. _doctest: https://docs.python.org/library/doctest.html

.. function:: doctest_teardown()

A function that cleans up after the run of the doctest by dropping the
database. It should be used as `tearDown` parameter when creating a
`DocFileSuite`.

.. attribute:: doctest_checker

    A specialized doctest checker to ensure the Python 2/3 compatibility

.. function:: suite()

A function returning a subclass of `unittest.TestSuite` that will drop the
database if it does not exist prior to the run of the tests.

.. module:: trytond.tests.tools

===========
Tests tools
===========

.. function:: activate_modules(modules)

This function is used in proteus doctests to activate a list of `modules` in
the scenario.

.. function:: set_user(user, config)

This function will set the user of the `config` proteus connection to `user`.
