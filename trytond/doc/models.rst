
:tocdepth: 2

Model
#####

A model is a python class that usually represent a business logic or a
concept. Such classes consist essentially of keywords, fields,
constraints and helper functions.
There are different kinds of Models for different purposes:

  * ``ModelView``: Define Model with views.

  * ``ModelStorage``: Define Model with storage capability.

  * ``ModelSQL``: Define ModelStorage with SQL database as storage backend.

  * ``ModelWorkflow``: Define Model with workflow.

  * ``ModelSingleton``: Define Model with singleton property.

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

Instantiating the class registers the Model class in the framework.
Later the class will be instantiated once per database and stored in the Pool.
Model instances are essentially accessors to records.

Model properties define meta-information of the model, they are
class attributes starting with an underscore.
Some Model Properties are instance attributes allowing to update
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

A simple clause is a list of conditions, with an implicit ``AND``
operator:

.. highlight:: python

::

  [('name', '=', 'Bob'),('age','>=', 20)]


More complex clauses can be made this way:

.. highlight:: python

::

  [ 'OR', [('name', '=', 'Bob'),('city','in', ['Brussels', 'Paris'])],
          [('name', '=', 'Charlie'),('country.name','=', 'Belgium')],
  ]


Where ``country`` is a ``Many2One`` field on the current field.  The
number of *dots* in the left hand side of a condition is not limited, but
the underlying relation must be a ``Many2One``.

If used in a search call on the Address model this will result in
something similar to the following sql code (the actual sql query will 
be more complex since it has to take care of the access rights of the
user):

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
possible to create the two models without using inheritance, because
each of the foreign keys (``first_owner`` and ``current_car``) needs the
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
modified `self._reset_columns` is called.  Also notice that a developer should try
to make no assumptions about the field so that additional modules could also
extend the same field.

Fields
******

Fields are class attributes with a name that can not start with an underscore.

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


Field events and methods
^^^^^^^^^^^^^^^^^^^^^^^^

Setting defaults
++++++++++++++++

If you want to set a default value for a field of a model you merely need to
define a function named `default_field_name` where field_name is the name of
the field.

.. highlight:: python

::

  class Sale(ModelWorkflow, ModelSQL, ModelView):
      'Sale'
      _name = 'sale.sale'
      sale_date = fields.Date('Sale Date', required=True, states={
          'readonly': "state != 'draft'",
          })
      def default_sale_date(self, cursor, user, context=None):
          date_obj = self.pool.get('ir.date')
          return date_obj.today(cursor, user, context=context)

This example sets the default sale date on a sale to be the current date.  The
client will use this default when filling a form for this model.  These
methods also can be called explicitly when creating a model manually to populate it
with defaults.  Finally these methods also will be called when using the create method
if there is no value set in values that were passed.

on_change versus on_change_with
+++++++++++++++++++++++++++++++

If a field's value depends on the value of another field a model must act on
the other field changing.  There are two ways to handle this depending on how
many dependencies there are.

 * `on_change` on field with field_name contained list of field names

   * method on_change_field_name is called
   * fields with name in on_change are passed in vals with their name as the
     key
   * method returns a dictionary with keys that are the names of fields to set

 * `on_change_with` defined on field with field_name containing list of
   field names

   * method on_change_with_field_name is called
   * fields with name in on_change_with are passed in vals with their name as
     the key
   * method returns only a new value of the field that defined on_change_with

.. highlight:: python

::

  class PackingOut(ModelWorkflow, ModelSQL, ModelView):
      _name = 'stock.packing.out'

      customer = fields.Many2One('party.party', 'Customer', required=True,
              states={
                  'readonly': "state != 'draft' or bool(outgoing_moves)",
              }, on_change=['customer'])

      def on_change_customer(self, cursor, user, ids, values, context=None):
          if not values.get('customer'):
              return {'delivery_address': False}
          party_obj = self.pool.get("party.party")
          address_id = party_obj.address_get(cursor, user, values['customer'],
                  type='delivery', context=context)
          return {
                  'delivery_address': address_id}      

In this example when the customer changes the delivery address also changes.
The new value is set when `on_change_customer` returns the new value for 
`delivery_address` in a dict. Any field of the model returned in this dict 
will be updated with the new value.

.. highlight:: python

::

  class Template(ModelSQL, ModelView):
      _name = "product.template"

      purchase_uom = fields.Many2One('product.uom', 'Purchase UOM', states={
          'readonly': "active == False",
          'invisible': "not purchasable",
          'required': "purchasable",
          }, domain=["('category', '=', (default_uom, 'uom.category'))"],
          context="{'category': (default_uom, 'uom.category')}",
          on_change_with=['default_uom', 'purchase_uom', 'purchasable'])

      def on_change_with_purchase_uom(self, cursor, user, ids, vals,
              context=None):
          uom_obj = self.pool.get('product.uom')
          res = False

          if vals.get('default_uom'):
              default_uom = uom_obj.browse(cursor, user, vals['default_uom'],
                      context=context)
              if vals.get('purchase_uom'):
                  purchase_uom = uom_obj.browse(cursor, user, vals['purchase_uom'],
                          context=context)
                  if default_uom.category.id == purchase_uom.category.id:
                      res = purchase_uom.id
                  else:
                      res = default_uom.id
              else:
                  res = default_uom.id
          return res

In this example when either default_uom, purchase_uom or purchasable change
then purchase_uom will be changed.  Notice that `on_change_with` differs from
`on_change` because `on_change_with` returns only the value for the specific
field compared to `on_change` which returns a dictionary of values. Also notice
that all the fields in `on_change_with` are passed into the `vals` argument of
the method call as keys in the dictionary.


How to use Function fields
^^^^^^^^^^^^^^^^^^^^^^^^^^

Assuming the following field is defined on the invoice model:

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

The first variant we'll look at is defining a unique function for
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


The framework is able to check, if ``names`` (instead of ``name``) is
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

Another possible improvement can be to provide a search function.
Indeed without it the user will not be able to search across
invoices for a certain amount.  If we forget about the
``total_service`` field, a solution could look like the following:

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


Note: Such an implementation would be very slow for a large number of invoices.


Write on Function fields
++++++++++++++++++++++++
It is also possible to allow the user to write on a function field:

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
