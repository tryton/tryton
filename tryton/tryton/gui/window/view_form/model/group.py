#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import tryton.rpc as rpc
from record import Record
from field import Field, O2MField
from tryton.signal_event import SignalEvent
import tryton.common as common


class Group(SignalEvent, list):

    def __init__(self, model_name, fields, window, ids=None, parent=None,
            parent_name='', context=None, readonly=False,
            parent_datetime_field=None):
        super(Group, self).__init__()
        self.lock_signal = False
        self.__window = window
        self.parent = parent
        self.parent_name = parent_name or ''
        self.parent_datetime_field = parent_datetime_field
        self._context = context or {}
        self.model_name = model_name
        self.fields = {}
        self.load_fields(fields)
        self.current_idx = None
        self.load(ids)
        self.record_removed = []
        self.record_deleted = []
        self.on_write = set()
        self.readonly = readonly
        if self._context.get('_datetime'):
            self.readonly = True
        self.__id2record = {}

    def __get_window(self):
        return self.__window

    def __set_window(self, window):
        for record in self:
            record.window = window
        self.__window = window

    window = property(__get_window, __set_window)

    def insert(self, pos, record):
        if pos >= 1:
            self.__getitem__(pos - 1).next[id(self)] = record
        if pos < self.__len__():
            record.next[id(self)] = self.__getitem__(pos)
        else:
            record.next[id(self)] = None
        super(Group, self).insert(pos, record)
        self.__id2record[record.id] = record
        if not self.lock_signal:
            self.signal('group-list-changed', ('record-added', pos))

    def append(self, record):
        if self.__len__() >= 1:
            self.__getitem__(self.__len__() - 1).next[id(self)] = record
        record.next[id(self)] = None
        super(Group, self).append(record)
        self.__id2record[record.id] = record
        if not self.lock_signal:
            self.signal('group-list-changed', ('record-added', -1))

    def _remove(self, record):
        idx = self.index(record)
        if idx >= 1:
            if idx + 1 < self.__len__():
                self.__getitem__(idx - 1).next[id(self)] = \
                        self.__getitem__(idx + 1)
            else:
                self.__getitem__(idx - 1).next[id(self)] = None
        super(Group, self).remove(record)
        del self.__id2record[record.id]
        if not self.lock_signal:
            self.signal('group-list-changed', ('record-removed', idx))

    def clear(self):
        while len(self):
            self.pop()
            if not self.lock_signal:
                self.signal('group-list-changed', ('record-removed', len(self)))
        self.record_removed = []
        self.record_deleted = []

    def move(self, record, pos):
        self.lock_signal = True
        if self.__len__() > pos:
            idx = self.index(record)
            self._remove(record)
            if pos > idx:
                pos -= 1
            self.insert(pos, record)
        else:
            self._remove(record)
            self.append(record)
        self.lock_signal = False

    def __setitem__(self, i, value):
        super(Group, self).__setitem__(i, value)
        if not self.lock_signal:
            self.signal('group-list-changed', ('record-changed', i))

    def __repr__(self):
        return '<Group %s at %s>' % (self.model_name, id(self))

    def load_fields(self, fields):
        for name, attr in fields.iteritems():
            field = Field(attr['type'])
            attr['name'] = name
            self.fields[name] = field(self, attr)
            if isinstance(self.fields[name], O2MField) \
                    and '_datetime' in self._context:
                self.fields[name].context.update({
                    '_datetime': self._context['_datetime'],
                    })

    def save(self):
        for record in self:
            saved = record.save()
            self.writen(saved)

    def writen(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        ids = [x for x in self.on_write_ids(ids) or [] if x not in ids]
        if not ids:
            return
        self.reload(ids)
        return ids

    def reload(self, ids):
        for record in self:
            if record.id in ids and not record.modified:
                record._loaded.clear()

    def on_write_ids(self, ids):
        if not self.on_write:
            return False
        res = []
        for fnct in self.on_write:
            args = ('model', self.model_name, fnct, ids, self.context)
            try:
                res += rpc.execute(*args)
            except Exception, exception:
                res2 = common.process_exception(exception, self.window, *args)
                if not res2:
                    return False
                res += res2
        return list({}.fromkeys(res))

    def load(self, ids, display=True, modified=False):
        if not ids:
            return True

        old_ids = [x.id for x in self]
        ids = [x for x in ids if x not in old_ids]
        if not ids:
            return True

        if len(ids) > 1:
            self.lock_signal = True
        new_records = []
        for id in ids:
            new_record = Record(self.model_name, id, self.window,
                    parent=self.parent, parent_name=self.parent_name, group=self)
            self.append(new_record)
            new_records.append(new_record)
            new_record.signal_connect(self, 'record-changed', self._record_changed)
            new_record.signal_connect(self, 'record-modified', self._record_modified)
        for record in self.record_removed[:]:
            if record.id in ids:
                self.record_removed.remove(record)
        for record in self.record_deleted[:]:
            if record.id in ids:
                self.record_deleted.remove(record)
        if self.lock_signal:
            self.lock_signal = False
            self.signal('group-cleared')

        if new_records and display:
            self.signal('group-changed', new_records[0])

        if new_records and modified:
            new_records[0].signal('record-changed')

        self.current_idx = 0
        return True

    def _get_context(self):
        ctx = rpc.CONTEXT.copy()
        ctx.update(self._context)
        if self.parent_datetime_field:
            ctx['_datetime'] = self.parent.get_eval(check_load=False)\
                    [self.parent_datetime_field]
        return ctx

    context = property(_get_context)

    def add(self, record, position=-1, modified=True):
        if not record.group is self:
            fields = {}
            for i in record.group.fields:
                fields[record.group.fields[i].attrs['name']] = \
                        record.group.fields[i].attrs
            self.add_fields(fields)
            record.group = self

        if position == -1:
            self.append(record)
        else:
            self.insert(position, record)
        self.current_idx = position
        record.parent = self.parent
        record.parent_name = self.parent_name
        record.window = self.window
        if modified:
            record.modified = True
        record.signal_connect(self, 'record-changed', self._record_changed)
        record.signal_connect(self, 'record-modified', self._record_modified)
        return record

    def set_sequence(self, field='sequence'):
        index = 0
        for record in self:
            if record[field]:
                if index >= record[field].get(record):
                    index += 1
                    record[field].set(record, index, modified=True)
                else:
                    index = record[field].get(record)

    def new(self, default=True, domain=None, context=None, signal=True):
        record = Record(self.model_name, None, self.window, group=self,
                parent=self.parent, parent_name=self.parent_name, new=True)
        record.signal_connect(self, 'record-changed', self._record_changed)
        record.signal_connect(self, 'record-modified', self._record_modified)
        if default:
            ctx = {}
            ctx.update(context or {})
            ctx.update(self.context)
            record.default_get(domain, ctx)
        if signal:
            self.signal('group-changed', record)
        return record

    def remove(self, record, remove=False, modified=True, signal=True):
        idx = self.index(record)
        if self[idx].id > 0:
            if remove:
                self.record_removed.append(self[idx])
            else:
                self.record_deleted.append(self[idx])
        if record.parent:
            record.parent.modified = True
        if modified:
            record.modified = True
        self._remove(self[idx])

        if len(self):
            self.current_idx = min(idx, len(self) - 1)
        else:
            self.current_idx = None

        if signal:
            record.signal('record-changed', record.parent)

    def _record_changed(self, record, signal_data):
        self.signal('group-changed', record)

    def _record_modified(self, record, signal_data):
        self.signal('record-modified', record)

    def prev(self):
        if len(self) and self.current_idx is not None:
            self.current_idx = (self.current_idx - 1) % len(self)
        elif len(self):
            self.current_idx = 0
        else:
            return None
        return self[self.current_idx]

    def next(self):
        if len(self) and self.current_idx is not None:
            self.current_idx = (self.current_idx + 1) % len(self)
        elif len(self):
            self.current_idx = 0
        else:
            return None
        return self[self.current_idx]

    def add_fields(self, fields, context=None, signal=True):
        if context is None:
            context = {}

        to_add = {}
        for name, attr in fields.iteritems():
            if name not in self.fields:
                to_add[name] = attr
            else:
                self.fields[name].attrs.update(attr)
        self.load_fields(to_add)
        for name in to_add:
            for record in self:
                record.value[name] = self.fields[name].create(record)

        if not len(self):
            return True

        new = []
        for record in self:
            if record.id <= 0:
                new.append(record)
        ctx = context.copy()

        if len(new) and len(to_add):
            ctx.update(self.context)
            args = ('model', self.model_name, 'default_get', to_add.keys(), ctx)
            try:
                values = rpc.execute(*args)
            except Exception, exception:
                values = common.process_exception(exception, self.window, *args)
                if not values:
                    return False
            for name in to_add:
                if name not in values:
                    values[name] = False
            for record in new:
                record.set_default(values, signal=signal)

    def get(self, id):
        'Return record with the id'
        return self.__id2record.get(id)

    def id_changed(self, old_id):
        'Update index for old id'
        record = self.__id2record[old_id]
        self.__id2record[record.id] = record
        del self.__id2record[old_id]
