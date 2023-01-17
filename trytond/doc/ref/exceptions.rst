.. _ref-exceptions:
.. module:: trytond.exceptions

Exceptions
==========

.. exception:: TrytonException

   The base class for all Tryton exceptions.

.. exception:: UserError(message[, description[, domain]])

   The base class for exceptions used to display an error message to users.
   The domain may be a 2-tuple containing a :ref:`domain <topics-domain>` and a
   dictionary of field definitions used to format the domain and append to the
   description.

.. exception:: UserWarning(name, message[, description])

   The base class for exceptions used to display a warning message to users.

.. exception:: LoginExceptions(name, message[, type])

   The exception used to request ``name`` parameter for the login process.

.. exception:: ConcurrencyException(message)

   The exception raised on concurrent modification.

.. exception:: RateLimitException

   The exception raised when user has sent too many login requests.

.. exception:: MissingDependenciesException(missings)

   The exception raised when modules are missing.


.. module:: trytond.model.exceptions

.. exception:: AccessError

   The exception raised when trying to access a record without the rights.

.. exception:: AccessButtonError

   The exception raised when trying to execute a button without the rights.

.. exception:: ButtonActionException

   The exception raised to launch the ``action`` instead of executing the
   button method.

   The ``value`` attribute is the action value returned.

.. exception:: ImportDataError

   The exception raises when importing data fails.

.. exception:: ValidationError

   The base class for all record validation error.

.. exception:: DomainValidationError

   The exception raised when the domain of a field is not valid.

.. exception:: RequiredValidationError

   The exception raised when a required field is empty.

.. exception:: SizeValidationError

   The exception raised when the size of a field is too big.

.. exception:: DigitsValidationError

   The exception raised when the value of a field does not respect its digits.

.. exception:: SelectionValidationError

   The exception raised when the value is not in the selection.

.. exception:: TimeFormatValidationError

   The exception raised when the time format of a field is not respected.

.. exception:: ForeignKeyError

   The exception raised when a foreign key is not respected.

.. exception:: SQLConstraintError

   The exception raised when a :attr:`~trytond.model.ModelSQL._sql_constraints`
   is not respected.

.. exception:: RecursionError

   The exception raised by :class:`~trytond.model.TreeMixin.check_recursion`.
