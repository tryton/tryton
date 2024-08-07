.. _topics-start-server:

=======================
How to start the server
=======================

Web service
===========

You can start the default web server bundled in ``trytond`` with this command
line:

.. code-block:: console

    $ trytond -c <config file>

The server will wait for client connections on the interface defined in the
:ref:`config-web` section of the configuration.

.. note::

   When using multiple config files the order is important as last entered
   files will override the items of first files

.. warning::
   This runs the of `Werkzeug`_ development server which should not be used on
   production systems.

.. _`Werkzeug`: https://werkzeug.palletsprojects.com/

WSGI server
-----------

If you prefer to run Tryton inside your own WSGI server instead of the simple
server of Werkzeug, you can use the application ``trytond.application.app``.
Following environment variables can be set:

 * ``TRYTOND_CONFIG``: Point to :ref:`topics-configuration`.
 * ``TRYTOND_LOGGING_CONFIG``: Point to :ref:`logging <topics-logs>` file.
 * ``TRYTOND_LOGGING_LEVEL``: An integer to set the default `logging level`_
   (default: ``ERROR``).
 * ``TRYTOND_COROUTINE``: Use coroutine for concurrency.
 * ``TRYTOND_DATABASE_NAMES``: A list of database names in CSV format, using
   python default dialect.

.. warning:: You must manage to serve the static files from the web root.

.. _`logging level`: https://docs.python.org/library/logging.html#logging-levels

Coroutine server
----------------

The Werkzeug server uses thread for concurrency. This is not optimal for the
long-polling request on the :ref:`bus <ref-bus>` as each client consumes
permanently one thread.
You can start the server with coroutine using the option ``--coroutine``.

.. note::
   This will use the pure-Python, gevent-friendly `WSGI server
   <http://www.gevent.org/api/gevent.pywsgi.html>`_.

Cron service
============

If you want to run some :ref:`scheduled actions <topics-cron>`, you must also
run the cron server with this command line:

.. code-block:: console

    $ trytond-cron -c <config file> -d <database>

The server will wake up every minutes and preform the scheduled actions defined
in the ``database``.
You can also launch the command every few minutes from a scheduler with the
option ``--once``.

Worker service
==============

If you want to use a pool of workers to run :ref:`asynchronously some tasks
<topics-task-queue>`, you must activate the :ref:`config-queue.worker` in the
:ref:`config-queue` section of the configuration and run the worker manager
with this command line:

.. code-block:: console

    $ trytond-worker -c <config file> -d <database>

The manager will dispatch tasks from the queue to a pool of worker processes.

Services options
================

You will find more options for those services by using ``--help`` arguments.
