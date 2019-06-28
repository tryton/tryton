.. _topics-configuration:

=============================
Configuration file for Tryton
=============================

The configuration file controls some aspects of the behavior of Tryton.
The file uses a simple ini-file format. It consists of sections, led by a
`[section]` header and followed by `name = value` entries:

.. highlight:: ini

::

    [database]
    uri = postgresql://user:password@localhost/
    path = /var/lib/trytond

For more information see ConfigParser_.

.. _ConfigParser: http://docs.python.org/2/library/configparser.html

The default value of any option can be changed using environment variables
with names using this syntax: `TRYTOND_<SECTION>__<NAME>`.

Sections
========

This section describes the different main sections that may appear in a Tryton
configuration file, the purpose of each section, its possible keys, and their
possible values.
Some modules could request the usage of other sections for which the guideline
asks them to be named like their module.

web
---

Defines the behavior of the web interface.

listen
~~~~~~

Defines the couple of host (or IP address) and port number separated by a colon
to listen on.

Default `localhost:8000`

hostname
~~~~~~~~

Defines the hostname.

root
~~~~

Defines the root path served by `GET` requests.

Default: Under the `www` directory of user's home running `trytond`.

num_proxies
~~~~~~~~~~~

The number of proxy servers in front of `trytond`.

Default: 0

database
--------

Defines how the database is managed.

uri
~~~

Contains the URI to connect to the SQL database. The URI follows the RFC-3986_.
The typical form is:

    database://username:password@host:port/

Default: `sqlite://`

The available databases are:

PostgreSQL
**********

`pyscopg2` supports two type of connections:

    - TCP/IP connection: `postgresql://user:password@localhost:5432/`
    - Unix domain connection: `postgresql://username:password@/`

SQLite
******

The only possible URI is: `sqlite://`

MySQL
*****

Same as for PostgreSQL.

path
~~~~

The directory where Tryton stores files and so the user running `trytond`
must have write access on this directory.

Default: The `db` folder under the user home directory running `trytond`.

list
~~~~

A boolean value to list available databases.

Default: `True`

retry
~~~~~

The number of retries when a database operational error occurs during a request.

Default: `5`

language
~~~~~~~~

The main language of the database that will be used for storage in the main
table for translations.

Default: `en`

request
-------

max_size
~~~~~~~~

The maximum size in bytes of unauthenticated request (zero means no limit).

Default: 2MB

max_size_authenticated
~~~~~~~~~~~~~~~~~~~~~~

The maximum size in bytes of an authenticated request (zero means no limit).

Default: 2GB


cache
-----

Defines size of various cache.

model
~~~~~

The number of different model kept in the cache per transaction.

Default: `200`

record
~~~~~~

The number of record loaded kept in the cache of the list.
It can be changed locally using the `_record_cache_size` key in
:attr:`Transaction.context`.

Default: `2000`

field
~~~~~

The number of field to load with an `eager` :attr:`Field.loading`.

Default: `100`

clean_timeout
~~~~~~~~~~~~~

The minimum number of seconds between two cleanings of the cache.

Default: `300`

queue
-----

worker
~~~~~~

Activate asynchronous processing of the tasks. Otherwise they are performed at
the end of the requests.

Default: `False`

table
-----

This section allows to override the default generated table name for a
:class:`ModelSQL`. The main goal is to bypass limitation on the name length of
the database backend.
For example::

    [table]
    account.invoice.line = acc_inv_line
    account.invoice.tax = acc_inv_tax

ssl
---

Activates SSL_ on all network protocols.

.. note:: SSL_ is activated by defining privatekey.
        Please refer to SSL-CERT_ on how to use private keys and certficates.

privatekey
~~~~~~~~~~

The path to the private key.

certificate
~~~~~~~~~~~

The path to the certificate.

email
-----

uri
~~~

The SMTP-URL_ to connect to the SMTP server which is extended to support SSL_
and STARTTLS_.
The available protocols are:

    - `smtp`: simple SMTP
    - `smtp+tls`: SMTP with STARTTLS
    - `smtps`: SMTP with SSL

The uri accepts the following additional parameters:

* `local_hostname`: used as FQDN of the local host in the HELO/EHLO commands,
  if omited it will use the value of `socket.getfqdn()`.
* `timeout`: A number of seconds used as timeout for blocking operations. A
  `socket.timeout` will be raised when exceeded. If omited the default timeout
  will be used.


Default: `smtp://localhost:25`

from
~~~~

Defines the default `From` address for emails sent by Tryton.

session
-------

authentications
~~~~~~~~~~~~~~~

A comma separated list of login methods to use to authenticate the user.
By default, Tryton supports only the `password` method which compare the
password entered by the user against a stored hash. But other modules can
define new methods (please refers to their documentation).
The methods are tested following the order of the list.

Default: `password`

max_age
~~~~~~~

The time in seconds that a session stay valid.

Default: `2592000` (30 days)

timeout
~~~~~~~

The time in seconds without activity before the session is no more fresh.

Default: `300` (5 minutes)

max_attempt
~~~~~~~~~~~

The maximum authentication attempt before the server answers unconditionally
`Too Many Requests` for any other attempts. The counting is done on all
attempts over a period of `timeout`.

Default: `5`

max_attempt_ip_network
~~~~~~~~~~~~~~~~~~~~~~

The maximum authentication attempt from the same network before the server
answers unconditionally `Too Many Requests` for any other attempts. The
counting is done on all attempts over a period of `timeout`.

Default: `300`

ip_network_4
~~~~~~~~~~~~

The network prefix to apply on IPv4 address for counting the authentication
attempts.

Default: `32`

ip_network_6
~~~~~~~~~~~~

The network prefix to apply on IPv6 address for counting the authentication
attempts.

Default: `56`

password
--------

length
~~~~~~

The minimal length required for the user password.

Default: `8`

forbidden
~~~~~~~~~

The path to a file containing one forbidden password per line.

entropy
~~~~~~~

The ratio of non repeated characters for the user password.

Default: `0.75`

reset_timeout
~~~~~~~~~~~~~

The time in seconds until the reset password expires.

Default: `86400` (24h)

passlib
~~~~~~~

The path to the `INI file to load as CryptContext
<https://passlib.readthedocs.io/en/stable/narr/context-tutorial.html#loading-saving-a-cryptcontext>`_.
If not path is set, Tryton will use the schemes `bcrypt` or `pbkdf2_sha512`.

Default: `None`

attachment
----------

Defines how to store the attachments

filestore
~~~~~~~~~

A boolean value to store attachment in the :ref:`FileStore <ref-filestore>`.

Default: `True`

store_prefix
~~~~~~~~~~~~

The prefix to use with the `FileStore`.

Default: `None`

bus
---

allow_subscribe
~~~~~~~~~~~~~~~

A boolean value to allow clients to subscribe to bus channels.

Default: `False`

long_polling_timeout
~~~~~~~~~~~~~~~~~~~~

The time in seconds to keep the connection to the client opened when using long
polling for bus messages

Default: `300`

cache_timeout
~~~~~~~~~~~~~

The number of seconds a message should be kept by the queue before being
discarded.

Default: `300`

select_timeout
~~~~~~~~~~~~~~

The timeout duration of the select call when listening on a channel.

Default: `5`

.. _JSON-RPC: http://en.wikipedia.org/wiki/JSON-RPC
.. _XML-RPC: http://en.wikipedia.org/wiki/XML-RPC
.. _RFC-3986: http://tools.ietf.org/html/rfc3986
.. _SMTP-URL: http://tools.ietf.org/html/draft-earhart-url-smtp-00
.. _SSL: http://en.wikipedia.org/wiki/Secure_Sockets_Layer
.. _SSL-CERT: https://docs.python.org/library/ssl.html#ssl.wrap_socket
.. _STARTTLS: http://en.wikipedia.org/wiki/STARTTLS
