Product Module
##############

The Product module defines the following models: Category of Unit of
Measure, Unit of Measure, Product Template, Product and Product
Category.


Category of Unit of Measure
***************************

A Category of Unit of Measure is simply defined by a name.


Unit of Measure
***************

A Unit of Measure is defined by:

- Name.
- Symbol.
- UOM category.
- Rate and a Factor (the later is the inverse of the former).
- Rounding Precision and Display Digits, used to round and display
  quantities expressed in the given UOM.
- Active, allow to disable a UOM.


Product category
****************

The Product Category Model is just composed of a name. Product
Categories are organised in a tree structure.


Product Template and Product
****************************

The product concept in Tryton is composed of two models: Product
Template and Product.

The Product Template model contains the following fields: 

- Name.
- Type, whose value can be *Goods*, *Assets*, *Service*.
- Category.
- List Price, the default sale price expressed in the List Price UOM.
  product.
- List Price UOM.
- Cost Price, the cost for one unit of this product expressed in the
  Cost Price UOM.
- Cost Price UOM.
- Cost Price Method, which can be *Fixed* or *Average*. Defines how
  the cost price should be updated. *Fixed* means that the cost price
  stay unchanged. *Average* means that the cost price is the average
  cost of all the items that are in stock.
- Default UOM. The default UOM for this product. Used for example to
  express stock levels.
- Active, allow to disable a product.


The Product model extend the Product Template with two fields: Code
and Description.

Configuration
*************

The product module uses the section `product` to retrieve some parameters:

- `price_decimal`: defines the number of decimal with which the unit prices are
  stored. The default value is `4`.

.. warning::
    It can not be lowered once a database is created.
..
