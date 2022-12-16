Company Module
##############

The company module defines the concepts of company and employee and
extend the user model.


Company
*******

The company model extends the party model and add several fields: the
currency, the list of employees and header and footer texts for
reports. There is also a parent company field which allow to setup
companies in a tree structure. The company model represent the actual
organisation the users of Tryton are members of.


Employee
********

The employee model extend the party model with a company field. The
employee model represent the actual employees of the companies defined
in Tryton. An employee can be optionally linked to a user trough the
user form.


User
****

Are added to the user model: a main company, a company and an employee
field. The company field defines the current company of the user, this
current company will influence the data this user see in Tryton: most
of the records that are linked to a company will only be available for
users in this very company. The main company define which current
company a user can choose: either the main company itself or one of
the children companies.
