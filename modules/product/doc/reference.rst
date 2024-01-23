API Reference
*************

Price
=====

.. data:: trytond.modules.product.price_digits

   A :py:class:`tuple <tuple>` containing the digits to use to store unit
   prices.

.. function:: trytond.modules.product.round_price(value[, rounding])

   Round the value following ``rounding`` to be stored as unit price.

Units of Measure conversion
===========================

.. data:: trytond.modules.product.uom_conversion_digits

   A :py:class:`tuple <tuple>` containing the digits to use to store conversion
   rates or factors.

Product Deactivatable
=====================

.. class:: trytond.modules.product.TemplateDeactivatableMixin

   A :class:`~trytond:trytond.model.DeactivableMixin` that includes the soft
   deletion state of the ``template`` record for record soft deletion.

.. class:: trytond.modules.product.ProductDeactivatableMixin

   A :class:`~trytond.modules.product.TemplateDeactivatableMixin` that includes
   the soft deletion state of the ``product`` record for record soft deletion.
