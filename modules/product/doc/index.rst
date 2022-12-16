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
- Code, a common prefix for all products. If a sequence is set on product
  configuration the code will be read-only and filled using the sequence.
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
  cost of all the items that are in stock. It's default value can be defined
  on product configuration.
- Default UOM. The default UOM for this product. Used for example to
  express stock levels.
- Active, allow to disable a product.


The Product model extends the Product Template with two fields: Code (aka SKU_)
and Description. If a sequence is set on product configuration the code will be
read-only and will be filled in using the sequence. It's also possible to
define a list of identifiers on product. An identifier is composed by a type
and a code. The following types are available:

    * International Article Number (EAN)
    * International Standard Audiovisual Number (ISAN)
    * International Standard Book Number (ISBN)
    * International Standard Identifier for Libraries (ISIL)
    * International Securities Identification Number (ISIN)
    * International Standard Music Number (ISMN)

.. _SKU: https://en.wikipedia.org/wiki/Stock_keeping_unit

Configuration
*************

The product module uses the section `product` to retrieve some parameters:

- `price_decimal`: defines the number of decimal digits with which the unit
  prices are stored. The default value is `4`.

- `uom_conversion_decimal`: defines the number of decimal digits with which the
  conversion rates and factors of UoM are stored. The default value is `12`.

.. warning::
    They can not be lowered once a database is created.
..
