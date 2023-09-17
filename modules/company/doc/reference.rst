*************
API Reference
*************

Company Multi-Values
====================

.. class:: trytond.modules.company.model.CompanyMultiValueMixin

   A :class:`~trytond:trytond.model.MultiValueMixin` that makes it
   simpler to create :class:`~trytond:trytond.model.fields.MultiValue` fields
   based on the `Company <model-company.company>` in the context.
   It does this by including the company from the context in the pattern by
   default.

.. class:: trytond.modules.company.model.CompanyValueMixin

   A :class:`~trytond:trytond.model.ValueMixin` used to store the values
   of a :class:`.CompanyMultiValueMixin`.

Employee Fields
===============

.. function:: trytond.modules.company.model.employee_field(string, [states], [company])

   A function that returns a :class:`~trytond:trytond.model.fields.Many2One`
   field.
   This field is intended to be used to store the
   `Employee <model-company.employee>` that performed some action on the
   :class:`~trytond:trytond.model.Model` that contains the
   :class:`~trytond:trytond.model.fields.Field`.

   :param string: The string that is used as the label for the field.
   :param states: The states in which the field will be read-only.
   :param company: The name of the field that contains the company.
   :return: The employee Many2One field.

.. decorator:: trytond.modules.company.model.set_employee(field, [company[, when]])

   Used to decorate methods which need to record the employee that last
   ran them.
   The specified ``field`` is updated with the *User's* current `Employee
   <model-company.employee>`, but only if the employee works for the
   ``company``.

   :param field: The name of the field to set to the user's current employee.
   :param company:
      The name of the field that contains the company.
      Defaults to 'company'.
   :param when:
      Define if the field is set 'after' calling the decorated method or
      'before'.
      Default to 'after'.

.. decorator:: trytond.modules.company.model.reset_employee(\*fields[, when])

   Used to decorate methods which indicate that the document is now in a
   state where the action has not yet been performed, so the
   `Employee <model-company.employee>` should be cleared from the ``fields``.

   :param fields:
      The names of the fields that should have the employee removed.
   :param when:
      Define if the field is set 'after' calling the decorated method or
      'before'.
      Default to 'after'.

Company Reports
===============

.. class:: trytond.modules.company.company.CompanyReport

   A report that places the `Company <model-company.company>` of the record
   in the header key and adds it to the context.
