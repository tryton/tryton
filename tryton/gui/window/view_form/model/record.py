#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import tryton.rpc as rpc
from tryton.signal_event import SignalEvent
import tryton.common as common
from tryton.pyson import PYSONDecoder
import field
import datetime
import logging
import time


class EvalEnvironment(dict):

    def __init__(self, parent, check_load):
        super(EvalEnvironment, self).__init__()
        self.parent = parent
        self.check_load = check_load

    def __getitem__(self, item):
        if item == '_parent_' + self.parent.parent_name and self.parent.parent:
            return EvalEnvironment(self.parent.parent, self.check_load)
        return self.parent.get_eval(check_load=self.check_load)[item]

    def __getattr__(self, item):
        return self.__getitem__(item)

    def get(self, item, default=None):
        try:
            return self.__getattr__(item)
        except Exception:
            pass
        return super(EvalEnvironment, self).get(item, default)

    def __nonzero__(self):
        return True

    def __str__(self):
        return str(self.parent)

    __repr__ = __str__

    def __contains__(self, item):
        return item in self.parent.group.fields


class Record(SignalEvent):

    id = -1


    def __init__(self, model_name, obj_id, window, group=None, parent=None,
            parent_name=''):
        super(Record, self).__init__()
        self.window = window
        self.model_name = model_name
        self.id = obj_id or Record.id
        if self.id < 0:
            Record.id -= 1
        self._loaded = set()
        self.parent = parent
        self.parent_name = parent_name
        self.group = group
        if group is not None:
            assert model_name == group.model_name
        self.state_attrs = {}
        self.__modified = False
        self.modified_fields = {}
        self._timestamp = None
        self.attachment_count = -1
        self.next = {} # Used in Group list
        self.value = {}

    def __getitem__(self, name):
        if name not in self._loaded and self.id > 0:
            ids =  [self.id]
            if self in self.group:
                idx = self.group.index(self)
                length = len(self.group)
                n = 1
                while len(ids) < 80 and (idx - n >= 0 or \
                        idx + n < length) and n < 100:
                    if idx - n >= 0:
                        record = self.group[idx - n]
                        if name not in record._loaded and record.id > 0:
                            ids.append(record.id)
                    if idx + n < length:
                        record = self.group[idx + n]
                        if name not in record._loaded and record.id > 0:
                            ids.append(record.id)
                    n += 1
            ctx = rpc.CONTEXT.copy()
            ctx.update(self.context_get())
            args = ('model', self.model_name, 'read',
                    ids, self.group.fields.keys() + \
                        [x + '.rec_name' for x in self.group.fields.keys()
                            if self.group.fields[x].attrs['type'] \
                                    in ('many2one', 'reference')] + \
                        ['_timestamp'], ctx)
            try:
                values = rpc.execute(*args)
            except Exception, exception:
                values = common.process_exception(exception, self.window, *args)
                if not values:
                    values = [{'id': x} for x in ids]
            id2value = dict((value['id'], value) for value in values)
            if ids != [self.id]:
                for id in ids:
                    record = self.group.get(id)
                    value = id2value.get(id)
                    if record and value:
                        record.set(value, signal=False)
            else:
                value = id2value.get(self.id)
                if value:
                    self.set(value, signal=False)
        return self.group.fields.get(name, False)

    def __repr__(self):
        return '<Record %s@%s>' % (self.id, self.model_name)

    def get_modified(self):
        return self.__modified

    def set_modified(self, value):
        self.__modified = value
        if value:
            self.signal('record-modified')

    modified = property(get_modified, set_modified)

    def is_modified(self):
        return self.modified

    def fields_get(self):
        return self.group.fields

    def _check_load(self):
        if not self.loaded:
            self.reload()
            return True
        return False

    def get_loaded(self):
        return set(self.group.fields.keys()) == self._loaded

    loaded = property(get_loaded)

    def get(self, get_readonly=True, includeid=False, check_load=True,
            get_modifiedonly=False):
        if check_load:
            self._check_load()
        value = []
        for name, field in self.group.fields.iteritems():
            if (get_readonly or \
                    not field.get_state_attrs(self).get('readonly', False)) \
                and (not get_modifiedonly \
                   or field.name in self.modified_fields):
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
            value[name] = field.get_eval(self, check_load=check_load)
        value['id'] = self.id
        return value

    def cancel(self):
        self._loaded.clear()
        self.reload()

    def get_timestamp(self):
        result = {self.model_name + ',' + str(self.id): self._timestamp}
        for name, field in self.group.fields.iteritems():
            result.update(field.get_timestamp(self))
        return result

    def save(self, force_reload=True):
        self._check_load()
        if self.id < 0:
            value = self.get(get_readonly=True)
            args = ('model', self.model_name, 'create', value, self.context_get())
            try:
                res = rpc.execute(*args)
            except Exception, exception:
                res = common.process_exception(exception, self.window, *args)
                if not res:
                    return False
            old_id = self.id
            self.id = res
            self.group.id_changed(old_id)
        else:
            if not self.is_modified():
                return self.id
            value = self.get(get_readonly=True, get_modifiedonly=True)
            context = self.context_get()
            context = context.copy()
            context['_timestamp'] = self.get_timestamp()
            args = ('model', self.model_name, 'write', [self.id], value, context)
            try:
                if not rpc.execute(*args):
                    return False
            except Exception, exception:
                if not common.process_exception(exception, self.window, *args):
                    return False
        self._loaded.clear()
        if force_reload:
            self.reload()
        if self.group:
            self.group.writen(self.id)
        return self.id

    def default_get(self, domain=None, context=None):
        if len(self.group.fields):
            args = ('model', self.model_name, 'default_get',
                    self.group.fields.keys(), context)
            try:
                vals = rpc.execute(*args)
            except Exception, exception:
                vals = common.process_exception(exception, self.window, *args)
                if not vals:
                    return
            self.set_default(vals)

    def rec_name(self):
        ctx = rpc.CONTEXT.copy()
        ctx.update(self.context_get())
        args = ('model', self.model_name, 'read', self.id, ['rec_name'], ctx)
        try:
            res = rpc.execute(*args)
        except Exception, exception:
            res = common.process_exception(exception, self.window, *args)
            if not res:
                return ''
        return res['rec_name']

    def validate_set(self):
        self._check_load()
        change = False
        for field in self.group.fields.itervalues():
            change = change or \
                    not field.get_state_attrs(self).get('valid', True)
            field.get_state_attrs(self)['valid'] = True
        if change:
            self.signal('record-changed')
        return change

    def validate(self, check_load=True):
        if check_load:
            self._check_load()
        res = True
        for field in self.group.fields.itervalues():
            if not field.validate(self):
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

    def get_default(self):
        self._check_load()
        value = dict([(name, field.get_default(self))
                      for name, field in self.group.fields.iteritems()])
        return value

    def set_default(self, val, signal=True, modified=False):
        for fieldname, value in val.items():
            if fieldname not in self.group.fields:
                continue
            if isinstance(self.group.fields[fieldname], field.M2OField):
                if fieldname + '.rec_name' in val:
                    value = (value, val[fieldname + '.rec_name'])
            elif isinstance(self.group.fields[fieldname], field.ReferenceField):
                if value:
                    ref_model, ref_id = value.split(',', 1)
                    if fieldname + '.rec_name' in val:
                        value = ref_model, (ref_id, val[fieldname + '.rec_name'])
                    else:
                        value = ref_model, (ref_id, ref_id)
            self.group.fields[fieldname].set_default(self, value,
                    modified=modified)
            self._loaded.add(fieldname)
        if signal:
            self.signal('record-changed')

    def set(self, val, modified=False, signal=True):
        later = {}
        for fieldname, value in val.iteritems():
            if fieldname == '_timestamp':
                self._timestamp = value
                continue
            if fieldname not in self.group.fields:
                continue
            if isinstance(self.group.fields[fieldname], field.O2MField):
                later[fieldname] = value
                continue
            if isinstance(self.group.fields[fieldname], field.M2OField):
                if fieldname + '.rec_name' in val:
                    value = (value, val[fieldname + '.rec_name'])
            elif isinstance(self.group.fields[fieldname], field.ReferenceField):
                if value:
                    ref_model, ref_id = value.split(',', 1)
                    if fieldname + '.rec_name' in val:
                        value = ref_model, (ref_id, val[fieldname + '.rec_name'])
                    else:
                        value = ref_model, (ref_id, ref_id)
            self.group.fields[fieldname].set(self, value, modified=modified)
            self._loaded.add(fieldname)
        for fieldname, value in later.iteritems():
            self.group.fields[fieldname].set(self, value, modified=modified)
            self._loaded.add(fieldname)
        self.modified = modified
        if not self.modified:
            self.modified_fields = {}
        if signal:
            self.signal('record-changed')

    def reload(self):
        if self.id < 0:
            return
        self['*']
        self.validate(check_load=False)

    def expr_eval(self, expr, check_load=False):
        if not isinstance(expr, basestring):
            return expr
        if check_load:
            self._check_load()
        ctx = rpc.CONTEXT.copy()
        for name, field in self.group.fields.items():
            ctx[name] = field.get_eval(self, check_load=check_load)

        ctx['context'] = self.context_get()
        ctx['active_id'] = self.id
        ctx['_user'] = rpc._USER
        if self.parent and self.parent_name:
            ctx['_parent_' + self.parent_name] = EvalEnvironment(self.parent,
                    check_load)
        val = PYSONDecoder(ctx).decode(expr)
        return val

    def _get_on_change_args(self, args):
        res = {}
        values = {}
        for name, field in self.group.fields.iteritems():
            values[name] = field.get_on_change_value(self, check_load=False)
        if self.parent and self.parent_name:
            values['_parent_' + self.parent_name] = EvalEnvironment(self.parent,
                    False)
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
        ctx = rpc.CONTEXT.copy()
        ctx.update(self.context_get())
        args = ('model', self.model_name, 'on_change_' + fieldname, args, ctx)
        try:
            res = rpc.execute(*args)
        except Exception, exception:
            res = common.process_exception(exception, self.window, *args)
            if not res:
                return
        later = {}
        for fieldname, value in res.items():
            if fieldname not in self.group.fields:
                continue
            if isinstance(self.group.fields[fieldname], field.O2MField):
                later[fieldname] = value
                continue
            if isinstance(self.group.fields[fieldname], field.M2OField):
                if fieldname + '.rec_name' in res:
                    value = (value, res[fieldname + '.rec_name'])
            elif isinstance(self.group.fields[fieldname],
                    field.ReferenceField):
                if value:
                    ref_model, ref_id = value.split(',', 1)
                    if fieldname + '.rec_name' in res:
                        value = ref_model, (ref_id,
                                res[fieldname + '.rec_name'])
                    else:
                        value = ref_model, (ref_id, ref_id)
            self.group.fields[fieldname].set_on_change(self, value)
        for fieldname, value in later.items():
            self.group.fields[fieldname].set_on_change(self, value)
        self.signal('record-changed')

    def on_change_with(self, field_name):
        for fieldname in self.group.fields:
            on_change_with = self.group.fields[fieldname].attrs.get(
                    'on_change_with')
            if not on_change_with:
                continue
            if field_name not in on_change_with:
                continue
            if field_name == fieldname:
                continue
            args = self._get_on_change_args(on_change_with)
            ctx = rpc.CONTEXT.copy()
            ctx.update(self.context_get())
            args = ('model', self.model_name, 'on_change_with_' + fieldname,
                    args, ctx)
            try:
                res = rpc.execute(*args)
            except Exception, exception:
                res = common.process_exception(exception, self.window, *args)
                if not res:
                    return
            self.group.fields[fieldname].set_on_change(self, res)

    def cond_default(self, field_name, value):
        ctx = rpc.CONTEXT.copy()
        ctx.update(self.context_get())
        args = ('model', 'ir.default', 'get_default', self.model_name,
                field_name + '=' + str(value), ctx)
        try:
            res = rpc.execute(*args)
        except Exception, exception:
            res = common.process_exception(exception, self.window, *args)
            if not res:
                return
        self.set_default(res)

    def get_attachment_count(self, reload=False):
        if self.id < 0:
            return 0
        if self.attachment_count < 0 or reload:
            args = ('model', 'ir.attachment', 'search_count', [
                ('resource', '=', '%s,%s' % (self.model_name, self.id)),
                ], rpc.CONTEXT)
            try:
                self.attachment_count = rpc.execute(*args)
            except Exception:
                return 0
        return self.attachment_count

    def destroy(self):
        super(Record, self).destroy()
        self.window = None
        self.parent = None
        self.group = None
        for v in self.value.itervalues():
            if hasattr(v, 'destroy'):
                v.destroy()
        self.value = None
        self.next = None
