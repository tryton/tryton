Sale Subscription Module
########################

The sale subscription module defines subscription, services and recurrence rule
models.

Subscription
************

A subscription defines how some recurring services are periodically invoiced.
The invoice is generated based on the consumption of each services. Here is the
extensive list of the fields:

- Party: The customer.
- Invoice Address: The invoice address of the customer.
- Number: The internal reference of the subscription.
- Reference: The optional external reference of the subscription.
- Description: An optional description for the subscription.
- Start Date: The date at which the subscription starts.
- End Date: The optional end date of the subscription.
- Invoice Start Date: The date at which the invoice starts to be generated.
- Invoice Recurrence: The definition of the invoicing recurrence.
- Payment Term: The payment term to apply on the invoices.
- Currency: Define the currency to use for the subscription. All service prices
  will be computed accordingly.
- Lines:

    - Service: A required reference to the service subscribed.
    - Description: The description of the service subscribed.
    - Consumption Recurrence: The optional recurrence of consumption of the
      service.
    - Quantity: The quantity consumed on each occurrence.
    - Unit: The unit of measure of the quantity.
    - Unit Price: The unit price of the service expressed in the currency of
      the subscription.
    - Start Date: An optional later start date than the subscription.
    - End Date: An optional earlier end date than the subscription.

- States: The state of the subscription. May take one of the following values:
  Draft, Quotation, Running, Closed, Canceled.
- Company: The company which issue the sale order.

A running subscription can be modified by going back to draft and edit. Some
field may not more be editable if the consumption has already started.
The draft subscription is momentary stopped until it is set back to running.

The consumptions are created by schedulers or by a wizard.
Idem for the creation of the invoices.

Service
*******

A subscription service defines the default consumption of a product. It is
composed of the fields:

- Product: A product of type service.
- Consumption Recurrence: The recurrence at which the service is consumed.
- Consumption Delay: A delay to apply between the date the consumption is
  created and the date of the consumption.

Recurrence Rule
***************

It defines combination of rules which compute the occurrence dates.

- Name: The name of the rule.
- Rules:

    - Exclusive: Define if the rule excludes the resulted dates.
    - Frequency: Daily, Weekly, Monthly, Yearly.
    - Interval: The interval of the frequency
    - By Week Day: Defines the list of weekdays where the recurrence will be
      applied.
    - By Month Day: Defines the list of month days to apply the recurrence to.
    - By Year Day: Defines the list of year days to apply the recurrence to.
    - By Week Number: Defines the list of week numbers (ISO8601) to apply the
      recurrence to.
    - By Month: Defines the list of months to apply the recurrence to.
    - By Position: Defines the list of occurrence positions.
    - Week Start Day.

The computation of occurrences is base on the `python-dateutil library`_.

.. _`python-dateutil library`: https://dateutil.readthedocs.io/en/stable/rrule.html
