Stock Forecast Module
#####################

The stock forecast module provide a simple way to create stock moves
toward customers with a date in the future. This allow other stock
mecanism to anticipate customer demand.


Forecast
********

The forecast form contains:

  - A location from which the products will leave.
  - A destination (which is a customer location).
  - Two dates defining a period in the future.
  - A company
  - A list of forcast lines with:

    - A product
    - A quantity which represent the total demand for the period
    - A minimal quantity for each move.
    - A unit of measure.

The "Complete Forecast" button allow to auto-complete forecast lines
based on previous stock output for dates in the past.

The forecasts are deactivated automatically when their period has passed.


Forecast States
^^^^^^^^^^^^^^^

Draft

  It is the initial state and the state used for edition. No moves are
  linked to the forecast lines

Done

  Once in state done, moves are created for each forecast line:

    - They are spread homogeneously between the two dates of the
      forecast.

    - Move quantities are bigger or equal to the minimal quantity set
      on the forecast line.

Cancel

 On a cancelled forecast all existing moves are cancelled and the form
 is readonly.
