# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import os
import gettext
import webbrowser
from functools import wraps, partial

from gi.repository import Gdk, GLib, Gtk

from tryton.gui.window.win_search import WinSearch
from tryton.gui.window.win_form import WinForm
from tryton.gui.window.view_form.screen import Screen
from tryton.common import file_selection, file_open, file_write
import tryton.common as common
from tryton.common.cellrendererbutton import CellRendererButton
from tryton.common.cellrenderertext import CellRendererText, \
    CellRendererTextCompletion
from tryton.common.cellrenderertoggle import CellRendererToggle
from tryton.common.cellrenderercombo import CellRendererCombo
from tryton.common.cellrendererinteger import CellRendererInteger
from tryton.common.cellrendererfloat import CellRendererFloat
from tryton.common.cellrendererclickablepixbuf import \
    CellRendererClickablePixbuf
from tryton.common import data2pixbuf
from tryton.common.completion import get_completion, update_completion
from tryton.common.selection import (
    SelectionMixin, PopdownMixin, selection_shortcuts)
from tryton.common.datetime_ import CellRendererDate, CellRendererTime
from tryton.common.domain_parser import quote
from tryton.config import CONFIG

_ = gettext.gettext

COLORS = {n: v for n, v in zip(
        ['muted', 'success', 'warning', 'danger'],
        CONFIG['tree.colors'].split(','))}


def send_keys(renderer, editable, position, treeview):
    editable.connect('key_press_event', treeview.on_keypressed, renderer)
    editable.editing_done_id = editable.connect('editing_done',
            treeview.on_editing_done, renderer)
    if isinstance(editable, Gtk.ComboBox):
        def changed(combobox):
            # "changed" signal is also triggered by text editing
            # so only trigger editing-done if a row is active
            if combobox.get_active_iter():
                treeview.on_editing_done(combobox, renderer)
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
        def wrapper(self, column, cell, store, iter_, user_data=None):
            if not hasattr(self, 'display_counters'):
                self.display_counters = {}
            if not hasattr(self, 'cell_caches'):
                self.cell_caches = {}
            record = store.get_value(iter_, 0)
            counter = self.view.treeview.display_counter
            if (self.display_counters.get(record.id) != counter):
                if getattr(cell, 'decorated', None):
                    func(self, column, cell, store, iter_, user_data)
                else:
                    cache = cls()
                    cache.decorate(cell)
                    func(self, column, cell, store, iter_, user_data)
                    cache.undecorate(cell)
                    self.cell_caches[record.id] = cache
                    self.display_counters[record.id] = counter
            else:
                self.cell_caches[record.id].apply(cell)
        return wrapper


class Cell(object):
    renderer = None
    setter = None
    expand = True
    attrs = None
    view = None
    prefixes = []
    suffixes = []

    def _get_record_field_from_path(self, path, store=None):
        if not store:
            store = self.view.treeview.get_model()
        record = store.get_value(store.get_iter(path), 0)
        field = record.group.fields[self.attrs['name']]
        return record, field

    def _get_record_field_from_iter(self, iter_, store=None):
        if not store:
            store = self.view.treeview.get_model()
        record = store.get_value(iter_, 0)
        field = record[self.attrs['name']]
        return record, field

    def _set_visual(self, cell, record):
        visual = record.expr_eval(self.attrs.get('visual'))
        if not visual:
            visual = record.expr_eval(self.view.attributes.get('visual'))
        background = COLORS.get(visual) if visual != 'muted' else None
        foreground = COLORS.get(visual) if visual == 'muted' else None
        cell.set_property('cell-background', background)
        if isinstance(cell, Gtk.CellRendererText):
            cell.set_property('foreground', foreground)
            cell.set_property('foreground-set', bool(foreground))

    def set_editable(self):
        pass


class Affix(Cell):
    expand = False

    def __init__(self, view, attrs, protocol=None):
        super(Affix, self).__init__()
        self.attrs = attrs
        self.protocol = protocol
        self.icon = attrs.get('icon')
        if protocol:
            self.renderer = CellRendererClickablePixbuf()
            self.renderer.connect('clicked', self.clicked)
            if not self.icon:
                self.icon = 'tryton-public'
        elif self.icon:
            self.renderer = Gtk.CellRendererPixbuf()
        else:
            self.renderer = Gtk.CellRendererText()
        self.view = view

    @realized
    @CellCache.cache
    def setter(self, column, cell, store, iter_, user_data=None):
        record, field = self._get_record_field_from_iter(iter_, store)
        field = record[self.attrs['name']]
        field.state_set(record, states=('invisible',))
        invisible = field.get_state_attrs(record).get('invisible', False)
        cell.set_property('visible', not invisible)
        if self.icon:
            if self.icon in record.group.fields:
                value = record[self.icon].get_client(record) or ''
            else:
                value = self.icon
            pixbuf = common.IconFactory.get_pixbuf(value, Gtk.IconSize.BUTTON)
            cell.set_property('pixbuf', pixbuf)
        else:
            text = self.attrs.get('string', '')
            if not text:
                text = field.get_client(record) or ''
            cell.set_property('text', text)
        self._set_visual(cell, record)

    def clicked(self, renderer, path):
        record, field = self._get_record_field_from_path(path)
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
    editable = None
    editing = None

    def __init__(self, view, attrs, renderer=None):
        super(GenericText, self).__init__()
        self.attrs = attrs
        if renderer is None:
            renderer = CellRendererText
        self.renderer = renderer()
        self.renderer.connect('editing-started', self.editing_started)
        self.renderer.connect_after(
            'editing-started', send_keys, view.treeview)
        self.renderer.set_property('yalign', 0)
        self.renderer.set_property('xalign', self.align)
        self.view = view

    @property
    def field_name(self):
        return self.attrs['name']

    @property
    def model_name(self):
        return self.view.screen.model_name

    @realized
    @CellCache.cache
    def setter(self, column, cell, store, iter_, user_data=None):
        record, field = self._get_record_field_from_iter(iter_, store)
        text = self.get_textual_value(record)

        if isinstance(cell, Gtk.CellRendererToggle):
            cell.set_active(bool(text))
        else:
            cell.set_sensitive(not (record.deleted or record.removed))
            if isinstance(cell, Gtk.CellRendererText):
                cell.set_property('strikethrough', record.deleted)
            cell.set_property('text', text)

        states = ('invisible',)
        if self.view.editable:
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

        if self.view.editable:
            readonly = self.attrs.get('readonly',
                field.get_state_attrs(record).get('readonly', False))
            if invisible:
                readonly = True

            if isinstance(cell, CellRendererToggle):
                cell.set_property('activatable', not readonly)
            elif isinstance(cell,
                    (Gtk.CellRendererProgress, CellRendererButton,
                        Gtk.CellRendererPixbuf)):
                pass
            else:
                cell.set_property('editable', not readonly)
        else:
            if isinstance(cell, CellRendererToggle):
                cell.set_property('activatable', False)
        self._set_visual(cell, record)

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

    def set_editable(self):
        if not self.editable or not self.editing:
            return
        record, field = self.editing
        self.editable.set_text(self.get_textual_value(record))

    def editing_started(self, cell, editable, path):
        def remove(editable):
            self.editable = None
            self.editing = None
        self.editable = editable
        self.editing = self._get_record_field_from_path(path)
        editable.connect('remove-widget', remove)
        return False


class Char(GenericText):

    @realized
    @CellCache.cache
    def setter(self, column, cell, store, iter_, user_data=None):
        super(Char, self).setter(column, cell, store, iter_, user_data)
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
        record, field = self._get_record_field_from_path(path)
        if not self.attrs.get('readonly',
                field.get_state_attrs(record).get('readonly', False)):
            value = record[self.attrs['name']].get_client(record)
            record[self.attrs['name']].set_client(record, int(not value))
            self.view.treeview.set_cursor(path)
        return True


class URL(Char):

    @realized
    @CellCache.cache
    def setter(self, column, cell, store, iter_, user_data=None):
        super(URL, self).setter(column, cell, store, iter_, user_data)
        record, field = self._get_record_field_from_iter(iter_, store)
        field.state_set(record, states=('readonly',))
        readonly = field.get_state_attrs(record).get('readonly', False)
        cell.set_property('visible', not readonly)


class Date(GenericText):

    def __init__(self, view, attrs, renderer=None):
        if renderer is None:
            renderer = CellRendererDate
        super(Date, self).__init__(view, attrs, renderer=renderer)

    @realized
    def setter(self, column, cell, store, iter_, user_data=None):
        record, field = self._get_record_field_from_iter(iter_, store)
        self.renderer.props.format = self.get_format(record, field)
        super(Date, self).setter(column, cell, store, iter_, user_data)

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
            return value.strftime(self.renderer.props.format)
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

    def set_editable(self):
        if not self.editable or not self.editing:
            return
        record, field = self.editing
        self.editable.get_child().set_text(self.get_textual_value(record))


class TimeDelta(GenericText):
    align = 1


class Float(Int):

    def __init__(self, view, attrs, renderer=None):
        if renderer is None:
            renderer = CellRendererFloat
        super(Float, self).__init__(view, attrs, renderer=renderer)

    @realized
    def setter(self, column, cell, store, iter_, user_data=None):
        super(Float, self).setter(column, cell, store, iter_, user_data)
        record, field = self._get_record_field_from_iter(iter_, store)
        digits = field.digits(record, factor=self.factor)
        cell.digits = digits


class Binary(GenericText):
    align = 1

    def __init__(self, view, attrs, renderer=None):
        if renderer is None:
            renderer = CellRendererText
        super(Binary, self).__init__(view, attrs, renderer=renderer)
        self.renderer.set_property('editable', False)
        self.renderer.set_property('xalign', self.align)
        self.renderer_save = _BinarySave(self)
        self.renderer_select = _BinarySelect(self)
        if self.attrs.get('filename'):
            self.renderer_open = _BinaryOpen(self)
        else:
            self.renderer_open = None

    @property
    def prefixes(self):
        return filter(None, [self.renderer_open])

    @property
    def suffixes(self):
        return [self.renderer_save, self.renderer_select]

    def get_textual_value(self, record):
        field = record[self.attrs['name']]
        if hasattr(field, 'get_size'):
            size = field.get_size(record)
        else:
            size = len(field.get(record))
        return common.humanize(size) if size else ''

    def value_from_text(self, record, text, callback=None):
        if callback:
            callback()

    @realized
    @CellCache.cache
    def setter(self, column, cell, store, iter_, user_data=None):
        record, field = self._get_record_field_from_iter(iter_, store)
        text = self.get_textual_value(record)
        cell.set_property('text', text)

        states = ('invisible',)
        if self.view.editable:
            states = ('readonly', 'required', 'invisible')

        field.state_set(record, states=states)
        invisible = field.get_state_attrs(record).get('invisible', False)
        cell.set_property('visible', not invisible)
        self._set_visual(cell, record)

    def get_data(self, record, field):
        if hasattr(field, 'get_data'):
            data = field.get_data(record)
        else:
            data = field.get(record)
        if isinstance(data, str):
            data = data.encode('utf-8')
        return data


class _BinaryIcon(Cell):
    expand = False

    def __init__(self, binary):
        super().__init__()
        self.binary = binary
        self.renderer = CellRendererClickablePixbuf()
        self.renderer.connect('clicked', self.clicked)

    @property
    def attrs(self):
        return self.binary.attrs

    @property
    def view(self):
        return self.binary.view


class _BinarySave(_BinaryIcon):
    icon_name = 'tryton-save'

    def __init__(self, binary):
        super().__init__(binary)
        pixbuf = common.IconFactory.get_pixbuf(
            self.icon_name, Gtk.IconSize.BUTTON)
        self.renderer.set_property('pixbuf', pixbuf)

    @common.idle_add
    def clicked(self, renderer, path):
        filename = ''
        record, field = self._get_record_field_from_path(path)
        if self.attrs.get('filename'):
            filename_field = record.group.fields.get(self.attrs['filename'])
            filename = filename_field.get(record)
        filename = file_selection(_('Save As...'), filename=filename,
            action=Gtk.FileChooserAction.SAVE)
        if filename:
            with open(filename, 'wb') as fp:
                fp.write(self.binary.get_data(record, field))

    @realized
    @CellCache.cache
    def setter(self, column, cell, store, iter_, user_data=None):
        record, field = self._get_record_field_from_iter(iter_, store)
        if hasattr(field, 'get_size'):
            size = field.get_size(record)
        else:
            size = len(field.get(record))
        field.state_set(record, states=['invisible'])
        invisible = field.get_state_attrs(record).get('invisible', False)
        cell.set_property('visible', not invisible and size)
        self._set_visual(cell, record)


class _BinarySelect(_BinaryIcon):
    def clicked(self, renderer, path):
        record, field = self._get_record_field_from_path(path)
        if hasattr(field, 'get_size'):
            size = field.get_size(record)
        else:
            size = len(field.get(record))
        if self.attrs.get('filename'):
            filename_field = record.group.fields[self.attrs['filename']]
        else:
            filename_field = None
        if size:
            if filename_field:
                filename_field.set_client(record, None)
            field.set_client(record, None)
        else:
            def _select():
                filename = file_selection(_('Open...'))
                if filename:
                    with open(filename, 'rb') as fp:
                        field.set_client(record, fp.read())
                    if filename_field:
                        filename_field.set_client(
                            record, os.path.basename(filename))
            GLib.idle_add(_select)

    @realized
    @CellCache.cache
    def setter(self, column, cell, store, iter_, user_data=None):
        record, field = self._get_record_field_from_iter(iter_, store)
        if hasattr(field, 'get_size'):
            size = field.get_size(record)
        else:
            size = len(field.get(record))
        if size:
            icon = 'tryton-clear'
        else:
            icon = 'tryton-search'
        pixbuf = common.IconFactory.get_pixbuf(icon, Gtk.IconSize.BUTTON)
        cell.set_property('pixbuf', pixbuf)
        field.state_set(record, states=['invisible', 'readonly'])
        invisible = field.get_state_attrs(record).get('invisible', False)
        readonly = self.attrs.get('readonly',
            field.get_state_attrs(record).get('readonly', False))
        if readonly and size:
            cell.set_property('visible', False)
        else:
            cell.set_property('visible', not invisible)
        self._set_visual(cell, record)


class _BinaryOpen(_BinarySave):
    icon_name = 'tryton-open'

    def clicked(self, renderer, path):
        record, field = self._get_record_field_from_path(path)
        filename_field = record.group.fields.get(self.attrs.get('filename'))
        filename = filename_field.get(record)
        file_path = file_write(filename, self.binary.get_data(record, field))
        root, type_ = os.path.splitext(filename)
        if type_:
            type_ = type_[1:]
        GLib.idle_add(file_open, file_path, type_)

    @realized
    @CellCache.cache
    def setter(self, column, cell, store, iter_, user_data=None):
        super().setter(column, cell, store, iter_)
        record, field = self._get_record_field_from_iter(iter_, store)
        filename_field = record.group.fields.get(self.attrs.get('filename'))
        filename = filename_field.get(record)
        if not filename:
            cell.set_property('visible', False)


class Image(GenericText):
    align = 0.5

    def __init__(self, view, attrs=None, renderer=None):
        if renderer is None:
            renderer = Gtk.CellRendererPixbuf
        super(Image, self).__init__(view, attrs, renderer)
        self.height = int(attrs.get('height', 100))
        self.width = int(attrs.get('width', 300))
        self.renderer.set_fixed_size(self.width, self.height)

    @realized
    @CellCache.cache
    def setter(self, column, cell, store, iter_, user_data=None):
        record, field = self._get_record_field_from_iter(iter_, store)
        value = field.get_client(record)
        if isinstance(value, int):
            if value > CONFIG['image.max_size']:
                value = None
            else:
                value = field.get_data(record)
        pixbuf = data2pixbuf(value)
        if pixbuf:
            pixbuf = common.resize_pixbuf(pixbuf, self.width, self.height)
        cell.set_property('pixbuf', pixbuf)
        self._set_visual(cell, record)

    def get_textual_value(self, record):
        if not record:
            return ''
        return str(record[self.attrs['name']].get_size(record))


class M2O(GenericText):

    def __init__(self, view, attrs, renderer=None):
        if renderer is None and int(attrs.get('completion', 1)):
            renderer = partial(CellRendererTextCompletion, self.set_completion)
        super(M2O, self).__init__(view, attrs, renderer=renderer)

    def get_model(self, record, field):
        return self.attrs['relation']

    def has_target(self, value):
        return value is not None

    def value_from_id(self, model, id_, str_=None):
        if str_ is None:
            str_ = ''
        return id_, str_

    def id_from_value(self, value):
        return value

    def value_from_text(self, record, text, callback=None):
        field = record.group.fields[self.attrs['name']]
        model = self.get_model(record, field)
        if not text:
            field.set_client(
                record, self.value_from_id(model, None, ''))
            if callback:
                callback()
            return

        if model and common.get_toplevel_window().get_focus():
            field = record[self.attrs['name']]
            win = self.search_remote(record, field, text, callback=callback)
            if len(win.screen.group) == 1:
                win.response(None, Gtk.ResponseType.OK)
            else:
                win.show()

    def editing_started(self, cell, editable, path):
        super(M2O, self).editing_started(cell, editable, path)
        record, field = self._get_record_field_from_path(path)
        model = self.get_model(record, field)

        def changed(editable):
            text = editable.get_text()
            if self.get_textual_value(record) != text:
                field.set_client(
                    record, self.value_from_id(model, None, ''))

            if self.has_target(field.get(record)):
                icon1, tooltip1 = 'tryton-open', _("Open the record <F2>")
                icon2, tooltip2 = 'tryton-clear', _("Clear the field <Del>")
            else:
                icon1, tooltip1 = None, ''
                icon2, tooltip2 = 'tryton-search', _("Search a record <F2>")
            for pos, icon, tooltip in [
                    (Gtk.EntryIconPosition.PRIMARY, icon1, tooltip1),
                    (Gtk.EntryIconPosition.SECONDARY, icon2, tooltip2)]:
                if icon:
                    pixbuf = common.IconFactory.get_pixbuf(
                        icon, Gtk.IconSize.MENU)
                else:
                    pixbuf = None
                editable.set_icon_from_pixbuf(pos, pixbuf)
                editable.set_icon_tooltip_text(pos, tooltip)

        def icon_press(editable, icon_pos, event):
            value = field.get(record)
            if not model:
                return
            if (icon_pos == Gtk.EntryIconPosition.SECONDARY
                    and self.has_target(value)):
                field.set_client(
                    record, self.value_from_id(model, None, ''))
                editable.set_text('')
            elif self.has_target(value):
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
        model = self.get_model(record, field)

        access = common.MODELACCESS[model]
        if (create
                and not (self.attrs.get('create', True) and access['create'])):
            return
        elif not access['read']:
            return

        domain = field.domain_get(record)
        context = field.get_context(record)
        if not create and changed:
            self.search_remote(record, field, text, callback=callback).show()
            return
        target_id = self.id_from_value(field.get(record))

        screen = Screen(model, domain=domain, context=context,
            mode=['form'], view_ids=self.attrs.get('view_ids', '').split(','),
            exclude_field=field.attrs.get('relation_field'))

        def open_callback(result):
            if result:
                value = self.value_from_id(
                    model,
                    screen.current_record.id,
                    screen.current_record.rec_name())
                field.set_client(record, value, force_change=True)
            if callback:
                callback()
        if target_id and target_id >= 0:
            screen.load([target_id])
            WinForm(screen, open_callback, save_current=True,
                title=field.attrs.get('string'))
        else:
            WinForm(screen, open_callback, new=True, save_current=True,
                title=field.attrs.get('string'), rec_name=text)

    def search_remote(self, record, field, text, callback=None):
        model = self.get_model(record, field)
        domain = field.domain_get(record)
        context = field.get_search_context(record)
        order = field.get_search_order(record)
        access = common.MODELACCESS[model]
        create_access = self.attrs.get('create', True) and access['create']

        def search_callback(found):
            value = None
            if found:
                value = self.value_from_id(model, *found[0])
                field.set_client(record, value)
            if callback:
                callback()
        win = WinSearch(model, search_callback, sel_multi=False,
            context=context, domain=domain,
            order=order, view_ids=self.attrs.get('view_ids', '').split(','),
            new=create_access, title=self.attrs.get('string'))
        win.screen.search_filter(quote(text))
        return win

    def set_completion(self, entry, path):
        record, field = self._get_record_field_from_path(path)
        if entry.get_completion():
            entry.set_completion(None)
        model = self.get_model(record, field)
        if not model:
            return
        access = common.MODELACCESS[model]
        completion = get_completion(
            search=access['read'],
            create=self.attrs.get('create', True) and access['create'])
        completion.connect('match-selected', self._completion_match_selected,
            record, field, model)
        completion.connect('action-activated',
            self._completion_action_activated, record, field)
        entry.set_completion(completion)
        entry.connect('key-press-event', self._key_press, record, field)
        entry.connect('changed', self._update_completion, record, field)

    def _key_press(self, entry, event, record, field):
        if (self.has_target(field.get(record))
                and event.keyval in [Gdk.KEY_Delete, Gdk.KEY_BackSpace]):
            entry.set_text('')
        return False

    def _completion_match_selected(
            self, completion, model, iter_, record, field, model_name):
        rec_name, record_id = model.get(iter_, 0, 1)
        field.set_client(
            record, self.value_from_id(model_name, record_id, rec_name))

        completion.get_entry().set_text(rec_name)
        completion_model = completion.get_model()
        completion_model.clear()
        completion_model.search_text = rec_name
        return True

    def _update_completion(self, entry, record, field):
        value = field.get(record)
        if self.has_target(value):
            id_ = self.id_from_value(value)
            if id_ is not None and id_ >= 0:
                return
        model = self.get_model(record, field)
        update_completion(entry, record, field, model)

    def _completion_action_activated(self, completion, index, record, field):
        entry = completion.get_entry()
        entry.handler_block(entry.editing_done_id)

        def callback():
            entry.handler_unblock(entry.editing_done_id)
            entry.set_text(field.get_client(record))
        if index == 0:
            self.open_remote(record, create=False, changed=True,
                text=entry.get_text(), callback=callback)
        elif index == 1:
            self.open_remote(record, create=True,
                text=entry.get_text(), callback=callback)
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

    def get_value(self, record, field):
        return field.get(record)

    def get_textual_value(self, record):
        field = record[self.attrs['name']]
        self.update_selection(record, field)
        value = self.get_value(record, field)
        text = dict(self.selection).get(value, '')
        if value and not text:
            text = self.get_inactive_selection(value)
        return text

    def value_from_text(self, record, text, callback=None):
        if callback:
            callback()

    def set_editable(self):
        if not self.editable and not self.editing:
            return
        record, field = self.editing
        value = self.get_value(record, field)
        self.update_selection(record, field)
        self.set_popdown_value(self.editable, value)

    def editing_started(self, cell, editable, path):
        super(Selection, self).editing_started(cell, editable, path)
        record, field = self._get_record_field_from_path(path)
        # Combobox does not emit remove-widget when focus is changed
        self.editable.connect(
            'editing-done',
            lambda *a: self.editable.emit('remove-widget'))

        selection_shortcuts(editable)

        def set_value(*a):
            return self.set_value(editable, record, field)
        editable.get_child().connect('activate', set_value)
        editable.get_child().connect('focus-out-event', set_value)
        editable.connect('changed', set_value)

        self.update_selection(record, field)
        self.set_popdown(self.selection, editable)

        value = self.get_value(record, field)
        if not self.set_popdown_value(editable, value):
            self.get_inactive_selection(value)
            self.set_popdown_value(editable, value)
        return False

    def set_value(self, editable, record, field):
        value = self.get_popdown_value(editable)
        if 'relation' in self.attrs and value:
            active = editable.get_active()
            if active < 0:
                text = None
            else:
                model = editable.get_model()
                index = editable.get_property('entry-text-column')
                text = model[active][index]
            value = (value, text)
        field.set_client(record, value)
        return False


class MultiSelection(GenericText, SelectionMixin):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_selection()

    @realized
    @CellCache.cache
    def setter(self, column, cell, store, iter_, user_data=None):
        super().setter(column, cell, store, iter_, user_data=user_data)
        cell.set_property('editable', False)

    def value_from_text(self, record, text, callback=None):
        if callback:
            callback()

    def get_textual_value(self, record):
        field = record[self.attrs['name']]
        self.update_selection(record, field)
        selection = dict(self.selection)
        values = []
        for value in field.get_eval(record):
            text = selection.get(value, '')
            values.append(text)
        return ';'.join(values)


class Reference(M2O):

    def __init__(self, view, attrs, renderer=None):
        super(Reference, self).__init__(view, attrs, renderer=renderer)
        self.renderer_selection = _ReferenceSelection(view, attrs)

    @property
    def prefixes(self):
        return [self.renderer_selection]

    def get_model(self, record, field):
        value = field.get_client(record)
        if value:
            model, value = value
            return model

    def has_target(self, value):
        if not value:
            return False
        model, value = value.split(',')
        if not value:
            value = None
        else:
            try:
                value = int(value)
            except ValueError:
                value = None
        return model and value >= 0

    def value_from_id(self, model, id_, str_=None):
        if str_ is None:
            str_ = ''
        return model, (id_, str_)

    def id_from_value(self, value):
        _, value = value.split(',')
        return int(value)

    def get_textual_value(self, record):
        value = super().get_textual_value(record)
        if value:
            model, value = value
        else:
            value = ''
        return value


class _ReferenceSelection(Selection):

    def get_value(self, record, field):
        value = field.get_client(record)
        if value:
            model, value = value
        else:
            model = None
        return model

    def set_value(self, editable, record, field):
        value = self.get_popdown_value(editable)
        if value != self.get_value(record, field):
            if value:
                value = (value, (-1, ''))
            else:
                value = ('', '')
            field.set_client(record, value)
        return False


class Dict(GenericText):
    align = 0.5

    def __init__(self, view, attrs):
        super().__init__(view, attrs)
        self.renderer.props.editable = False

    def setter(self, column, cell, store, iter_, user_data=None):
        super().setter(column, cell, store, iter_, user_data=None)
        cell.props.editable = False

    def get_textual_value(self, record):
        return '(%s)' % len(record[self.attrs['name']].get_client(record))


class ProgressBar(Cell):
    align = 0.5
    orientations = {
        'left_to_right': (Gtk.Orientation.HORIZONTAL, False),
        'right_to_left': (Gtk.Orientation.HORIZONTAL, True),
        'bottom_to_top': (Gtk.Orientation.VERTICAL, True),
        'top_to_bottom': (Gtk.Orientation.VERTICAL, False),
        }

    def __init__(self, view, attrs):
        super(ProgressBar, self).__init__()
        self.view = view
        self.attrs = attrs
        self.renderer = Gtk.CellRendererProgress()
        orientation, inverted = self.orientations.get(
            self.attrs.get('orientation', 'left_to_right'))
        self.renderer.set_orientation(orientation)
        self.renderer.set_property('inverted', inverted)
        self.renderer.set_property('yalign', 0)

    @realized
    @CellCache.cache
    def setter(self, column, cell, store, iter_, user_data=None):
        record, field = self._get_record_field_from_iter(iter_, store)
        field.state_set(record, states=('invisible',))
        invisible = field.get_state_attrs(record).get('invisible', False)
        cell.set_property('visible', not invisible)
        text = self.get_textual_value(record)
        if text:
            text = _('%s%%') % text
        cell.set_property('text', text)
        value = field.get(record) or 0.0
        cell.set_property('value', value * 100)
        self._set_visual(cell, record)

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


class Button(Cell):

    def __init__(self, view, attrs):
        super(Button, self).__init__()
        self.attrs = attrs
        self.renderer = CellRendererButton(attrs.get('string', _('Unknown')))
        self.view = view

        self.renderer.connect('clicked', self.button_clicked)
        self.renderer.set_property('yalign', 0)

    @realized
    @CellCache.cache
    def setter(self, column, cell, store, iter_, user_data=None):
        record = store.get_value(iter_, 0)
        states = record.expr_eval(self.attrs.get('states', {}))
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
        self._set_visual(cell, record)

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
