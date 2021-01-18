*************
Configuration
*************

The *Account Module* uses values from settings in the ``[account]`` section
of the :doc:`configuration file <trytond:topics/configuration>`.

.. _config-account.reconciliation_chunk:

``reconciliation_chunk``
========================

The ``reconciliation_chunk`` defines the size of each block of sequential
`Account Move Lines <model-account.move.line>` that are searched for
`Reconciliation <model-account.move.reconciliation>` proposals.
Larger chunk sizes allow more lines to be considered together, and sometimes
better matches to be found.

.. warning::

   The number of combinations of lines considered, and consequently the search
   time, increases exponentially along with the chunk size.
   So you should keep this setting to a relatively low value.

.. seealso::

   The `Reconcile Accounts <wizard-account.reconcile>` wizard for details
   of how this setting is used.

The default value is: ``10``
