.. _ref-pyson:
.. module:: trytond.pyson

=====
PYSON
=====


PYSON is the PYthon Statement and Object Notation.

There is also a more :ref:`practical introduction into
PYSON statements <topics-pyson>`.

.. class:: PYSON

Base class of any PYSON statement. It is never used directly.

Instance methods:

.. method:: PYSON.pyson()

Method that returns the internal dictionary representation of the
statement.

.. method:: PYSON.types()

Method that returns a set of all possible types which the statement
can become when evaluated.

.. classmethod:: PYSON.eval(dct, context)

Method which returns the evaluation of the statement given in
``dct`` within the ``context``. ``dct`` contains a
dictionary which is the internal representation of a PYSON
statement. ``context`` contains a dictionary with contextual
values.


Encoder and Decoder
===================

.. class:: PYSONEncoder()

Encoder for PYSON statements into string representations.

Instance method:

    .. method:: PYSONEncoder.encode(object)

    Returns a string representation of a given PYSON statement.
    ``object`` contains a PYSON statement.

.. class:: PYSONDecoder([context[, noeval]])

Decoder for string into the evaluated or not PYSON statement.

Instance method:

    .. method:: PYSONDecoder.decode(object)

    Returns a PYSON statement evaluated or not of a given string.
    ``object`` contains a string.

Statements
==========

The following statements can be used in :class:`PYSON`.

.. class:: Eval(value[, default])

An :class:`Eval()` object represents the PYSON ``Eval()``
statement for evaluations. When evaluated, it returns the
value of the statement named by ``value``, if defined in the
evaluation context, otherwise the ``default`` value (empty
string by default). 

.. note::

    The default value determines the type of the statement.
..

.. note::

    If the ``value`` includes dots the value will be dereferenced. For
    example::

        Eval('_parent_sale.number')

    The ``number`` value of the ``_parent_sale`` key of the evaluation context
    will be returned.
..

.. class:: Not(value)

A :class:`Not` object represents the PYSON ``Not()``
statement for logical negations. When evaluated, returns
the boolean negation of the value of the statement named by
``value``, if defined in the evaluation context. Returns an
instance of itself.

.. class:: Bool(value)

A :class:`Bool` object represents the PYSON ``Bool()``
statement for boolean evaluations. Returns the boolean
representation of the value of the statement named by
``value``.

.. class:: And(\*statements)

An :class:`And` object represents the PYSON ``And()``
statement for logical *and* operations. Returns the result of
the logical conjunction of two or more values named by the
statements in the ``statements`` tuple.

.. class:: Or(\*statements)

An :class:`Or` object represents the PYSON ``Or()``
statement for logical *or* operations. Returns the result of
the logical disjunction of two or more values named by the
statements in the ``statements`` tuple.

.. class:: Equal(statement1, statement2)

An :class:`Equal` object represents the PYSON ``Equal()``
statement for equation comparisons. Returns true when a value of
a statement named by ``statement1`` and the value of a statement
named by ``statement2`` are equal, otherwise returns false.

.. class:: Greater(statement1, statement2[, equal])

A :class:`Greater` object represents the PYSON ``Greater()``
statement for *greater-than* comparisons. Returns true when the value
of the statement named by ``statement1`` is strictly greater than the
value of the statement named by ``statement2``,  otherwise
returns false. Is the value of the variable named by ``equal`` is 
true, then returns also true when both values of statements named by
``statement1`` and ``statement2`` are equal. In this case
:class:`Greater` works as a *greater-than or equal* operator.

.. note:: `None` value is replaced by `0` for the comparison.

.. class:: Less(statement1, statement2[, equal])

A :class:`Less` object represents the PYSON ``Less()``
statement for *less-than* comparisons. Returns true when the value
of the statement named by ``statement1`` is strictly less than the
value of the statement named by ``statement2``,  otherwise
returns false. Is the value of the variable named ``equal`` is true,
then returns also true when both values of the statements named by
``statement1`` and ``statement2`` are equal. In this case
:class:`Less`  works as a *less-than or equal* operator.

.. note:: `None` value is replaced by `0` for the comparison.

.. class:: If(condition, then_statement, else_statement)

An :class:`If` object represents the PYSON ``If()``
statement for conditional flow control operations. Returns the
value of the statement named by ``then_statement`` when the value
of the statement named by ``condition`` evaluates true.
Otherwise returns the value of the statement named by
``else_statement``.

.. class:: Get(obj, key[, default])

A :class:`Get` object represents the PYSON ``Get()``
statement for dictionary look-up operations and evaluation.
Look up and returns the value of a key named by ``key`` in an
object named by ``obj`` if defined.
Otherwise returns the value of the variable named by ``default``.

.. class:: In(key, obj)

An :class:`In` object represents the PYSON ``In()``
statement for look-up dictionary or integer objects. Returns true when
a list (or dictionary) object named by ``obj`` contains the value of
the variable (or key) named by ``key``. Otherwise returns false.

.. class:: Date([year[, month[, day[, delta_years[, delta_month[, delta_days[, start]]]]]]])

A :class:`Date` object represents the PYSON ``Date()`` statement for date
related conversions and basic calculations.
Returns a date object which represents the values of arguments named by the
*variables* explained below.
Missing values of arguments named by ``year`` or ``month`` or ``day`` take
their defaults from ``start`` or the actual date. When values of arguments
named by ``delta_*`` are given, they are added to the values of the appropriate
arguments in a date and time preserving manner.

Arguments:

``year``
    Contains a PYSON statement of type int or long.

``month``
    Contains a PYSON statement of type int or long.

``day``
    Contains a PYSON statement of type int or long.

``delta_years``
    Contains a PYSON statement of type int or long.

``delta_month``
    Contains a PYSON statement of type int or long.

``delta_days``
    Contains a PYSON statement of type int or long.

``start``
    Contains a PYSON statement of type date.

.. class:: DateTime([year[, month[, day[, hour[, minute[, second[, microsecond[, delta_years[, delta_months[, delta_days[, delta_hours[, delta_minutes[, delta_seconds[, delta_microseconds[, start]]]]]]]]]]]]]]])

A :class:`DateTime` object represents the PYSON ``Date()`` statement for date
and time related conversions and calculations.
Returns a date time object which represents the values of variables named by
the *arguments* explained below.
Missing values of arguments named by  ``year``, ``month``, ``day``, ``hour``,
``minute``, ``second``, ``microseconds`` take their defaults from ``start`` or
the actual date and time in `UTC`_.
When values of arguments named by ``delta_*`` are given, these are added  to
the appropriate attributes in a date and time preserving manner.

.. _`UTC`: https://en.wikipedia.org/wiki/Coordinated_Universal_Time

Arguments:

``year``
    Contains a PYSON statement of type int or long.

``month``
    Contains a PYSON statement of type int or long.

``day``
    Contains a PYSON statement of type int or long.

``hour``
    Contains a PYSON statement of type int or long.

``minute``
    Contains a PYSON statement of type int or long.

``second``
    Contains a PYSON statement of type int or long.

``microsecond``
    Contains a PYSON statement of type int or long.

``delta_years``
    Contains a PYSON statement of type int or long.

``delta_month``
    Contains a PYSON statement of type int or long.

``delta_days``
    Contains a PYSON statement of type int or long.

``delta_hours``
    Contains a PYSON statement of type int or long.

``delta_minutes``
    Contains a PYSON statement of type int or long.

``delta_seconds``
    Contains a PYSON statement of type int or long.

``delta_microseconds``
    Contains a PYSON statement of type int or long.

``start``
    Contains a PYSON statement of type datetime.

.. class:: Len(value)

A :class:`Len` object represents the PYSON ``Len()`` statement for length of a
dictionary, list or string. Returns the number of items in ``value``.

.. class:: Id(module, fs_id)

An :class:`Id` object represents the PYSON ``Id()`` statement for filesystem id
evaluations. When converted into the internal dictionary, it returns the
database id stored in `ir.model.data`.
