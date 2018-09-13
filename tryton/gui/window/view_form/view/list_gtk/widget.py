# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import os
import tempfile
import gtk
import gettext
import webbrowser

from functools import wraps, partial

from tryton.gui.window.win_search import WinSearch
from tryton.gui.window.win_form import WinForm
from tryton.gui.window.view_form.screen import Screen
from tryton.common import file_selection, file_open, slugify
import tryton.common as common
from tryton.common.cellrendererbutton import CellRendererButton
from tryton.common.cellrenderertext import CellRendererText, \
    CellRendererTextCompletion
from tryton.common.cellrenderertoggle import CellRendererToggle
from tryton.common.cellrenderercombo import CellRendererCombo
from tryton.common.cellrendererinteger import CellRendererInteger
from tryton.common.cellrendererfloat import CellRendererFloat
from tryton.common.cellrendererbinary import CellRendererBinary
from tryton.common.cellrendererclickablepixbuf import \
    CellRendererClickablePixbuf
from tryton.common import data2pixbuf
from tryton.common.completion import get_completion, update_completion
from tryton.common.selection import SelectionMixin, PopdownMixin
from tryton.common.datetime_ import CellRendererDate, CellRendererTime
from tryton.common.datetime_strftime import datetime_strftime
from tryton.common.domain_parser import quote

_ = gettext.gettext


def send_keys(renderer, editable, position, treeview):
    editable.connect('key_press_event', treeview.on_keypressed)
    editable.editing_done_id = editable.connect('editing_done',
            treeview.on_editing_done)
    if isinstance(editable, (gtk.ComboBoxEntry, gtk.ComboBox)):
        def changed(combobox):
            # "changed" signal is also triggered by text editing
            # so only trigger editing-done if a row is active
            if combobox.get_active_iter():
                treeview.on_editing_done(combobox)
        editable.connect('changed', changed)


def realized(func):
    "Decorator for treeview realized"
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if (hasattr(self.view.treeview, 'get_realized')
                and not self.view.treeview.get_realized()):
            return
        return func(self, *args, **kwargs)
    return wrapper


class CellCache(list):

    methods = ('set_active', 'set_sensitive', 'set_property')

    def apply(self, cell):
        for method, args, kwargs in self:
            getattr(cell, method)(*args, **kwargs)

    def decorate(self, cell):
        def decorate(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                self.append((func.__name__, args, kwargs))
                return func(*args, **kwargs)
            wrapper.previous = func
            return wrapper

        for method in self.methods:
            if getattr(cell, method, None):
                setattr(cell, method, decorate(getattr(cell, method)))
        cell.decorated = True
        return cell

    def undecorate(self, cell):
        for method in self.methods:
            if getattr(cell, method, None):
                setattr(cell, method, getattr(cell, method).previous)
        del cell.decorated

    @classmethod
    def cache(cls, func):
        @wraps(func)
        def wrapper(self, column, cell, store, iter):
            if not hasattr(self, 'display_counters'):
                self.display_counters = {}
            if not hasattr(self, 'cell_caches'):
                self.cell_caches = {}
            record = store.get_value(iter, 0)
            counter = self.view.treeview.display_counter
            if (self.display_counters.get(record.id) != counter):
                if getattr(cell, 'decorated', None):
                    func(self, column, cell, store, iter)
                else:
                    cache = cls()
                    cache.decorate(cell)
                    func(self, column, cell, store, iter)
                    cache.undecorate(cell)
                    self.cell_caches[record.id] = cache
                    self.display_counters[record.id] = counter
            else:
                self.cell_caches[record.id].apply(cell)
        return wrapper


class Cell(object):
    pass


class Affix(Cell):

    def __init__(self, view, attrs, protocol=None):
        super(Affix, self).__init__()
        self.attrs = attrs
        self.protocol = protocol
        self.icon = attrs.get('icon')
        if protocol:
            self.renderer = CellRendererClickablePixbuf()
            self.renderer.connect('clicked', self.clicked)
            if not self.icon:
                self.icon = 'tryton-web-browser'
        elif self.icon:
            self.renderer = gtk.CellRendererPixbuf()
        else:
            self.renderer = gtk.CellRendererText()
        self.view = view

    @realized
    @CellCache.cache
    def setter(self, column, cell, store, iter_):
        record = store.get_value(iter_, 0)
        field = record[self.attrs['name']]
        field.state_set(record, states=('invisible',))
        invisible = field.get_state_attrs(record).get('invisible', False)
        cell.set_property('visible', not invisible)
        if self.icon:
            if self.icon in record.group.fields:
                value = record[self.icon].get_client(record) or ''
            else:
                value = self.icon
            common.ICONFACTORY.register_icon(value)
            pixbuf = self.view.treeview.render_icon(stock_id=value,
                size=gtk.ICON_SIZE_BUTTON, detail=None)
            cell.set_property('pixbuf', pixbuf)
        else:
            text = self.attrs.get('string', '')
            if not text:
                text = field.get_client(record) or ''
            cell.set_property('text', text)

    def clicked(self, renderer, path):
        store = self.view.treeview.get_model()
        record = store.get_value(store.get_iter(path), 0)
        value = record[self.attrs['name']].get(record)
        if value:
            if self.protocol == 'email':
                value = 'mailto:%s' % value
            elif self.protocol == 'callto':
                value = 'callto:%s' % value
            elif self.protocol == 'sip':
                value = 'sip:%s' % value
            webbrowser.open(value, new=2)


class GenericText(Cell):
    align = 0

    def __init__(self, view, attrs, renderer=None):
        super(GenericText, self).__init__()
        self.attrs = attrs
        if renderer is None:
            renderer = CellRendererText
        self.renderer = renderer()
        self.renderer.connect('editing-started', self.editing_started)
        if not isinstance(self.renderer, CellRendererBinary):
            self.renderer.connect_after('editing-started', send_keys,
                view.treeview)
        self.renderer.set_property('yalign', 0)
        self.view = view

    @property
    def field_name(self):
        return self.attrs['name']

    @property
    def model_name(self):
        return self.view.screen.model_name

    @realized
    @CellCache.cache
    def setter(self, column, cell, store, iter):
        record = store.get_value(iter, 0)
        text = self.get_textual_value(record)

        if isinstance(cell, CellRendererToggle):
            cell.set_active(bool(text))
        else:
            cell.set_sensitive(not (record.deleted or record.removed))
            if isinstance(cell,
                    (CellRendererText, CellRendererDate, CellRendererCombo)):
                cell.set_property('strikethrough', record.deleted)
            cell.set_property('text', text)

        field = record[self.attrs['name']]

        editable = getattr(self.view.treeview, 'editable', False)
        states = ('invisible',)
        if editable:
            states = ('readonly', 'required', 'invisible')

        field.state_set(record, states=states)
        invisible = field.get_state_attrs(record).get('invisible', False)
        cell.set_property('visible', not invisible)
        # Sometimes, the treeview with fixed height mode computes a too big
        # height for not visible cell with text
        # We can force an empty text because not visible cell can not be edited
        # and so value_from_text is never called.
        if invisible and not isinstance(cell, CellRendererToggle):
            cell.set_property('text', '')

        if editable:
            readonly = self.attrs.get('readonly',
                field.get_state_attrs(record).get('readonly', False))
            if invisible:
                readonly = True

            if isinstance(cell, CellRendererToggle):
                cell.set_property('activatable', not readonly)
            elif isinstance(cell, (gtk.CellRendererProgress,
                        CellRendererButton, gtk.CellRendererPixbuf)):
                pass
            else:
                cell.set_property('editable', not readonly)
        else:
            if isinstance(cell, CellRendererToggle):
                cell.set_property('activatable', False)

        cell.set_property('xalign', self.align)

    def open_remote(self, record, create, changed=False, text=None,
            callback=None):
        raise NotImplementedError

    def get_textual_value(self, record):
        if not record:
            return ''
        return record[self.attrs['name']].get_client(record)

    def value_from_text(self, record, text, callback=None):
        field = record[self.attrs['name']]
        field.set_client(record, text)
        if callback:
            callback()

    def editing_started(self, cell, editable, path):
        return False

    def _get_record_field(self, path):
        store = self.view.treeview.get_model()
        record = store.get_value(store.get_iter(path), 0)
        field = record.group.fields[self.attrs['name']]
        return record, field


class Char(GenericText):

    @realized
    @CellCache.cache
    def setter(self, column, cell, store, iter_):
        super(Char, self).setter(column, cell, store, iter_)
        cell.set_property('single-paragraph-mode', True)


class Text(GenericText):
    pass


class Int(GenericText):
    align = 1

    def __init__(self, view, attrs, renderer=None):
        if renderer is None:
            renderer = CellRendererInteger
        super(Int, self).__init__(view, attrs, renderer=renderer)
        self.factor = float(attrs.get('factor', 1))

    def get_textual_value(self, record):
        if not record:
            return ''
        return record[self.attrs['name']].get_client(
            record, factor=self.factor)

    def value_from_text(self, record, text, callback=None):
        field = record[self.attrs['name']]
        field.set_client(record, text, factor=self.factor)
        if callback:
            callback()


class Boolean(GenericText):
    align = 0.5

    def __init__(self, view, attrs=None,
            renderer=None):
        if renderer is None:
            renderer = CellRendererToggle
        super(Boolean, self).__init__(view, attrs, renderer=renderer)
        self.renderer.connect('toggled', self._sig_toggled)

    def _sig_toggled(self, renderer, path):
        store = self.view.treeview.get_model()
        record = store.get_value(store.get_iter(path), 0)
        field = record[self.attrs['name']]
        if not self.attrs.get('readonly',
                field.get_state_attrs(record).get('readonly', False)):
            value = record[self.attrs['name']].get_client(record)
            record[self.attrs['name']].set_client(record, int(not value))
            self.view.treeview.set_cursor(path)
        return True


class URL(Char):

    @realized
    @CellCache.cache
    def setter(self, column, cell, store, iter):
        super(URL, self).setter(column, cell, store, iter)
        record = store.get_value(iter, 0)
        field = record[self.attrs['name']]
        field.state_set(record, states=('readonly',))
        readonly = field.get_state_attrs(record).get('readonly', False)
        cell.set_property('visible', not readonly)


class Date(GenericText):

    def __init__(self, view, attrs, renderer=None):
        if renderer is None:
            renderer = CellRendererDate
        super(Date, self).__init__(view, attrs, renderer=renderer)

    @realized
    def setter(self, column, cell, store, iter):
        record = store.get_value(iter, 0)
        field = record[self.attrs['name']]
        self.renderer.props.format = self.get_format(record, field)
        super(Date, self).setter(column, cell, store, iter)

    def get_format(self, record, field):
        if field and record:
            return field.date_format(record)
        else:
            return '%x'

    def get_textual_value(self, record):
        if not record:
            return ''
        value = record[self.attrs['name']].get_client(record)
        if value:
            return datetime_strftime(value, self.renderer.props.format)
        else:
            return ''


class Time(Date):

    def __init__(self, view, attrs, renderer=None):
        if renderer is None:
            renderer = CellRendererTime
        super(Time, self).__init__(view, attrs, renderer=renderer)

    def get_format(self, record, field):
        if field and record:
            return field.time_format(record)
        else:
            return '%X'

    def get_textual_value(self, record):
        if not record:
            return ''
        value = record[self.attrs['name']].get_client(record)
        if value is not None:
            if isinstance(value, datetime.datetime):
                value = value.time()
            return value.strftime(self.renderer.props.format)
        else:
            return ''


class TimeDelta(GenericText):
    align = 1


class Float(Int):

    def __init__(self, view, attrs, renderer=None):
        if renderer is None:
            renderer = CellRendererFloat
        super(Float, self).__init__(view, attrs, renderer=renderer)

    @realized
    def setter(self, column, cell, store, iter):
        super(Float, self).setter(column, cell, store, iter)
        record = store.get_value(iter, 0)
        field = record[self.attrs['name']]
        digits = field.digits(record, factor=self.factor)
        cell.digits = digits


class Binary(GenericText):
    align = 0.5

    def __init__(self, view, attrs, renderer=None):
        self.filename = attrs.get('filename')
        if renderer is None:
            renderer = partial(CellRendererBinary, bool(self.filename))
        super(Binary, self).__init__(view, attrs, renderer=renderer)
        self.renderer.connect('select', self.select_binary)
        self.renderer.connect('open', self.open_binary)
        self.renderer.connect('save', self.save_binary)
        self.renderer.connect('clear', self.clear_binary)

    def get_textual_value(self, record):
        pass

    def value_from_text(self, record, text, callback=None):
        if callback:
            callback()

    @realized
    @CellCache.cache
    def setter(self, column, cell, store, iter):
        record = store.get_value(iter, 0)
        field = record[self.attrs['name']]
        if hasattr(field, 'get_size'):
            size = field.get_size(record)
        else:
            size = len(field.get(record))
        cell.set_property('size', common.humanize(size) if size else '')

        states = ('invisible',)
        if getattr(self.view.treeview, 'editable', False):
            states = ('readonly', 'required', 'invisible')

        field.state_set(record, states=states)
        invisible = field.get_state_attrs(record).get('invisible', False)
        cell.set_property('visible', not invisible)

        if getattr(self.view.treeview, 'editable', False):
            readonly = self.attrs.get('readonly',
                field.get_state_attrs(record).get('readonly', False))
            if invisible:
                readonly = True
            cell.set_property('editable', not readonly)

    def select_binary(self, renderer, path):
        record, field = self._get_record_field(path)
        filename = ''
        filename = file_selection(_('Open...'))
        if filename:
            field.set_client(record, open(filename, 'rb').read())
            if self.filename:
                filename_field = record.group.fields[self.filename]
                filename_field.set_client(record, os.path.basename(filename))

    def open_binary(self, renderer, path):
        if not self.filename:
            return
        dtemp = tempfile.mkdtemp(prefix='tryton_')
        record, field = self._get_record_field(path)
        filename_field = record.group.fields.get(self.filename)
        filename = filename_field.get(record)
        if not filename:
            return
        root, ext = os.path.splitext(filename)
        filename = ''.join([slugify(root), os.extsep, slugify(ext)])
        file_path = os.path.join(dtemp, filename)
        with open(file_path, 'wb') as fp:
            if hasattr(field, 'get_data'):
                fp.write(field.get_data(record))
            else:
                fp.write(field.get(record))
        root, type_ = os.path.splitext(filename)
        if type_:
            type_ = type_[1:]
        file_open(file_path, type_)

    def save_binary(self, renderer, path):
        filename = ''
        record, field = self._get_record_field(path)
        if self.filename:
            filename_field = record.group.fields.get(self.filename)
            filename = filename_field.get(record)
        filename = file_selection(_('Save As...'), filename=filename,
            action=gtk.FILE_CHOOSER_ACTION_SAVE)
        if filename:
            with open(filename, 'wb') as fp:
                if hasattr(field, 'get_data'):
                    fp.write(field.get_data(record))
                else:
                    fp.write(field.get(record))

    def clear_binary(self, renderer, path):
        record, field = self._get_record_field(path)
        if self.filename:
            filename_field = record.group.fields[self.filename]
            filename_field.set_client(record, None)
        field.set_client(record, None)


class Image(GenericText):
    align = 0.5

    def __init__(self, view, attrs=None, renderer=None):
        if renderer is None:
            renderer = gtk.CellRendererPixbuf
        super(Image, self).__init__(view, attrs, renderer)
        self.renderer.set_fixed_size(self.attrs.get('width', -1),
            self.attrs.get('height', -1))

    @realized
    @CellCache.cache
    def setter(self, column, cell, store, iter_):
        record = store.get_value(iter_, 0)
        field = record[self.field_name]
        value = field.get_client(record)
        if isinstance(value, (int, long)):
            if value > common.BIG_IMAGE_SIZE:
                value = None
            else:
                value = field.get_data(record)
        pixbuf = data2pixbuf(value)
        width = self.attrs.get('width', -1)
        height = self.attrs.get('height', -1)
        if width != -1 or height != -1:
            pixbuf = common.resize_pixbuf(pixbuf, width, height)
        cell.set_property('pixbuf', pixbuf)

    def get_textual_value(self, record):
        if not record:
            return ''
        return str(record[self.attrs['name']].get_size(record))


class M2O(GenericText):

    def __init__(self, view, attrs, renderer=None):
        if renderer is None and int(attrs.get('completion', 1)):
            renderer = partial(CellRendererTextCompletion, self.set_completion)
        super(M2O, self).__init__(view, attrs, renderer=renderer)

    def value_from_text(self, record, text, callback=None):
        field = record.group.fields[self.attrs['name']]
        if not text:
            field.set_client(record, (None, ''))
            if callback:
                callback()
            return

        field = record[self.attrs['name']]
        win = self.search_remote(record, field, text, callback=callback)
        if len(win.screen.group) == 1:
            win.response(None, gtk.RESPONSE_OK)
        else:
            win.show()

    def editing_started(self, cell, editable, path):
        super(M2O, self).editing_started(cell, editable, path)
        record, field = self._get_record_field(path)

        def changed(editable):
            text = editable.get_text()
            if field.get_client(record) != text:
                field.set_client(record, (None, ''))

            if field.get(record):
                stock1, tooltip1 = 'tryton-open', _("Open the record <F2>")
                stock2, tooltip2 = 'tryton-clear', _("Clear the field <Del>")
            else:
                stock1, tooltip1 = None, ''
                stock2, tooltip2 = 'tryton-find', _("Search a record <F2>")
            for pos, stock, tooltip in [
                    (gtk.ENTRY_ICON_PRIMARY, stock1, tooltip1),
                    (gtk.ENTRY_ICON_SECONDARY, stock2, tooltip2)]:
                editable.set_icon_from_stock(pos, stock)
                editable.set_icon_tooltip_text(pos, tooltip)

        def icon_press(editable, icon_pos, event):
            value = field.get(record)
            if icon_pos == gtk.ENTRY_ICON_SECONDARY and value:
                field.set_client(record, (None, ''))
                editable.set_text('')
            elif value:
                self.open_remote(record, create=False, changed=False)
            else:
                self.open_remote(
                    record, create=False, changed=True,
                    text=editable.get_text())

        editable.connect('icon-press', icon_press)
        editable.connect('changed', changed)
        changed(editable)
        return False

    def open_remote(self, record, create=True, changed=False, text=None,
            callback=None):
        field = record.group.fields[self.attrs['name']]
        relation = field.attrs['relation']

        access = common.MODELACCESS[relation]
        if (create
                and not (self.attrs.get('create', True) and access['create'])):
            return
        elif not access['read']:
            return

        domain = field.domain_get(record)
        context = field.get_context(record)
        if create:
            obj_id = None
        elif not changed:
            obj_id = field.get(record)
        else:
            self.search_remote(record, field, text, callback=callback).show()
            return

        screen = Screen(relation, domain=domain, context=context,
            mode=['form'], view_ids=self.attrs.get('view_ids', '').split(','),
            exclude_field=field.attrs.get('relation_field'))

        def open_callback(result):
            if result:
                value = (screen.current_record.id,
                    screen.current_record.rec_name())
                field.set_client(record, value, force_change=True)
            if callback:
                callback()
        if obj_id:
            screen.load([obj_id])
            WinForm(screen, open_callback, save_current=True,
                title=field.attrs.get('string'))
        else:
            WinForm(screen, open_callback, new=True, save_current=True,
                title=field.attrs.get('string'), rec_name=text)

    def search_remote(self, record, field, text, callback=None):
        relation = field.attrs['relation']
        domain = field.domain_get(record)
        context = field.get_search_context(record)
        order = field.get_search_order(record)
        access = common.MODELACCESS[relation]
        create_access = self.attrs.get('create', True) and access['create']

        def search_callback(found):
            value = None
            if found:
                value = found[0]
            field.set_client(record, value)
            if callback:
                callback()
        win = WinSearch(relation, search_callback, sel_multi=False,
            context=context, domain=domain,
            order=order, view_ids=self.attrs.get('view_ids', '').split(','),
            new=create_access, title=self.attrs.get('string'))
        win.screen.search_filter(quote(text.decode('utf-8')))
        return win

    def set_completion(self, entry, path):
        if entry.get_completion():
            entry.set_completion(None)
        access = common.MODELACCESS[self.attrs['relation']]
        completion = get_completion(
            search=access['read'],
            create=self.attrs.get('create', True) and access['create'])
        completion.connect('match-selected', self._completion_match_selected,
            path)
        completion.connect('action-activated',
            self._completion_action_activated, path)
        entry.set_completion(completion)
        entry.connect('key-press-event', self._key_press, path)
        entry.connect('changed', self._update_completion, path)

    def _key_press(self, entry, event, path):
        record, field = self._get_record_field(path)
        if (field.get(record) is not None
                and event.keyval in (gtk.keysyms.Delete,
                    gtk.keysyms.BackSpace)):
            entry.set_text('')
            field.set_client(record, None)
        return False

    def _completion_match_selected(self, completion, model, iter_, path):
        record, field = self._get_record_field(path)
        rec_name, record_id = model.get(iter_, 0, 1)
        field.set_client(record, (record_id, rec_name))

        completion.get_entry().set_text(rec_name)
        completion_model = completion.get_model()
        completion_model.clear()
        completion_model.search_text = rec_name
        return True

    def _update_completion(self, entry, path):
        record, field = self._get_record_field(path)
        if field.get(record) is not None:
            return
        model = field.attrs['relation']
        update_completion(entry, record, field, model)

    def _completion_action_activated(self, completion, index, path):
        record, field = self._get_record_field(path)
        entry = completion.get_entry()
        entry.handler_block(entry.editing_done_id)

        def callback():
            entry.handler_unblock(entry.editing_done_id)
            entry.set_text(field.get_client(record))
        if index == 0:
            self.open_remote(record, create=False, changed=True,
                text=entry.get_text(), callback=callback)
        elif index == 1:
            self.open_remote(record, create=True, callback=callback)
        else:
            entry.handler_unblock(entry.editing_done_id)


class O2O(M2O):
    pass


class O2M(GenericText):
    align = 0.5

    def get_textual_value(self, record):
        return '( ' + str(len(record[self.attrs['name']]
                .get_eval(record))) + ' )'

    def value_from_text(self, record, text, callback=None):
        if callback:
            callback()

    def open_remote(self, record, create=True, changed=False, text=None,
            callback=None):
        group = record.value[self.attrs['name']]
        field = record.group.fields[self.attrs['name']]
        relation = field.attrs['relation']
        context = field.get_context(record)

        access = common.MODELACCESS[relation]
        if not access['read']:
            return

        screen = Screen(relation, mode=['tree', 'form'],
            view_ids=self.attrs.get('view_ids', '').split(','),
            exclude_field=field.attrs.get('relation_field'))
        screen.pre_validate = bool(int(self.attrs.get('pre_validate', 0)))
        screen.group = group

        def open_callback(result):
            if callback:
                callback()
        WinForm(screen, open_callback, view_type='tree', context=context,
            title=field.attrs.get('string'))


class M2M(O2M):

    def open_remote(self, record, create=True, changed=False, text=None,
            callback=None):
        group = record.value[self.attrs['name']]
        field = record.group.fields[self.attrs['name']]
        relation = field.attrs['relation']
        context = field.get_context(record)
        domain = field.domain_get(record)

        screen = Screen(relation, mode=['tree', 'form'],
            view_ids=self.attrs.get('view_ids', '').split(','),
            exclude_field=field.attrs.get('relation_field'))
        screen.group = group

        def open_callback(result):
            if callback:
                callback()
        WinForm(screen, open_callback, view_type='tree', domain=domain,
            context=context, title=field.attrs.get('string'))


class Selection(GenericText, SelectionMixin, PopdownMixin):

    def __init__(self, *args, **kwargs):
        if 'renderer' not in kwargs:
            kwargs['renderer'] = CellRendererCombo
        super(Selection, self).__init__(*args, **kwargs)
        self.init_selection()
        # Use a variable let Python holding reference when calling set_property
        model = self.get_popdown_model(self.selection)[0]
        self.renderer.set_property('model', model)
        self.renderer.set_property('text-column', 0)

    def get_textual_value(self, record):
        field = record[self.attrs['name']]
        self.update_selection(record, field)
        value = field.get(record)
        text = dict(self.selection).get(value, '')
        if value and not text:
            text = self.get_inactive_selection(value)
        return text

    def value_from_text(self, record, text, callback=None):
        if callback:
            callback()

    def editing_started(self, cell, editable, path):
        super(Selection, self).editing_started(cell, editable, path)
        store = self.view.treeview.get_model()
        record = store.get_value(store.get_iter(path), 0)
        field = record[self.attrs['name']]

        set_value = lambda *a: self.set_value(editable, record, field)
        editable.get_child().connect('activate', set_value)
        editable.get_child().connect('focus-out-event', set_value)
        editable.connect('changed', set_value)

        self.update_selection(record, field)
        self.set_popdown(self.selection, editable)

        value = field.get(record)
        if not self.set_popdown_value(editable, value):
            self.get_inactive_selection(value)
            self.set_popdown_value(editable, value)
        return False

    def set_value(self, editable, record, field):
        value = self.get_popdown_value(editable)
        if 'relation' in self.attrs and value:
            value = (value, editable.get_active_text())
        field.set_client(record, value)
        return False


class Reference(GenericText, SelectionMixin):

    def __init__(self, view, attrs, renderer=None):
        super(Reference, self).__init__(view, attrs, renderer=renderer)
        self.init_selection()

    def get_textual_value(self, record):
        field = record[self.attrs['name']]
        self.update_selection(record, field)
        value = field.get_client(record)
        if not value:
            model, name = '', ''
        else:
            model, name = value
        if model:
            return dict(self.selection).get(model, model) + ',' + name
        else:
            return name

    def value_from_text(self, record, text, callback=None):
        if callback:
            callback()


class ProgressBar(object):
    align = 0.5
    orientations = {
        'left_to_right': gtk.PROGRESS_LEFT_TO_RIGHT,
        'right_to_left': gtk.PROGRESS_RIGHT_TO_LEFT,
        'bottom_to_top': gtk.PROGRESS_BOTTOM_TO_TOP,
        'top_to_bottom': gtk.PROGRESS_TOP_TO_BOTTOM,
    }

    def __init__(self, view, attrs):
        super(ProgressBar, self).__init__()
        self.view = view
        self.attrs = attrs
        self.renderer = gtk.CellRendererProgress()
        orientation = self.orientations.get(self.attrs.get('orientation',
            'left_to_right'), gtk.PROGRESS_LEFT_TO_RIGHT)
        if hasattr(self.renderer, 'set_orientation'):
            self.renderer.set_orientation(orientation)
        else:
            self.renderer.set_property('orientation', orientation)
        self.renderer.set_property('yalign', 0)

    @realized
    @CellCache.cache
    def setter(self, column, cell, store, iter):
        record = store.get_value(iter, 0)
        field = record[self.attrs['name']]
        field.state_set(record, states=('invisible',))
        invisible = field.get_state_attrs(record).get('invisible', False)
        cell.set_property('visible', not invisible)
        text = self.get_textual_value(record)
        if text:
            text = _('%s%%') % text
        cell.set_property('text', text)
        value = field.get(record) or 0.0
        cell.set_property('value', value * 100)

    def open_remote(self, record, create, changed=False, text=None,
            callback=None):
        raise NotImplementedError

    def get_textual_value(self, record):
        return record[self.attrs['name']].get_client(record, factor=100) or ''

    def value_from_text(self, record, text, callback=None):
        field = record[self.attrs['name']]
        field.set_client(record, float(text))
        if callback:
            callback()


class Button(object):

    def __init__(self, view, attrs):
        super(Button, self).__init__()
        self.attrs = attrs
        self.renderer = CellRendererButton(attrs.get('string', _('Unknown')))
        self.view = view

        self.renderer.connect('clicked', self.button_clicked)
        self.renderer.set_property('yalign', 0)

    @realized
    @CellCache.cache
    def setter(self, column, cell, store, iter):
        record = store.get_value(iter, 0)
        states = record.expr_eval(self.attrs.get('states', {}))
        if record.group.readonly or record.readonly:
            states['readonly'] = True
        invisible = states.get('invisible', False)
        cell.set_property('visible', not invisible)
        readonly = states.get('readonly', False)
        cell.set_property('sensitive', not readonly)
        parent = record.parent if record else None
        while parent:
            if parent.modified:
                cell.set_property('sensitive', False)
                break
            parent = parent.parent
        # TODO icon

    def button_clicked(self, widget, path):
        if not path:
            return True
        store = self.view.treeview.get_model()
        record = store.get_value(store.get_iter(path), 0)

        state_changes = record.expr_eval(
            self.attrs.get('states', {}))
        if state_changes.get('invisible') \
                or state_changes.get('readonly'):
            return True
        widget.handler_block_by_func(self.button_clicked)
        try:
            self.view.screen.button(self.attrs)
        finally:
            widget.handler_unblock_by_func(self.button_clicked)
