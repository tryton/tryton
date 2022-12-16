Sale Opportunity Module
#######################

The sale_opportunity module defines the lead/opportunity model.

Lead/Opportunity
****************

The lead and opportunity are defined by the same record but with different state.
Depending on the state, fields of the record become mandatory. Here is the
extensive list of the fields, most of them are optional:

- Party: The customer.
- Address: The main address of the customer.
- Description: The description of the lead/opportunity.
- Reference: The internal reference of the lead/opportunity (will be generated
  automatically at creation).
- Amount: The estimated revenue amount.
- Currency: Define the currency of the amount.
- Probability: The probability of conversion.
- Company: The company which issue the lead/opportunity.
- Employee: The employee responsible of the lead/opportunity.
- Start Date: When the lead started.
- End Date: When the lead ends (automatically set on win, cancel or lost).
- Payment Term: Define which payment term will be used for the future invoice.
- Comment: A text field to add custom comments.
- State: The state of the lead/opportunity. May take one of the following
  values:

    - Lead
    - Opportunity
    - Converted
    - Won
    - Cancelled
    - Lost

- Lines: A list of *Lead/Opportunity* line
- Sales: The list of sales converted from this opportunity.
- History: The list of changes made over time to the lead/opportunity.

The first time an opportunity is converted, a sale is created base on the
information of the opportunity and the lines.
The amount of the opportunity is later updated with the sales amount.
Once all the sales of an opportunity are confirmed (or cancelled with at least
one confirmed), the opportunity is won.
If all the sales of an opportunity are cancelled than the opportunity is lost.

Lead/Opportunity Line
*********************

A lead/opportunity line define a quantity of product that are expected to be sold.

Reports
*******

The sale_opportunity module defines also some reports:

- Opportunities per Employee.
- Opportunities per Month.
- Opportunities per Employee per Month.

which all show:

- The number of leads/opportunities.
- The number of converted opportunities.
- The convertion rate.
- The number of won opportunities.
- The winning rate.
- The number of lost opportunities.

- The total amount of leads/opportunities.
- The total amount of converted opportunities.
- The convertion amount rate.
- The total amount of won opportunities.
- The winning amount rate.
