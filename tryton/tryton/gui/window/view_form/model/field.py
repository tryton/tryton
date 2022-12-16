#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import tryton.rpc as rpc
from tryton.common import DT_FORMAT, DHM_FORMAT, HM_FORMAT, datetime_strftime
import tryton.common as common
from tryton.pyson import PYSONDecoder
import time
import datetime
from decimal import Decimal
import logging


class Field(object):
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

    def sig_changed(self, record):
        if self.get_state_attrs(record).get('readonly', False):
            return
        if self.attrs.get('on_change', False):
            record.on_change(self.name, self.attrs['on_change'])
        if self.attrs.get('change_default', False):
            record.cond_default(self.attrs['name'], self.get(record))
        record.on_change_with(self.name)

    def domain_get(self, record):
        return record.expr_eval(self.attrs.get('domain', []))

    def context_get(self, record, check_load=True, eval_context=True):
        context = {}
        context.update(self.parent.context)
        if eval_context:
            context.update(record.expr_eval(self.attrs.get('context', {}),
                check_load=check_load))
        return context

    def validate(self, record):
        res = True
        if bool(int(self.get_state_attrs(record).get('required') or 0)):
            if not self.get(record) \
                    and not bool(int(self.get_state_attrs(record
                        ).get('readonly') or 0)):
                res = False
        self.get_state_attrs(record)['valid'] = res
        return res

    def set(self, record, value, modified=False):
        record.value[self.name] = value
        if modified:
            record.modified = True
            record.modified_fields.setdefault(self.name)
        return True

    def get(self, record, check_load=True, readonly=True, modified=False):
        return record.value.get(self.name, False) or False

    def get_eval(self, record, check_load=True):
        return self.get(record, check_load=check_load, readonly=True,
                modified=False)

    def get_on_change_value(self, record, check_load=True):
        return self.get_eval(record, check_load=check_load)

    def set_client(self, record, value, force_change=False):
        internal = record.value.get(self.name, False)
        prev_modified = record.modified
        self.set(record, value)
        if (internal or False) != (record.value.get(self.name, False) or False):
            record.modified = True
            record.modified_fields.setdefault(self.name)
            try:
                self.sig_changed(record)
            except Exception:
                record.value[self.name] = internal
                record.modified = prev_modified
                return
            record.signal('record-changed')

    def get_client(self, record):
        return record.value.get(self.name) or False

    def set_default(self, record, value, modified=False):
        res = self.set(record, value, modified=modified)
        return res

    def set_on_change(self, record, value):
        return self.set(record, value, modified=True)

    def get_default(self, record):
        return self.get(record)

    def state_set(self, record, states=('readonly', 'required', 'invisible')):
        state_changes = record.expr_eval(self.attrs.get('states', {}),
                check_load=False)
        for key in states:
            if key == 'readonly' and self.attrs.get(key, False):
                continue
            if key in state_changes:
                self.get_state_attrs(record)[key] = state_changes[key]
            elif key in self.attrs:
                self.get_state_attrs(record)[key] = self.attrs[key]
        if record.group.readonly:
            self.get_state_attrs(record)['readonly'] = True
        if 'value' in state_changes:
            value = state_changes['value']
            if value:
                self.set(record, value, modified=True)

    def get_state_attrs(self, record):
        if self.name not in record.state_attrs:
            record.state_attrs[self.name] = self.attrs.copy()
        if record.group.readonly:
            record.state_attrs[self.name]['readonly'] = True
        return record.state_attrs[self.name]

    def get_timestamp(self, record):
        return {}

    def destroy(self):
        self.parent = None


class SelectionField(CharField):

    def set(self, record, value, modified=False):
        if isinstance(value, (list, tuple)):
            value = value[0]
        return super(SelectionField, self).set(record, value,
                modified=modified)


class DateTimeField(CharField):

    def set_client(self, record, value, force_change=False):
        if value:
            value = datetime.datetime(*time.strptime(value, DHM_FORMAT)[:6])
        return super(DateTimeField, self).set_client(record, value,
                force_change=force_change)

    def get_client(self, record):
        value = super(DateTimeField, self).get_client(record)
        if not value:
            return False
        return datetime_strftime(value, DHM_FORMAT)


class DateField(CharField):

    def set_client(self, record, value, force_change=False):
        if value:
            value = datetime.date(*time.strptime(value, DT_FORMAT)[:3])
        return super(DateField, self).set_client(record, value,
                force_change=force_change)

    def get_client(self, record):
        value = super(DateField, self).get_client(record)
        if not value:
            return False
        return datetime_strftime(value, DT_FORMAT)


class FloatField(CharField):

    def set_client(self, record, value, force_change=False):
        internal = record.value.get(self.name)
        prev_modified = record.modified
        self.set(record, value)
        digits = record.expr_eval(self.attrs.get('digits', (16, 2)))
        if abs(float(internal or 0.0) - float(record.value[self.name] or 0.0)) \
                >= (10.0**(-int(digits[1]))):
            if not self.get_state_attrs(record).get('readonly', False):
                record.modified = True
                record.modified_fields.setdefault(self.name)
                try:
                    self.sig_changed(record)
                except Exception:
                    record.value[self.name] = internal
                    record.modified = prev_modified
                record.signal('record-changed')


class NumericField(CharField):

    def set_client(self, record, value, force_change=False):
        value = Decimal(str(value))
        internal = record.value.get(self.name)
        prev_modified = record.modified
        self.set(record, value)
        digits = record.expr_eval(self.attrs.get('digits', (16, 2)))
        if abs((internal or Decimal('0.0')) - \
                (record.value[self.name] or Decimal('0.0'))) \
                >= Decimal(str(10.0**(-int(digits[1])))):
            if not self.get_state_attrs(record).get('readonly', False):
                record.modified = True
                record.modified_fields.setdefault(self.name)
                try:
                    self.sig_changed(record)
                except Exception:
                    record.value[self.name] = internal
                    record.modified = prev_modified
                    return
                record.signal('record-changed')


class IntegerField(CharField):

    def get(self, record, check_load=True, readonly=True, modified=False):
        return record.value.get(self.name) or 0

    def get_client(self, record):
        return record.value.get(self.name) or 0

class BooleanField(CharField):

    def set_client(self, record, value, force_change=False):
        value = bool(value)
        internal = bool(record.value.get(self.name, False))
        prev_modified = record.modified
        self.set(record, value)
        if internal != bool(record.value.get(self.name, False)):
            record.modified = True
            record.modified_fields.setdefault(self.name)
            try:
                self.sig_changed(record)
            except Exception:
                record.value[self.name] = internal
                record.modified = prev_modified
                return
            record.signal('record-changed')

    def get(self, record, check_load=True, readonly=True, modified=False):
        return bool(record.value.get(self.name, False))

    def get_client(self, record):
        return bool(record.value.get(self.name))


class M2OField(CharField):
    '''
    internal = (id, name)
    '''

    def get(self, record, check_load=True, readonly=True, modified=False):
        if record.value.get(self.name):
            if isinstance(record.value[self.name], (int, basestring, long)):
                self.set(record, record.value[self.name])
            if isinstance(record.value[self.name], (int, basestring, long)):
                return record.value[self.name]
            return record.value[self.name][0] or False
        return False

    def get_client(self, record):
        if record.value.get(self.name):
            if isinstance(record.value[self.name], (int, basestring, long)):
                self.set(record, record.value[self.name])
            if isinstance(record.value[self.name], (int, basestring, long)):
                return record.value[self.name]
            return record.value[self.name][1]
        return False

    def set(self, record, value, modified=False):
        if value and isinstance(value, (int, long)):
            args = ('model', self.attrs['relation'], 'read', value,
                    ['rec_name'], rpc.CONTEXT)
            try:
                result = rpc.execute(*args)
            except Exception, exception:
                result = common.process_exception(exception, record.window,
                        *args)
                if not result:
                    return
            value = value, result['rec_name']
        if value and len(value) != 2:
            value = (False, '')
            record.value[self.name + '.rec_name'] = ''
        else:
            if value:
                record.value[self.name + '.rec_name'] = value[1]
            else:
                record.value[self.name + '.rec_name'] = ''
        record.value[self.name] = value or (False, '')
        if modified:
            record.modified = True
            record.modified_fields.setdefault(self.name)

    def set_client(self, record, value, force_change=False):
        internal = record.value.get(self.name) or (False, '')
        prev_modified = record.modified
        self.set(record, value)
        if (internal[0] or False) != (record.value[self.name][0] or False):
            record.modified = True
            record.modified_fields.setdefault(self.name)
            try:
                self.sig_changed(record)
            except Exception:
                record.value[self.name] = internal
                record.modified = prev_modified
                return
            record.signal('record-changed')
        elif force_change:
            try:
                self.sig_changed(record)
            except Exception:
                record.value[self.name] = internal
                return
            record.signal('record-changed')

    def context_get(self, record, check_load=True, eval_context=True):
        context = super(M2OField, self).context_get(record,
                check_load=check_load, eval_context=eval_context)
        if eval_context and self.attrs.get('datetime_field'):
            context['_datetime'] = record.get_eval(
                    check_load=check_load)[self.attrs.get('datetime_field')]
        return context


class O2MField(CharField):
    '''
    internal = Group of the related objects
    '''

    def __init__(self, parent, attrs):
        super(O2MField, self).__init__(parent, attrs)
        self.context = {}

    def _group_changed(self, group, record):
        record.parent.modified = True
        record.parent.modified_fields.setdefault(self.name)
        self.sig_changed(record.parent)
        record.parent.signal('record-changed')

    def _set_default_value(self, record):
        if record.value.get(self.name) is not None:
            return
        from group import Group
        group = Group(self.attrs['relation'], {}, record.window,
                parent=record,
                parent_name=self.attrs.get('relation_field', ''),
                context=self.context,
                parent_datetime_field=self.attrs.get('datetime_field'))
        group.signal_connect(group, 'group-changed', self._group_changed)
        record.value[self.name] = group

    def get_client(self, record):
        self._set_default_value(record)
        return record.value.get(self.name)

    def get(self, record, check_load=True, readonly=True, modified=False):
        if record.value.get(self.name) is None:
            return []
        result = [('add', [])]
        for record2 in record.value[self.name]:
            if record2.id > 0:
                values = record2.get(check_load=check_load, get_readonly=readonly,
                        get_modifiedonly=modified)
                if record2.is_modified() and values:
                    result.append(('write', record2.id, values))
                result[0][1].append(record2.id)
            else:
                result.append(('create',
                    record2.get(check_load=check_load, get_readonly=readonly)))
        if not result[0][1]:
            del result[0]
        if record.value[self.name].record_removed:
            result.append(('unlink', [x.id for x in \
                    record.value[self.name].record_removed]))
        if record.value[self.name].record_deleted:
            result.append(('delete', [x.id for x in \
                    record.value[self.name].record_deleted]))
        return result

    def get_timestamp(self, record):
        if record.value.get(self.name) is None:
            return {}
        result = {}
        for record2 in (record.value[self.name] \
                + record.value[self.name].record_removed \
                + record.value[self.name].record_deleted):
             result.update(record2.get_timestamp())
        return result

    def get_eval(self, record, check_load=True):
        return [x.id for x in record.value.get(self.name) or []]

    def get_on_change_value(self, record, check_load=True):
        result = []
        if record.value.get(self.name) is None:
            return []
        for record2 in record.value[self.name]:
            result.append(record2.get_eval(check_load=check_load))
        return result

    def set(self, record, value, modified=False):
        from group import Group
        group = record.value.get(self.name)
        if group is not None:
            group.signal_unconnect(group)
        group = Group(self.attrs['relation'], {}, record.window,
                parent=record, parent_name=self.attrs.get('relation_field', ''),
                context=self.context,
                parent_datetime_field=self.attrs.get('datetime_field'))
        record.value[self.name] = group
        record.value[self.name].load(value, display=False)
        group.signal_connect(group, 'group-changed', self._group_changed)
        if modified:
            record.modified = True
            record.modified_fields.setdefault(self.name)

    def set_client(self, record, value, force_change=False):
        pass

    def set_default(self, record, value, modified=False):
        from group import Group

        if value and len(value) and isinstance(value[0], (int, long)):
            return self.set(record, value, modified=modified)

        fields = {}
        if value and len(value):
            context = self.context_get(record)
            field_names = []
            for val in value:
                for fieldname in val.keys():
                    if fieldname not in field_names:
                        field_names.append(fieldname)
            args = ('model', self.attrs['relation'], 'fields_get',
                    field_names, context)
            try:
                fields = rpc.execute(*args)
            except Exception, exception:
                fields = common.process_exception(exception, record.window,
                        *args)
                if not fields:
                    return False

        group = record.value.get(self.name)
        if group is not None:
            group.signal_unconnect(group)
        group = Group(
                self.attrs['relation'], fields, record.window, parent=record,
                parent_name=self.attrs.get('relation_field', ''),
                context=self.context,
                parent_datetime_field=self.attrs.get('datetime_field'))
        if record.value.get(self.name):
            group.record_deleted.extend(x for x in record.value[self.name]
                    if x.id > 0)
            group.record_deleted.extend(record.value[self.name].record_deleted)
            group.record_removed.extend(record.value[self.name].record_removed)
        record.value[self.name] = group
        for vals in (value or []):
            new_record = record.value[self.name].new(default=False)
            new_record.set_default(vals, modified=modified)
            group.add(new_record)
        group.signal_connect(group,
                'group-changed', self._group_changed)
        return True

    def set_on_change(self, record, value):
        self._set_default_value(record)
        if isinstance(value, (list, tuple)):
            return self.set(record, value, modified=True)

        if value and (value.get('add') or value.get('update')):
            context = self.context_get(record)
            field_names = []
            for val in (value.get('add', []) + value.get('update', [])):
                for fieldname in val.keys():
                    if fieldname not in field_names:
                        field_names.append(fieldname)
            args = ('model', self.attrs['relation'], 'fields_get',
                    field_names, context)
            try:
                fields = rpc.execute(*args)
            except Exception, exception:
                fields = common.process_exception(exception, record.window,
                        *args)
                if not fields:
                    return False

        to_remove = []
        for record2 in record.value[self.name]:
            if not record2.id:
                to_remove.append(record2)
        if value and value.get('remove'):
            for record_id in value['remove']:
                record2 = record.value[self.name].get(record_id)
                if record2 is not None:
                    to_remove.append(record2)
        for record2 in to_remove:
            record.value[self.name].remove(record2, signal=False)

        if value and (value.get('add') or value.get('update', [])):
            record.value[self.name].add_fields(fields, signal=False)
            for vals in value.get('add', []):
                new_record = record.value[self.name].new(default=False,
                        signal=False)
                record.value[self.name].add(new_record)
                new_record.set(vals, modified=True, signal=False)

            for vals in value.get('update', []):
                if 'id' not in vals:
                    continue
                record2 = record.value[self.name].get(vals['id'])
                if record2 is not None:
                    record2.set(vals, modified=True, signal=False)
        return True

    def get_default(self, record):
        res = [x.get_default() for x in record.value.get(self.name) or []]
        return res

    def validate(self, record):
        res = True
        for record2 in record.value[self.name] or []:
            if not record2.loaded:
                continue
            if not record2.validate():
                if not record2.is_modified():
                    record.value[self.name].remove(record2)
                else:
                    res = False
        if not super(O2MField, self).validate(record):
            res = False
        self.get_state_attrs(record)['valid'] = res
        return res

    def state_set(self, record, states=('readonly', 'required', 'invisible')):
        self._set_default_value(record)
        super(O2MField, self).state_set(record, states=states)
        if self.get_state_attrs(record).get('readonly', False):
            record.value[self.name].readonly = True
        else:
            record.value[self.name].readonly = False

    def get_removed_ids(self, record):
        return [x.id for x in record.value[self.name].record_removed]


class M2MField(O2MField):

    def get_default(self, record):
        return [x.id for x in record.value.get(self.name) or [] if x.id > 0]

    def get_eval(self, record, check_load=True):
        return [x.id for x in record.value.get(self.name) or []]

    def set(self, record, value, modified=False):
        from group import Group
        group = record.value.get(self.name)
        if group is not None:
            group.signal_unconnect(group)
        group = Group(self.attrs['relation'], {}, record.window,
                parent=record, parent_name=self.attrs.get('relation_field', ''),
                context=self.context,
                parent_datetime_field=self.attrs.get('datetime_field'))
        if record.value.get(self.name):
            group.record_removed.extend(record.value[self.name])
            group.record_deleted.extend(record.value[self.name].record_deleted)
            group.record_removed.extend(record.value[self.name].record_removed)
        record.value[self.name] = group
        record.value[self.name].load(value, display=False)
        group.signal_connect(group, 'group-changed', self._group_changed)
        if modified:
            record.modified = True
            record.modified_fields.setdefault(self.name)


class ReferenceField(CharField):

    def get_client(self, record):
        if record.value.get(self.name):
            return record.value[self.name]
        return False

    def get(self, record, check_load=True, readonly=True, modified=False):
        if record.value.get(self.name):
            if isinstance(record.value[self.name][1], (list, tuple)):
                return '%s,%s' % (record.value[self.name][0],
                        str(record.value[self.name][1][0]))
            else:
                return '%s,%s' % (record.value[self.name][0],
                        str(record.value[self.name][1]))
        return False

    def set_client(self, record, value, force_change=False):
        internal = record.value.get(self.name)
        prev_modified = record.modified
        self.set(record, value)
        if (internal or False) != (record.value[self.name] or False):
            record.modified = True
            record.modified_fields.setdefault(self.name)
            try:
                self.sig_changed(record)
            except Exception:
                record.value[self.name] = internal
                record.modified = prev_modified
                return
            record.signal('record-changed')

    def set(self, record, value, modified=False):
        if not value:
            record.value[self.name] = False
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
                args = ('model', ref_model, 'read', ref_id,
                        ['rec_name'], rpc.CONTEXT)
                try:
                    result = rpc.execute(*args)
                except Exception, exception:
                    result = common.process_exception(exception, record.window,
                            *args)
                    if not result:
                        return
                result = result['rec_name']
                if result:
                    record.value[self.name] = ref_model, (ref_id, result)
                    record.value[self.name + '.rec_name'] = result
                else:
                    record.value[self.name] = ref_model, (0, '')
                    record.value[self.name + '.rec_name'] = ''
            else:
                record.value[self.name] = ref_model, (ref_id, ref_str)
                record.value[self.name + '.rec_name'] = ref_str
        else:
            record.value[self.name] = ref_model, (ref_id, ref_id)
            if self.name + '.rec_name' in record.value:
                del record.value[self.name + '.rec_name']
        if modified:
            record.modified = True
            record.modified_fields.setdefault(self.name)

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
