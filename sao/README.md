sao
===

Prerequisites
-------------

 * Node.js v24 or later (https://nodejs.org/)

Installation
------------

Once you've downloaded and unpacked the sao source release, enter the directory
where the archive was unpacked, and run:

    $ npm install --omit=dev

Development
...........

For development, you have to run instead:

    $ npm install
    $ grunt

Setup
-----

Note that the entry `root` in the section `[web]` of `trytond.conf` must be set
to the directory where the package was unpacked.
