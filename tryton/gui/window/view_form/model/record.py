# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import tryton.rpc as rpc
from tryton.signal_event import SignalEvent
import tryton.common as common
from tryton.pyson import PYSONDecoder
import field as fields
from functools import reduce
from tryton.common import RPCExecute, RPCException
from tryton.config import CONFIG


class Record(SignalEvent):

    id = -1

    def __init__(self, model_name, obj_id, group=None):
        super(Record, self).__init__()
        self.model_name = model_name
        if obj_id is None:
            self.id = Record.id
        else:
            self.id = obj_id
        if self.id < 0:
            Record.id -= 1
        self._loaded = set()
        self.group = group
        if group is not None:
            assert model_name == group.model_name
        self.state_attrs = {}
        self.modified_fields = {}
        self._timestamp = None
        self.attachment_count = -1
        self.unread_note = -1
        self.next = {}  # Used in Group list
        self.value = {}
        self.autocompletion = {}
        self.exception = False
        self.destroyed = False

    def __getitem__(self, name):
        if name not in self._loaded and self.id >= 0:
            id2record = {
                self.id: self,
                }
            if name == '*':
                loading = reduce(
                        lambda x, y: 'eager' if x == y == 'eager' else 'lazy',
                        (field.attrs.get('loading', 'eager')
                            for field in self.group.fields.itervalues()),
                        'eager')
                # Set a valid name for next loaded check
                for fname, field in self.group.fields.iteritems():
                    if field.attrs.get('loading', 'eager') == loading:
                        name = fname
                        break
            else:
                loading = self.group.fields[name].attrs.get('loading', 'eager')

            if loading == 'eager':
                fnames = [fname
                    for fname, field in self.group.fields.iteritems()
                    if field.attrs.get('loading', 'eager') == 'eager']
            else:
                fnames = self.group.fields.keys()
            fnames = [fname for fname in fnames if fname not in self._loaded]
            fnames.extend(('%s.rec_name' % fname for fname in fnames[:]
                    if self.group.fields[fname].attrs['type']
                    in ('many2one', 'one2one', 'reference')))
            if 'rec_name' not in fnames:
                fnames.append('rec_name')
            fnames.append('_timestamp')

            record_context = self.context_get()
            if loading == 'eager':
                limit = int(CONFIG['client.limit'] / len(fnames))

                def filter_group(record):
                    return name not in record._loaded and record.id >= 0

                def filter_parent_group(record):
                    return (filter_group(record)
                        and record.id not in id2record
                        and ((record.group == self.group)
                            # Don't compute context for same group
                            or (record.context_get() == record_context)))

                if self.parent and self.parent.model_name == self.model_name:
                    group = sum(self.parent.group.children, [])
                    filter_ = filter_parent_group
                else:
                    group = self.group
                    filter_ = filter_group
                if self in group:
                    idx = group.index(self)
                    length = len(group)
                    n = 1
                    while len(id2record) < limit and (idx - n >= 0
                            or idx + n < length) and n < 2 * limit:
                        if idx - n >= 0:
                            record = group[idx - n]
                            if filter_(record):
                                id2record[record.id] = record
                        if idx + n < length:
                            record = group[idx + n]
                            if filter_(record):
                                id2record[record.id] = record
                        n += 1

            ctx = record_context.copy()
            ctx.update(dict(('%s.%s' % (self.model_name, fname), 'size')
                    for fname, field in self.group.fields.iteritems()
                    if field.attrs['type'] == 'binary' and fname in fnames))
            exception = None
            try:
                values = RPCExecute('model', self.model_name, 'read',
                    id2record.keys(), fnames, context=ctx)
            except RPCException, exception:
                values = [{'id': x} for x in id2record]
                default_values = dict((f, None) for f in fnames)
                for value in values:
                    value.update(default_values)
                self.exception = True
            id2value = dict((value['id'], value) for value in values)
            for id, record in id2record.iteritems():
                if not record.exception:
                    record.exception = bool(exception)
                value = id2value.get(id)
                if record and not record.destroyed and value:
                    for key in record.modified_fields:
                        value.pop(key, None)
                    record.set(value, signal=False)
        return self.group.fields.get(name, False)

    def __repr__(self):
        return '<Record %s@%s at %s>' % (self.id, self.model_name, id(self))

    @property
    def modified(self):
        return bool(self.modified_fields)

    @property
    def parent(self):
        return self.group.parent

    @property
    def parent_name(self):
        return self.group.parent_name

    @property
    def root_parent(self):
        parent = self
        while parent.parent:
            parent = parent.parent
        return parent

    @property
    def depth(self):
        parent = self.parent
        i = 0
        while parent:
            i += 1
            parent = parent.parent
        return i

    def set_modified(self, value):
        if value:
            self.signal('record-modified')

    def children_group(self, field_name):
        if not field_name:
            return []
        self._check_load([field_name])
        group = self.value.get(field_name)
        if group is None:
            return None

        if id(group.fields) != id(self.group.fields):
            self.group.fields.update(group.fields)
            group.fields = self.group.fields
        group.on_write = self.group.on_write
        group.readonly = self.group.readonly
        group._context.update(self.group._context)
        return group

    def get_path(self, group):
        path = []
        i = self
        child_name = ''
        while i:
            path.append((child_name, i.id))
            if i.group is group:
                break
            child_name = i.group.child_name
            i = i.parent
        path.reverse()
        return tuple(path)

    def get_removed(self):
        if self.group is not None:
            return self in self.group.record_removed
        return False

    removed = property(get_removed)

    def get_deleted(self):
        if self.group is not None:
            return self in self.group.record_deleted
        return False

    deleted = property(get_deleted)

    def get_readonly(self):
        return self.deleted or self.removed or self.exception

    readonly = property(get_readonly)

    def fields_get(self):
        return self.group.fields

    def _check_load(self, fields=None):
        if fields is not None:
            if not self.get_loaded(fields):
                self.reload(fields)
                return True
            return False
        if not self.loaded:
            self.reload()
            return True
        return False

    def get_loaded(self, fields=None):
        if fields:
            return set(fields) <= (self._loaded | set(self.modified_fields))
        return set(self.group.fields.keys()) == self._loaded

    loaded = property(get_loaded)

    def get(self):
        value = {}
        for name, field in self.group.fields.iteritems():
            if field.attrs.get('readonly'):
                continue
            if field.name not in self.modified_fields and self.id >= 0:
                continue
            value[name] = field.get(self)
        return value

    def get_eval(self):
        value = {}
        for name, field in self.group.fields.iteritems():
            if name not in self._loaded and self.id >= 0:
                continue
            value[name] = field.get_eval(self)
        value['id'] = self.id
        return value

    def get_on_change_value(self, skip=None):
        value = {}
        for name, field in self.group.fields.iteritems():
            if skip and name in skip:
                continue
            if (self.id >= 0
                    and (name not in self._loaded
                        or name not in self.modified_fields)):
                continue
            value[name] = field.get_on_change_value(self)
        value['id'] = self.id
        return value

    def cancel(self):
        self._loaded.clear()
        self.modified_fields.clear()
        self._timestamp = None

    def get_timestamp(self):
        result = {self.model_name + ',' + str(self.id): self._timestamp}
        for name, field in self.group.fields.iteritems():
            if name in self._loaded:
                result.update(field.get_timestamp(self))
        return result

    def pre_validate(self):
        if not self.modified_fields:
            return True
        values = self._get_on_change_args(self.modified_fields)
        try:
            RPCExecute('model', self.model_name, 'pre_validate', values,
                context=self.context_get())
        except RPCException:
            return False
        return True

    def save(self, force_reload=True):
        if self.id < 0 or self.modified:
            if self.id < 0:
                value = self.get()
                try:
                    res, = RPCExecute('model', self.model_name, 'create',
                        [value], context=self.context_get())
                except RPCException:
                    return False
                old_id = self.id
                self.id = res
                self.group.id_changed(old_id)
            elif self.modified:
                value = self.get()
                if value:
                    context = self.context_get()
                    context = context.copy()
                    context['_timestamp'] = self.get_timestamp()
                    try:
                        RPCExecute('model', self.model_name, 'write',
                            [self.id], value, context=context)
                    except RPCException:
                        return False
            self.cancel()
            if force_reload:
                self.reload()
            if self.group:
                self.group.written(self.id)
        if self.parent:
            self.parent.modified_fields.pop(self.group.child_name, None)
            self.parent.save(force_reload=force_reload)
        return self.id

    @staticmethod
    def delete(records):
        if not records:
            return
        record = records[0]
        root_group = record.group.root_group
        assert all(r.model_name == record.model_name for r in records)
        assert all(r.group.root_group == root_group for r in records)
        records = [r for r in records if r.id >= 0]
        ctx = {}
        ctx['_timestamp'] = {}
        for rec in records:
            ctx['_timestamp'].update(rec.get_timestamp())
        record_ids = set(r.id for r in records)
        reload_ids = set(root_group.on_write_ids(list(record_ids)))
        reload_ids -= record_ids
        reload_ids = list(reload_ids)
        try:
            RPCExecute('model', record.model_name, 'delete', list(record_ids),
                context=ctx)
        except RPCException:
            return False
        if reload_ids:
            root_group.reload(reload_ids)
        return True

    def default_get(self):
        if len(self.group.fields):
            try:
                vals = RPCExecute('model', self.model_name, 'default_get',
                    self.group.fields.keys(), context=self.context_get())
            except RPCException:
                return
            if (self.parent
                    and self.parent_name in self.group.fields):
                parent_field = self.group.fields[self.parent_name]
                if isinstance(parent_field, fields.ReferenceField):
                    vals[self.parent_name] = (
                        self.parent.model_name, self.parent.id)
                elif (self.group.fields[self.parent_name].attrs['relation']
                        == self.group.parent.model_name):
                    vals[self.parent_name] = self.parent.id
            self.set_default(vals)
        for fieldname, fieldinfo in self.group.fields.iteritems():
            if not fieldinfo.attrs.get('autocomplete'):
                continue
            self.do_autocomplete(fieldname)
        return vals

    def rec_name(self):
        try:
            return RPCExecute('model', self.model_name, 'read', [self.id],
                ['rec_name'], context=self.context_get())[0]['rec_name']
        except RPCException:
            return ''

    def validate(self, fields=None, softvalidation=False, pre_validate=None):
        if isinstance(fields, list) and fields:
            self._check_load(fields)
        elif fields is None:
            self._check_load()
        res = True
        for field_name, field in self.group.fields.iteritems():
            if fields is not None and field_name not in fields:
                continue
            if field.attrs.get('readonly'):
                continue
            if field_name == self.group.exclude_field:
                continue
            if not field.validate(self, softvalidation, pre_validate):
                res = False
        return res

    def _get_invalid_fields(self):
        fields = {}
        for fname, field in self.group.fields.iteritems():
            invalid = field.get_state_attrs(self).get('invalid')
            if invalid:
                fields[fname] = invalid
        return fields

    invalid_fields = property(_get_invalid_fields)

    def context_get(self):
        return self.group.context

    def set_default(self, val, signal=True, validate=True):
        fieldnames = []
        for fieldname, value in val.items():
            if fieldname not in self.group.fields:
                continue
            if fieldname == self.group.exclude_field:
                continue
            if isinstance(self.group.fields[fieldname], (fields.M2OField,
                        fields.ReferenceField)):
                field_rec_name = fieldname + '.rec_name'
                if field_rec_name in val:
                    self.value[field_rec_name] = val[field_rec_name]
                elif field_rec_name in self.value:
                    del self.value[field_rec_name]
            self.group.fields[fieldname].set_default(self, value)
            self._loaded.add(fieldname)
            fieldnames.append(fieldname)
        self.on_change(fieldnames)
        self.on_change_with(fieldnames)
        if validate:
            self.validate(softvalidation=True)
        if signal:
            self.signal('record-changed')

    def set(self, val, signal=True):
        later = {}
        for fieldname, value in val.iteritems():
            if fieldname == '_timestamp':
                # Always keep the older timestamp
                if not self._timestamp:
                    self._timestamp = value
                continue
            if fieldname not in self.group.fields:
                if fieldname == 'rec_name':
                    self.value['rec_name'] = value
                continue
            if isinstance(self.group.fields[fieldname], fields.O2MField):
                later[fieldname] = value
                continue
            if isinstance(self.group.fields[fieldname], (fields.M2OField,
                        fields.ReferenceField)):
                field_rec_name = fieldname + '.rec_name'
                if field_rec_name in val:
                    self.value[field_rec_name] = val[field_rec_name]
                elif field_rec_name in self.value:
                    del self.value[field_rec_name]
            self.group.fields[fieldname].set(self, value)
            self._loaded.add(fieldname)
        for fieldname, value in later.iteritems():
            self.group.fields[fieldname].set(self, value)
            self._loaded.add(fieldname)
        if signal:
            self.signal('record-changed')

    def set_on_change(self, values):
        for fieldname, value in values.items():
            if fieldname not in self.group.fields:
                continue
            if isinstance(self.group.fields[fieldname], (fields.M2OField,
                        fields.ReferenceField)):
                field_rec_name = fieldname + '.rec_name'
                if field_rec_name in values:
                    self.value[field_rec_name] = values[field_rec_name]
                elif field_rec_name in self.value:
                    del self.value[field_rec_name]
            self.group.fields[fieldname].set_on_change(self, value)

    def reload(self, fields=None):
        if self.id < 0:
            return
        if not fields:
            self['*']
        else:
            for field in fields:
                self[field]
        self.validate(fields or [])

    def expr_eval(self, expr):
        if not isinstance(expr, basestring):
            return expr
        ctx = rpc.CONTEXT.copy()
        ctx['context'] = ctx.copy()
        ctx['context'].update(self.context_get())
        ctx.update(self.get_eval())
        ctx['active_model'] = self.model_name
        ctx['active_id'] = self.id
        ctx['_user'] = rpc._USER
        if self.parent and self.parent_name:
            ctx['_parent_' + self.parent_name] = \
                common.EvalEnvironment(self.parent)
        val = PYSONDecoder(ctx).decode(expr)
        return val

    def _get_on_change_args(self, args):
        res = {}
        values = common.EvalEnvironment(self, 'on_change')
        for arg in args:
            scope = values
            for i in arg.split('.'):
                if i not in scope:
                    break
                scope = scope[i]
            else:
                res[arg] = scope
        res['id'] = self.id
        return res

    def on_change(self, fieldnames):
        values = {}
        for fieldname in fieldnames:
            on_change = self.group.fields[fieldname].attrs.get('on_change')
            if not on_change:
                continue
            values.update(self._get_on_change_args(on_change))

        if values:
            try:
                changes = RPCExecute('model', self.model_name, 'on_change',
                    values, fieldnames, context=self.context_get())
            except RPCException:
                return
            for change in changes:
                self.set_on_change(change)

    def on_change_with(self, field_names):
        field_names = set(field_names)
        fieldnames = set()
        values = {}
        later = set()
        for fieldname in self.group.fields:
            on_change_with = self.group.fields[fieldname].attrs.get(
                    'on_change_with')
            if not on_change_with:
                continue
            if not field_names & set(on_change_with):
                continue
            if fieldnames & set(on_change_with):
                later.add(fieldname)
                continue
            fieldnames.add(fieldname)
            values.update(self._get_on_change_args(on_change_with))
            if isinstance(self.group.fields[fieldname], (fields.M2OField,
                        fields.ReferenceField)):
                field_rec_name = fieldname + '.rec_name'
                if field_rec_name in self.value:
                    del self.value[field_rec_name]
        if fieldnames:
            try:
                result = RPCExecute('model', self.model_name, 'on_change_with',
                    values, list(fieldnames), context=self.context_get())
            except RPCException:
                return
            self.set_on_change(result)
        for fieldname in later:
            on_change_with = self.group.fields[fieldname].attrs.get(
                    'on_change_with')
            values = self._get_on_change_args(on_change_with)
            try:
                result = RPCExecute('model', self.model_name,
                    'on_change_with_' + fieldname, values,
                    context=self.context_get())
            except RPCException:
                return
            self.group.fields[fieldname].set_on_change(self, result)

    def autocomplete_with(self, field_name):
        for fieldname, fieldinfo in self.group.fields.iteritems():
            autocomplete = fieldinfo.attrs.get('autocomplete', [])
            if field_name not in autocomplete:
                continue
            self.do_autocomplete(fieldname)

    def do_autocomplete(self, fieldname):
        self.autocompletion[fieldname] = []
        autocomplete = self.group.fields[fieldname].attrs['autocomplete']
        args = self._get_on_change_args(autocomplete)
        try:
            res = RPCExecute('model', self.model_name, 'autocomplete_' +
                fieldname, args, context=self.context_get())
        except RPCException:
            # ensure res is a list
            res = []
        self.autocompletion[fieldname] = res

    def set_field_context(self):
        from .group import Group
        for name, field in self.group.fields.iteritems():
            value = self.value.get(name)
            if not isinstance(value, Group):
                continue
            context = field.attrs.get('context')
            if context:
                value.context = self.expr_eval(context)

    def get_attachment_count(self, reload=False):
        if self.id < 0:
            return 0
        if self.attachment_count < 0 or reload:
            try:
                self.attachment_count = RPCExecute('model', 'ir.attachment',
                    'search_count', [
                        ('resource', '=',
                            '%s,%s' % (self.model_name, self.id)),
                        ], context=self.context_get())
            except RPCException:
                return 0
        return self.attachment_count

    def get_unread_note(self, reload=False):
        if self.id < 0:
            return 0
        if self.unread_note < 0 or reload:
            try:
                self.unread_note = RPCExecute('model', 'ir.note',
                    'search_count', [
                        ('resource', '=',
                            '%s,%s' % (self.model_name, self.id)),
                        ('unread', '=', True),
                        ], context=self.context_get())
            except RPCException:
                return 0
        return self.unread_note

    def destroy(self):
        for v in self.value.itervalues():
            if hasattr(v, 'destroy'):
                v.destroy()
        super(Record, self).destroy()
        self.destroyed = True
