# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gettext

import gobject

from .widget import Widget
from tryton.common.datetime_ import (Date as DateEntry, Time as TimeEntry,
    DateTime as DateTimeEntry, add_operators)
from tryton.common.widget_style import set_widget_style
from tryton.config import CONFIG

_ = gettext.gettext


class Date(Widget):

    def __init__(self, view, attrs, _entry=DateEntry):
        super(Date, self).__init__(view, attrs)

        self.widget = gtk.HBox()
        self.entry = self.mnemonic_widget = add_operators(_entry())
        self.real_entry.set_property('activates_default', True)
        self.real_entry.connect('key_press_event', self.sig_key_press)
        self.real_entry.connect('activate', self.sig_activate)
        self.real_entry.connect('changed', lambda _: self.send_modified())
        self.real_entry.connect('focus-out-event',
            lambda x, y: self._focus_out())
        self.widget.pack_start(self.entry, expand=False, fill=False)

    @property
    def real_entry(self):
        return self.entry

    def _set_editable(self, value):
        self.entry.set_editable(value)
        set_widget_style(self.entry, value)
        self.entry.set_icon_sensitive(gtk.ENTRY_ICON_SECONDARY, value)

    def _readonly_set(self, value):
        self._set_editable(not value)
        if value and CONFIG['client.fast_tabbing']:
            self.widget.set_focus_chain([])
        else:
            self.widget.unset_focus_chain()

    @property
    def modified(self):
        if self.record and self.field:
            return self.field.get_client(self.record) != self.entry.props.value
        return False

    def sig_key_press(self, widget, event):
        self.send_modified()

    def set_value(self, record, field):
        field.set_client(record, self.get_value())

    def get_value(self):
        return self.entry.props.value

    def set_format(self, record, field):
        if field and record:
            format_ = field.date_format(record)
        else:
            format_ = self.view.screen.context.get('date_format', '%x')
        self.entry.props.format = format_

    def display(self, record, field):
        super(Date, self).display(record, field)
        if field and record:
            value = field.get_client(record)
        else:
            value = ''
        self.entry.props.value = value
        self.set_format(record, field)


class Time(Date):
    def __init__(self, view, attrs):
        super(Time, self).__init__(view, attrs, _entry=TimeEntry)
        self.entry.set_focus_chain([self.entry.get_child()])
        self.entry.connect('time-changed', self.changed)

    def _set_editable(self, value):
        self.entry.set_sensitive(value)

    @property
    def real_entry(self):
        return self.entry.get_child()

    def display(self, record, field):
        super(Time, self).display(record, field)

    def set_format(self, record, field):
        if field and record:
            format_ = field.time_format(record)
        else:
            format_ = '%X'
        self.entry.props.format = format_

    def changed(self, combobox):
        def focus_out():
            if combobox.props.window:
                self._focus_out()
        # Only when changed from pop list
        if not combobox.get_child().has_focus():
            # Must be deferred because it triggers a display of the form
            gobject.idle_add(focus_out)


class DateTime(Date):
    def __init__(self, view, attrs):
        Widget.__init__(self, view, attrs)

        self.widget = gtk.HBox()
        self.entry = self.mnemonic_widget = DateTimeEntry()
        for child in self.entry.get_children():
            add_operators(child)
            if isinstance(child, gtk.ComboBoxEntry):
                child.set_focus_chain([child.get_child()])
                child = child.get_child()
            child.set_property('activates_default', True)
            child.connect('key_press_event', self.sig_key_press)
            child.connect('activate', self.sig_activate)
            child.connect('changed', lambda _: self.send_modified())
            child.connect('focus-out-event', lambda x, y: self._focus_out())
        self.widget.pack_start(self.entry, expand=False, fill=False)

    def _set_editable(self, value):
        for child in self.entry.get_children():
            if isinstance(child, gtk.Entry):
                child.set_editable(value)
                set_widget_style(child, value)
                child.set_icon_sensitive(gtk.ENTRY_ICON_SECONDARY, value)
            elif isinstance(child, gtk.ComboBoxEntry):
                child.set_sensitive(value)

    def set_format(self, record, field):
        if field and record:
            date_format = field.date_format(record)
            time_format = field.time_format(record)
        else:
            date_format = self.view.screen.context.get('date_format', '%x')
            time_format = '%X'
        self.entry.props.date_format = date_format
        self.entry.props.time_format = time_format
