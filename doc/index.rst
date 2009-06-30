Company Module
##############

The company module defines the concepts of company and employee and
extend the user model.


Company
*******

The company model extends the party model and add several fields: the
currency, the list of employees and header and footer texts for
reports. there is also a parent company field which allow to setup
companies in a tree structure. Creating a company will also create a
corresponding party, but a company is more than that as it represent
the companies of the users and employee who are using Tryton.


Employee
********

An employee is a party that is linked to a company.


User
****

Are added to the user model: a main company, a company and an employee
field. The company field define the current company of the user, this
current company will influence the data this user see in Tryton: most
of the records that are linked to a company will only be available for
users in this very company. The main company define which current
company a user can choose: either the main company itself or one of
the child companies.
