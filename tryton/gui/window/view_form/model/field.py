#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import os
import tempfile
import locale
from tryton.common import datetime_strftime, \
        domain_inversion, eval_domain, localize_domain, unlocalize_domain, \
        merge, inverse_leaf, EvalEnvironment
import tryton.common as common
import time
import datetime
import decimal
from decimal import Decimal
from tryton.translate import date_format
from tryton.common import RPCExecute, RPCException


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

    _default = ''

    def __init__(self, attrs):
        self.attrs = attrs
        self.name = attrs['name']
        self.internal = False
        self.default_attrs = {}

    def sig_changed(self, record):
        if self.get_state_attrs(record).get('readonly', False):
            return
        if self.attrs.get('on_change', False):
            record.on_change(self.name, self.attrs['on_change'])
        record.on_change_with(self.name)
        record.autocomplete_with(self.name)

    def domains_get(self, record):
        screen_domain = domain_inversion(record.group.domain4inversion,
            self.name, EvalEnvironment(record, False))
        if isinstance(screen_domain, bool) and not screen_domain:
            screen_domain = [('id', '=', False)]
        elif isinstance(screen_domain, bool) and screen_domain:
            screen_domain = []
        attr_domain = record.expr_eval(self.attrs.get('domain', []))
        return screen_domain, attr_domain

    def domain_get(self, record):
        screen_domain, attr_domain = self.domains_get(record)
        return localize_domain(screen_domain) + attr_domain

    def validation_domains(self, record):
        screen_domain, attr_domain = self.domains_get(record)
        if attr_domain:
            return (screen_domain, screen_domain +
                unlocalize_domain(attr_domain, self.name))
        else:
            return screen_domain, screen_domain

    def context_get(self, record, check_load=True, eval_context=True):
        context = record.context_get().copy()
        if record.parent:
            context.update(record.parent.context_get())
        if eval_context:
            context.update(record.expr_eval(self.attrs.get('context', {}),
                check_load=check_load))
        return context

    def check_required(self, record):
        state_attrs = self.get_state_attrs(record)
        if bool(int(state_attrs.get('required') or 0)):
            if (not self.get(record)
                    and not bool(int(state_attrs.get('readonly') or 0))):
                return False
        return True

    def validate(self, record, softvalidation=False):
        if self.attrs.get('readonly'):
            return True
        res = True
        self.get_state_attrs(record)['domain_readonly'] = False
        inverted_domain, domain = self.validation_domains(record)
        if not softvalidation:
            res = res and self.check_required(record)
        if isinstance(domain, bool):
            res = res and domain
        elif domain == [('id', '=', False)]:
            res = False
        else:
            if (isinstance(inverted_domain, list)
                    and len(inverted_domain) == 1
                    and inverted_domain[0][1] == '='):
                # If the inverted domain is so constraint that only one value
                # is possible we should use it. But we must also pay attention
                # to the fact that the original domain might be a 'OR' domain
                # and thus not preventing the modification of fields.
                leftpart, _, value = inverted_domain[0][:3]
                if value is False:
                    # XXX to remove once server domains are fixed
                    value = None
                setdefault = True
                if '.' in leftpart:
                    recordpart, localpart = leftpart.split('.', 1)
                    original_domain = merge(record.group.domain)
                    constraintfields = set()
                    if original_domain[0] == 'AND':
                        for leaf in localize_domain(original_domain[1:]):
                            constraintfields.add(leaf[0])
                    if localpart != 'id' or recordpart not in constraintfields:
                        setdefault = False
                if setdefault:
                    self.set_client(record, value)
                    self.get_state_attrs(record)['domain_readonly'] = True
            res = res and eval_domain(domain, EvalEnvironment(record, False))
        self.get_state_attrs(record)['valid'] = res
        return res

    def set(self, record, value, modified=False):
        record.value[self.name] = value
        if modified:
            record.modified_fields.setdefault(self.name)
            record.signal('record-modified')
            record.signal('record-changed')
        return True

    def get(self, record, check_load=True, readonly=True, modified=False):
        return record.value.get(self.name) or self._default

    def get_eval(self, record, check_load=True):
        return self.get(record, check_load=check_load, readonly=True,
                modified=False)

    def get_on_change_value(self, record, check_load=True):
        return self.get_eval(record, check_load=check_load)

    def set_client(self, record, value, force_change=False):
        previous_value = self.get(record)
        self.set(record, value)
        if previous_value != self.get(record):
            record.modified_fields.setdefault(self.name)
            record.signal('record-modified')
            self.sig_changed(record)
            record.validate(softvalidation=True)
            record.signal('record-changed')
        elif force_change:
            self.sig_changed(record)
            record.validate(softvalidation=True)
            record.signal('record-changed')

    def get_client(self, record):
        return record.value.get(self.name) or self._default

    def set_default(self, record, value, modified=False):
        res = self.set(record, value, modified=modified)
        return res

    def set_on_change(self, record, value):
        record.modified_fields.setdefault(self.name)
        return self.set(record, value, modified=False)

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
        if (record.group.readonly
            or self.get_state_attrs(record).get('domain_readonly')):
            self.get_state_attrs(record)['readonly'] = True
        if 'value' in state_changes:
            value = state_changes['value']
            if value:
                self.set(record, value, modified=True)

    def get_state_attrs(self, record):
        if self.name not in record.state_attrs:
            record.state_attrs[self.name] = self.attrs.copy()
        if record.group.readonly or record.readonly:
            record.state_attrs[self.name]['readonly'] = True
        return record.state_attrs[self.name]

    def get_timestamp(self, record):
        return {}


class SelectionField(CharField):

    _default = None

    def get_client(self, record):
        return record.value.get(self.name)


class DateTimeField(CharField):

    _default = None

    def set_client(self, record, value, force_change=False):
        if not isinstance(value, datetime.datetime):
            try:
                value = datetime.datetime(*time.strptime(value,
                        date_format() + ' ' + self.time_format(record))[:6])
                value = common.untimezoned_date(value)
            except ValueError:
                value = self._default
        super(DateTimeField, self).set_client(record, value,
            force_change=force_change)

    def get_client(self, record):
        value = super(DateTimeField, self).get_client(record)
        if value:
            value = common.timezoned_date(value)
            return datetime_strftime(value, date_format() + ' ' +
                self.time_format(record))
        return ''

    def time_format(self, record):
        return record.expr_eval(self.attrs['format'])


class DateField(CharField):

    _default = None

    def set_client(self, record, value, force_change=False):
        if not isinstance(value, datetime.date):
            try:
                value = datetime.date(*time.strptime(value,
                        date_format())[:3])
            except ValueError:
                value = self._default
        super(DateField, self).set_client(record, value,
            force_change=force_change)

    def get_client(self, record):
        value = super(DateField, self).get_client(record)
        if value:
            return datetime_strftime(value, date_format())
        return ''


class TimeField(CharField):

    _default = None

    def set_client(self, record, value, force_change=False):
        if not isinstance(value, datetime.time):
            try:
                value = datetime.time(*time.strptime(value,
                        self.time_format(record))[3:6])
            except ValueError:
                value = None
        super(TimeField, self).set_client(record, value,
            force_change=force_change)

    def get_client(self, record):
        value = super(TimeField, self).get_client(record)
        if value is not None:
            return value.strftime(self.time_format(record))
        return ''

    def time_format(self, record):
        return record.expr_eval(self.attrs['format'])


class NumberField(CharField):
    _default = None

    def check_required(self, record):
        state_attrs = self.get_state_attrs(record)
        if bool(int(state_attrs.get('required') or 0)):
            if (self.get(record) is None
                    and not bool(int(state_attrs.get('readonly') or 0))):
                return False
        return True

    def get(self, record, check_load=True, readonly=True, modified=False):
        return record.value.get(self.name, self._default)

    def digits(self, record):
        default = (16, 2)
        return tuple(y if x is None else x for x, y in zip(
                record.expr_eval(self.attrs.get('digits', default)), default))


class FloatField(NumberField):

    def set_client(self, record, value, force_change=False):
        if isinstance(value, basestring):
            try:
                value = locale.atof(value)
            except ValueError:
                value = self._default
        super(FloatField, self).set_client(record, value,
            force_change=force_change)

    def get_client(self, record):
        value = record.value.get(self.name)
        if value is not None:
            digits = self.digits(record)
            return locale.format('%.' + str(digits[1]) + 'f', value, True)
        else:
            return ''


class NumericField(NumberField):

    def set_client(self, record, value, force_change=False):
        if isinstance(value, basestring):
            try:
                value = locale.atof(value, Decimal)
            except decimal.InvalidOperation:
                value = self._default
        super(NumericField, self).set_client(record, value,
            force_change=force_change)

    def get_client(self, record):
        value = record.value.get(self.name)
        if value is not None:
            digits = self.digits(record)
            return locale.format('%.' + str(digits[1]) + 'f', value, True)
        else:
            return ''


class IntegerField(NumberField):

    def set_client(self, record, value):
        if isinstance(value, basestring):
            try:
                value = locale.atoi(value)
            except ValueError:
                value = self._default
        super(IntegerField, self).set_client(record, value)

    def get_client(self, record):
        value = record.value.get(self.name)
        if value is not None:
            return locale.format('%d', value, True)
        else:
            return ''

    def digits(self, record):
        return (16, 0)


class BooleanField(CharField):

    _default = False

    def set_client(self, record, value, force_change=False):
        value = bool(value)
        super(BooleanField, self).set_client(record, value,
            force_change=force_change)

    def get(self, record, check_load=True, readonly=True, modified=False):
        return bool(record.value.get(self.name))

    def get_client(self, record):
        return bool(record.value.get(self.name))


class M2OField(CharField):
    '''
    internal = (id, name)
    '''

    _default = None

    def get(self, record, check_load=True, readonly=True, modified=False):
        value = record.value.get(self.name)
        if (record.parent_name == self.name
                and self.attrs['relation'] == record.group.parent.model_name):
            value = record.parent.id if record.parent else None
        return value

    def get_client(self, record):
        rec_name = record.value.get(self.name + '.rec_name')
        if rec_name is None:
            self.set(record, self.get(record))
            rec_name = record.value.get(self.name + '.rec_name') or ''
        return rec_name

    def set_client(self, record, value, force_change=False):
        if isinstance(value, (tuple, list)):
            value, rec_name = value
        else:
            if value == self.get(record):
                rec_name = record.value.get(self.name + '.rec_name', '')
            else:
                rec_name = ''
        record.value[self.name + '.rec_name'] = rec_name
        super(M2OField, self).set_client(record, value,
            force_change=force_change)

    def set(self, record, value, modified=False):
        rec_name = record.value.get(self.name + '.rec_name') or ''
        if value is False:
            value = None
        if (record.parent_name == self.name
                and self.attrs['relation'] == record.group.parent.model_name):
            if record.parent:
                value = record.parent.id
                if 'rec_name' in record.parent.value:
                    rec_name = record.parent.value['rec_name'] or ''
            else:
                value = None
        if not rec_name and value >= 0:
            try:
                result, = RPCExecute('model', self.attrs['relation'], 'read',
                    [value], ['rec_name'], main_iteration=False)
            except RPCException:
                return False
            rec_name = result['rec_name'] or ''
        record.value[self.name + '.rec_name'] = rec_name
        record.value[self.name] = value
        if (record.parent_name == self.name
                and self.attrs['relation'] == record.group.parent.model_name):
            if record.parent:
                if 'rec_name' not in record.parent.value:
                    record.parent.value['rec_name'] = rec_name
        if modified:
            record.modified_fields.setdefault(self.name)
            record.signal('record-modified')
            record.signal('record-changed')

    def context_get(self, record, check_load=True, eval_context=True):
        context = super(M2OField, self).context_get(record,
                check_load=check_load, eval_context=eval_context)
        if eval_context and self.attrs.get('datetime_field'):
            context['_datetime'] = record.get_eval(
                    check_load=check_load)[self.attrs.get('datetime_field')]
        return context

    def validation_domains(self, record):
        screen_domain, attr_domain = self.domains_get(record)
        return screen_domain, screen_domain

    def domain_get(self, record):
        screen_domain, attr_domain = self.domains_get(record)
        return (localize_domain(inverse_leaf(screen_domain), self.name)
            + attr_domain)

    def get_state_attrs(self, record):
        result = super(M2OField, self).get_state_attrs(record)
        if (record.parent_name == self.name
                and self.attrs['relation'] == record.group.parent.model_name):
            result = result.copy()
            result['readonly'] = True
        return result


class O2OField(M2OField):
    pass


class O2MField(CharField):
    '''
    internal = Group of the related objects
    '''

    _default = None

    def __init__(self, attrs):
        super(O2MField, self).__init__(attrs)
        self.in_on_change = False
        self.context = {}

    def sig_changed(self, record):
        if not self.in_on_change:
            return super(O2MField, self).sig_changed(record)

    def _group_changed(self, group, record):
        if not record.parent:
            return
        record.parent.modified_fields.setdefault(self.name)
        self.sig_changed(record.parent)
        record.parent.validate(softvalidation=True)
        record.parent.signal('record-changed')

    def _group_list_changed(self, group, signal):
        if group.model_name == group.parent.model_name:
            group.parent.group.signal('group-list-changed', signal)

    def _group_cleared(self, group, signal):
        if group.model_name == group.parent.model_name:
            group.parent.signal('group-cleared')

    def _record_modified(self, group, record):
        if not record.parent:
            return
        record.parent.signal('record-modified')

    def _set_default_value(self, record):
        if record.value.get(self.name) is not None:
            return
        from group import Group
        parent_name = self.attrs.get('relation_field', '')
        group = Group(self.attrs['relation'], {},
                parent=record,
                parent_name=parent_name,
                child_name=self.name,
                context=self.context,
                parent_datetime_field=self.attrs.get('datetime_field'))
        if record.model_name == self.attrs['relation']:
            group.fields = record.group.fields
        group.signal_connect(group, 'group-changed', self._group_changed)
        group.signal_connect(group, 'group-list-changed',
            self._group_list_changed)
        group.signal_connect(group, 'group-cleared', self._group_cleared)
        group.signal_connect(group, 'record-modified', self._record_modified)
        record.value[self.name] = group

    def get_client(self, record):
        self._set_default_value(record)
        return record.value.get(self.name)

    def get(self, record, check_load=True, readonly=True, modified=False):
        if record.value.get(self.name) is None:
            return []
        record_removed = record.value[self.name].record_removed
        record_deleted = record.value[self.name].record_deleted
        result = [('add', [])]
        parent_name = self.attrs.get('relation_field', '')
        for record2 in record.value[self.name]:
            if record2 in record_removed or record2 in record_deleted:
                continue
            if record2.id >= 0:
                values = record2.get(check_load=check_load,
                    get_readonly=readonly, get_modifiedonly=modified)
                values.pop(parent_name, None)
                if record2.modified and values:
                    result.append(('write', [record2.id], values))
                result[0][1].append(record2.id)
            else:
                values = record2.get(check_load=check_load,
                    get_readonly=readonly)
                values.pop(parent_name, None)
                result.append(('create', values))
        if not result[0][1]:
            del result[0]
        if record_removed:
            result.append(('unlink', [x.id for x in record_removed]))
        if record_deleted:
            result.append(('delete', [x.id for x in record_deleted]))
        return result

    def get_timestamp(self, record):
        if record.value.get(self.name) is None:
            return {}
        result = {}
        for record2 in (record.value[self.name]
                + record.value[self.name].record_removed
                + record.value[self.name].record_deleted):
            result.update(record2.get_timestamp())
        return result

    def get_eval(self, record, check_load=True):
        if record.value.get(self.name) is None:
            return []
        record_removed = record.value[self.name].record_removed
        record_deleted = record.value[self.name].record_deleted
        return [x.id for x in record.value[self.name]
            if x not in record_removed and x not in record_deleted]

    def get_on_change_value(self, record, check_load=True):
        result = []
        if record.value.get(self.name) is None:
            return []
        for record2 in record.value[self.name]:
            if not (record2.deleted or record2.removed):
                result.append(
                    record2.get_on_change_value(check_load=check_load))
        return result

    def set(self, record, value, modified=False):
        from group import Group
        group = record.value.get(self.name)
        fields = {}
        if group is not None:
            fields = group.fields.copy()
            # Unconnect to prevent infinite loop
            group.signal_unconnect(group)
            group.destroy()
        elif record.model_name == self.attrs['relation']:
            fields = record.group.fields
        parent_name = self.attrs.get('relation_field', '')
        group = Group(self.attrs['relation'], {},
                parent=record, parent_name=parent_name,
                child_name=self.name,
                context=self.context,
                parent_datetime_field=self.attrs.get('datetime_field'))
        group.fields = fields
        record.value[self.name] = group
        group.load(value, display=False)
        group.signal_connect(group, 'group-changed', self._group_changed)
        group.signal_connect(group, 'group-list-changed',
            self._group_list_changed)
        group.signal_connect(group, 'group-cleared', self._group_cleared)
        group.signal_connect(group, 'record-modified', self._record_modified)
        if modified:
            record.modified_fields.setdefault(self.name)
            record.signal('record-modified')
            record.signal('record-changed')

    def set_client(self, record, value, force_change=False):
        pass

    def set_default(self, record, value, modified=False):
        from group import Group

        # value is a list of id
        if value and len(value) and isinstance(value[0], (int, long)):
            return self.set(record, value, modified=modified)

        group = record.value.get(self.name)
        fields = {}
        if group is not None:
            fields = group.fields.copy()
            # Unconnect to prevent infinite loop
            group.signal_unconnect(group)
            group.destroy()
        elif record.model_name == self.attrs['relation']:
            fields = record.group.fields
        if fields:
            fields = dict((fname, field.attrs)
                for fname, field in fields.iteritems())
        if value and len(value):
            context = self.context_get(record)
            field_names = []
            for val in value:
                for fieldname in val.keys():
                    if (fieldname not in field_names
                            and fieldname not in fields):
                        field_names.append(fieldname)
            if field_names:
                try:
                    fields.update(RPCExecute('model', self.attrs['relation'],
                            'fields_get', field_names,
                            main_iteration=False, context=context))
                except RPCException:
                    return False

        parent_name = self.attrs.get('relation_field', '')
        group = Group(self.attrs['relation'], fields,
                parent=record, parent_name=parent_name, child_name=self.name,
                context=self.context,
                parent_datetime_field=self.attrs.get('datetime_field'))
        if record.value.get(self.name):
            group.record_deleted.extend(x for x in record.value[self.name]
                if x.id >= 0)
            group.record_deleted.extend(record.value[self.name].record_deleted)
            group.record_removed.extend(record.value[self.name].record_removed)
        record.value[self.name] = group
        for vals in (value or []):
            new_record = record.value[self.name].new(default=False)
            new_record.set_default(vals, modified=modified)
            group.add(new_record)
        group.signal_connect(group, 'group-changed', self._group_changed)
        group.signal_connect(group, 'group-list-changed',
            self._group_list_changed)
        group.signal_connect(group, 'group-cleared', self._group_cleared)
        group.signal_connect(group, 'record-modified', self._record_modified)
        return True

    def set_on_change(self, record, value):
        self._set_default_value(record)
        if isinstance(value, (list, tuple)):
            self.set(record, value, modified=False)
            record.modified_fields.setdefault(self.name)
            record.signal('record-modified')
            return True

        if value and (value.get('add') or value.get('update')):
            context = self.context_get(record)
            field_names = []
            for val in (value.get('add', []) + value.get('update', [])):
                for fieldname in val.keys():
                    if fieldname not in field_names:
                        field_names.append(fieldname)
            try:
                fields = RPCExecute('model', self.attrs['relation'],
                    'fields_get', field_names,
                    main_iteration=False, context=context)
            except RPCException:
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
            record.value[self.name].remove(record2, signal=False,
                force_remove=False)

        if value and (value.get('add') or value.get('update', [])):
            record.value[self.name].add_fields(fields, signal=False)
            for vals in value.get('add', []):
                new_record = record.value[self.name].new(default=False)
                record.value[self.name].add(new_record)
                new_record.set(vals, modified=True, signal=False)

            for vals in value.get('update', []):
                if 'id' not in vals:
                    continue
                record2 = record.value[self.name].get(vals['id'])
                if record2 is not None:
                    record2.set(vals, modified=True, signal=False)
        return True

    def validation_domains(self, record):
        screen_domain, attr_domain = self.domains_get(record)
        return screen_domain, screen_domain

    def validate(self, record, softvalidation=False):
        if self.attrs.get('readonly'):
            return True
        res = True
        for record2 in record.value.get(self.name, []):
            if not record2.loaded and record2.id >= 0:
                continue
            if not record2.validate(softvalidation=softvalidation):
                if not record2.modified:
                    record.value[self.name].remove(record2)
                else:
                    res = False
        if not super(O2MField, self).validate(record, softvalidation):
            res = False
        self.get_state_attrs(record)['valid'] = res
        return res

    def state_set(self, record, states=('readonly', 'required', 'invisible')):
        self._set_default_value(record)
        super(O2MField, self).state_set(record, states=states)
        record.value[self.name].readonly = self.get_state_attrs(record).get(
            'readonly', False)

    def get_removed_ids(self, record):
        return [x.id for x in record.value[self.name].record_removed]

    def domain_get(self, record):
        screen_domain, attr_domain = self.domains_get(record)
        return localize_domain(inverse_leaf(screen_domain)) + attr_domain


class M2MField(O2MField):

    def set(self, record, value, modified=False):
        from group import Group
        group = record.value.get(self.name)
        fields = {}
        if group is not None:
            fields = group.fields.copy()
            # Unconnect to prevent infinite loop
            group.signal_unconnect(group)
            group.destroy()
        elif record.model_name == self.attrs['relation']:
            fields = record.group.fields
        parent_name = self.attrs.get('relation_field', '')
        group = Group(self.attrs['relation'], {},
                parent=record, parent_name=parent_name,
                child_name=self.name,
                context=self.context,
                parent_datetime_field=self.attrs.get('datetime_field'))
        if record.value.get(self.name):
            group.record_removed.extend(record.value[self.name])
            group.record_deleted.extend(record.value[self.name].record_deleted)
            group.record_removed.extend(record.value[self.name].record_removed)
        record.value[self.name] = group
        group.fields = fields
        group.load(value, display=False)
        group.signal_connect(group, 'group-changed', self._group_changed)
        group.signal_connect(group, 'group-list-changed',
            self._group_list_changed)
        group.signal_connect(group, 'group-cleared', self._group_cleared)
        group.signal_connect(group, 'record-modified', self._record_modified)
        if modified:
            record.modified_fields.setdefault(self.name)
            record.signal('record-modified')
            record.signal('record-changed')

    def get_on_change_value(self, record, check_load=True):
        return self.get_eval(record, check_load=check_load)


class ReferenceField(CharField):

    _default = None

    def get_client(self, record):
        if record.value.get(self.name):
            model, _ = record.value[self.name]
            name = record.value.get(self.name + '.rec_name') or ''
            return model, name
        else:
            return None

    def get(self, record, check_load=True, readonly=True, modified=False):
        if (record.value.get(self.name)
                and record.value[self.name][0]
                and record.value[self.name][1] >= 0):
            return ','.join(map(str, record.value[self.name]))
        return None

    def set_client(self, record, value, force_change=False):
        if value:
            if isinstance(value, basestring):
                value = value.split(',')
            ref_model, ref_id = value
            if isinstance(ref_id, (tuple, list)):
                ref_id, rec_name = ref_id
            else:
                if '%s,%s' % (ref_model, ref_id) == self.get(record):
                    rec_name = record.value.get(self.name + '.rec_name', '')
                else:
                    rec_name = ''
            record.value[self.name + '.rec_name'] = rec_name
            value = (ref_model, ref_id)
        super(ReferenceField, self).set_client(record, value,
            force_change=force_change)

    def set(self, record, value, modified=False):
        if not value:
            record.value[self.name] = self._default
            return
        if isinstance(value, basestring):
            ref_model, ref_id = value.split(',')
            if not ref_id:
                ref_id = None
            else:
                try:
                    ref_id = int(ref_id)
                except ValueError:
                    pass
        else:
            ref_model, ref_id = value
        rec_name = record.value.get(self.name + '.rec_name') or ''
        if ref_model and ref_id >= 0:
            if not rec_name and ref_id >= 0:
                try:
                    result, = RPCExecute('model', ref_model, 'read', [ref_id],
                        ['rec_name'], main_iteration=False)
                except RPCException:
                    return
                rec_name = result['rec_name']
        elif ref_model:
            rec_name = ''
        else:
            rec_name = ref_id
        record.value[self.name] = ref_model, ref_id
        record.value[self.name + '.rec_name'] = rec_name
        if modified:
            record.modified_fields.setdefault(self.name)
            record.signal('record-modified')


class BinaryField(CharField):

    _default = None

    def get(self, record, check_load=True, readonly=True, modified=False):
        result = record.value.get(self.name) or self._default
        if isinstance(result, basestring):
            try:
                with open(result, 'rb') as fp:
                    result = buffer(fp.read())
            except IOError:
                result = self.get_data(record)
        return result

    def get_client(self, record):
        return self.get(record)

    def set_client(self, record, value, force_change=False):
        _, filename = tempfile.mkstemp(prefix='tryton_')
        with open(filename, 'wb') as fp:
            fp.write(value or '')
        self.set(record, filename)
        record.modified_fields.setdefault(self.name)
        record.signal('record-modified')
        self.sig_changed(record)
        record.validate(softvalidation=True)
        record.signal('record-changed')

    def get_size(self, record):
        result = record.value.get(self.name) or 0
        if isinstance(result, basestring):
            result = os.stat(result).st_size
        elif isinstance(result, buffer):
            result = len(result)
        return result

    def get_data(self, record):
        if not isinstance(record.value.get(self.name), (basestring, buffer)):
            if record.id < 0:
                return ''
            context = record.context_get()
            try:
                values, = RPCExecute('model', record.model_name, 'read',
                    [record.id], [self.name], main_iteration=False,
                    context=context)
            except RPCException:
                return ''
            _, filename = tempfile.mkstemp(prefix='tryton_')
            with open(filename, 'wb') as fp:
                fp.write(values[self.name] or '')
            self.set(record, filename)
        return self.get(record)

TYPES = {
    'char': CharField,
    'sha': CharField,
    'float_time': FloatField,
    'integer': IntegerField,
    'biginteger': IntegerField,
    'float': FloatField,
    'numeric': NumericField,
    'many2one': M2OField,
    'many2many': M2MField,
    'one2many': O2MField,
    'reference': ReferenceField,
    'selection': SelectionField,
    'boolean': BooleanField,
    'datetime': DateTimeField,
    'date': DateField,
    'time': TimeField,
    'one2one': O2OField,
    'binary': BinaryField,
}
