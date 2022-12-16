.. _topics-domain:


======
Domain
======

Domains_ represent a set of records. A domain is a list of none or
more clauses. A clause is a condition, which returns true or false.
A record belongs to a domain, when the final result of the list of
clauses returns true.

.. _Domains: http://en.wikipedia.org/wiki/Data_domain


Syntax
======

The definition of a simple domain with one clause is represented
by this pattern::

    domain = [(<field name>, <operator>, <operand>)]

``<field name>``
    Is the name of a :mod:`~trytond.model.fields` or a
    :ref:`pyson <topics-pyson>` statement, that evaluates to a
    string.

    A field of type :class:`~trytond.model.fields.Many2One` or
    :class:`~trytond.model.fields.Many2Many` or
    :class:`~trytond.model.fields.One2Many` or
    :class:`~trytond.model.fields.One2One` or
    :class:`~trytond.model.fields.Reference` can be dereferenced to related
    models. This is illustrated by the following example::

        domain = [('country.name', '=', 'Japan')]

    The number of *dots* in a clause is not limited.

.. warning::
    For :class:`trytond.model.fields.Reference`, an extra ending clause is
    needed to define the target model to join, for example::

        domain = [('origin.party.name', '=', 'John Doe', 'sale.sale')]
..

    A field of type :class:`~trytond.model.fields.Dict` can be searched by key
    also by using one *dot*. For example::

        domain = [('attributes.color', '=', 'yellow')]

.. warning::
    Order comparison of `date` and `datetime` types is not supported.

``operator``
    Is an operator out of `Domain Operators`_ or a
    :ref:`pyson <topics-pyson>` statement, that evaluates to
    a domain operator string.

``operand``
   Is an operand or a :ref:`pyson <topics-pyson>` statement. The
   type of operand depends on the kind of <field name>.

The definition of an empty domain is::

    domain = []

An empty domain without clauses will always return all *active*
records. A record is active, when its appropriate
:class:`~trytond.model.Model` contains a
:class:`~trytond.model.fields.Boolean` field with name ``active``,
and set to true. When the appropriate :class:`~trytond.model.Model`
does not contain a :class:`~trytond.model.fields.Boolean` field with
name ``active`` all records are returned.

A domain can be setup as a combination of clauses, like shown in
this pattern::

    domain = [
        ('field name1', 'operator1', 'operand1'),
        ('field name2', 'operator2', 'operand2'),
        ('field name3', 'operator3', 'operand3'),]

The single clauses are implicitly combined with a logical
AND_ operation.


In the domain syntax it is possible to provide explicitly the
combination operation of the clauses. These operations can be AND_
or OR_. This is illustrated by the following pattern::

    domain = [ 'OR', [
                ('field name1', 'operator1', 'operand1'),
                ('field name2', 'operator2', 'operand2'),
            ], [
                ('field name3', 'operator3', 'operand3'),
            ],]

.. _AND: http://en.wikipedia.org/wiki/Logical_and
.. _OR: http://en.wikipedia.org/wiki/Logical_or


Here the domain is evaluated like this: ``((clause1 AND clause2)
OR clause3)``. Please note that the ``AND`` operation is implicit
assumed when no operator is given. While the ``OR`` operation must
be given explicitly. The former pattern is equivalent to the
following completely explicit domain definition::

    domain = [ 'OR',
                 [ 'AND', [
                         ('field name1', 'operator1', 'operand1'),
                     ], [
                         ('field name2', 'operator2', 'operand2'),
                     ],
                 ], [
                     ('field name3', 'operator3', 'operand3'),
             ],]

Obviously the use of the implicit ``AND`` operation makes the code
more readable.


Domain Operators
================

The following operators are allowed in the domain syntax.
``<field name>``, ``<operator>`` and ``<operand>`` are dereferenced
to their values. The description of each operator follows this
pattern, unless otherwise noted::

    (<field name>, <operator>, <operand>)

``=``
-----

    Is a parity operator. Returns true when ``<field name>``
    equals to ``<operand>``.

``!=``
------

    Is an imparity operator. It is the negation of the `=`_ operator.

``like``
--------

    Is a pattern matching operator. Returns true when ``<field name>``
    is contained in the pattern represented by ``<operand>``.

    In ``<operand>`` an underscore (``_``) matches any single
    character, a percent sign (``%``) matches any string with zero
    or more characters. To use ``_`` or ``%`` as literal, use the
    backslash ``\`` to escape them. All matching is case sensitive.

``not like``
------------

    Is a pattern matching operator. It is the negation of the `like`_
    operator.

``ilike``
---------

    Is a pattern matching operator. The same use as `like`_ operator,
    but matching is case insensitive.

``not ilike``
-------------

    Is a pattern matching operator. The negation of the  `ilike`_ operator.

``in``
------

    Is a list member operator. Returns true when ``<field name>`` is
    in ``<operand>`` list.

``not in``
----------

    Is a list non-member operator. The negation of the `in`_ operator.

``<``
-----

    Is a *less than* operator. Returns true for type string of
    ``<field name>``  when ``<field name>`` is alphabetically
    sorted before ``<operand>``.

    Returns true for type number of ``<field name>`` when
    ``<field name>`` is less than ``<operand>``.

``>``
-----

    Is a *greater than* operator. Returns true for type string of
    ``<field name>`` when ``<field name>`` is alphabetically
    sorted after  ``<operand>``.

    Returns true for type number of ``<field name>`` when
    ``<field name>`` is greater ``<operand>``.

``<=``
------

    Is a *less than or equal* operator. Returns the same as using the
    `<`_ operator, but also returns true when ``<field name>`` is
    equal to ``<operand>``.

``>=``
------

    Is a *greater than or equal* operator. Returns the same as using
    the `>`_ operator, but also returns true when ``<field name>``
    is equal to ``<operand>``.

``child_of``
------------

    Is a parent child comparison operator. Returns true for records that are
    a child of ``<operand>``. ``<operand>`` is a list of ``ids`` and ``<field
    name>`` must be a :class:`~trytond.model.fields.many2one` or a
    :class:`~trytond.model.fields.many2many`.
    In case ``<field name>`` is not linked to itself, the clause pattern
    extends to::

        (<field name>, ['child_of'|'not_child_of'], <operand>, <parent field>)

    Where ``<parent field>`` is the name of the field constituting the
    :class:`~trytond.model.fields.many2one` on the target model.

``not child_of``
----------------

    Is a parent child comparison operator. It is the negation of the
    `child_of`_ operator.

``parent_of``
-------------

    Is a parent child comparison operator. It is the same as `child_of`_
    operator but if ``<field name>`` is a parent of ``<operand>``.

``not parent_of``
-----------------

    Is a parent child comparison operator. It is the negation of this
    `parent_of`_ operator.

``where``
---------

    Is a :class:`trytond.model.fields.One2Many` /
    :class:`trytond.model.fields.Many2Many` domain operator. It returns true
    for every row of the target model that match the domain specified as
    ``<operand>``.

``not where``
-------------

    Is a :class:`trytond.model.fields.One2Many` /
    :class:`trytond.model.fields.Many2Many` domain operator. It returns true
    for every row of the target model that does not match the domain specified
    as ``<operand>``.
