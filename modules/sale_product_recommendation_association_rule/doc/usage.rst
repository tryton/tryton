*****
Usage
*****

In order to make recommendations the `Product Association Rules
<model-sale.product.association.rule>` must be computed.

.. _Compute product association rules:

Compute product association rules
=================================

You may want to schedule the computation of rules based on previous `Sales
<sale:model-sale.sale>` using a scheduled task *Compute Sale Product
Association Rules*.
In order to select the sales used, you must define a delay in the
`Configuration <sale:model-sale.configuration>`.
