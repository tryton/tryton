.. _ref-tools-logging:
.. module:: trytond.tools.logging

logging
=======

.. class:: format_args(args, kwargs[, verbose[, max_args[, max_items]]])

   If ``verbose`` is False, the string representation of this class is a
   shortened version of the arguments taken from ``args`` and from the keyword
   arguments in ``kwargs``. Otherwise, they are fully represented.

   ``max_args`` is the maximum number of arguments shown before using an ellipse.
   ``max_items`` is the maximum number of items shown in each argument before
   using an ellipse.

   In the shortened version, strings and bytes are shortened.
