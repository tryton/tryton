*************
API Reference
*************

Classification
==============

.. class:: trytond.modules.product_classification.product.ClassificationMixin

   A :class:`~trytond:trytond.model.DeactivableMixin` that defines the
   requirements to implement a product classification.

classification_tree
===================

.. function:: trytond.modules.product_classification.product.classification_tree(name)

   A function that returns a
   :class:`~trytond.modules.product_classification.product.ClassificationMixin`
   which implements :func:`~trytond:trytond.model.tree`.
