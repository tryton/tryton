# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import operator
import gobject
import gtk
import locale
import decimal
import gettext
from decimal import Decimal

from .widget import Widget
from tryton.config import CONFIG
from tryton.gui.window.win_search import WinSearch
from tryton.common import RPCExecute, RPCException, timezoned_date, \
    datetime_strftime, Tooltips
from tryton.common.date_widget import DateEntry
from tryton.common.placeholder_entry import PlaceholderEntry
from tryton.common.selection import selection_shortcuts
from tryton.translate import date_format

_ = gettext.gettext


class DictEntry(object):
    expand = True
    fill = True

    def __init__(self, name, parent_widget):
        self.name = name
        self.definition = parent_widget.keys[name]
        self.parent_widget = parent_widget
        self.widget = self.create_widget()

    def create_widget(self):
        widget = gtk.Entry()
        widget.connect('key-press-event', self.parent_widget.send_modified)
        widget.connect('focus-out-event',
            lambda w, e: self.parent_widget._focus_out())
        return widget

    def modified(self, value):
        return self.get_value() != value.get(self.name)

    def get_value(self):
        return self.widget.get_text()

    def set_value(self, value):
        return self.widget.set_text(value or '')

    def set_readonly(self, readonly):
        self.widget.set_editable(not readonly)


class DictBooleanEntry(DictEntry):

    def create_widget(self):
        widget = gtk.CheckButton()
        widget.connect('toggled', self.parent_widget.send_modified)
        widget.connect('focus-out-event', lambda w, e:
            self.parent_widget._focus_out())
        return widget

    def get_value(self):
        return self.widget.props.active

    def set_value(self, value):
        self.widget.props.active = bool(value)

    def set_readonly(self, readonly):
        self.widget.set_sensitive(not readonly)


class DictSelectionEntry(DictEntry):
    expand = False
    fill = False

    def create_widget(self):
        widget = gtk.ComboBoxEntry()

        # customizing entry
        widget.child.props.activates_default = True
        widget.child.connect('changed', self.parent_widget.send_modified)
        widget.child.connect('focus-out-event',
            lambda w, e: self.parent_widget._focus_out())
        widget.child.connect('activate',
            lambda w: self.parent_widget._focus_out())
        widget.connect('notify::active',
            lambda w, e: self.parent_widget._focus_out())
        selection_shortcuts(widget)

        # setting completion and selection
        model = gtk.ListStore(gobject.TYPE_STRING)
        model.append(('',))
        self._selection = {'': None}
        width = 10
        selection = self.definition['selection']
        if self.definition.get('sorted', True):
            selection.sort(key=operator.itemgetter(1))
        for value, name in selection:
            name = str(name)
            self._selection[name] = value
            model.append((name,))
            width = max(width, len(name))
        widget.set_model(model)
        widget.set_text_column(0)
        widget.child.set_width_chars(width)
        completion = gtk.EntryCompletion()
        completion.set_inline_selection(True)
        completion.set_model(model)
        widget.child.set_completion(completion)
        completion.set_text_column(0)
        return widget

    def get_value(self):
        if not self.widget.child:  # widget is destroyed
            return
        text = self.widget.child.get_text()
        value = None
        if text:
            for txt, val in self._selection.items():
                if not val:
                    continue
                if txt[:len(text)].lower() == text.lower():
                    value = val
                    if len(txt) == len(text):
                        break
        return value

    def set_value(self, value):
        values = dict(self.definition['selection'])
        self.widget.child.set_text(values.get(value, ''))

    def set_readonly(self, readonly):
        self.widget.set_sensitive(not readonly)


class DictIntegerEntry(DictEntry):
    expand = False
    fill = False

    def create_widget(self):
        widget = super(DictIntegerEntry, self).create_widget()
        widget.set_width_chars(8)
        widget.set_max_length(0)
        widget.set_alignment(1.0)
        widget.connect('insert-text', self.sig_insert_text)
        return widget

    def sig_insert_text(self, entry, new_text, new_text_length, position):
        value = entry.get_text()
        position = entry.get_position()
        new_value = value[:position] + new_text + value[position:]
        if new_value == '-':
            return
        try:
            locale.atoi(new_value)
        except ValueError:
            entry.stop_emission('insert-text')

    def get_value(self):
        txt_value = self.widget.get_text()
        if txt_value:
            try:
                return locale.atoi(txt_value)
            except ValueError:
                pass
        return None

    def set_value(self, value):
        if value is not None:
            txt_val = locale.format('%d', value, True)
        else:
            txt_val = ''
        self.widget.set_text(txt_val)


class DictFloatEntry(DictIntegerEntry):

    def digits(self):
        default = (16, 2)
        record = self.parent_widget.record
        if not record:
            return default
        return tuple(y if x is None else x for x, y in zip(
                record.expr_eval(self.definition.get('digits', default)),
                default))

    def sig_insert_text(self, entry, new_text, new_text_length, position):
        value = entry.get_text()
        position = entry.get_position()
        new_value = value[:position] + new_text + value[position:]
        decimal_point = locale.localeconv()['decimal_point']

        if new_value in ('-', decimal_point):
            return

        digits = self.digits()

        try:
            locale.atof(new_value)
        except ValueError:
            entry.stop_emission('insert-text')
            return

        new_int = new_value
        new_decimal = ''
        if decimal_point in new_value:
            new_int, new_decimal = new_value.rsplit(decimal_point, 1)

        if (len(new_int) > digits[0]
                or len(new_decimal) > digits[1]):
            entry.stop_emission('insert-text')

    def get_value(self):
        txt_value = self.widget.get_text()
        if txt_value:
            try:
                return locale.atof(txt_value)
            except ValueError:
                pass
        return None

    def set_value(self, value):
        digits = self.digits()
        if value is not None:
            txt_val = locale.format('%.' + str(digits[1]) + 'f', value, True)
        else:
            txt_val = ''
        self.widget.set_width_chars(sum(digits))
        self.widget.set_text(txt_val)


class DictNumericEntry(DictFloatEntry):

    def get_value(self):
        txt_value = self.widget.get_text()
        if txt_value:
            try:
                return locale.atof(txt_value, Decimal)
            except decimal.InvalidOperation:
                pass
        return None


class DictDateTimeEntry(DictEntry):
    expand = False
    fill = False

    def create_widget(self):
        widget = DateEntry('')
        widget.set_format(self.get_format())
        widget.connect('key_press_event', self.parent_widget.send_modified)
        widget.connect('focus-out-event', lambda w, e:
            self.parent_widget._focus_out())
        return widget

    def modified(self, value):
        if value.get(self.name):
            text = datetime_strftime(timezoned_date(value[self.name]),
                self.get_format())
        else:
            text = ''
        return self.widget.compute_date(self.widget.get_text()) != text

    def get_format(self):
        return date_format() + ' %H:%M:%S'  # got to find a way

    def get_value(self):
        return self.widget.date_get()

    def set_value(self, value):
        self.widget.date_set(value)
        txt = self.widget.get_text()
        if txt:
            if len(txt) > self.widget.get_width_chars():
                self.widget.set_width_chars(len(txt))


class DictDateEntry(DictDateTimeEntry):

    def modified(self, value):
        if value.get(self.name):
            text = datetime_strftime(value[self.name], self.get_format())
        else:
            text = ''
        return self.widget.compute_date(self.widget.get_text()) != text

    def get_format(self):
        return date_format()

    def get_value(self):
        dt = super(DictDateEntry, self).get_value()
        return dt.date() if dt else None


DICT_ENTRIES = {
    'char': DictEntry,
    'boolean': DictBooleanEntry,
    'selection': DictSelectionEntry,
    'datetime': DictDateTimeEntry,
    'date': DictDateEntry,
    'integer': DictIntegerEntry,
    'float': DictFloatEntry,
    'numeric': DictNumericEntry,
    }


class DictWidget(Widget):

    def __init__(self, view, attrs):
        super(DictWidget, self).__init__(view, attrs)
        self.schema_model = attrs['schema_model']
        self.keys = {}
        self.fields = {}
        self.buttons = {}
        self.rows = {}

        self.widget = gtk.Frame(attrs.get('string', ''))
        self.widget.set_shadow_type(gtk.SHADOW_OUT)

        vbox = gtk.VBox()
        self.widget.add(vbox)

        self.table = gtk.Table(1, 3, homogeneous=False)
        self.table.set_col_spacings(0)
        self.table.set_row_spacings(0)
        self.table.set_border_width(0)
        vbox.pack_start(self.table, expand=True, fill=True)

        hbox = gtk.HBox()
        hbox.set_border_width(2)
        self.wid_text = PlaceholderEntry()
        self.wid_text.set_placeholder_text(_('Search'))
        self.wid_text.props.width_chars = 13
        self.wid_text.connect('activate', self._sig_activate)
        hbox.pack_start(self.wid_text, expand=True, fill=True)
        self.but_add = gtk.Button()
        self.but_add.connect('clicked', self._sig_add)
        img_add = gtk.Image()
        img_add.set_from_stock('tryton-list-add', gtk.ICON_SIZE_SMALL_TOOLBAR)
        img_add.set_alignment(0.5, 0.5)
        self.but_add.add(img_add)
        self.but_add.set_relief(gtk.RELIEF_NONE)
        hbox.pack_start(self.but_add, expand=False, fill=False)
        hbox.set_focus_chain([self.wid_text])
        vbox.pack_start(hbox, expand=True, fill=True)

        self.tooltips = Tooltips()
        self.tooltips.set_tip(self.but_add, _('Add value'))
        self.tooltips.enable()

        self._readonly = False
        self._record_id = None

    def _new_remove_btn(self):
        but_remove = gtk.Button()
        img_remove = gtk.Image()
        img_remove.set_from_stock('tryton-list-remove',
            gtk.ICON_SIZE_SMALL_TOOLBAR)
        img_remove.set_alignment(0.5, 0.5)
        but_remove.add(img_remove)
        but_remove.set_relief(gtk.RELIEF_NONE)
        return but_remove

    def _sig_activate(self, *args):
        if self.wid_text.get_editable():
            self._sig_add()

    def _sig_add(self, *args):
        context = self.field.context_get(self.record)
        value = self.wid_text.get_text().decode('utf-8')
        domain = self.field.domain_get(self.record)

        def callback(result):
            if result:
                self.send_modified()
                try:
                    new_fields = RPCExecute('model', self.schema_model,
                        'get_keys', [r[0] for r in result],
                        context=context)
                except RPCException:
                    new_fields = []
                for new_field in new_fields:
                    if new_field['name'] not in self.fields:
                        self.keys[new_field['name']] = new_field
                        self.add_line(new_field['name'])
            self.wid_text.set_text('')

        win = WinSearch(self.schema_model, callback, sel_multi=True,
            context=context, domain=domain, new=False)
        win.screen.search_filter(value)

    def _sig_remove(self, button, key, modified=True):
        del self.fields[key]
        del self.buttons[key]
        for widget in self.rows[key]:
            self.table.remove(widget)
            widget.destroy()
        del self.rows[key]
        if modified:
            self.send_modified()
            self.set_value(self.record, self.field)

    def set_value(self, record, field):
        field.set_client(record, self.get_value())

    def get_value(self):
        return dict((key, widget.get_value())
            for key, widget in self.fields.items())

    @property
    def modified(self):
        if self.record and self.field:
            value = self.field.get_client(self.record)
            return any(widget.modified(value)
                for widget in self.fields.itervalues())
        return False

    def _readonly_set(self, readonly):
        self._readonly = readonly
        self._set_button_sensitive()
        for widget in self.fields.values():
            widget.set_readonly(readonly)
        self.wid_text.set_editable(not readonly)

    def _set_button_sensitive(self):
        self.but_add.set_sensitive(bool(
                not self._readonly
                and self.attrs.get('create', True)))
        for button in self.buttons.itervalues():
            button.set_sensitive(bool(
                    not self._readonly
                    and self.attrs.get('delete', True)))

    def add_line(self, key):
        self.fields[key] = DICT_ENTRIES[self.keys[key]['type_']](key, self)
        field = self.fields[key]
        alignment = gtk.Alignment(
            float(self.attrs.get('xalign', 0.0)),
            float(self.attrs.get('yalign', 0.5)),
            float(self.attrs.get('xexpand', 1.0)),
            float(self.attrs.get('yexpand', 1.0)))
        hbox = gtk.HBox()
        hbox.pack_start(field.widget, expand=field.expand, fill=field.fill)
        alignment.add(hbox)
        n_rows = self.table.props.n_rows
        self.table.resize(n_rows + 1, 3)
        if gtk.widget_get_default_direction() == gtk.TEXT_DIR_RTL:
            text = _(':') + self.keys[key]['string']
        else:
            text = self.keys[key]['string'] + _(':')
        label = gtk.Label(text)
        label.set_alignment(1., .5)
        self.table.attach(label, 0, 1, n_rows - 1, n_rows,
            xoptions=gtk.FILL, yoptions=False, xpadding=2)
        label.show()
        self.table.attach(alignment, 1, 2, n_rows - 1, n_rows,
            xoptions=gtk.FILL | gtk.EXPAND, yoptions=False, xpadding=2)
        alignment.show_all()
        remove_but = self._new_remove_btn()
        self.tooltips.set_tip(remove_but, _('Remove "%s"') %
            self.keys[key]['string'])
        self.table.attach(remove_but, 2, 3, n_rows - 1, n_rows,
            xoptions=gtk.FILL, yoptions=False, xpadding=2)
        remove_but.connect('clicked', self._sig_remove, key)
        remove_but.show_all()
        self.rows[key] = [label, alignment, remove_but]
        self.buttons[key] = remove_but

    def add_keys(self, keys):
        context = self.field.context_get(self.record)
        domain = self.field.domain_get(self.record)
        batchlen = min(10, CONFIG['client.limit'])
        for i in xrange(0, len(keys), batchlen):
            sub_keys = keys[i:i + batchlen]
            try:
                key_ids = RPCExecute('model', self.schema_model, 'search',
                    [('name', 'in', sub_keys), domain], 0,
                    CONFIG['client.limit'], None, context=context)
                if not key_ids:
                    continue
                values = RPCExecute('model', self.schema_model,
                    'get_keys', key_ids, context=context)
                if not values:
                    continue
            except RPCException:
                pass
            self.keys.update({k['name']: k for k in values})

    def display(self, record, field):
        super(DictWidget, self).display(record, field)

        if field is None:
            return

        record_id = record.id if record else None
        if record_id != self._record_id:
            for key in self.fields.keys():
                self._sig_remove(None, key, modified=False)
            self._record_id = record_id

        value = field.get_client(record) if field else {}
        new_key_names = set(value.iterkeys()) - set(self.keys)
        if new_key_names:
            self.add_keys(list(new_key_names))
        for key, val in sorted(value.iteritems()):
            if key not in self.keys:
                continue
            if key not in self.fields:
                self.add_line(key)
            widget = self.fields[key]
            widget.set_value(val)
            widget.set_readonly(self._readonly)
        for key in set(self.fields.keys()) - set(value.keys()):
            self._sig_remove(None, key, modified=False)

        self._set_button_sensitive()
