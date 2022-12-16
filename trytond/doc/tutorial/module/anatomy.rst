.. _tutorial-module-anatomy:

Anatomy of a module
===================

A Tryton module is a `python module`_ thus it is a directory that contains a
:ref:`__init__.py <topics-modules-init>` file.

A Tryton module must also contain a :ref:`tryton.cfg
<topics-modules-tryton-cfg>` file which is used to define the dependencies
between modules and also lists the :ref:`XML files <topics-modules-xml-files>`
that must be loaded by Tryton.

Usually a module will define views used in the user interface, those views are
described by XML files stored in the :file:`view` directory.

Translations are handled with `po files`_ that sit in the :file:`locale`
directory, one file per language.

Let's continue with :ref:`creating the models <tutorial-module-model>`

.. _`python module`: https://docs.python.org/tutorial/modules.html
.. _`po files`: https://www.gnu.org/software/gettext/manual/html_node/PO-Files.html
