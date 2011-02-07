#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from tryton.rpc import RPCProxy
import tryton.rpc as rpc
from tryton.common import DT_FORMAT, DHM_FORMAT, HM_FORMAT, safe_eval
import time
import datetime
from decimal import Decimal
import mx.DateTime
import logging


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
        dom = self.attrs.get('domain', [])
        def eval_domain(domain):
            res = []
            for arg in domain:
                if isinstance(arg, basestring):
                    if arg in ('AND', 'OR'):
                        res.append(arg)
                    else:
                        res.append(model.expr_eval(arg))
                elif isinstance(arg, tuple):
                    res.append(arg)
                elif isinstance(arg, list):
                    res.append(eval_domain(arg))
            return res
        return eval_domain(dom)

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
            if not self.get(model) \
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
        return model.value.get(self.name) or False

    def set_default(self, model, value):
        res = self.set(model, value)
        return res

    def set_on_change(self, model, value):
        return self.set(model, value, modified=True)

    def get_default(self, model):
        return self.get(model)

    def create(self, model):
        return False

    def state_set(self, model, states=('readonly', 'required', 'invisible')):
        state_changes = self.attrs.get('states', {})
        if isinstance(state_changes, basestring):
            try:
                state_changes = safe_eval(state_changes)
            except:
                return
        for key in states:
            if key == 'readonly' and self.attrs.get(key, False):
                continue
            if key in state_changes:
                try:
                    self.get_state_attrs(model)[key] = \
                            model.expr_eval(state_changes[key],
                                    check_load=False)
                except:
                    log = logging.getLogger('record')
                    log.error("Unable to eval %s for field %s (record: %s@%s)"% \
                                  (state_changes[key], self.name, model.id,
                                   model.resource))
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
                log = logging.getLogger('record')
                log.error("Unable to eval %s for field %s (record: %s@%s)"% \
                              (state_changes['value'], self.name, model.id,
                               model.resource))
                return
            if value:
                self.set(model, value, modified=True)

    def get_state_attrs(self, model):
        if self.name not in model.state_attrs:
            model.state_attrs[self.name] = self.attrs.copy()
        if model.mgroup.readonly:
            model.state_attrs[self.name]['readonly'] = True
        return model.state_attrs[self.name]

    def get_timestamp(self, model):
        return {}


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


class NumericField(CharField):

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
        return model.value.get(self.name) or 0

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
        return bool(model.value.get(self.name))


class M2OField(CharField):
    '''
    internal = (id, name)
    '''

    def create(self, model):
        return (False, '')

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
        if model.value.get(self.name):
            if isinstance(model.value[self.name], (int, basestring, long)):
                self.set(model, model.value[self.name])
            if isinstance(model.value[self.name], (int, basestring, long)):
                return model.value[self.name]
            return model.value[self.name][1]
        return False

    def set(self, model, value, modified=False):
        if value and isinstance(value, (int, long)):
            rpc2 = RPCProxy(self.attrs['relation'])
            try:
                result = rpc2.read(value, ['rec_name'], rpc.CONTEXT)
            except:
                return
            value = value, result['rec_name']
        if value and len(value) != 2:
            value = (False, '')
            model.value[self.name + '.rec_name'] = ''
        else:
            if value:
                model.value[self.name + '.rec_name'] = value[1]
            else:
                model.value[self.name + '.rec_name'] = ''
        model.value[self.name] = value or (False, '')
        if modified:
            model.modified = True
            model.modified_fields.setdefault(self.name)

    def set_client(self, model, value, force_change=False):
        internal = model.value[self.name]
        prev_modified = model.modified
        self.set(model, value)
        if (internal[0] or False) != (model.value[self.name][0] or False):
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

    def context_get(self, model, check_load=True, eval_context=True):
        context = super(M2OField, self).context_get(model,
                check_load=check_load, eval_context=eval_context)
        if eval_context and self.attrs.get('datetime_field'):
            context['_datetime'] = model.get_eval(
                    check_load=check_load)[self.attrs.get('datetime_field')]
        return context


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
        return model.value.get(self.name) or []

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

    def rec_name(self, model):
        rpc2 = RPCProxy(self.attrs['relation'])
        try:
            result = rpc2.read(self.get_client(model), ['rec_name'],
                    rpc.CONTEXT)
        except:
            return self.get_client(model)
        return ', '.join(x['rec_name'] for x in result)


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
                parent=model, parent_name=self.attrs.get('relation_field', ''),
                context=self.context,
                parent_datetime_field=self.attrs.get('datetime_field'))
        mod.signal_connect(mod, 'model-changed', self._model_changed)
        return mod

    def _model_changed(self, group, model):
        if model.modified:
            model.parent.modified = True
            model.parent.modified_fields.setdefault(self.name)
            self.sig_changed(model.parent)
        model.parent.signal('record-changed', model.parent)

    def get_client(self, model):
        return model.value.get(self.name)

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
            result.append(('unlink', [x.id for x in \
                    model.value[self.name].model_removed]))
        if model.value[self.name].model_deleted:
            result.append(('delete', [x.id for x in \
                    model.value[self.name].model_deleted]))
        return result

    def get_timestamp(self, model):
        if not model.value[self.name]:
            return {}
        result = {}
        for model2 in (model.value[self.name].models \
                + model.value[self.name].model_removed \
                + model.value[self.name].model_deleted):
             result.update(model2.get_timestamp())
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
                parent=model, parent_name=self.attrs.get('relation_field', ''),
                context=self.context,
                parent_datetime_field=self.attrs.get('datetime_field'))
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
                parent_name=self.attrs.get('relation_field', ''),
                context=self.context,
                parent_datetime_field=self.attrs.get('datetime_field'))
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

    def state_set(self, model, states=('readonly', 'required', 'invisible')):
        super(O2MField, self).state_set(model, states=states)
        if self.get_state_attrs(model).get('readonly', False):
            model.value[self.name].readonly = True
        else:
            model.value[self.name].readonly = False

    def get_removed_ids(self, model):
        return [x.id for x in model.value[self.name].model_removed]


class ReferenceField(CharField):

    def get_client(self, model):
        if model.value.get(self.name):
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
        #model.value[self.name] = value
        self.set(model, value)
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
        if isinstance(value, basestring):
            model, ref_id = value.split(',')
            value = model, (ref_id, record.value.get(self.name + '.rec_name'))
        ref_model, (ref_id, ref_str) = value
        if ref_model:
            ref_id = int(ref_id)
            if not ref_id:
                ref_str = ''
            if not ref_str and ref_id:
                rpc2 = RPCProxy(ref_model)
                try:
                    result = rpc2.read(ref_id, ['rec_name'],
                            rpc.CONTEXT)['rec_name']
                except:
                    return
                if result:
                    model.value[self.name] = ref_model, (ref_id, result)
                    model.value[self.name + '.rec_name'] = result
                else:
                    model.value[self.name] = ref_model, (0, '')
                    model.value[self.name + '.rec_name'] = ''
            else:
                model.value[self.name] = ref_model, (ref_id, ref_str)
                model.value[self.name + '.rec_name'] = ref_str
        else:
            model.value[self.name] = ref_model, (ref_id, ref_id)
            if self.name + '.rec_name' in model.value:
                del model.value[self.name + '.rec_name']
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
