.. _topics-pyson:

=====
PYSON
=====

PYSON is the PYthon Statement and Object Notation. It is a
lightweight `domain specific language`_ for the general representation
of statements. PYSON is used to encode statements which can be
evaluated in different programming languages, serving for the
communication between trytond and any third party software.
A PYSON parser can easily be implemented in other programming languages.
So third party softwares do not need to depend on Python to be able to
fully communicate with the Tryton server.

PYSON is a `deterministic algorithm`_ which will always succeed to evaluate
statements. There is a default behavior for unknown values. It is statically
typed and checked on instantiation.

There is also a :ref:`reference documentation of the API <ref-pyson>`.

.. _`domain specific language`: http://en.wikipedia.org/wiki/Domain-specific_language
.. _`deterministic algorithm`: http://en.wikipedia.org/wiki/Deterministic_algorithm

Syntax
======

The syntax of a PYSON statement follows this pattern::

    Statement(argument1[, argument2[, ...]])

where arguments can be another statement or a value. The evaluation
direction is inside out, deepest first.


PYSON Examples
==============

Given the PYSON statement::

    Eval('active_id', -1)

``Eval()`` checks the evaluation context for the variable ``active_id``
and returns its value or ``-1`` if not defined. A similar expression
in Python looks like this::

    'active_id' in locals() and active_id or -1

Given the PYSON statement::

    Not(Bool(Eval('active')))

``Eval()`` checks the evaluation context for a variable ``active`` and
returns its value to ``Bool()`` or ``''`` if not defined. ``Bool()``
returns the corresponding boolean value of the former result to ``Not()``.
``Not()`` returns the boolean negation of the previous result. A similar
expression in Python looks like this::

    'active' in locals() and active == False

Given the PYSON statement::

    Or(Not(Equal(Eval('state'), 'draft')), Bool(Eval('lines')))

In this example are the results of two partial expressions
``Not(Equal(Eval('state'), 'draft'))`` and ``Bool(Eval('lines'))``
evaluated by a logical *OR* operator. The first expression part is
evaluated as follow: When the value of ``Eval('state')`` is equal to
the string ``'draft'`` then return true, else false. ``Not()`` negates
the former result. A similar expression in Python looks like this::

    'states' in locals() and 'lines' in locals() \
            and state != 'draft' or bool(lines)

Given the PYSON statement::

    If(In('company', Eval('context', {})), '=', '!=')

In this example the result is determined by an `if-then-else`_ condition.
``In('company', Eval('context', {}))`` is evaluated like this: When
the key ``'company'`` is in the dictionary ``context``, returns
true, otherwise false. ``If()`` evaluates the former result and returns
the string ``'='`` if the result is true, otherwise returns the
string ``'!='``. A similar expression in Python looks like this::

    'context' in locals() and isinstance(context, dict) \
            and 'company' in context and '=' or '!='

.. _if-then-else: http://en.wikipedia.org/wiki/Conditional_statement#If-Then.28-Else.29

Given the PYSON statement::

    Get(Eval('context', {}), 'company', 0))

``Eval()`` checks the evaluation context for a variable ``context`` if
defined, return the variable ``context``, otherwise return an empty
dictionary ``{}``. ``Get()`` checks the former resulting dictionary
and returns the value of the key ``'company'``, otherwise it returns
the number ``0``. A similar expression in Python looks like this::

    'context' in locals() and context.get('company', 0) or 0



