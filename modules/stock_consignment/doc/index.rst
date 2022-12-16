Stock Consignment Module
########################

The stock consignment modules allow to manage consignment stock from supplier
or at customer warehouse.

The consignment stock from supplier is managed by creating a supplier location
under the company's warehouse storage. The location can be filled using an
Internal Shipment from the external supplier location. The products are used
also by using an Internal Shipment from the consignment location to a storage
location. In this case, a supplier invoice line is created for the supplier
defined on the location.

The consignment stock at customer warehouse is managed by creating a storage
location under the customer location. The location can be filled using an
Internal Shipment from a warehouse. It is possible to define a lead time
between the warehouse and the storage location. The products are used also by
using an Internal Shipment from the consignment location to a customer
location. In this case, a customer invoice line is created for the customer
defined on the location.

It is allowed to make inventory for those consignment locations.

A new field is added to Location:

- Consignment Party: The party invoiced when consignment is used.
