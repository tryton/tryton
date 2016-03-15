.. _topics-setup-database:

=======================
How to setup a database
=======================

The database section of the :ref:`configuration <topics-configuration>` must be
set before starting.

Create a database
=================

Depending of the database backend choosen, you must create a database (see the
documentation of the choosen backend). The user running `trytond` must be
granted the priviledge to create tables. For backend that has the option, the
encoding of the database must be set to `UTF-8`.

Initialize a database
=====================

A database can be initialized using this command line::

    trytond-admin -c <config file> -d <database name> --all

At the end of the process, `trytond-admin` will ask to set the password for the
`admin` user.
