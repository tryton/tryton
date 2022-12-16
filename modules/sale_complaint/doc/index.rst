Sale Complaint Module
#####################

The sale_complaint module defines Complaint model.

Complaint
*********

The complaint is mainly defined by a customer which complains about a sale or
an invoice. Actions can be taken to solve the complaint. Here is the extensive
list of the fields, most of them are optional:

- Customer: The customer.
- Address: The main address of the customer.
- Date: The date the complaint is filled.
- Number: The internal reference of the complaint (will be generated
  automatically on creation).
- Reference: The optional external reference of the complaint.
- Employee: The employee responsible of the complaint.
- Type: The type of complaint
- Origin: The original document for which the complaint if filled.
- Company: The company against which the complaint is filled.
- Description: The description of the complaint.
- Actions: The actions to take to solve it.
- State:

  - Draft
  - Waiting: The complaint is waiting for approval.
  - Approved: The complaint has been approved by a sale admin.
  - Rejected: The complaint has been rejected by a sale admin.
  - Done: The complaint's actions have been executed.
  - Cancelled

Action
******

A complaint action defines an action to execute to solve the complaint.
There are two types of action: *Create Sale Return* and *Create Credit Note*.
When the origin of the complaint is a line, only this line will proceeded and
it will be possible to define the quantity and the unit price otherwise it is
the all document.

Type
****

It defines the type of complaint per document: *Sale*, *Sale Line*, *Customer
Invoice* and *Customer Invoice Line*.
