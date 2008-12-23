
:tocdepth: 2

Models
######

Models are python classes that usually represent business object or
concepts. Such classes consist essentially of keywords, fields,
constraints and helper functions. They inherit from the OSV class
which provide the framework integration like the database abstraction,
workflows, translations, etc.

The following snippet gives a first idea of what can be done:

.. highlight:: python

::

  class Category(OSV):
      "Party category"
      _name = 'relationship.category'
      _description = __doc__
      name = fields.Char('Name')
  Category()

  class Country(OSV):
      "Country"
      _name = 'relationship.country'
      _description = __doc__
      name = fields.Char('Name')
  Category()

  class Address(OSV):
      "Address"
      _name = 'relationship.address'
      _description = __doc__
      name = fields.Char('Contact Name')
      party = fields.Many2One('relationship.party', 'Party')
      country = fields.Many2One('relationship.country', 'Country')
      city = fields.Char('City')
  Address()

  class Party(OSV):
      "Party"
      _description = __doc__
      _name = "relationship.party"
      name = fields.Char('Name')
      addresses = fields.One2Many('relationship.address', 'party', 'Addresses')
      categories = fields.Many2Many('relationship.category', 'relationship_category_rel',
                                    'party', 'category', 'Categories')
  Party()

Instantiating the class makes it alive for the framework. Actually
there will be only one instance per class and per database. So model
instances are essentially accessors to the underlying table. Columns of
the table correspond to the fields of the class. Rows of the table
corresponds to records.


Model Properties
****************

Model properties defines meta-informations about the model, they are
class attributes starting with and underscore.

   * ``_description``: A non technical description of the model.

   * ``_name``: The unique identifier that can be use to reference the
     model across all the framework.

   * ``_table``: The name of the database table which is mapped to
     the current class. If not set the value of ``_name`` is used with
     dots converted to underscores.

   * ``_rec_name``: The name of the main field of the model. If not
     set the field ``name`` is used (like in the above example).

   * ``_sequence``: The  name of the postgresql sequence that
     increment the ``id`` column.

   * ``_order_name``: The name of the field (or an sql expression) on
     which the row must be sorted when the underlying table is read.

   * ``_auto``: When set to ``False`` will prevent the framework from
     creating a table for this class.

   * ``_sql``: The sql code that must be used to fetch data from the
     database. The columns outputted by the given query must reflect
     the class fields.

Some Model Properties are instance attributes which allow to update
them at other places in the framework

   * ``_order``: A tuple defining how the row are sorted when the
     underlying table is read. E.g.: ``[('name', 'ASC'), 'age',
     'DESC']``

   * ``_error_messages``: A dictionary mapping keywords to a user
     message. E.g.: ``{'recursive_categories': 'You can not create
     recursive categories!'}``

   * ``_constraints``: A list of constraints that each record must
     respect. Each item of this list is a couple ``('function_name',
     'error_keyword')``, where ``'function_name'`` is the name of a
     method of the same class, which should return a boolean value
     (``False`` when the constraint is violated). ``error_keyword``
     must be one of the key of ``_sql_error_messages``.

   * ``_sql_constraints``: A list of constraints that are added on
     the underlying table. E.g.: ``('constrain_name, sql_constraint,
     'error_msg')`` where  ``'constrain_name'`` is the name of the
     sql constraint for the database, ``sql_constraint`` is the actual
     sql constraint (E.g.: ``'UNIQUE(name)'``) and ``'error_msg'`` is
     one of the key of ``_error_messages``.

   * ``_sql_error_messages``: Like ``_error_messages`` for
     ``_sql_constraints``.

   * ``_rpc_allowed``: The list of the names of the method that are
     allowed to be called remotely. By default it contains: ``[
     'read', 'write', 'create', 'default_get', 'delete', 'fields_get',
     'fields_view_get', 'search', 'name_get', 'name_search', 'copy',
     'import_data', 'export_data', 'search_count', 'search_read']``
     and all the ``default_*`` and ``on_change_*`` methods.


Fields
******

Fields are class attributes that do not start with an underscore. Some
fields are automatically added on each tables:

   * ``id``: An integer providing a identifier for each row.

   * ``create_date``: The date at which the row was created.

   * ``create_uid``: The identifier of the user (I.e. the ``id`` of
     one row of the table defining the users) who created the row.

   * ``write_date``: The date of the last modification.

   * ``write_uid``: The user who made the last modification.


Fields types
^^^^^^^^^^^^

A field can be one of the following basic types:

   * ``Char``: A string of character.

   * ``Text``: A multi-line text.

   * ``Boolean``: True or False.

   * ``Integer``: An integer number.

   * ``BigInteger``: An integer number with a larger range.

   * ``Float``: A floating point number.

   * ``Numeric``: Like Float, but provide an arbitrary precision on
     all operations.

   * ``Date``: A day. E.g.: 2008-12-31.

   * ``DateTime``: A time in a day. E.g.: 2008-12-31 11:30:59.

   * ``Selection``: A value from a list. See :ref:`define_selection`
     for details.

   * ``Binary``: A blob. E.g.: a picture.

   * ``Sha``: Like a char but his content is never shown to the
     user. The typical usage is for password fields.

Or one of these relation types:

   * ``Many2One``: A relation from the current model to another one
     where several record of the current model can be linked to the
     same record of the other. E.g.: ``party =
     fields.Many2One('relationship.party', 'Party')`` where
     ``'relationship.party'`` is the identifier of the other
     model. This correspond in the database to a foreign key from the
     table of the current model to the ``relationship_party``
     table. See :ref:`define_tree` for advanced usage.

   * ``One2Many``: A relation from the current model to another one
     where one record of the current model can be linked to many
     records of the other. E.g.: ``addresses =
     fields.One2Many('relationship.party', 'party',
     'Addresses')``. This correspond in the database to a foreign key
     (who's name is ``party``) from the ``relationship_address`` table
     to the table of the current model. A ``One2Many`` alone will not
     work, it rely on the ``Many2One`` to create the foreign key.

   * ``Many2Many``: A relation from the current model to another one
     where many record of the current model can be linked to many
     records of the other. E.g.: ``categories =
     fields.Many2Many('relationship.category',
     'relationship_category_rel', 'party', 'category',
     'Categories')``. This correspond in the database to a new table
     ``relationship_category_rel`` with two foreign key ``party`` and
     ``category`` pointing to ``relationship_party`` and
     ``relationship_category``.

Or one of these composed types:

   * ``Property``: Like a ``Many2One`` but allow complex usage of
     default value: when the default value is updated, all the fields
     with this default value are updated.  When the company module is
     installed it also allow to define different value for the same
     field depending on the company of the user.

   * ``Reference``: Also like a ``Many2One``. It allow to create a
     link to an arbitrary selection of other  model. This selection is
     defined by the records of ``res.request.link``.



Function field can be used to mimic any other type:

   * ``Function``: A computed field. E.g. ``total =
     fields.Function('get_total', type='float',
     string='Total')``. Where ``'get_total'`` is the name if a method
     of the current class. See :ref:`use_function` for more details.

.. _define_selection:

How to define selections
++++++++++++++++++++++++

A selection field allow the user to choose one value across a limited
number of values. There are two ways to define a field that will be
shown as a selection to the user:

  1. Using the fields.Selection()

  2. Using a fields.Many2One() (with a static domain) and define it in
  the xml view of the module as ``widget="Selection"``, see
  :ref:`example_form_view`.

Let's take the following model as an example of the first option:

.. highlight:: python

::

  class Truck(OSV):
      _name = "truck"
      _rec_name = "registration"
      registration = fields.Char('Registration number', required=True)
      color = fields.Selection(
              [("white", "White"),
               ("black", "Black"),
              ], "Color")
  Truck ()

The selection define a list of couple, the first member of each tuple
will be the value to store in the database if selected. The second
member is the string (or one of his translations) that the user will
see .

By default the selection is sorted when presented to the user. In some
case it could be useful to avoid this behaviour. In this case one can
use the ``sort`` argument, like:

.. highlight:: python

::

 size = fields.Selection([("small","Small"),
                          ("average", "Average"),
                          ("big", "Big")], "Size", sort=False)

If we want overwrite the list of available colors in another module, the
following will work as expected (See :ref:`define_inheritance`):

.. highlight:: python

::

  class Truck(OSV):
      _name = "truck"
      color = fields.Selection(
              [("white", "White"),
               ("black", "Black"),
               ("red", "Red"),
              ], "Color")
  Truck ()

But this can create problems if a third module wants to add other
colors or if the base module evolve.

The solution is to extend the list:

.. highlight:: python

::

  class Truck(OSV):
      _name = "truck"

      def __init__(self):
          super(Truck, self).__init__()
          self.color.selection += [('red', 'Red')]
  Truck ()

.. _define_tree:

How to define tree structures
+++++++++++++++++++++++++++++

Todo: letf, right and child_of.


.. _use_function:

How to use function fields
++++++++++++++++++++++++++

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
````````````````````````````

The first variant we can use is tho define a unique function for
several fields. Let's consider this new field:

.. highlight:: python

::

  total_service = fields.Function('get_total', type='float', string='Total Service')



Which return the total for the invoice lines of kind *service*. Thus
the method ``get_total`` can be defined this way:

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


Search on function fields
`````````````````````````

Another improvement is to provide a search function. Indeed without it
the user will not be able to search across invoice for a certain
amount.  If we forget about the ``total_service`` field a first
solution could be something like this:

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


One should note that this implementation will be very slow for a big
number of invoices.


Write on function fields
````````````````````````
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


This naive example is another (inefficient) way to handle default value on the
``name`` field.


Fields options
^^^^^^^^^^^^^^

Options are available on all type of fields, except when stated
otherwise in the description.

   * ``readonly``: A boolean, when set to ``True`` the field is not
     editable in the interface.

   * ``required``: A boolean. When a field is required a ``NOT NULL``
     constraint is added in the database. It appear with a blue
     background in the interface.

   * ``help``: A text to be show in the interface on mouse-over.

   * ``select``: An integer. When equal to ``1``, an index is
     created in the database and the field appear in the search box on
     list view. When equal to ``2`` the field appear in the *Advanced
     Search* part of the search box.

   * ``on_change``: A list of values. If set, the client will call
     the method ``on_change_<field_name>`` when a user change the field
     and pass this list of values as argument. This method must return
     a dictionary ``{field_name: new_value}`` for all the field that
     must be updated.

   * ``states``: A dictionary. Keys are name of other options and
     values are python expression. This allow to update dynamically
     options for the current field. E.g.: ``states={"readonly":
     "total > 10"}``.

   * ``domain``: A domain on the current field. E.g.: ``[('name',
     '!=', 'Steve')]`` on the ``party`` field of the
     ``relationship.address`` model will forbid to link the current
     address to a Party for which ``name`` is equal to ``Steve``. See
     :ref:`search_clause` for a more complete explanation.

   * ``translate``: If true, this field is translatable. A flag in the
     interface will allow users to change translate the field for
     the defined language.

   * ``priority``: An integer. Allow to force the order in which
     fields are written in the database. This is used only for fields
     that are not in the table, like One2Many.

   * ``change_default``: When the user choose a default value for a
     field in the current model, the current field with
     ``change_default`` equal to ``True`` can be used as a a condition
     to the default value.

   * ``on_change_with``: Like ``on_change``, but defined the other
     way around: It's a list containing all the fields that must
     update the current field.

   * ``size``: A maximum size on ``Char`` fields.

   * ``digits``: A couple of integer which define the total number of
     digit and the number of decimal to show in the interface. Only
     for ``Float`` and ``Numeric``.

   * ``on_delete``: Sql expression handling behaviour when a the
     target of a ``Many2One`` is removed. Possible values:
     ``CASCADE``, ``NO ACTION``, ``RESTRICT``, ``SET DEFAULT``, ``SET
     NULL`` (default).

   * ``context``: A string defining a diction nay which will be given
     to evaluate the relation fields.

   * ``ondelete_origin`` and ``ondelete_target``: Like ``on_delete``
     for the columns of the table supporting a ``Many2Many`` relation.



Manipulating Models
*******************

.. module:: OSV

Create
^^^^^^

.. method:: create(self, cursor, user, vals[, context])

   :param cursor: An instance of the ``Fakecursor`` class.

   :param user: The id of the user initiating the action.

   :param vals: A dictionary containing the values to be written in
                the database.

   :param context: The context of the action.

   :return: An integer, the id of the new record.

Read
^^^^

.. method:: read(self, cursor, user, ids[, fields_names, context])

   :param cursor: An instance of the ``Fakecursor`` class.

   :param user: The id of the user initiating the action.

   :param ids: A list of integer defining the rows to be read.

   :param fields_name: A list of the name of the columns to be
      read. If empty all the columns a read.

   :param context: The context of the action.

   :return: A list of dictionary whose keys are the fields names.

Note: one should favour ``browse`` over ``read``, because it's more
powerful.

Browse
^^^^^^

.. method:: browse(self, cursor, user, ids[, context])

   :param cursor: An instance of the ``Fakecursor`` class.

   :param user: The id of the user initiating the action.

   :param ids: A list of integer defining the rows to be read.

   :param context: The context of the action.

   :return: A ``BrowseRecordList`` instance.

Example usage:

.. highlight:: python

::

   party_obj = self.pool.get('relationship.party')
   parties = party_obj.browse(self, cursor, user, ids, context=None)
   countries = Set()
   for party in parties:
       for address in party.addresses:
           countries.add(party.country.name)


This example collect all the countries connected to a given set of
parties (defined by ``ids``).

One can see that the ``BrowseRecord`` list return by the ``browse`` function
is able to resolve foreign keys by itself and thus allowing to browse
the data in a pythonic way.


Write
^^^^^

.. method::  write(self, cursor, user, ids, vals[, context])

   :param cursor: An instance of the ``Fakecursor`` class.

   :param user: The id of the user initiating the action.

   :param ids: A list of integer defining the rows to be written.

   :param vals: A dictionary containing the values to be written in the
     database.

   :param context: The context of the action.

   :return: ``True``


Delete
^^^^^^

.. method:: delete(self, cursor, user, ids[, context])

   :param self: The current model on which the action take place.

   :param cursor: An instance of the ``Fakecursor`` class.

   :param user: The id of the user initiating the action.

   :param ids: A list of integer defining the rows to be deleted.

   :param context: The context of the action.

   :return: ``True``


Search
^^^^^^

.. method:: search(self, cursor, user, args[, offset, limit, order,context, count, query_string])

   :param self: The current model on which the action take place.

   :param cursor: An instance of the ``Fakecursor`` class.

   :param args: The search clause, see :ref:`search_clause` for
                details.

   :param offset: An integer. Specify the offset in the results.

   :param limit: An integer. The maximum number of results.

   :param order: A list of tuple. The first element of each tuple is a
                 name of the field, the second is ``ASC`` or
                 ``DESC``. E.g.: ``[('date', 'DESC'),('name',
                 'ASC')]``.

   :param context: The context of the action.

   :param count: A boolean. If true, the result is the length of all
     the items found.

   :param query_string: A boolean: If true, the result is a tuple with
                        the generated sql query and his arguments.

   :return: A list of ids.


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
******************

Model Inheritance allow add or override fields, methods and
constraints on existing models. To inherit an existing model (like
``Party`` on the first example), one just need to instantiate a class
with the same ``_name``:

.. highlight:: python

::


  class Car(OSV):
      _name = "vehicle.car"
      _rec_name = model
      model = fields.Char("Model", required=True)
      manufacturer = fields.Char("Manufacturer")
      first_owner = fields.Many2One('relationship.party', 'First Owner')
  Car()

  class Party(OSV):
      _name = "relationship.party"
      current_car = fields.Many2One('vehicle.car', 'Current car')

      def __init__(self):
          super(Party, self).__init__()
          self._sql_constraints += [
              ('party_car_uniq', 'UNIQUE(model)',
                  'Two party cannot use the same car!'),
          ]

  Party()


This show how to define a new model and link an existing one to it.
This is also a way to define reflecting ``Many2One``: It's not
possible to create the two models without using inheritance because
each of the foreign key (``first_owner`` and ``current_car``) need the
other model table.
