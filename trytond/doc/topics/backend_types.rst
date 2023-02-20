.. _topics-backend_types:

Backend Types supported
=======================

This table give a comprehensive list of the SQL Types that are expected to be
supported by the database backends. If the type is not supported then the
backend will have to emulate the behavior described here.

The columns are in the following order:

* The SQL type [#]_ representing the field
* The python type expected on input
* The python type received on output

.. _`SQL 92`: https://en.wikipedia.org/wiki/SQL-92
.. _`PostgreSQL type`: https://www.postgresql.org/docs/current/static/datatype.html

``None`` will represent the ``NULL`` value and vice versa, it can be used as
input or output for any SQL type.

+----------------------+----------------------+----------------------+
| SQL Type             | Python input type    | Python output type   |
+======================+======================+======================+
| ``BOOL``             | bool                 | bool                 |
+----------------------+----------------------+----------------------+
| ``SMALLINT``         | int                  | int                  |
+----------------------+----------------------+----------------------+
| ``INTEGER``          | int                  | int                  |
+----------------------+----------------------+----------------------+
| ``BIGINT``           | int                  | int                  |
+----------------------+----------------------+----------------------+
| ``REAL``             | float / int          | float                |
+----------------------+----------------------+----------------------+
| ``FLOAT``            | float / int          | float                |
+----------------------+----------------------+----------------------+
| ``NUMERIC``          | decimal.Decimal_     | decimal.Decimal_     |
+----------------------+----------------------+----------------------+
| ``VARCHAR`` /        | str                  | str                  |
| ``VARCHAR(length)``  |                      |                      |
+----------------------+----------------------+----------------------+
| ``TEXT``             | str                  | str                  |
+----------------------+----------------------+----------------------+
| ``TIMESTAMP``        | datetime.datetime_   | datetime.datetime_   |
|                      | [#utc_tz]_           | [#utc_tz]_           |
+----------------------+----------------------+----------------------+
| ``DATETIME``         | datetime.datetime_   | datetime.datetime_   |
|                      | without microseconds | without microseconds |
|                      | [#utc_tz]_           | [#utc_tz]_           |
+----------------------+----------------------+----------------------+
| ``DATE``             | datetime.date_       | datetime.date_       |
+----------------------+----------------------+----------------------+
| ``TIME``             | datetime.time_       | datetime.time_       |
+----------------------+----------------------+----------------------+
| ``INTERVAL``         | datetime.timedelta_  | datetime.timedelta_  |
+----------------------+----------------------+----------------------+
| ``BLOB``             | bytes                | bytes                |
+----------------------+----------------------+----------------------+
| ``JSON``             | dict                 | dict                 |
+----------------------+----------------------+----------------------+

.. [#] Corresponding to the `SQL 92`_ standard or to a `PostgreSQL type`_.
.. [#utc_tz] datetime objects are in UTC but without timezone.

.. _datetime.date: https://docs.python.org/library/datetime.html#date-objects
.. _datetime.datetime: https://docs.python.org/library/datetime.html#datetime-objects
.. _datetime.time: https://docs.python.org/library/datetime.html#time-objects
.. _datetime.timedelta: https://docs.python.org/library/datetime.html#timedelta-objects
.. _decimal.Decimal: https://docs.python.org/library/decimal.html#decimal-objects
