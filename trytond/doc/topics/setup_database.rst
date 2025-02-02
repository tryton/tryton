.. _topics-setup-database:

=======================
How to setup a database
=======================

The :ref:`config-database` section of the configuration must be set before
starting.

Create a database
=================

Depending of the database backend choosen, you must create a database (see the
documentation of the choosen backend). The user running ``trytond`` must be
granted the priviledge to create tables. For backend that has the option, the
encoding of the database must be set to ``UTF-8``.

Initialize a database
=====================

A database can be initialized using this command line:

.. code-block:: console

    $ trytond-admin -c <config file> -d <database name> --all

At the end of the process, ``trytond-admin`` will ask you to set the email and
password for the ``admin`` `user <model-res.user>` that will be used to connect
to the server from one of the clients for the first time.

.. note::

   These users are different from the database user used in
   :ref:`config-database.uri` of the database section.

Update a database
=================

To upgrade to a new series, the command line is:

.. code-block:: console

    $ trytond-admin -c <config file> -d <database name> --all

.. warning::
   Because the database is modified in place it is important to make a backup before
   running the update.

.. warning::
    Prior to upgrade see if there is no manual action to take on the `migration
    topic`_.

.. _`migration topic`: https://docs.tryton.org/migration

To activate a new language on an existing database, the command line is:

.. code-block:: console

    $ trytond-admin -c <config file> -d <database name> --all -l <language code>

Once activated, the language appears in the user preferences.

When installing new modules, the list of modules must be updated with:

.. code-block:: console

    $ trytond-admin -c <config file> -d <database name> --update-modules-list

Once updated, the new modules can be activated from the client or activated with:

.. code-block:: console

    $ trytond-admin -c <config file> -d <database name> -u <module name> --activate-dependencies
