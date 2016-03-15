.. _topics-start-server:

=======================
How to start the server
=======================

Web service
===========

You can start the default web server bundled in Tryton with this command line::

    trytond -c <config file>

The server will wait for client connections on the interface defined in the
`web` section of the :ref:`configuration <topics-configuration>`.

WSGI server
-----------

If you prefer to run Tryton inside your own WSGI server instead of the simple
server of Werkzeug, you can use the application `trytond.application.app` and
set the environment variable `TRYTOND_CONFIG` to point to the
:ref:`configuration <topics-configuration>`.

.. warning:: You must manage to serve the static files from the web root.

Cron service
============

If you want to run some scheduled actions, you must also run the cron server
with this command line::

    trytond-cron -c <config file> -d <database>

The server will wake up every minutes and preform the scheduled actions defined
in the `database`.

Services options
================

You will find more options for those services by using `--help` arguments.
