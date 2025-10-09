# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import functools
import logging
import operator

import tryton.common as common
from tryton.common import RPCException, RPCExecute
from tryton.config import CONFIG
from tryton.pyson import PYSONDecoder

from . import field as fields

logger = logging.getLogger(__name__)


def get_x2m_sub_fields(f_attrs, prefix):
    if f_attrs.get('visible') and f_attrs.get('views'):
        sub_fields = functools.reduce(
            operator.or_,
            (v.get('fields', {}) for v in f_attrs['views'].values()),
            {})
        x2m_sub_fields = []
        for s_field, f_def in sub_fields.items():
            x2m_sub_fields.append(f"{prefix}.{s_field}")
            if f_def['type'] in {'many2one', 'one2one', 'reference'}:
                x2m_sub_fields.append(f"{prefix}.{s_field}.rec_name")
            elif f_def['type'] in {'selection', 'multiselection'}:
                x2m_sub_fields.append(f"{prefix}.{s_field}:string")
            elif f_def['type'] in {'one2many', 'many2many'}:
                x2m_sub_fields.extend(
                    get_x2m_sub_fields(f_def, f"{prefix}.{s_field}"))
        x2m_sub_fields.extend(
            f"{prefix}.{f}"
            for f in ['_timestamp', '_write', '_delete'])
        return x2m_sub_fields
    else:
        return []


class Record:

    id = -1

    def __init__(self, model_name, obj_id, group=None):
        super().__init__()
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
        self.load(name)
        if name != '*':
            return self.group.fields[name]

    def load(self, name, process_exception=True):
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
                views_operator = set.issubset
            else:
                fields = self.group.fields.items()
                views_operator = set.intersection

            fnames = [fname for fname, field in fields
                if fname not in self._loaded
                and (not views or views_operator(views, field.views))]
            related_read_limit = 0
            for fname in list(fnames):
                f_attrs = self.group.fields[fname].attrs
                if f_attrs['type'] in {'many2one', 'one2one', 'reference'}:
                    fnames.append('%s.rec_name' % fname)
                elif (f_attrs['type'] in {'selection', 'multiselection'}
                        and f_attrs.get('loading', 'lazy') == 'eager'):
                    fnames.append('%s:string' % fname)
                elif f_attrs['type'] in {'many2many', 'one2many'}:
                    sub_fields = get_x2m_sub_fields(f_attrs, fname)
                    fnames.extend(sub_fields)
                    if sub_fields:
                        related_read_limit += len(sub_fields)
            if 'rec_name' not in fnames:
                fnames.append('rec_name')
            fnames.extend(['_timestamp', '_write', '_delete'])

            record_context = self.get_context()
            if loading == 'eager':
                limit = CONFIG['client.limit'] // min(len(fnames), 10)

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
            if related_read_limit:
                ctx['related_read_limit'] = (
                    CONFIG['client.limit'] // min(related_read_limit, 10))
            try:
                values = RPCExecute('model', self.model_name, 'read',
                    list(id2record.keys()), fnames, context=ctx,
                    process_exception=process_exception)
            except RPCException:
                for record in id2record.values():
                    record.exception = True
                if process_exception:
                    values = []
                    default_values = {f: None for f in fnames if f != 'id'}
                    for id in id2record:
                        values.append({'id': id, **default_values})
                else:
                    raise
            id2value = dict((value['id'], value) for value in values)
            for id, record in id2record.items():
                value = id2value.get(id)
                if record and not record.destroyed and value:
                    for key in record.modified_fields:
                        value.pop(key, None)
                    record.set(value, modified=False)

    def __repr__(self):
        return '<Record %s@%s at %s>' % (self.id, self.model_name, id(self))

    @property
    def modified(self):
        if self.modified_fields:
            logger.info(
                "Modified fields %s of %s",
                list(self.modified_fields.keys()), self)
            return True
        else:
            return False

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
            or self.group.readonly
            or not self._write)

    readonly = property(get_readonly)

    @property
    def deletable(self):
        return self._delete

    def fields_get(self):
        return self.group.fields

    def _check_load(self, fields=None):
        if not self.get_loaded(fields):
            self.reload(fields)

    def get_loaded(self, fields=None):
        if self.id < 0:
            return True
        if fields is None:
            fields = self.group.fields.keys()
        return set(fields) <= (self._loaded | set(self.modified_fields))

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
        self.value = {}
        self.modified_fields.clear()
        self._timestamp = None
        self.button_clicks.clear()
        self.links_counts.clear()
        self.exception = False

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

    def default_get(self, defaults=None):
        vals = {}
        if len(self.group.fields):
            context = self.get_context()
            if defaults is not None:
                for name, value in defaults.items():
                    context.setdefault(f'default_{name}', value)
            try:
                vals = RPCExecute('model', self.model_name, 'default_get',
                    list(self.group.fields.keys()), context=context)
            except RPCException:
                return vals
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
        res = True
        for field_name, field in list(self.group.fields.items()):
            if fields is not None and field_name not in fields:
                continue
            if not self.get_loaded([field_name]):
                continue
            if field.attrs.get('readonly'):
                continue
            if field_name in {
                    self.group.exclude_field, self.group.parent_name}:
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

    def set_default(self, val, modified=True, validate=True):
        fieldnames = []
        for fieldname, value in list(val.items()):
            if fieldname in {'_write', '_delete', '_timestamp'}:
                setattr(self, fieldname, value)
                continue
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
        if modified:
            self.set_modified()

    def set(self, val, modified=True, validate=True):
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
            field = self.group.fields[fieldname]
            if isinstance(field, fields.O2MField):
                later[fieldname] = value
                continue
            if isinstance(field, (fields.M2OField, fields.ReferenceField)):
                related = fieldname + '.'
                self.value[related] = val.get(related) or {}
            elif isinstance(field, (
                        fields.SelectionField,
                        fields.MultiSelectionField)):
                related = fieldname + ':string'
                if fieldname + ':string' in val:
                    self.value[related] = val[related]
                else:
                    self.value.pop(related, None)
            self.group.fields[fieldname].set(self, value)
            self._loaded.add(fieldname)
            fieldnames.append(fieldname)
        for fieldname, value in later.items():
            if isinstance(
                    field := self.group.fields[fieldname], fields.O2MField):
                field.set(self, value, preloaded=val.get(f"{fieldname}."))
            self._loaded.add(fieldname)
            fieldnames.append(fieldname)
        if validate:
            self.validate(fieldnames, softvalidation=True)
        if modified:
            self.set_modified()

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

    def reset(self, value):
        self.cancel()
        self.set(value, modified=False)

        if self.parent:
            self.parent.on_change([self.group.child_name])
            self.parent.on_change_with([self.group.child_name])

        self.set_modified()

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

        modified = set(fieldnames)
        if values:
            values['id'] = self.id
            try:
                if len(fieldnames) == 1 or 'id' not in values:
                    changes = []
                    for fieldname in fieldnames:
                        changes.append(RPCExecute(
                                'model', self.model_name,
                                'on_change_' + fieldname,
                                values, context=self.get_context()))
                else:
                    changes = [RPCExecute(
                            'model', self.model_name, 'on_change',
                            values, fieldnames, context=self.get_context())]
            except RPCException:
                pass
            else:
                for change in changes:
                    self.set_on_change(change)
                    modified.update(change)

        notification_fields = common.MODELNOTIFICATION.get(self.model_name)
        if modified & set(notification_fields):
            values = self._get_on_change_args(notification_fields)
            try:
                notifications = RPCExecute(
                    'model', self.model_name, 'on_change_notify', values,
                    context=self.get_context())
            except RPCException:
                pass
            else:
                self.group.record_notify(notifications)

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
            values.update(
                self._get_on_change_args(on_change_with + [fieldname]))
            if isinstance(self.group.fields[fieldname], (fields.M2OField,
                        fields.ReferenceField)):
                self.value.pop(fieldname + '.', None)
        if fieldnames:
            try:
                if len(fieldnames) == 1 or 'id' not in values:
                    changed = {}
                    for fieldname in fieldnames:
                        changed.update(RPCExecute(
                                'model', self.model_name,
                                'on_change_with_' + fieldname,
                                values, context=self.get_context()))
                else:
                    values['id'] = self.id
                    changed = RPCExecute(
                        'model', self.model_name, 'on_change_with',
                        values, list(fieldnames), context=self.get_context())
            except RPCException:
                return
            self.set_on_change(changed)
        if later:
            values = {}
            for fieldname in later:
                on_change_with = self.group.fields[fieldname].attrs.get(
                        'on_change_with')
                values.update(
                    self._get_on_change_args(on_change_with + [fieldname]))
            try:
                if len(later) == 1 or 'id' not in values:
                    changed = {}
                    for fieldname in later:
                        changed.update(RPCExecute(
                                'model', self.model_name,
                                'on_change_with_' + fieldname,
                                values, context=self.get_context()))
                else:
                    values['id'] = self.id
                    changed = RPCExecute(
                        'model', self.model_name, 'on_change_with',
                        values, list(later), context=self.get_context())
            except RPCException:
                return
            self.set_on_change(changed)
        notification_fields = common.MODELNOTIFICATION.get(self.model_name)
        if set(field_names) & set(notification_fields):
            values = self._get_on_change_args(notification_fields)
            try:
                notifications = RPCExecute(
                    'model', self.model_name, 'on_change_notify', values,
                    context=self.get_context())
            except RPCException:
                pass
            else:
                self.group.record_notify(notifications)

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
                'autocomplete_' + fieldname, args, context=self.get_context(),
                process_exception=False)
        except RPCException:
            # ensure res is a list
            res = []
        self.autocompletion[fieldname] = res

    def on_scan_code(self, code, depends):
        depends = self.expr_eval(depends)
        values = self._get_on_change_args(depends)
        values['id'] = self.id
        try:
            changes = RPCExecute(
                'model', self.model_name, 'on_scan_code', values, code,
                context=self.get_context(), process_exception=False)
        except RPCException:
            changes = []
        self.set_on_change(changes)
        self.set_modified()
        return bool(changes)

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

    def set_modified(self, field=None):
        if field:
            self.modified_fields.setdefault(field)
        self.group.record_modified()

    def destroy(self):
        for v in self.value.values():
            if hasattr(v, 'destroy'):
                v.destroy()
        self.destroyed = True
