.. _tutorial-module-setup-database:

Initialize the database
=======================

By default Tryton, use an SQLite database stored in the folder :file:`db` of
your home directory.
This can be changed in the ``database`` section of the `configuration
<topics-configuration>`.

Now creating a Tryton database is only a matter of executing the following
commands:

.. code-block:: console

   $ mkdir ~/db
   $ touch ~/db/test.sqlite
   $ trytond-admin -d test --all

You will be prompted to set the administrator email and password.

Once the database is initialized you can run the Tryton server:

.. code-block:: console

    $ trytond

Connecting to the database using a Tryton client you will be greeted by the
module configuration wizard.

We will continue with :ref:`the anatomy of the module <tutorial-module-anatomy>`.
