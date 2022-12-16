.. _topics-wizard:

======
Wizard
======

A wizard describes a series of steps defined as :class:`trytond.wizard.State`.
The wizard stores data in ``ir.session.wizard`` between states.

The basics:

    * Each wizard is a Python class that subclasses
      :class:`trytond.wizard.Wizard`.

    * The states of the wizard are attributes that are instances of
      :class:`trytond.wizard.State`.

Example
=======

This example defines a wizard which export translations

.. highlight:: python

::

    from trytond.wizard import Wizard, StateView, StateTransition, Button
    from trytond.pool import Pool

    class TranslationExport(Wizard):
        "Export translation"
        __name__ = "ir.translation.export"

        start = StateView('ir.translation.export.start',
            'ir.translation_export_start_view_form', [
                Button('Cancel', 'end', 'tryton-cancel'),
                Button('Export', 'export', 'tryton-ok', default=True),
                ])
        export = StateTransition()
        result = StateView('ir.translation.export.result',
            'ir.translation_export_result_view_form', [
                Button('Close', 'end', 'tryton-close'),
                ])

        def transition_export(self):
            pool = Pool()
            translation_obj = pool.get('ir.translation')
            file_data = translation_obj.translation_export(
                self.start.language.code, self.start.module.name)
            self.result.file = buffer(file_data)
            return 'result'

        def default_result(self, fields):
            return {
                'file': self.result.file,
                }

    Pool.register(TranslationExport, type_='wizard')

The class must be registered in the :ref:`Pool <ref-pool>`.
