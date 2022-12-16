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

.. [#] Corresponding to the `SQL 92`_ standard or to a `PostgreSQL type`_.
.. _`SQL 92`: http://www.contrib.andrew.cmu.edu/~shadow/sql/sql1992.txt
.. _`PostgreSQL type`: https://www.postgresql.org/docs/current/static/datatype.html

``None`` will represent the ``NULL`` value and vice versa, it can be used as
input or output for any SQL type.

+----------------------+----------------------+----------------------+
| SQL Type             | Python input type    | Python output type   |
+======================+======================+======================+
| ``BOOL``             | bool                 | bool                 |
+----------------------+----------------------+----------------------+
| ``INTEGER``          | int                  | int                  |
+----------------------+----------------------+----------------------+
| ``BIGINT``           | int / long           | int / long           |
|                      | [#pyver_int]_        | [#pyver_int]_        |
+----------------------+----------------------+----------------------+
| ``FLOAT``            | float / int / long   | float                |
|                      | [#pyver_int]_        |                      |
+----------------------+----------------------+----------------------+
| ``NUMERIC``          | decimal.Decimal_     | decimal.Decimal_     |
+----------------------+----------------------+----------------------+
| ``VARCHAR`` /        | str / unicode        | str / unicode        |
| ``VARCHAR(length)``  | [#pyver_str]_        | [#pyver_str]_        |
+----------------------+----------------------+----------------------+
| ``TEXT``             | str / unicode        | str / unicode        |
|                      | [#pyver_str]_        | [#pyver_str]_        |
+----------------------+----------------------+----------------------+
| ``TIMESTAMP``        | datetime.datetime_   | datetime.datetime_   |
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

.. [#pyver_int] in python 2 integers over *sys.maxint* are represented by the
                ``long`` type
.. [#pyver_str] str when using python 3 ; unicode when using python 2
.. [#utc_tz] Datetime objects are not localized to any timezone

.. _datetime.date: https://docs.python.org/library/datetime.html#date-objects
.. _datetime.datetime: https://docs.python.org/library/datetime.html#datetime-objects
.. _datetime.time: https://docs.python.org/library/datetime.html#time-objects
.. _datetime.timedelta: https://docs.python.org/library/datetime.html#timedelta-objects
.. _decimal.Decimal: https://docs.python.org/library/decimal.html#decimal-objects
