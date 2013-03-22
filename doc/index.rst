Project Invoice Module
######################

The Project Invoice module adds invoice methods on project.
The methods are:

- Manual: Tryton doesn't create any invoice.
- On Effort: The invoices are created based on the *Effort* hours for all
  children works in state *Done*.
- On Timesheet: The invoices are created based on the timesheets encoded on all
  children works.
