Timesheet User Application
##########################

The timesheet module defines some routes for user applications:

    - `GET` `/<database_name>/timesheet/employees`:
      return the list of the user employees as dictionary with the keys: `id`
      and `name`.

    - `GET` `/<database_name>/timesheet/employee/<int:employee>/works`:
      return the list of works available for the employee. The works are
      dictionary with keys: `id`, `name`, `start` and `end`. The dates are in
      the format `%Y-%m-%d`.

    - `GET` `/<database_name>/timesheet/employee/<int:employee>/lines/<date>`:
      return the list of timesheet lines for the employee at the date
      (`%Y-%m-%d'). The lines are dictionary with keys: `id`, `work`,
      `work.name`, `duration`, `description` and `uuid`. The duration is in
      seconds.

    - `POST` `/<database_name>/timesheet/line`:
      Create a line using the data as dictionary of value. The date must be in
      the format `%Y-%m-%d` and the `duration` in seconds. If a `uuid` value is
      provided, it will update the record if found instead of create a new one.

    - `PUT` `/<database_name>/timesheet/line/<int:line>`:
      Update the line using the data like for the `POST`.

    - `DELETE` `/<database_name>/timesheet/line/<int:line>`:
      Delete the line
