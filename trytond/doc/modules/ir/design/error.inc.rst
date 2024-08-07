.. _model-ir.error:

Error
=====

The *Error* stores exceptions raised by non interactive processes.
An *Error* can be processed and then solved by a `User <model-res.user>`.
When an *Error* is solved the process that originally reported the error is run
again.

.. note::

   A `scheduled task <model-ir.cron>` deletes the errors after the configured
   `number of days <config-queue.clean_days>`.

.. seealso::

   The Errors can be found by opening the main menu item:

      |Administration --> Scheduler --> Errors|__

      .. |Administration --> Scheduler --> Errors| replace:: :menuselection:`Administration --> Scheduler --> Errors`
      __ https://demo.tryton.org/model/ir.error
