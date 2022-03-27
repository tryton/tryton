.. _topics-extension:

==============
Extending View
==============

Extending a view means, that the original view will be modified by a set of
rules which are defined with XML.
For this purpose, the extension engine uses XPath_ expressions.
The view is defined with the field ``inherit`` of the ``ir.ui.view``.

If the field :ref:`domain <topics-domain>` is not set or evaluated to ``True``,
the inheritance will be proceeded.

.. _XPath: https://en.wikipedia.org/wiki/XPath

Example:

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

data
----

Each view must start with this tag.

xpath
-----

``expr``
   The XPath expression to find the nodes in the inherited view.

``position``
   Define the position in relation to the nodes found.
   It can be ``before``, ``after``, ``replace``, ``inside`` or
   ``replace_attributes`` which will change the attributes.
