sao
===

Prerequisites
-------------

 * Node.js 0.8.0 or later (http://nodejs.org/)

Installation
------------

Once you've downloaded and unpacked the sao source release, enter the directory
where the archive was unpacked, and run:

    $ npm install --production --legacy-peer-deps

Development
...........

For development, you have to run instead:

    $ npm install --legacy-peer-deps
    $ grunt

Setup
-----

Note that the entry `root` in the section `[web]` of `trytond.conf` must be set
to the directory where the package was unpacked.
