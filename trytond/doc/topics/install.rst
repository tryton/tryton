.. _topics-install:

======================
How to install Tryton
======================

Install Tryton
==============

There are three options to install Tryton:

    * Install the version provided by your operating system distribution. This
      is the quickest and recommended option for those who has operating system
      that distributes Tryton.

    * Install the published package.
      You first need to have `pip <https://pip.pypa.io/>`_ installed.
      Then to install ``trytond`` run:

      .. code-block:: console

         $ python3 -m pip install trytond

      You can also install for example the ``sale`` module with:

      .. code-block:: console

         $ python3 -m pip install trytond_sale

    * Without installation, you need to make sure you have all the dependencies
      installed and then run:

      .. code-block:: console

         $ python3 bin/trytond

      You can register modules by linking them into the ``trytond/modules``
      folder.
