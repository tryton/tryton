*************
API Reference
*************

Party
=====

.. method:: Party.check_credit_limit(amount[, origin])

   Raise an error if the amount, when credited to the party, reaches the credit
   limit.
   If origin is set then a warning is raised instead of an error.
