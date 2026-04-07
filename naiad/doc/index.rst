==================
Tryton REST Client
==================

A library to access Tryton's REST API.

Example of usage
----------------

   >>> from naiad import Client, Record

Configuration
~~~~~~~~~~~~~

   >>> import os
   >>> url = os.environ.get('NAIAD_URL', 'https://localhost:8000/:memory:')
   >>> client = Client(url, os.getenv('NAIAD_KEY'))

Creating a new group
~~~~~~~~~~~~~~~~~~~~

   >>> group = Record('res.group')
   >>> group.name = "New Group"
   >>> group = client.store(group)
   >>> group.id >= 0
   True

Searching a user
~~~~~~~~~~~~~~~~

   >>> admin, = client.search(
   ...      'res.user', [('login', '=', 'admin')], fields=['login'])
   >>> admin.login
   'admin'

Modifying a user
~~~~~~~~~~~~~~~~

   >>> admin.signature = "Administrator"
   >>> admin.groups = [group]
   >>> admin = client.store(admin, fields=['signature', 'groups.id'])
   >>> admin.signature
   'Administrator'
   >>> group in admin.groups
   True

Calling an action
~~~~~~~~~~~~~~~~~

   >>> _ = client.action(admin, 'reset_password')

Fetching a report
~~~~~~~~~~~~~~~~~

   >>> filename, content = client.report('res.user.email_reset_password', admin.id)

.. toctree::
   :maxdepth: 2

   releases
