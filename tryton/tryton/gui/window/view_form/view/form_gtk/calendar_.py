# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import gettext

from gi.repository import GLib, Gtk

from .widget import Widget
from tryton import common
from tryton.common.datetime_ import (Date as DateEntry, Time as TimeEntry,
    DateTime as DateTimeEntry, add_operators)

_ = gettext.gettext


class Date(Widget):

    def __init__(self, view, attrs, _entry=DateEntry):
        super(Date, self).__init__(view, attrs)

        self.widget = Gtk.HBox()
        self.entry = self.mnemonic_widget = add_operators(_entry())
        self.real_entry.set_property('activates_default', True)
        self.real_entry.connect('key_press_event', self.sig_key_press)
        self.real_entry.connect('activate', self.sig_activate)
        self.real_entry.connect('changed', lambda _: self.send_modified())
        self.real_entry.connect('focus-out-event',
            lambda x, y: self._focus_out())
        self.widget.pack_start(self.entry, expand=False, fill=False, padding=0)

    @property
    def real_entry(self):
        return self.entry

    def _set_editable(self, value):
        self.entry.set_editable(value)
        self.entry.set_icon_sensitive(Gtk.EntryIconPosition.PRIMARY, value)

    def _readonly_set(self, value):
        self._set_editable(not value)

    @classmethod
    def cast(cls, value):
        if isinstance(value, datetime.datetime):
            value = value.date()
        return value

    @property
    def modified(self):
        if self.record and self.field:
            field_value = self.cast(self.field.get_client(self.record))
            return field_value != self.get_value()
        return False

    def sig_key_press(self, widget, event):
        self.send_modified()

    def set_value(self):
        self.field.set_client(self.record, self.get_value())

    def get_value(self):
        self.entry.parse()
        return self.entry.props.value

    def set_format(self):
        if self.field and self.record:
            format_ = self.field.date_format(self.record)
        else:
            format_ = common.date_format(
                self.view.screen.context.get('date_format'))
        self.entry.props.format = format_

    def display(self):
        super(Date, self).display()
        if self.field and self.record:
            value = self.field.get_client(self.record)
        else:
            value = ''
        self.entry.props.value = value
        self.set_format()


class Time(Date):
    def __init__(self, view, attrs):
        super(Time, self).__init__(view, attrs, _entry=TimeEntry)
        self.entry.connect('time-changed', self.changed)

    def _set_editable(self, value):
        self.entry.set_sensitive(value)

    @classmethod
    def cast(cls, value):
        if isinstance(value, datetime.datetime):
            value = value.time()
        return value

    @property
    def real_entry(self):
        return self.entry.get_child()

    def display(self):
        super(Time, self).display()

    def set_format(self):
        if self.field and self.record:
            format_ = self.field.time_format(self.record)
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
            GLib.idle_add(focus_out)


class DateTime(Date):
    def __init__(self, view, attrs):
        Widget.__init__(self, view, attrs)

        self.widget = Gtk.HBox()
        self.entry = self.mnemonic_widget = DateTimeEntry()
        for child in self.entry.get_children():
            add_operators(child)
            if isinstance(child, Gtk.ComboBox):
                child = child.get_child()
            child.set_property('activates_default', True)
            child.connect('key_press_event', self.sig_key_press)
            child.connect('activate', self.sig_activate)
            child.connect('changed', lambda _: self.send_modified())
            child.connect('focus-out-event', lambda x, y: self._focus_out())
        self.widget.pack_start(self.entry, expand=False, fill=False, padding=0)

    @classmethod
    def cast(cls, value):
        return value

    def _set_editable(self, value):
        for child in self.entry.get_children():
            if isinstance(child, Gtk.Entry):
                child.set_editable(value)
                child.set_icon_sensitive(Gtk.EntryIconPosition.PRIMARY, value)
            elif isinstance(child, Gtk.ComboBox):
                child.set_sensitive(value)

    def set_format(self):
        if self.field and self.record:
            date_format = self.field.date_format(self.record)
            time_format = self.field.time_format(self.record)
        else:
            date_format = common.date_format(
                self.view.screen.context.get('date_format'))
            time_format = '%X'
        self.entry.props.date_format = date_format
        self.entry.props.time_format = time_format
