.. _topics-configuration:

=============================
Configuration file for Tryton
=============================

The configuration file control some aspects of the behavior of Tryton.
The file uses a simple ini-file format. It consists of sections, led by a
`[section]` header and followed by `name = value` entries:

.. highlight:: ini

::

    [database]
    uri = postgresql://user:password@localhost/
    path = /var/lib/trytond

For more information see ConfigParser_.

.. _ConfigParser: http://docs.python.org/2/library/configparser.html

Sections
========

This section describes the different main sections that may appear in a Tryton
configuration file, the purpose of each section, its possible keys, and their
possible values.
Some modules could request the usage of other sections for which the guideline
asks them to be named like their module.

jsonrpc
-------

Defines the behavior of the JSON-RPC_ network interface.

listen
~~~~~~

Defines a comma separated list of couple of host (or IP address) and port numer
separeted by a colon to listen on.
The default value is `localhost:8000`.

hostname
~~~~~~~~

Defines the hostname for this network interface.

data
~~~~

Defines the root path to retrieve data for `GET` request.

xmlrpc
------

Defines the behavior of the XML-RPC_ network interface.

listen
~~~~~~

Same as for `jsonrpc` except it have no default value.

webdav
------

Define the behavior of the WebDAV_ network interface.

listen
~~~~~~

Same as for `jsonrpc` except it have no default value.

database
--------

Defines how database is managed.

uri
~~~

Contains the URI to connect to the SQL database. The URI follows the RFC-3986_.
The typical form is:

    database://username:password@host:port/

The default available databases are:

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

The directory where Tryton should store files and so the user running `trytond`
must have write access on this directory.
The default value is `/var/lib/trytond/`.

list
~~~~

A boolean value (default: `True`) to list available databases.

retry
~~~~~

The number of retries when a database operation error occurs during a request.

language
~~~~~~~~

The main language (default: `en_US`) of the database that will be stored in the
main table for translatable fields.

ssl
---

Activates the SSL_ on all network protocol.

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

The default value is: `smtp://localhost:25`

from
~~~~

Defines the default `From` address when Tryton send emails.

session
-------

timeout
~~~~~~~

The time in second before a session expires.

super_pwd
~~~~~~~~~

Theserver password uses to authenticate database management from the client.
It is encrypted using using the Unix `crypt(3)` routine.
Such password can be generated using this command line::

    python -c 'import getpass,crypt,random,string; print crypt.crypt(getpass.getpass(), "".join(random.sample(string.ascii_letters + string.digits, 8)))'

report
------

unoconv
~~~~~~~

The parameters for `unoconv`.

.. _JSON-RPC: http://en.wikipedia.org/wiki/JSON-RPC
.. _XML-RPC: http://en.wikipedia.org/wiki/XML-RPC
.. _WebDAV: http://en.wikipedia.org/wiki/WebDAV
.. _RFC-3986: http://tools.ietf.org/html/rfc3986
.. _SMTP-URL: http://tools.ietf.org/html/draft-earhart-url-smtp-00
.. _SSL: http://en.wikipedia.org/wiki/Secure_Sockets_Layer
.. _STARTTLS: http://en.wikipedia.org/wiki/STARTTLS
