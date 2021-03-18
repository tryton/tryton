.. _topics-extension:

==============
Extending View
==============

Extending a view means, that the original view will be modified by a set of
rules which are defined with XML.

For this purpose, the extension engine uses xpath expressions.

The view is defined with the field ``inherit`` of the ir.ui.view.

If the field ``domain`` (a Python string representation of a :ref:`domain
<topics-domain>`) is not set or evaluated to True, the inheritance will be
proceeded.

XML Description
===============

data
----

Each view must start with this tag.

xpath
-----

    * ``expr``: the xpath expression to find a node in the inherited view.

    * ``position``: Define the position in relation to the node found. It can
      be ``before``, ``after``, ``replace``, ``inside`` or
      ``replace_attributes`` which will change the attributes.

Example
=======

.. highlight:: xml

::

  <data>
      <xpath
          expr="/form/notebook/page/separator[@name=&quot;signature&quot;]"
          position="before">
          <label name="company"/>
          <field name="company"/>
          <label name="employee"/>
          <field name="employee"/>
      </xpath>
  </data>
