******
Design
******

The *Sale Product Recommendation Association Rule Module* introduces the
following concepts.

.. _model-sale.product.association.rule:

Product Association Rule
========================

The model is used to store the rules learned by the system.
They are composed of antecedents and consequents which are lists of `Products
<product:concept-product>`.
The antecedents is that items that can be found in the data while the
consequents are the items found when combined with the antecedents.

The rule stores also various measures like the *confidence*, *support*, *lift*
and *conviction*.

.. seealso::

   You can learn more on `association rule learning
   <https://en.wikipedia.org/wiki/Association_rule_learning>`_

.. seealso::

   Rules are found by opening the menu item:

      |Products --> Products --> Sale Association Rules|__

      .. |Products --> Products --> Sale Association Rules| replace:: :menuselection:`Products --> Products --> Sale Association Rules`
      __ https://demo.tryton.org/model/sale.product.association.rule
