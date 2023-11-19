.. _tutorial-module-setup:

Setup
=====

Create virtual environment
--------------------------

This step will cover the installation of tryton from a developer perspective.
We will assume that you are already fluent with venv_ and pip_.

Let's create a virtual environment inside your working directory:

.. code-block:: console

   $ python3 -m venv .venv
   $ source .venv/bin/activate
   $ python -m pip install --upgrade pip

Install cookiecutter and mercurial
----------------------------------

To bootstrap the module, we provide a cookiecutter_ template.
First we install cookiecutter_ and mercurial_ with:

.. code-block:: console

   $ python3 -m pip install cookiecutter mercurial

Setup module
------------

The Tryton template can be rendered into a module with:

.. code-block:: console

   $ cookiecutter hg+https://code.tryton.org/tryton --directory cookiecutter-module
   module_name [my_module]: opportunity
   prefix []: tuto
   package_name [tuto_opportunity]:
   version []: x.y.0
   description []:
   author [Tryton]: John Doe
   author_email [bugs@tryton.org]: john@example.com
   fullname []: John Doe
   url [http://www.tryton.org/]: http://www.example.com/
   keywords []:
   test_with_scenario []:

.. note::
   The version number must use the same two first numbers as the Tryton series
   wanted.

Install module
--------------

Now we can install the new module in editable mode:

.. code-block:: console

   $ python3 -m pip install --use-pep517 --editable opportunity

Continue with :ref:`initializing the database <tutorial-module-setup-database>`

.. _pip: https://pip.pypa.io/
.. _venv: https://docs.python.org/library/venv.html
.. _cookiecutter: https://pypi.org/project/cookiecutter/
.. _mercurial: https://www.mercurial-scm.org/
