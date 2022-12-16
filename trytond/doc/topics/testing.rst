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

Tryton provides the :class:`ModuleTestCase` class that bundles a set of tests
that are useful for every module.

Unit tests in ``ModuleTestCase`` can be decorated with
:func:`trytond.tests.test_tryton.with_transaction` to run the test in a
transaction.

To use it in your own module you just have to inherit from
:class:`ModuleTestCase` and set the class attribute 
:attr:`module <ModuleTestCase.module>` to the name of your module.

.. highlight:: python

::

    from trytond.tests.test_tryton import ModuleTestCase, with_transaction

    class MyModuleTestCase(ModuleTestCase):
        "My Module Test Case"
        module = 'my_module'

        @with_transaction()
        def test_method(self):
            "Test method"
            self.assertTrue(True)


Tests from this modules are found by the function
``trytond.modules.my_module.tests.suite`` which must return a
``unittest.TestSuite`` containing all the module's tests. This function is
called by the Tryton test runner script to gather all the tests.

A typical ``suite()`` function thus looks like this:

.. highlight:: python

::

    def suite():
        suite = trytond.tests.test_tryton.suite()
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            MyModuleTestCase))
        suite.addTests(doctest.DocFileSuite('scenario_my_module.rst',
                tearDown=doctest_teardown, encoding='utf-8',
                optionflags=doctest.REPORT_ONLY_FIRST_FAILURE,
                checker=doctest_checker))
        return suite

.. _doctests: https://docs.python.org/library/doctest.html
.. _unittest: https://docs.python.org/library/unittest.html

Running your module's tests
---------------------------

Tryton provides the script ``trytond/tests/run-tests.py``, just invoke it like
that::

    run-tests.py -m my_module

Testing trytond
~~~~~~~~~~~~~~~

Extending tests
---------------

Python modules extending tryton core can define additional tests that should be
added to the existing ones.

Those modules must create an entry point ``trytond.tests``. Any file in the
module path specified by this entry point starting with ``test_`` and ending by
``.py`` will be imported. Each of those file must define a ``suite()`` function
that returns a ``unittest.TestSuite`` that will be included in the trytond test
suite.  If the module from the entry point defines a ``register`` function it
will be called when registering the test-specific models in the
:class:`trytond.pool.Pool`.

Running trytond tests
---------------------

You should use the script ``trytond/tests/run-tests.py`` by invoking it like
that::

    run-tests.py [-c configuration]

You can use a different configuration file to check trytond against different
backend.
