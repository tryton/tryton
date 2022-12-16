.. _topics-install:

======================
How to install Tryton
======================

Install Tryton
==============

There are three easy options to install Tryton:

    * Install the version provided by your operating system distribution. This
      is the quickest and recommended option for those who has operating system
      that distributes Tryton.

    * Install an official release. Once you've downloaded and unpacked a
      trytond source release, enter the directory where the archive was
      unpacked, and run: ``python setup.py install``

      For advanced options, please refer to the easy_install and/or the
      distutils documentation:

          * http://setuptools.readthedocs.io/en/latest/easy_install.html
          * http://docs.python.org/inst/inst.html

    * Without installation, just run ``bin/trytond`` from where the archive was
      unpacked.

.. warning::
      Note that you may need administrator/root privileges for this step, as
      this command will by default attempt to install trytond to the Python
      site-packages directory on your system.
..
