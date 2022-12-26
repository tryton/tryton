.. _ref-tools-barcode:
.. module:: trytond.tools.barcode

barcode
=======

.. function:: generate_svg(name, code[, width[, height[, border,[ font_size[, text_distance[, background[, foreground]]]]]]])

   Return a :py:class:`~io.BytesIO` containing the SVG image of the named
   barcode.

.. function:: generate_png(name, code[, width[, height[, border[, font_size[, text_distance[, background[, foreground]]]]]]])

   Return a :py:class:`~io.BytesIO` containing the PNG image of the named
   barcode.

.. attribute:: BARCODES

   A set of available barcode names.
