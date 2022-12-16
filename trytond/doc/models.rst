
:tocdepth: 2

Model
#####

Model is python classes that usually represents business logical or
concepts. Such classes consist essentially of keywords, fields,
constraints and helper functions.
There is different kind of Model for different purpose:

  * ``ModelView``: Define Model with views.

  * ``ModelStorage``: Define Model with storage capability.

  * ``ModelSQL``: Define ModelStorage with SQL database for storage backend.

  * ``ModelWorkflow``: Define Model with workflow.

The following snippet gives a first idea of what can be done:

.. highlight:: python

::

  from trytond.model import ModelView, ModelSQL, fields

  class Category(ModelSQL, ModelView):
      "Party category"
      _name = 'relationship.category'
      _description = __doc__
      name = fields.Char('Name')
  Category()

  class Country(ModelSQL, ModelView):
      "Country"
      _name = 'relationship.country'
      _description = __doc__
      name = fields.Char('Name')
  Category()

  class Address(ModelSQL, ModelView):
      "Address"
      _name = 'relationship.address'
      _description = __doc__
      name = fields.Char('Contact Name')
      party = fields.Many2One('relationship.party', 'Party')
      country = fields.Many2One('relationship.country', 'Country')
      city = fields.Char('City')
  Address()

  class Party(ModelSQL, ModelView):
      "Party"
      _description = __doc__
      _name = "relationship.party"
      name = fields.Char('Name')
      addresses = fields.One2Many('relationship.address', 'party', 'Addresses')
      categories = fields.Many2Many('relationship.category', 'relationship_category_rel',
                                    'party', 'category', 'Categories')
  Party()

Instantiating the class register the Model class in the framework.
Later they will be instanciate once per database and stored in the Pool.
Model instances are essentially accessors to records.

Model properties defines meta-informations about the model, they are
class attributes starting with and underscore.
Some Model Properties are instance attributes which allow to update
them at other places in the framework.

.. _model:

Model
*****

.. _trytond.model.Model:
.. autoclass:: trytond.model.Model
    :members:
    :undoc-members:

.. _trytond.model.ModelView:
.. autoclass:: trytond.model.ModelView
    :members:
    :undoc-members:

.. _trytond.model.ModelStorage:
.. autoclass:: trytond.model.ModelStorage
    :members:
    :undoc-members:

.. _trytond.model.ModelSQL:
.. autoclass:: trytond.model.ModelSQL
    :members:
    :undoc-members:

.. _search_clause:

Search clauses
^^^^^^^^^^^^^^

Simple clause are a list of condition, with an implicit ``AND``
operator:

.. highlight:: python

::

  [('name', '=', 'Bob'),('age','>=', 20)]


More complex clause can be made this way:

.. highlight:: python

::

  [ 'OR', [('name', '=', 'Bob'),('city','in', ['Brussels', 'Paris'])],
          [('name', '=', 'Charlie'),('country.name','=', 'Belgium')],
  ]


Where ``country`` is a ``Many2One`` field on the current field.  The
number *dots* in the left hand side of a condition is not limited, but
the underlying relation must be a ``Many2One``.

Which if used in a search call on the Address model will result in
something similar to the following sql code (the actual sql query will
be more complex since it has to take care of the access rights of the
user.):

.. highlight:: sql

::

  SELECT relationship_address.id FROM relationship_address
  JOIN relationship_country ON
       (relationship_address.country = relationship_country.id)
  WHERE (relationship_address.name = 'Bob' AND
         relationship_address.city in ('Brussels', 'Paris'))
        OR
        (relationship_address.name = 'Charlie' AND
         relationship_country.name  = 'Belgium')

.. _define_inheritance:

Models Inheritance
^^^^^^^^^^^^^^^^^^

Model Inheritance provides the ability to add or override fields, methods and
constraints on existing models. 

Adding fields to an existing model
++++++++++++++++++++++++++++++++++

To inherit an existing model (like
``Party`` on the first example), one just needs to instantiate a class
with the same ``_name`` attribute:

.. highlight:: python

::


  class Car(ModelSQL, ModelView):
      _name = "vehicle.car"
      _rec_name = model
      model = fields.Char("Model", required=True)
      manufacturer = fields.Char("Manufacturer")
      first_owner = fields.Many2One('relationship.party', 'First Owner')
  Car()

  class Party(ModelSQL, ModelView):
      _name = "relationship.party"
      current_car = fields.Many2One('vehicle.car', 'Current car')

      def __init__(self):
          super(Party, self).__init__()
          self._sql_constraints += [
              ('party_car_uniq', 'UNIQUE(model)',
                  'Two parties cannot use the same car!'),
          ]

  Party()


This example shows how to define and relate a new model to an existing model.
The example also demonstrates how to define a reflecting ``Many2One``: It's not
possible to create the two models without using inheritance because
each of the foreign key (``first_owner`` and ``current_car``) need the
other model table.


Extending existing fields from an existing model
++++++++++++++++++++++++++++++++++++++++++++++++

An existing field can be extended by calling `copy.copy` on it, modifying its attributes
and then calling `self._reset_columns`.

.. highlight:: python

::

  import copy

  class Line(ModelSQL, ModelView):
      _name = 'timesheet.line'

      #...

      def __init__(self):
          super(Line, self).__init__()
          self.employee = copy.copy(self.employee)
          if self.employee.on_change is None:
              self.employee.on_change = []
          if 'employee' not in self.employee.on_change:
              self.employee.on_change += ['employee']
              self._reset_columns()


In this example the extended model wants on_change_employee(...) to be called so it adds 'employee'
to the on_change attribute of the employee field.  Notice that only if the the field is
modified then `self._reset_columns` is called.  Also notice that a developer should try
to make no assumptions about the field so that additional modules could also
extend the same field.

Fields
******

Fields are class attributes which a name that can not start with an underscore.

.. _trytond.model.fields.Boolean:
.. autoclass:: trytond.model.fields.Boolean
    :members:
    :undoc-members:

.. _trytond.model.fields.Integer:
.. autoclass:: trytond.model.fields.Integer
    :members:
    :undoc-members:

.. _trytond.model.fields.BigInteger:
.. autoclass:: trytond.model.fields.BigInteger
    :members:
    :undoc-members:

.. _trytond.model.fields.Char:
.. autoclass:: trytond.model.fields.Char
    :members:
    :undoc-members:

.. _trytond.model.fields.Sha:
.. autoclass:: trytond.model.fields.Sha
    :members:
    :undoc-members:

.. _trytond.model.fields.Text:
.. autoclass:: trytond.model.fields.Text
    :members:
    :undoc-members:

.. _trytond.model.fields.Float:
.. autoclass:: trytond.model.fields.Float
    :members:
    :undoc-members:

.. _trytond.model.fields.Numeric:
.. autoclass:: trytond.model.fields.Numeric
    :members:
    :undoc-members:

.. _trytond.model.fields.Date:
.. autoclass:: trytond.model.fields.Date
    :members:
    :undoc-members:

.. _trytond.model.fields.DateTime:
.. autoclass:: trytond.model.fields.DateTime
    :members:
    :undoc-members:

.. _trytond.model.fields.Time:
.. autoclass:: trytond.model.fields.Time
    :members:
    :undoc-members:

.. _trytond.model.fields.Binary:
.. autoclass:: trytond.model.fields.Binary
    :members:
    :undoc-members:

.. _trytond.model.fields.Selection:
.. autoclass:: trytond.model.fields.Selection
    :members:
    :undoc-members:

.. _trytond.model.fields.Reference:
.. autoclass:: trytond.model.fields.Reference
    :members:
    :undoc-members:

.. _trytond.model.fields.Many2One:

.. autoclass:: trytond.model.fields.Many2One
    :members:
    :undoc-members:

.. _trytond.model.fields.One2Many:
.. autoclass:: trytond.model.fields.One2Many
    :members:
    :undoc-members:

.. _trytond.model.fields.Many2Many:
.. autoclass:: trytond.model.fields.Many2Many
    :members:
    :undoc-members:

.. _trytond.model.fields.Function:
.. autoclass:: trytond.model.fields.Function
    :members:
    :undoc-members:

.. _trytond.model.fields.Property:
.. autoclass:: trytond.model.fields.Property
    :members:
    :undoc-members:

.. _use_function:

How to use Function fields
^^^^^^^^^^^^^^^^^^^^^^^^^^

Let's say that the following field is defined on the invoice model:

.. highlight:: python

::

  total = fields.Function('get_total', type='float', string='Total')



The ``get_total`` method should look like this:

.. highlight:: python

::

  def get_total(self, cursor, user, ids, name, arg, context=None):
      res = {}.fromkeys(ids, 0.0)
      for invoice in self.browse(cursor, user, ids, context=context):
          for line in invoice:
              if invoice.id in res:
                  res[invoice.id] += line.amount
              else:
                  res[invoice.id] = line.amount
      return res


One should note that the dictionary ``res`` should map a value for
each id in ``ids``.


One method to rule them all
+++++++++++++++++++++++++++

The first variant of this we'll look at is defining a unique function for
several fields. Let's consider this new field which returns the total for
the invoice lines of kind *service*:

.. highlight:: python

::

  total_service = fields.Function('get_total', type='float', string='Total Service')



For this field the method ``get_total`` can be defined this way:

.. highlight:: python

::

  def get_total(self, cursor, user, ids, name, arg, context=None):
      res = {}.fromkeys(ids, 0.0)
      for invoice in self.browse(cursor, user, ids, context=context):
          for line in invoice:
              if name == 'total_service' and line.kind != "service":
                  continue
              if invoice.id in res:
                  res[invoice.id] += line.amount
              else:
                  res[invoice.id] = line.amount
      return res


Or even better:

.. highlight:: python

::

  def get_total(self, cursor, user, ids, names, arg, context=None):
      res = {'total': {}.fromkeys(ids, 0.0),
             'total_service': {}.fromkeys(ids, 0.0)}
      for invoice in self.browse(cursor, user, ids, context=context):
          for line in invoice:
              if invoice.id in res['total']:
                  res['total'][invoice.id] += line.amount
              else:
                  res['total'][invoice.id] = line.amount

              if line.kind != "service":
                  continue
              if invoice.id in res['total_service']:
                  res['total_service'][invoice.id] += line.amount
              else:
                  res['total_service'][invoice.id] = line.amount
      return res


The framework is able to check if ``names`` (instead of ``name``) is
used in the method definition, hence adapting the way the method is
called.


Another way to tackle Function implementation is to pass a dictionary
to the ``args`` argument on the field definition. It will be forwarded
to the function call:

.. highlight:: python

::

  state = fields.Function(
      'get_state', type='selection', string='Total Service',
      args={'key':'value'},
      selection=[('draft','Draft'),('done','Done')],
      )

  def get_state(self, cursor, user, ids, names, arg, context=None):
      # [...]
      if arg.get('key'):
          pass # do something with 'value'


Search on Function fields
+++++++++++++++++++++++++

Another improvement would be to provide a search function.
Indeed without it the user will not be able to search across
invoices for a certain amount.  If we forget about the
``total_service`` field, solution could be something like the
following:

.. highlight:: python

::

  total = fields.Function('get_total', type='float', string='Total',
                          fnct_search='search_total')


  def get_total(self, cursor, user, ids, name, arg, context=None):
      pass #<See first example>

  def search_total(self, cursor, user, name, domain=[], context=None):
      # First fetch all the invoice ids
      invoice_ids = self.search(cursor, user, [], context=context)
      # Then collect total for each one, implicitly calling get_total:
      lines = []
      for invoice in self.browse(cursor, user, invoice_ids, context=context):
          lines.append({'invoice': invoice.id, 'total': invoice.total})

      res= [l['invoice'] for l in lines if self._eval_domain(l, domain)]

      return [('id', 'in', res)]

  def _eval_domain(self, line, domain):
      # domain is something like: [('total', '<', 20), ('total', '>', 10)]
      res = True
      for field, operator, operand in domain:
          value = line.get(field)
          if value == None:
              return False
          if operator not in ("=", ">=", "<=", ">", "<", "!="):
              return False
          if operator == "=":
              operator= "=="
          res = res and (eval(str(value) + operator + str(operand)))
      return res


One should note that such an implementation would be very slow for a large
number of invoices.


Write on Function fields
++++++++++++++++++++++++
It's also possible to allow the user to write on a function field:

.. highlight:: python

::

  name = fields.Function('get_name', type='char', string='Total',
                          fnct_inv='set_name')
  hidden_name= fields.Char('Hidden')

  def set_name(self, cursor, user, id, name, value, arg, context=None):
    self.write(cursor, user, id, {'hidden_name': value}, context=context)

  def get_name(self, cursor, user, ids, name, arg, context=None):
    res = {}
    for party in self.browse(cursor, user, ids, context=context):
       res[party.id] = party.hidden_name or "unknown"
    return res


This simplistic (and inefficient) example is another way to handle a default
value on the ``name`` field.
