# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from tryton.signal_event import SignalEvent
import tryton.common as common
from tryton.pyson import PYSONDecoder
from . import field as fields
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
        self._write = True
        self._delete = True
        self.resources = None
        self.button_clicks = {}
        self.links_counts = {}
        self.next = {}  # Used in Group list
        self.value = {}
        self.autocompletion = {}
        self.exception = False
        self.destroyed = False

    def __getitem__(self, name):
        if not self.destroyed and self.id >= 0 and name not in self._loaded:
            id2record = {
                self.id: self,
                }
            if name == '*':
                loading = 'eager'
                views = set()
                for field in self.group.fields.values():
                    if field.attrs.get('loading', 'eager') == 'lazy':
                        loading = 'lazy'
                    views |= field.views
                # Set a valid name for next loaded check
                for fname, field in self.group.fields.items():
                    if field.attrs.get('loading', 'eager') == loading:
                        name = fname
                        break
            else:
                loading = self.group.fields[name].attrs.get('loading', 'eager')
                views = self.group.fields[name].views

            if loading == 'eager':
                fields = ((fname, field)
                    for fname, field in self.group.fields.items()
                    if field.attrs.get('loading', 'eager') == 'eager')
            else:
                fields = self.group.fields.items()

            fnames = [fname for fname, field in fields
                if fname not in self._loaded
                and (not views or (views & field.views))]
            fnames.extend(('%s.rec_name' % fname for fname in fnames[:]
                    if self.group.fields[fname].attrs['type']
                    in ('many2one', 'one2one', 'reference')))
            if 'rec_name' not in fnames:
                fnames.append('rec_name')
            fnames.extend(['_timestamp', '_write', '_delete'])

            record_context = self.get_context()
            if loading == 'eager':
                limit = int(CONFIG['client.limit'] / len(fnames))

                def filter_group(record):
                    return (not record.destroyed
                        and record.id >= 0
                        and name not in record._loaded)

                def filter_parent_group(record):
                    return (filter_group(record)
                        and record.id not in id2record
                        and ((record.group == self.group)
                            # Don't compute context for same group
                            or (record.get_context() == record_context)))

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
                    for fname, field in self.group.fields.items()
                    if field.attrs['type'] == 'binary' and fname in fnames))
            exception = False
            try:
                values = RPCExecute('model', self.model_name, 'read',
                    list(id2record.keys()), fnames, context=ctx)
            except RPCException:
                values = [{'id': x} for x in id2record]
                default_values = dict((f, None) for f in fnames)
                for value in values:
                    value.update(default_values)
                self.exception = exception = True
            id2value = dict((value['id'], value) for value in values)
            for id, record in id2record.items():
                if not record.exception:
                    record.exception = exception
                value = id2value.get(id)
                if record and not record.destroyed and value:
                    for key in record.modified_fields:
                        value.pop(key, None)
                    record.set(value, signal=False)
        if name != '*':
            return self.group.fields[name]

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

    def get_index_path(self, group=None):
        path = []
        record = self
        while record:
            path.append(record.group.index(record))
            if record.group is group:
                break
            record = record.parent
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
        return (self.deleted
            or self.removed
            or self.exception
            or not self._write)

    readonly = property(get_readonly)

    @property
    def deletable(self):
        return self._delete

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
        for name, field in self.group.fields.items():
            if (field.attrs.get('readonly')
                    and not (isinstance(field, fields.O2MField)
                        and not isinstance(field, fields.M2MField))):
                continue
            if field.name not in self.modified_fields and self.id >= 0:
                continue
            value[name] = field.get(self)
            # Sending an empty x2MField breaks ModelFieldAccess.check
            if isinstance(field, fields.O2MField) and not value[name]:
                del value[name]
        return value

    def get_eval(self):
        value = {}
        for name, field in self.group.fields.items():
            if name not in self._loaded and self.id >= 0:
                continue
            value[name] = field.get_eval(self)
        value['id'] = self.id
        return value

    def get_on_change_value(self, skip=None):
        value = {}
        for name, field in self.group.fields.items():
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
        self.button_clicks.clear()
        self.links_counts.clear()

    def get_timestamp(self):
        result = {self.model_name + ',' + str(self.id): self._timestamp}
        for name, field in self.group.fields.items():
            if name in self._loaded:
                result.update(field.get_timestamp(self))
        return result

    def pre_validate(self):
        if not self.modified_fields:
            return True
        values = self._get_on_change_args(['id'] + list(self.modified_fields))
        try:
            RPCExecute('model', self.model_name, 'pre_validate', values,
                context=self.get_context())
        except RPCException:
            return False
        return True

    def save(self, force_reload=True):
        if self.id < 0 or self.modified:
            value = self.get()
            if self.id < 0:
                try:
                    res, = RPCExecute('model', self.model_name, 'create',
                        [value], context=self.get_context())
                except RPCException:
                    return False
                old_id = self.id
                self.id = res
                self.group.id_changed(old_id)
            elif self.modified:
                if value:
                    context = self.get_context()
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

    def default_get(self, rec_name=None):
        if len(self.group.fields):
            context = self.get_context()
            context.setdefault('default_rec_name', rec_name)
            try:
                vals = RPCExecute('model', self.model_name, 'default_get',
                    list(self.group.fields.keys()), context=context)
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
        return vals

    def rec_name(self):
        try:
            return RPCExecute('model', self.model_name, 'read', [self.id],
                ['rec_name'], context=self.get_context())[0]['rec_name']
        except RPCException:
            return ''

    def validate(self, fields=None, softvalidation=False, pre_validate=None):
        if isinstance(fields, list) and fields:
            self._check_load(fields)
        elif fields is None:
            self._check_load()
        res = True
        for field_name, field in self.group.fields.items():
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
        for fname, field in self.group.fields.items():
            invalid = field.get_state_attrs(self).get('invalid')
            if invalid:
                fields[fname] = invalid
        return fields

    invalid_fields = property(_get_invalid_fields)

    def get_context(self, local=False):
        if not local:
            return self.group.context
        else:
            return self.group.local_context

    def set_default(self, val, signal=True, validate=True):
        fieldnames = []
        for fieldname, value in list(val.items()):
            if fieldname not in self.group.fields:
                continue
            if fieldname == self.group.exclude_field:
                continue
            if isinstance(self.group.fields[fieldname], (fields.M2OField,
                        fields.ReferenceField)):
                related = fieldname + '.'
                self.value[related] = val.get(related) or {}
            self.group.fields[fieldname].set_default(self, value)
            self._loaded.add(fieldname)
            fieldnames.append(fieldname)
        self.on_change(fieldnames)
        self.on_change_with(fieldnames)
        if validate:
            self.validate(softvalidation=True)
        if signal:
            self.signal('record-changed')

    def set(self, val, signal=True, validate=True):
        later = {}
        fieldnames = []
        for fieldname, value in val.items():
            if fieldname == '_timestamp':
                # Always keep the older timestamp
                if not self._timestamp:
                    self._timestamp = value
                continue
            if fieldname in {'_write', '_delete'}:
                setattr(self, fieldname, value)
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
                related = fieldname + '.'
                self.value[related] = val.get(related) or {}
            self.group.fields[fieldname].set(self, value)
            self._loaded.add(fieldname)
            fieldnames.append(fieldname)
        for fieldname, value in later.items():
            self.group.fields[fieldname].set(self, value)
            self._loaded.add(fieldname)
        if validate:
            self.validate(fieldnames, softvalidation=True)
        if signal:
            self.signal('record-changed')

    def set_on_change(self, values):
        for fieldname, value in list(values.items()):
            if fieldname not in self.group.fields:
                continue
            if isinstance(self.group.fields[fieldname], (fields.M2OField,
                        fields.ReferenceField)):
                related = fieldname + '.'
                self.value[related] = values.get(related) or {}
            # Load fieldname before setting value
            self[fieldname].set_on_change(self, value)

    def reload(self, fields=None):
        if self.id < 0:
            return
        if not fields:
            self['*']
        else:
            for field in fields:
                self[field]
        self.validate(fields or [])

    def reset(self, value):
        self.cancel()
        self.set(value, signal=False)

        if self.parent:
            self.parent.on_change([self.group.child_name])
            self.parent.on_change_with([self.group.child_name])

        self.signal('record-changed')

    def expr_eval(self, expr):
        if not isinstance(expr, str):
            return expr
        if not expr:
            return
        elif expr == '[]':
            return []
        elif expr == '{}':
            return {}
        ctx = self.get_eval()
        ctx['context'] = self.get_context()
        ctx['active_model'] = self.model_name
        ctx['active_id'] = self.id
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
                if len(fieldnames) == 1:
                    fieldname, = fieldnames
                    changes = []
                    changes.append(RPCExecute(
                            'model', self.model_name, 'on_change_' + fieldname,
                            values, context=self.get_context()))
                else:
                    changes = RPCExecute(
                        'model', self.model_name, 'on_change',
                        values, fieldnames, context=self.get_context())
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
                self.value.pop(fieldname + '.', None)
        if fieldnames:
            try:
                if len(fieldnames) == 1:
                    fieldname, = fieldnames
                    result = {}
                    result[fieldname] = RPCExecute(
                        'model', self.model_name,
                        'on_change_with_' + fieldname,
                        values, context=self.get_context())
                else:
                    result = RPCExecute(
                        'model', self.model_name, 'on_change_with',
                        values, list(fieldnames), context=self.get_context())
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
                    context=self.get_context())
            except RPCException:
                return
            # Load fieldname before setting value
            self[fieldname].set_on_change(self, result)

    def autocomplete_with(self, field_name):
        for fieldname, fieldinfo in self.group.fields.items():
            autocomplete = fieldinfo.attrs.get('autocomplete', [])
            if field_name not in autocomplete:
                continue
            self.do_autocomplete(fieldname)

    def do_autocomplete(self, fieldname):
        self.autocompletion[fieldname] = []
        autocomplete = self.group.fields[fieldname].attrs['autocomplete']
        args = self._get_on_change_args(autocomplete)
        try:
            res = RPCExecute(
                'model', self.model_name,
                'autocomplete_' + fieldname, args, context=self.get_context())
        except RPCException:
            # ensure res is a list
            res = []
        self.autocompletion[fieldname] = res

    def set_field_context(self):
        from .group import Group
        for name, field in self.group.fields.items():
            value = self.value.get(name)
            if not isinstance(value, Group):
                continue
            context = field.attrs.get('context')
            if context:
                value.context = self.expr_eval(context)

    def get_resources(self, reload=False):
        if self.id >= 0 and (not self.resources or reload):
            try:
                self.resources = RPCExecute(
                    'model', self.model_name, 'resources', self.id,
                    context=self.get_context())
            except RPCException:
                pass
        return self.resources

    def get_button_clicks(self, name):
        if self.id < 0:
            return
        clicks = self.button_clicks.get(name)
        if clicks is not None:
            return clicks
        try:
            clicks = RPCExecute('model', 'ir.model.button.click',
                'get_click', self.model_name, name, self.id)
            self.button_clicks[name] = clicks
        except RPCException:
            return
        return clicks

    def destroy(self):
        for v in self.value.values():
            if hasattr(v, 'destroy'):
                v.destroy()
        super(Record, self).destroy()
        self.destroyed = True
