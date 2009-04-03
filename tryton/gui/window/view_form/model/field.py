#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
from tryton.rpc import RPCProxy
import tryton.rpc as rpc
from tryton.common import DT_FORMAT, DHM_FORMAT, HM_FORMAT
import time
import datetime
from decimal import Decimal
import mx.DateTime

class ModelField(object):
    '''
    get: return the values to write to the server
    get_client: return the value for the client widget (form_gtk)
    set: save the value from the server
    set_client: save the value from the widget
    '''

    def __new__(cls, ctype):
        klass = TYPES.get(ctype, CharField)
        return klass


class CharField(object):

    def __init__(self, parent, attrs):
        self.parent = parent
        self.attrs = attrs
        self.name = attrs['name']
        self.internal = False
        self.default_attrs = {}

    def sig_changed(self, model):
        if self.get_state_attrs(model).get('readonly', False):
            return
        if self.attrs.get('on_change', False):
            model.on_change(self.name, self.attrs['on_change'])
        if self.attrs.get('change_default', False):
            model.cond_default(self.attrs['name'], self.get(model))
        model.on_change_with(self.name)

    def domain_get(self, model):
        dom = self.attrs.get('domain', '[]')
        return model.expr_eval(dom)

    def context_get(self, model, check_load=True, eval_context=True):
        context = {}
        context.update(self.parent.context)
        if eval_context:
            field_context_str = self.attrs.get('context', '{}') or '{}'
            field_context = model.expr_eval('dict(%s)' % field_context_str,
                    check_load=check_load)
            context.update(field_context)
        return context

    def validate(self, model):
        res = True
        if bool(int(self.get_state_attrs(model).get('required') or 0)):
            if not model.value[self.name] \
                    and not bool(int(self.get_state_attrs(model
                        ).get('readonly') or 0)):
                res = False
        self.get_state_attrs(model)['valid'] = res
        return res

    def set(self, model, value, modified=False):
        model.value[self.name] = value
        if modified:
            model.modified = True
            model.modified_fields.setdefault(self.name)
        return True

    def get(self, model, check_load=True, readonly=True, modified=False):
        return model.value.get(self.name, False) or False

    def get_eval(self, model, check_load=True):
        return self.get(model, check_load=check_load, readonly=True,
                modified=False)

    def set_client(self, model, value, force_change=False):
        internal = model.value.get(self.name, False)
        prev_modified = model.modified
        self.set(model, value)
        if (internal or False) != (model.value.get(self.name, False) or False):
            model.modified = True
            model.modified_fields.setdefault(self.name)
            try:
                self.sig_changed(model)
            except:
                model.value[self.name] = internal
                model.modified = prev_modified
                return
            model.signal('record-changed', model)

    def get_client(self, model):
        return model.value[self.name] or False

    def set_default(self, model, value):
        res = self.set(model, value)
        return res

    def set_on_change(self, model, value):
        return self.set(model, value, modified=True)

    def get_default(self, model):
        return self.get(model)

    def create(self, model):
        return False

    def state_set(self, model):
        state_changes = self.attrs.get('states', {})
        if isinstance(state_changes, basestring):
            try:
                state_changes = eval(state_changes)
            except:
                return
        for key in ('readonly', 'required', 'invisible'):
            if key == 'readonly' and self.attrs.get(key, False):
                continue
            if key in state_changes:
                try:
                    self.get_state_attrs(model)[key] = \
                            model.expr_eval(state_changes[key],
                                    check_load=False)
                except:
                    continue
            elif key in self.attrs:
                self.get_state_attrs(model)[key] = self.attrs[key]
        if model.mgroup.readonly:
            self.get_state_attrs(model)['readonly'] = True
        if 'value' in state_changes:
            try:
                value = model.expr_eval(state_changes['value'],
                        check_load=False)
            except:
                return
            if value:
                self.set(model, value, modified=True)

    def get_state_attrs(self, model):
        if self.name not in model.state_attrs:
            model.state_attrs[self.name] = self.attrs.copy()
        if model.mgroup.readonly:
            model.state_attrs[self.name]['readonly'] = True
        return model.state_attrs[self.name]


class SelectionField(CharField):

    def set(self, model, value, modified=False):
        if isinstance(value, (list, tuple)):
            value = value[0]
        return super(SelectionField, self).set(model, value,
                modified=modified)


class DateTimeField(CharField):

    def set_client(self, model, value, force_change=False):
        if value:
            date = mx.DateTime.strptime(value, DHM_FORMAT)
            value = datetime.datetime(date.year, date.month, date.day,
                    date.hour, date.minute, int(date.second))
        return super(DateTimeField, self).set_client(model, value,
                force_change=force_change)

    def get_client(self, model):
        value = super(DateTimeField, self).get_client(model)
        if not value:
            return False
        value = mx.DateTime.DateTime(*(value.timetuple()[:6]))
        return value.strftime(DHM_FORMAT)


class DateField(CharField):

    def set_client(self, model, value, force_change=False):
        if value:
            date = mx.DateTime.strptime(value, DT_FORMAT)
            value = datetime.date(date.year, date.month, date.day)
        return super(DateField, self).set_client(model, value,
                force_change=force_change)

    def get_client(self, model):
        value = super(DateField, self).get_client(model)
        if not value:
            return False
        value = mx.DateTime.DateTime(*(value.timetuple()[:6]))
        return value.strftime(DT_FORMAT)


class FloatField(CharField):

    def set_client(self, model, value, force_change=False):
        internal = model.value[self.name]
        prev_modified = model.modified
        self.set(model, value)
        if isinstance(self.attrs.get('digits'), str):
            digits = model.expr_eval(self.attrs['digits'])
        else:
            digits = self.attrs.get('digits', (12, 2))
        if abs(float(internal or 0.0) - float(model.value[self.name] or 0.0)) \
                >= (10.0**(-int(digits[1]))):
            if not self.get_state_attrs(model).get('readonly', False):
                model.modified = True
                model.modified_fields.setdefault(self.name)
                try:
                    self.sig_changed(model)
                except:
                    model.value[self.name] = internal
                    model.modified = prev_modified
                model.signal('record-changed', model)


class NumericField(FloatField):

    def set_client(self, model, value, force_change=False):
        value = Decimal(str(value))
        internal = model.value[self.name]
        prev_modified = model.modified
        self.set(model, value)
        if isinstance(self.attrs.get('digits'), str):
            digits = model.expr_eval(self.attrs['digits'])
        else:
            digits = self.attrs.get('digits', (12, 2))
        if abs((internal or Decimal('0.0')) - (model.value[self.name] or Decimal('0.0'))) \
                >= Decimal(str(10.0**(-int(digits[1])))):
            if not self.get_state_attrs(model).get('readonly', False):
                model.modified = True
                model.modified_fields.setdefault(self.name)
                try:
                    self.sig_changed(model)
                except:
                    model.value[self.name] = internal
                    model.modified = prev_modified
                    return
                model.signal('record-changed', model)


class IntegerField(CharField):

    def get(self, model, check_load=True, readonly=True, modified=False):
        return model.value.get(self.name, 0) or 0

    def get_client(self, model):
        return model.value[self.name] or 0

class BooleanField(CharField):

    def set_client(self, model, value, force_change=False):
        value = bool(value)
        internal = bool(model.value.get(self.name, False))
        prev_modified = model.modified
        self.set(model, value)
        if internal != bool(model.value.get(self.name, False)):
            model.modified = True
            model.modified_fields.setdefault(self.name)
            try:
                self.sig_changed(model)
            except:
                model.value[self.name] = internal
                model.modified = prev_modified
                return
            model.signal('record-changed', model)

    def get(self, model, check_load=True, readonly=True, modified=False):
        return bool(model.value.get(self.name, False))

    def get_client(self, model):
        return bool(model.value[self.name])


class M2OField(CharField):
    '''
    internal = (id, name)
    '''

    def create(self, model):
        return False

    def get(self, model, check_load=True, readonly=True, modified=False):
        if model.value[self.name]:
            if isinstance(model.value[self.name], (int, basestring, long)):
                self.set(model, model.value[self.name])
            if isinstance(model.value[self.name], (int, basestring, long)):
                return model.value[self.name]
            return model.value[self.name][0] or False
        return False

    def get_client(self, model):
        #model._check_load()
        if model.value[self.name]:
            if isinstance(model.value[self.name], (int, basestring, long)):
                self.set(model, model.value[self.name])
            if isinstance(model.value[self.name], (int, basestring, long)):
                return model.value[self.name]
            return model.value[self.name][1]
        return False

    def set(self, model, value, modified=False):
        if value and isinstance(value, (int, basestring, long)):
            rpc2 = RPCProxy(self.attrs['relation'])
            try:
                result = rpc2.name_get([value], rpc.CONTEXT)
            except:
                return
            value = result[0]
        if value and len(value) != 2:
            value = False
        model.value[self.name] = value
        if modified:
            model.modified = True
            model.modified_fields.setdefault(self.name)

    def set_client(self, model, value, force_change=False):
        internal = model.value[self.name]
        prev_modified = model.modified
        self.set(model, value)
        if internal != model.value[self.name]:
            model.modified = True
            model.modified_fields.setdefault(self.name)
            try:
                self.sig_changed(model)
            except:
                model.value[self.name] = internal
                model.modified = prev_modified
                return
            model.signal('record-changed', model)
        elif force_change:
            try:
                self.sig_changed(model)
            except:
                model.value[self.name] = internal
                return
            model.signal('record-changed', model)


class M2MField(CharField):
    '''
    internal = [id]
    '''

    def __init__(self, parent, attrs):
        super(M2MField, self).__init__(parent, attrs)

    def create(self, model):
        return []

    def get(self, model, check_load=True, readonly=True, modified=False):
        return [('set', model.value[self.name] or [])]

    def get_eval(self, model, check_load=True):
        return self.get(model, check_load=check_load, readonly=True,
                modified=False)[0][1]

    def get_client(self, model):
        return model.value[self.name] or []

    def set(self, model, value, modified=False):
        model.value[self.name] = value or []
        if modified:
            model.modified = True
            model.modified_fields.setdefault(self.name)

    def set_client(self, model, value, force_change=False):
        internal = model.value[self.name]
        prev_modified = model.modified
        self.set(model, value, modified=False)
        if set(internal) != set(value):
            model.modified = True
            model.modified_fields.setdefault(self.name)
            try:
                self.sig_changed(model)
            except:
                model.value[self.name] = internal
                model.modified = prev_modified
                return
            model.signal('record-changed', model)

    def get_default(self, model):
        return self.get_client(model)


class O2MField(CharField):
    '''
    internal = ModelRecordGroup of the related objects
    '''

    def __init__(self, parent, attrs):
        super(O2MField, self).__init__(parent, attrs)
        self.context = {}

    def create(self, model):
        from group import ModelRecordGroup
        mod = ModelRecordGroup(self.attrs['relation'], {}, model.window,
                parent=model, parent_name=self.attrs.get('relation_field', ''))
        mod.signal_connect(mod, 'model-changed', self._model_changed)
        return mod

    def _model_changed(self, group, model):
        if model.modified:
            model.parent.modified = True
            model.parent.modified_fields.setdefault(self.name)
            self.sig_changed(model.parent)
        self.parent.signal('record-changed', model)

    def get_client(self, model):
        return model.value[self.name]

    def get(self, model, check_load=True, readonly=True, modified=False):
        if not model.value[self.name]:
            return []
        result = []
        for model2 in model.value[self.name].models:
            if (modified and not model2.is_modified()):
                continue
            if model2.id > 0:
                result.append(('write', model2.id,
                    model2.get(check_load=check_load, get_readonly=readonly,
                        get_modifiedonly=modified)))
            else:
                result.append(('create',
                    model2.get(check_load=check_load, get_readonly=readonly)))
        if model.value[self.name].model_removed:
            result.append(('unlink', model.value[self.name].model_removed))
        if model.value[self.name].model_deleted:
            result.append(('delete', model.value[self.name].model_deleted))
        return result

    def get_eval(self, model, check_load=True):
        result = []
        if not model.value[self.name]:
            return []
        for model2 in model.value[self.name].models:
            result.append(model2.get_eval(check_load=check_load))
        return result

    def set(self, model, value, modified=False):
        from group import ModelRecordGroup
        mod = ModelRecordGroup(self.attrs['relation'], {}, model.window,
                parent=model, parent_name=self.attrs.get('relation_field', ''))
        mod.signal_connect(mod, 'model-changed', self._model_changed)
        model.value[self.name] = mod
        #self.internal.signal_connect(self.internal, 'model-changed',
        #       self._model_changed)
        model.value[self.name].load(value, display=False)
        #self.internal.signal_connect(self.internal, 'model-changed',
        #       self._model_changed)

    def set_client(self, model, value, force_change=False):
        self.set(model, value)
        model.signal('record-changed', model)

    def set_default(self, model, value):
        from group import ModelRecordGroup
        fields = {}
        if value and len(value):
            context = self.context_get(model)
            rpc2 = RPCProxy(self.attrs['relation'])
            try:
                fields_name = []
                for val in value:
                    for fieldname in val.keys():
                        if fieldname not in fields_name:
                            fields_name.append(fieldname)
                fields = rpc2.fields_get(fields_name, context)
            except:
                return False

        model.value[self.name] = ModelRecordGroup(
                self.attrs['relation'], fields, model.window, parent=model,
                parent_name=self.attrs.get('relation_field', ''))
        model.value[self.name].signal_connect(model.value[self.name],
                'model-changed', self._model_changed)
        mod = None
        for record in (value or []):
            mod = model.value[self.name].model_new(default=False)
            mod.set_default(record)
            model.value[self.name].model_add(mod)
        model.value[self.name].current_model = mod
        #mod.signal('record-changed')
        return True

    def set_on_change(self, model, value):
        if value and (value.get('add') or value.get('update')):
            context = self.context_get(model)
            rpc2 = RPCProxy(self.attrs['relation'])
            try:
                fields_name = []
                for val in (value.get('add', []) + value.get('update', [])):
                    for fieldname in val.keys():
                        if fieldname not in fields_name:
                            fields_name.append(fieldname)
                fields = rpc2.fields_get(fields_name, context)
            except:
                return False

        to_remove = []
        for mod in model.value[self.name]:
            if not mod.id:
                to_remove.append(mod)
        if value and value.get('remove'):
            for model_id in value['remove']:
                mod = model.value[self.name].get_by_id(model_id)
                if mod:
                    to_remove.append(mod)
        for mod in to_remove:
            model.value[self.name].remove(mod, signal=False)

        mod = None
        if value and value.get('add') or value.get('update', []):
            model.value[self.name].add_fields(fields, model.value[self.name],
                    signal=False)
            for record in value.get('add', []):
                mod = model.value[self.name].model_new(default=False)
                model.value[self.name].model_add(mod)
                mod.set(record, modified=True, signal=False)

            for record in value.get('update', []):
                if 'id' not in record:
                    continue
                mod = model.value[self.name].get_by_id(record['id'])
                if mod:
                    mod.set(record, modified=True, signal=False)
        model.value[self.name].current_model = mod
        return True

    def get_default(self, model):
        res = [x.get_default() for x in model.value[self.name].models or []]
        return res

    def validate(self, model):
        res = True
        for model2 in model.value[self.name].models:
            if not model2.loaded:
                continue
            if not model2.validate():
                if not model2.is_modified():
                    model.value[self.name].models.remove(model2)
                else:
                    res = False
        if not super(O2MField, self).validate(model):
            res = False
        self.get_state_attrs(model)['valid'] = res
        return res

    def state_set(self, model):
        super(O2MField, self).state_set(model)
        if self.get_state_attrs(model).get('readonly', False):
            model.value[self.name].readonly = True
        else:
            model.value[self.name].readonly = False

    def get_removed_ids(self, model):
        return model.value[self.name].model_removed


class ReferenceField(CharField):

    def get_client(self, model):
        if model.value[self.name]:
            return model.value[self.name]
        return False

    def get(self, model, check_load=True, readonly=True, modified=False):
        if model.value[self.name]:
            if isinstance(model.value[self.name][1], (list, tuple)):
                return '%s,%s' % (model.value[self.name][0],
                        str(model.value[self.name][1][0]))
            else:
                return '%s,%s' % (model.value[self.name][0],
                        str(model.value[self.name][1]))
        return False

    def set_client(self, model, value, force_change=False):
        internal = model.value[self.name]
        prev_modified = model.modified
        model.value[self.name] = value
        if (internal or False) != (model.value[self.name] or False):
            model.modified = True
            model.modified_fields.setdefault(self.name)
            try:
                self.sig_changed(model)
            except:
                model.value[self.name] = internal
                model.modified = prev_modified
                return
            model.signal('record-changed', model)

    def set(self, model, value, modified=False):
        if not value:
            model.value[self.name] = False
            return
        ref_model, ref_id = value.split(',', 1)
        try:
            ref_id = eval(ref_id)
        except:
            pass
        if isinstance(ref_id, (int, basestring, long)) and ref_model:
            rpc2 = RPCProxy(ref_model)
            try:
                result = rpc2.name_get([ref_id], rpc.CONTEXT)
            except:
                return
            if result:
                model.value[self.name] = ref_model, result[0]
            else:
                model.value[self.name] = ref_model, (0, '')
        else:
            model.value[self.name] = ref_model, ref_id
        if modified:
            model.modified = True
            model.modified_fields.setdefault(self.name)

TYPES = {
    'char': CharField,
    'sha': CharField,
    'float_time': FloatField,
    'integer' : IntegerField,
    'biginteger' : IntegerField,
    'float' : FloatField,
    'numeric' : NumericField,
    'many2one' : M2OField,
    'many2many' : M2MField,
    'one2many' : O2MField,
    'reference' : ReferenceField,
    'selection': SelectionField,
    'boolean': BooleanField,
    'datetime': DateTimeField,
    'date': DateField,
}
