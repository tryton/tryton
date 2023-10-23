# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    from backports.entry_points_selectable import entry_points
except ImportError:
    from importlib.metadata import entry_points


def register():
    from . import (
        access, copy_, export_data, field_binary, field_boolean, field_char,
        field_context, field_date, field_datetime, field_dict, field_float,
        field_function, field_integer, field_many2many, field_many2one,
        field_multiselection, field_numeric, field_one2many, field_one2one,
        field_reference, field_selection, field_text, field_time,
        field_timedelta, history, import_data, mixin, model, model_log,
        modelsql, modelstorage, modelview, mptt, multivalue, path, resource,
        rule, tree, trigger, wizard, workflow)

    access.register('tests')
    copy_.register('tests')
    export_data.register('tests')
    field_binary.register('tests')
    field_boolean.register('tests')
    field_char.register('tests')
    field_context.register('tests')
    field_date.register('tests')
    field_datetime.register('tests')
    field_dict.register('tests')
    field_float.register('tests')
    field_function.register('tests')
    field_integer.register('tests')
    field_many2many.register('tests')
    field_many2one.register('tests')
    field_multiselection.register('tests')
    field_numeric.register('tests')
    field_one2many.register('tests')
    field_one2one.register('tests')
    field_reference.register('tests')
    field_selection.register('tests')
    field_text.register('tests')
    field_time.register('tests')
    field_timedelta.register('tests')
    history.register('tests')
    import_data.register('tests')
    mixin.register('tests')
    model.register('tests')
    modelsql.register('tests')
    modelstorage.register('tests')
    modelview.register('tests')
    model_log.register('tests')
    mptt.register('tests')
    multivalue.register('tests')
    path.register('tests')
    resource.register('tests')
    rule.register('tests')
    tree.register('tests')
    trigger.register('tests')
    wizard.register('tests')
    workflow.register('tests')

    for test_ep in entry_points().select(group='trytond.tests'):
        test_module = test_ep.load()
        if hasattr(test_module, 'register'):
            test_module.register('tests')
