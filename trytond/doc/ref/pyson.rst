.. _ref-pyson:
.. module:: trytond.pyson

PYSON
=====

PYSON is the Python Statement and Object Notation.

There is also a more :ref:`practical introduction into
PYSON statements <topics-pyson>`.

.. class:: PYSON

   Base class of any PYSON statement.
   It is never used directly.

Instance methods:

.. method:: PYSON.pyson()

   Return the internal dictionary representation of the statement.

.. method:: PYSON.types()

   Return a set of all possible types which the statement can become when
   evaluated.

Class methods:

.. classmethod:: PYSON.eval(dct, context)

   Return the evaluation of the statement given in ``dct`` within the
   ``context``.

   ``dct`` contains a dictionary which is the internal representation of a
   PYSON statement.

   ``context`` contains a dictionary with contextual values.


Encoder and Decoder
-------------------

.. class:: PYSONEncoder()

   Encoder for PYSON statements into string representations.

Instance methods:

.. method:: PYSONEncoder.encode(object)

   Return a string representation of a given PYSON statement.

   ``object`` contains a PYSON statement.


.. class:: PYSONDecoder([context[, noeval]])

   Decoder for string into the evaluated or not PYSON statement.

Instance methods:

.. method:: PYSONDecoder.decode(object)

   Return a PYSON statement evaluated or not of a given string.

   ``object`` contains a string.

Statements
----------

The following classes can be used as :class:`PYSON` statement:

.. contents::
   :local:
   :backlinks: entry
   :depth: 1

Eval
^^^^

.. class:: Eval(value[, default])

   Represent the PYSON statement for evaluations.

   When evaluated, it returns the value of the statement named by ``value``, if
   defined in the evaluation context, otherwise the ``default`` value (empty
   string by default).

   .. note::

      The default value determines the type of the statement.

   .. note::

      If the ``value`` includes dots the value will be dereferenced.
      For example::

         Eval('_parent_sale.number')

      The ``number`` value of the ``_parent_sale`` key of the evaluation
      context will be returned.


Not
^^^

.. class:: Not(value)

   Represent the PYSON statement for logical negations.

   When evaluated, returns the boolean negation of the value of the statement
   named by ``value``, if defined in the evaluation context.
   Returns an instance of itself.

Bool
^^^^

.. class:: Bool(value)

   Represent the PYSON statement for boolean evaluations.

   Returns the boolean representation of the value of the statement named by
   ``value``.

And
^^^

.. class:: And(\*statements)

   Represent the PYSON statement for logical *and* operations.

   Returns the result of the logical conjunction of two or more values named by
   the statements in the ``statements`` tuple.

Or
^^

.. class:: Or(\*statements)

   Represent the PYSON statement for logical *or* operations.

   Returns the result of the logical disjunction of two or more values named by
   the statements in the ``statements`` tuple.

Equal
^^^^^

.. class:: Equal(statement1, statement2)

   Represent the PYSON statement for equation comparisons.

   Returns ``True`` when a value of a statement named by ``statement1`` and the
   value of a statement named by ``statement2`` are equal, otherwise returns
   ``False``.

Greater
^^^^^^^

.. class:: Greater(statement1, statement2[, equal])

   Represent the PYSON statement for *greater-than* comparisons.

   Returns ``True`` when the value of the statement named by ``statement1`` is
   strictly greater than the value of the statement named by ``statement2``,
   otherwise returns false.
   Is the value of the variable named by ``equal`` is ``True``, then returns
   also ``True`` when both values of statements named by ``statement1`` and
   ``statement2`` are equal.
   In this case :class:`Greater` works as a *greater-than or equal* operator.

   .. note::

      ``None`` value is replaced by ``0`` for the comparison.

Less
^^^^

.. class:: Less(statement1, statement2[, equal])

   Represent the PYSON statement for *less-than* comparisons.

   Returns ``True`` when the value of the statement named by ``statement1`` is
   strictly less than the value of the statement named by ``statement2``,
   otherwise returns ``False``.
   Is the value of the variable named ``equal`` is true, then returns also true
   when both values of the statements named by ``statement1`` and
   ``statement2`` are equal.
   In this case :class:`Less`  works as a *less-than or equal* operator.

   .. note::

      ``None`` value is replaced by ``0`` for the comparison.

If
^^

.. class:: If(condition, then_statement, else_statement)

   Represent the PYSON statement for conditional flow control operations.

   Returns the value of the statement named by ``then_statement`` when the
   value of the statement named by ``condition`` evaluates true.
   Otherwise returns the value of the statement named by ``else_statement``.

Get
^^^

.. class:: Get(obj, key[, default])

   Represent the PYSON statement for dictionary look-up operations and
   evaluation.

   Look up and returns the value of a key named by ``key`` in an object named
   by ``obj`` if defined.
   Otherwise returns the value of the variable named by ``default``.

In
^^

.. class:: In(key, obj)

   Represent the PYSON statement for look-up dictionary or integer objects.

   Returns true when a list (or dictionary) object named by ``obj`` contains
   the value of the variable (or key) named by ``key``.
   Otherwise returns false.

Date
^^^^

.. class:: Date([year[, month[, day[, delta_years[, delta_month[, delta_days[, start]]]]]]])

   Represent the PYSON statement for date related conversions and basic
   calculations.

   Returns a date object which represents the values of arguments named by the
   *variables* explained below.
   Missing values of arguments named by ``year`` or ``month`` or ``day`` take
   their defaults from ``start`` or the actual date. When values of arguments
   named by ``delta_*`` are given, they are added to the values of the
   appropriate arguments in a date and time preserving manner.

   Arguments:

   ``year``
      A PYSON statement of type int or long.

   ``month``
      A PYSON statement of type int or long.

   ``day``
      A PYSON statement of type int or long.

   ``delta_years``
      A PYSON statement of type int or long.

   ``delta_month``
      A PYSON statement of type int or long.

   ``delta_days``
      A PYSON statement of type int or long.

   ``start``
      A PYSON statement of type date.

DateTime
^^^^^^^^

.. class:: DateTime([year[, month[, day[, hour[, minute[, second[, microsecond[, delta_years[, delta_months[, delta_days[, delta_hours[, delta_minutes[, delta_seconds[, delta_microseconds[, start]]]]]]]]]]]]]]])

   Represent the PYSON statement for date and time related conversions and
   calculations.

   Returns a date time object which represents the values of variables named by
   the *arguments* explained below.
   Missing values of arguments named by  ``year``, ``month``, ``day``,
   ``hour``, ``minute``, ``second``, ``microseconds`` take their defaults from
   ``start`` or the actual date and time in `UTC`_.
   When values of arguments named by ``delta_*`` are given, these are added  to
   the appropriate attributes in a date and time preserving manner.

   Arguments:

   ``year``
       A PYSON statement of type int or long.

   ``month``
       A PYSON statement of type int or long.

   ``day``
       A PYSON statement of type int or long.

   ``hour``
       A PYSON statement of type int or long.

   ``minute``
       A PYSON statement of type int or long.

   ``second``
       A PYSON statement of type int or long.

   ``microsecond``
       A PYSON statement of type int or long.

   ``delta_years``
       A PYSON statement of type int or long.

   ``delta_month``
       A PYSON statement of type int or long.

   ``delta_days``
       A PYSON statement of type int or long.

   ``delta_hours``
       A PYSON statement of type int or long.

   ``delta_minutes``
       A PYSON statement of type int or long.

   ``delta_seconds``
       A PYSON statement of type int or long.

   ``delta_microseconds``
       A PYSON statement of type int or long.

   ``start``
       A PYSON statement of type datetime.

.. _`UTC`: https://en.wikipedia.org/wiki/Coordinated_Universal_Time

Len
^^^

.. class:: Len(value)

   Represent the PYSON statement for length of a dictionary, list or string.

   Returns the number of items in ``value``.

Id
^^

.. class:: Id(module, fs_id)

   Represent the PYSON statement for filesystem id evaluations.

   When converted into the internal dictionary, it returns the database id
   stored in ``ir.model.data``.
