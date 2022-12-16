.. _topics-setup-database:

=======================
How to setup a database
=======================

The database section of the :ref:`configuration <topics-configuration>` must be
set before starting.

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

At the end of the process, ``trytond-admin`` will ask to set the password for
the ``admin`` user.

Update a database
=================

To upgrade to a new series, the command line is:

.. code-block:: console

    $ trytond-admin -c <config file> -d <database name> --all

.. warning::
    Prior to upgrade see if there is no manual action to take on the `migration
    topic`_.

.. _`migration topic`: https://discuss.tryton.org/c/migration

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
