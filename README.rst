######
Tryton
######

Tryton is business software, ideal for companies of any size, easy to use,
complete and 100% Open Source.

This repository contains the source for all the packages of Tryton.

Setup
=====

It is recommended to isolate the development within a Python `virtual
environment <https://docs.python.org/tutorial/venv.html>`_.

From the root directory of the repository run:

.. code-block:: console

   .hooks/update_requirements
   .hooks/link_modules

.. warning::

   The process of updating requirements files may take some time.

Install the dependencies with:

.. code-block:: console

   pip install -e trytond -e tryton -e proteus -r requirements.txt -r requirements-dev.txt

Automate
========

To automate the process, add the following lines to the ``[hooks]`` section of
the ``.hg/hgrc``:

.. code-block:: ini

   [hooks]
   update.modules = .hooks/link_modules
   update.requirements = .hooks/update_requirements

On ``hg update``, the first hook will automatically create symlinks for modules
and the second hook will automatically generate requirements files.

Submit Change
=============

For information about how to submit change, please read on and follow the
`guidelines <https://www.tryton.org/develop>`_.
