#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import tryton.rpc as rpc
from tryton.signal_event import SignalEvent
import tryton.common as common
from tryton.pyson import PYSONDecoder
import field as fields
from functools import reduce
from tryton.common import RPCExecute, RPCException


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
        self.next = {}  # Used in Group list
        self.value = {}
        self.autocompletion = {}
        self.exception = False
        self.destroyed = False
        self.pool.add(self)

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
            if self in self.group and loading == 'eager':
                idx = self.group.index(self)
                length = len(self.group)
                n = 1
                while len(id2record) < 80 and (idx - n >= 0 or \
                        idx + n < length) and n < 100:
                    if idx - n >= 0:
                        record = self.group[idx - n]
                        if name not in record._loaded and record.id >= 0:
                            id2record[record.id] = record
                    if idx + n < length:
                        record = self.group[idx + n]
                        if name not in record._loaded and record.id >= 0:
                            id2record[record.id] = record
                    n += 1
            record_context = self.context_get()
            if loading == 'eager' and len(id2record) < 80:
                for record in self.pool:
                    if (name not in record._loaded
                            and record.id >= 0
                            and record.id not in id2record
                            and record.context_get() == record_context):
                        id2record[record.id] = record
                        if len(id2record) == 80:
                            break
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
            ctx = record_context.copy()
            ctx.update(dict(('%s.%s' % (self.model_name, fname), 'size')
                    for fname, field in self.group.fields.iteritems()
                    if field.attrs['type'] == 'binary' and fname in fnames))
            exception = None
            try:
                values = RPCExecute('model', self.model_name, 'read',
                    id2record.keys(), fnames, context=ctx,
                    main_iteration=False)
            except RPCException, exception:
                values = [{'id': x} for x in id2record]
                default_values = dict((f, None) for f in fnames)
                for value in values:
                    value.update(default_values)
                self.exception = True
            id2value = dict((value['id'], value) for value in values)
            if len(id2record) > 1:
                for id, record in id2record.iteritems():
                    if not record.exception:
                        record.exception = bool(exception)
                    value = id2value.get(id)
                    if record and not record.destroyed and value:
                        record.set(value, signal=False)
            else:
                value = id2value.get(self.id)
                if value:
                    self.set(value, signal=False)
        return self.group.fields.get(name, False)

    def __repr__(self):
        return '<Record %s@%s at %s>' % (self.id, self.model_name, id(self))

    @property
    def modified(self):
        return bool(self.modified_fields)

    @property
    def pool(self):
        group = self.group
        while (group.parent is not None
                and group.parent.model_name == self.model_name):
            group = group.parent
        return group.pool

    @property
    def parent(self):
        return self.group.parent

    @property
    def parent_name(self):
        return self.group.parent_name

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

    def children_group(self, field_name, check_load=True):
        if not field_name:
            return []
        if check_load:
            self._check_load([field_name])
        group = self.value.get(field_name)
        if group is None:
            return []

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
            return set(fields) <= self._loaded
        return set(self.group.fields.keys()) == self._loaded

    loaded = property(get_loaded)

    def get(self, get_readonly=True, includeid=False, check_load=True,
            get_modifiedonly=False):
        if check_load:
            self._check_load()
        value = []
        for name, field in self.group.fields.iteritems():
            if field.attrs.get('readonly'):
                continue
            if (field.get_state_attrs(self).get('readonly', False)
                    and not get_readonly):
                continue
            if (field.name not in self.modified_fields
                    and get_modifiedonly):
                continue
            value.append((name, field.get(self, check_load=check_load,
                readonly=get_readonly, modified=get_modifiedonly)))
        value = dict(value)
        if includeid:
            value['id'] = self.id
        return value

    def get_eval(self, check_load=True):
        if check_load:
            self._check_load()
        value = {}
        for name, field in self.group.fields.iteritems():
            if name not in self._loaded and self.id >= 0:
                continue
            value[name] = field.get_eval(self, check_load=check_load)
        value['id'] = self.id
        return value

    def get_on_change_value(self, check_load=True):
        if check_load:
            self._check_load()
        value = {}
        for name, field in self.group.fields.iteritems():
            value[name] = field.get_on_change_value(self,
                check_load=check_load)
        value['id'] = self.id
        return value

    def cancel(self):
        self._loaded.clear()
        self.modified_fields.clear()

    def get_timestamp(self):
        result = {self.model_name + ',' + str(self.id): self._timestamp}
        for name, field in self.group.fields.iteritems():
            result.update(field.get_timestamp(self))
        return result

    def save(self, force_reload=True):
        if self.id < 0 or self.modified:
            if self.id < 0:
                value = self.get(get_readonly=True)
                try:
                    res = RPCExecute('model', self.model_name, 'create', value,
                        main_iteration=False,
                        context=self.context_get())
                except RPCException:
                    return False
                old_id = self.id
                self.id = res
                self.group.id_changed(old_id)
            elif self.modified:
                self._check_load()
                value = self.get(get_readonly=True, get_modifiedonly=True,
                        check_load=False)
                if value:
                    context = self.context_get()
                    context = context.copy()
                    context['_timestamp'] = self.get_timestamp()
                    try:
                        if not RPCExecute('model', self.model_name, 'write',
                                [self.id], value, main_iteration=False,
                                context=context):
                            return False
                    except RPCException:
                        return False
            self._loaded.clear()
            self.modified_fields = {}
            if force_reload:
                self.reload()
            if self.group:
                self.group.written(self.id)
        if self.parent:
            self.parent.modified_fields.pop(self.group.child_name, None)
            self.parent.save(force_reload=force_reload)
        return self.id

    @staticmethod
    def delete(records, context=None):
        if not records:
            return
        record = records[0]
        root_group = record.group.root_group
        assert all(r.model_name == record.model_name for r in records)
        assert all(r.group.root_group == root_group for r in records)
        records = [r for r in records if r.id >= 0]
        ctx = {}
        ctx.update(context or {})
        ctx['_timestamp'] = {}
        for rec in records:
            ctx['_timestamp'].update(rec.get_timestamp())
        record_ids = set(r.id for r in records)
        reload_ids = set(root_group.on_write_ids(list(record_ids)))
        reload_ids -= record_ids
        reload_ids = list(reload_ids)
        try:
            RPCExecute('model', record.model_name, 'delete', list(record_ids),
                main_iteration=False, context=ctx)
        except RPCException:
            return False
        if reload_ids:
            root_group.reload(reload_ids)
        return True

    def default_get(self, domain=None, context=None):
        if len(self.group.fields):
            try:
                vals = RPCExecute('model', self.model_name, 'default_get',
                    self.group.fields.keys(), main_iteration=False,
                    context=context)
            except RPCException:
                return
            if (self.parent
                    and self.parent_name in self.group.fields
                    and (self.group.fields[self.parent_name].attrs['relation']
                        == self.group.parent.model_name)):
                vals[self.parent_name] = self.parent.id
            self.set_default(vals)
        for fieldname, fieldinfo in self.group.fields.iteritems():
            if not fieldinfo.attrs.get('autocomplete'):
                continue
            self.do_autocomplete(fieldname)

    def rec_name(self):
        try:
            return RPCExecute('model', self.model_name, 'read', self.id,
                ['rec_name'], main_iteration=False,
                context=self.context_get())['rec_name']
        except RPCException:
            return ''

    def validate(self, fields=None, softvalidation=False):
        if isinstance(fields, list) and fields:
            self._check_load(fields)
        elif fields is None:
            self._check_load()
        res = True
        for field_name, field in self.group.fields.iteritems():
            if fields and field_name not in fields:
                continue
            if field.get_state_attrs(self).get('readonly', False):
                continue
            if field_name == self.group.exclude_field:
                continue
            if not field.validate(self, softvalidation):
                res = False
        return res

    def _get_invalid_fields(self):
        res = []
        for fname, field in self.group.fields.iteritems():
            if not field.get_state_attrs(self).get('valid', True):
                res.append((fname, field.attrs['string']))
        return dict(res)

    invalid_fields = property(_get_invalid_fields)

    def context_get(self):
        return self.group.context

    def set_default(self, val, signal=True, modified=False):
        for fieldname, value in val.items():
            if fieldname not in self.group.fields:
                continue
            if isinstance(self.group.fields[fieldname], (fields.M2OField,
                        fields.ReferenceField)):
                field_rec_name = fieldname + '.rec_name'
                if field_rec_name in val:
                    self.value[field_rec_name] = val[field_rec_name]
                elif field_rec_name in self.value:
                    del self.value[field_rec_name]
            self.group.fields[fieldname].set_default(self, value,
                modified=modified)
            self._loaded.add(fieldname)
        self.validate(softvalidation=True)
        if signal:
            self.signal('record-changed')

    def set(self, val, modified=False, signal=True):
        later = {}
        for fieldname, value in val.iteritems():
            if fieldname == '_timestamp':
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
            self.group.fields[fieldname].set(self, value, modified=False)
            self._loaded.add(fieldname)
        for fieldname, value in later.iteritems():
            self.group.fields[fieldname].set(self, value, modified=False)
            self._loaded.add(fieldname)
        if modified:
            self.modified_fields.update(dict((x, None) for x in val))
            self.signal('record-modified')
        if signal:
            self.signal('record-changed')

    def reload(self, fields=None):
        if self.id < 0:
            return
        if not fields:
            self['*']
        else:
            for field in fields:
                self[field]
        self.validate(fields or [])

    def expr_eval(self, expr, check_load=False):
        if not isinstance(expr, basestring):
            return expr
        if check_load:
            self._check_load()
        ctx = rpc.CONTEXT.copy()
        ctx['context'] = ctx.copy()
        ctx['context'].update(self.context_get())
        for name, field in self.group.fields.items():
            ctx[name] = field.get_eval(self, check_load=check_load)

        ctx['active_id'] = self.id
        ctx['id'] = self.id  # Force local id
        ctx['_user'] = rpc._USER
        if self.parent and self.parent_name:
            ctx['_parent_' + self.parent_name] = \
                    common.EvalEnvironment(self.parent, check_load)
        val = PYSONDecoder(ctx).decode(expr)
        return val

    def _get_on_change_args(self, args):
        res = {}
        values = common.EvalEnvironment(self, True, 'on_change')
        for arg in args:
            scope = values
            for i in arg.split('.'):
                if i not in scope:
                    scope = False
                    break
                scope = scope[i]
            res[arg] = scope
        return res

    def on_change(self, fieldname, attr):
        if isinstance(attr, basestring):
            attr = PYSONDecoder().decode(attr)
        args = self._get_on_change_args(attr)
        try:
            res = RPCExecute('model', self.model_name, 'on_change_' +
                fieldname, args, main_iteration=False,
                context=self.context_get())
        except RPCException:
            return
        later = {}
        for fieldname, value in res.items():
            if fieldname not in self.group.fields:
                continue
            if isinstance(self.group.fields[fieldname], fields.O2MField):
                later[fieldname] = value
                continue
            if isinstance(self.group.fields[fieldname], (fields.M2OField,
                        fields.ReferenceField)):
                field_rec_name = fieldname + '.rec_name'
                if field_rec_name in res:
                    self.value[field_rec_name] = res[field_rec_name]
                elif field_rec_name in self.value:
                    del self.value[field_rec_name]
            self.group.fields[fieldname].set_on_change(self, value)
        for fieldname, value in later.items():
            # on change recursion checking is done only for x2many
            field_x2many = self.group.fields[fieldname]
            try:
                field_x2many.in_on_change = True
                field_x2many.set_on_change(self, value)
            finally:
                field_x2many.in_on_change = False

    def on_change_with(self, field_name):
        fieldnames = set()
        values = {}
        later = set()
        for fieldname in self.group.fields:
            on_change_with = self.group.fields[fieldname].attrs.get(
                    'on_change_with')
            if not on_change_with:
                continue
            if field_name not in on_change_with:
                continue
            if field_name == fieldname:
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
                    list(fieldnames), values, main_iteration=False,
                    context=self.context_get())
            except RPCException:
                return
            for fieldname, value in result.items():
                self.group.fields[fieldname].set_on_change(self, value)
        for fieldname in later:
            on_change_with = self.group.fields[fieldname].attrs.get(
                    'on_change_with')
            values = self._get_on_change_args(on_change_with)
            try:
                result = RPCExecute('model', self.model_name,
                    'on_change_with_' + fieldname, values,
                    main_iteration=False, context=self.context_get())
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
                fieldname, args, main_iteration=False,
                context=self.context_get())
        except RPCException:
            # ensure res is a list
            res = []
        self.autocompletion[fieldname] = res

    def get_attachment_count(self, reload=False):
        if self.id < 0:
            return 0
        if self.attachment_count < 0 or reload:
            try:
                self.attachment_count = RPCExecute('model', 'ir.attachment',
                    'search_count', [
                        ('resource', '=',
                            '%s,%s' % (self.model_name, self.id)),
                        ], main_iteration=False)
            except RPCException:
                return 0
        return self.attachment_count

    def destroy(self):
        # Get reference to pool before unref group
        pool = self.pool
        for v in self.value.itervalues():
            if hasattr(v, 'destroy'):
                v.destroy()
        super(Record, self).destroy()
        self.group = None
        self.value = None
        self.next = None
        self.destroyed = True
        pool.remove(self)
