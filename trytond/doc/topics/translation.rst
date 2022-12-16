.. _topics-translation:

===========
Translation
===========

The translation of the user interface is provided module-wise.
Translations are stored in the ``locale/`` directory of a module, each language
in a `PO-file <https://en.wikipedia.org/wiki/Gettext#Translating>`_. The
official language files are named after the
`POSIX locale <https://en.wikipedia.org/wiki/Locale#POSIX_platforms>`_
standard, e.g. de_DE.po, es.po, es_AR.po, es_EC.po...

The names of custom language files must match the code of the language in the
Model ir.lang.

If a language is set ``translatable``, the translations will be loaded into
the database on each trytond module update.

Tryton supports derivative translations. This means that if the translation of
a term is missing in one language, it will search on the parent languages.
Also when activate a children language, you must also activate all parents.

Translation Wizards
===================

Set Translations
----------------

The wizard adds new translations to the base language ``en``.

Clean Translations
------------------

The wizard deletes obsolete translations from the database.

Synchronize Translations
------------------------

The wizard updates the translations of the selected language based on the
translations of the base language ``en``. It will also remove duplicate
translations with its direct parent.

Export Translations
-------------------

The wizard requires to select a language and a module and will export the
translations for this selection into a PO-file.


Override translations
=====================

Translations of a module can be overridden by another module. This can be done
by putting a PO file into the ``locale/override`` directory of the module that
shall contain the translations to override.

To override the translation of another module the ``msgctxt`` string must have
the following content:

type:name:module.xml_id

    * ``type``: Value of the field type of ir.translation.
    * ``name``: Value of the field name of ir.translation.
    * ``module``: Value of the field module ir.translation.
    * ``xml_id``: The XML id that is stored in ir.model.data as fs_id

The xml_id part is optional and can be omitted if it is None.
