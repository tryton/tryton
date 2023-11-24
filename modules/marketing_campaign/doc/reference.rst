*************
API Reference
*************

Parameter
=========

.. class:: Parameter

   The *Parameter* is a mixin_ to define marketing parameters like `Campaign
   <model-marketing.campaign>`.

.. classmethod:: Parameter.from_name(name[, create])

   Return the parameter instance for the name.
   If ``create`` is set and no instance is found, a new instance is created.

Campaign
========

.. class:: MarketingCampaignMixin

   The *MarketingCampaignMixin* is a mixin_ to add marketing parameters to a
   :class:`~trytond:trytond.model.Model`.
   They are filled by default using
   the string value from the
   :attr:`~trytond:trytond.transaction.Transaction.context` key of the same
   name.

.. classmethod:: MarketingCampaignMixin.marketing_campaign_fields

   Yield the field names of the :class:`Parameter` fields.

.. class:: MarketingCampaignUTM

   The *MarketingCampaignUTM* is a mixin_ that helps to add UTM_ parameters to
   URL.

.. _mixin: https://en.wikipedia.org/wiki/Mixin
.. _UTM: https://en.wikipedia.org/wiki/UTM_parameters
