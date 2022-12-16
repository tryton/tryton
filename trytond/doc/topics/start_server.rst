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

.. note:: When using multiple config files the order is importart as last
          entered files will override the items of first files

WSGI server
-----------

If you prefer to run Tryton inside your own WSGI server instead of the simple
server of Werkzeug, you can use the application `trytond.application.app`.
Following environment variables can be set:

 * `TRYTOND_CONFIG`: Point to :ref:`configuration <topics-configuration>` file.
 * `TRYTOND_LOGGING_CONFIG`: Point to :ref:`logging <topics-logs>` file.
 * `TRYTOND_DATABASE_NAMES`: A list of database names in CSV format, using
   python default dialect.

.. warning:: You must manage to serve the static files from the web root.

Cron service
============

If you want to run some scheduled actions, you must also run the cron server
with this command line::

    trytond-cron -c <config file> -d <database>

The server will wake up every minutes and preform the scheduled actions defined
in the `database`.

Worker service
==============

If you want to use a pool of workers to run :ref:`asynchronously some tasks
<topics-task-queue>`, you must activate the worker in the `queue` section of
the :ref:`configuration <topics-configuration>` and run the worker manager with
this command line::

    trytond-worker -c <config file> -d <database>

The manager will dispatch tasks from the queue to a pool of worker processes.

Services options
================

You will find more options for those services by using `--help` arguments.
