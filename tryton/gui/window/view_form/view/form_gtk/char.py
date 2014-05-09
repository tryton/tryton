#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gettext

import gobject
import gtk
from interface import WidgetInterface, TranslateMixin
from tryton.common import Tooltips

_ = gettext.gettext


class Char(WidgetInterface, TranslateMixin):
    "Char"

    def __init__(self, field_name, model_name, attrs=None):
        super(Char, self).__init__(field_name, model_name, attrs=attrs)

        self.widget = gtk.HBox()
        self.autocomplete = bool(attrs.get('autocomplete'))
        if self.autocomplete:
            self.entry = gtk.ComboBoxEntry()
            self.entry_store = gtk.ListStore(gobject.TYPE_STRING)
            self.entry.set_model(self.entry_store)
            self.entry.set_text_column(0)
            completion = gtk.EntryCompletion()
            completion.set_model(self.entry_store)
            completion.set_text_column(0)
            self.entry.get_child().set_completion(completion)
            focus_entry = self.entry.get_child()
        else:
            self.entry = gtk.Entry()
            focus_entry = self.entry

        focus_entry.set_property('activates_default', True)
        focus_entry.connect('activate', self.sig_activate)
        focus_entry.connect('focus-out-event', lambda x, y: self._focus_out())
        focus_entry.connect('key-press-event', self.send_modified)
        expand, fill = True, True
        if attrs.get('size'):
            expand, fill = False, False
        self.widget.pack_start(self.entry, expand=expand, fill=fill)

        self.button = None
        if attrs.get('translate'):
            self.button = self.translate_button()
            self.widget.pack_start(self.button, False, False)

    def translate_widget(self):
        entry = gtk.Entry()
        entry.set_property('activates_default', True)
        if self.record:
            field_size = self.record.expr_eval(self.attrs.get('size'))
            entry.set_width_chars(field_size or -1)
            entry.set_max_length(field_size or 0)
        return entry

    @staticmethod
    def translate_widget_set(widget, value):
        widget.set_text(value or '')

    @staticmethod
    def translate_widget_get(widget):
        return widget.get_text()

    @staticmethod
    def translate_widget_set_readonly(widget, value):
        widget.set_editable(not value)
        widget.props.sensitive = not value

    def _color_widget(self):
        if self.autocomplete:
            return self.entry.get_child()
        return self.entry

    def grab_focus(self):
        return self.entry.grab_focus()

    @property
    def modified(self):
        if self.record and self.field:
            entry = self.entry.get_child() if self.autocomplete else self.entry
            value = entry.get_text() or ''
            return self.field.get_client(self.record) != value
        return False

    def set_value(self, record, field):
        entry = self.entry.get_child() if self.autocomplete else self.entry
        value = entry.get_text() or ''
        return field.set_client(record, value)

    def get_value(self):
        entry = self.entry.get_child() if self.autocomplete else self.entry
        return entry.get_text()

    def display(self, record, field):
        super(Char, self).display(record, field)
        if record and self.autocomplete:
            autocompletion = record.autocompletion.get(self.field_name, [])
            current = [elem[0] for elem in self.entry_store]
            if autocompletion != current:
                self.entry_store.clear()
                for row in autocompletion:
                    self.entry_store.append((row,))
        elif self.autocomplete:
            self.entry_store.clear()

        # Set size
        if self.autocomplete:
            size_entry = self.entry.get_child()
        else:
            size_entry = self.entry
        if record:
            field_size = record.expr_eval(self.attrs.get('size'))
            size_entry.set_width_chars(field_size or -1)
            size_entry.set_max_length(field_size or 0)
        else:
            size_entry.set_width_chars(-1)
            size_entry.set_max_length(0)

        if not field:
            value = ''
        else:
            value = field.get_client(record)

        if not self.autocomplete:
            self.entry.set_text(value)
        else:
            for idx, row in enumerate(self.entry_store):
                if row[0] == value:
                    self.entry.set_active(idx)
                    return
            else:
                self.entry.get_child().set_text(value)

    def _readonly_set(self, value):
        sensitivity = {True: gtk.SENSITIVITY_OFF, False: gtk.SENSITIVITY_AUTO}
        super(Char, self)._readonly_set(value)
        if self.autocomplete:
            self.entry.get_child().set_editable(not value)
            self.entry.set_button_sensitivity(sensitivity[value])
        else:
            self.entry.set_editable(not value)
        if self.button:
            self.button.set_sensitive(not value)
        if value:
            self.widget.set_focus_chain([])
        else:
            self.widget.set_focus_chain([self.entry])


class Sha(Char):

    def __init__(self, field_name, model_name, attrs=None):
        super(Sha, self).__init__(field_name, model_name, attrs=attrs)
        self.entry.props.visibility = False

        self.visibility_checkbox = gtk.CheckButton()
        self.visibility_checkbox.connect('toggled', self.toggle_visibility)
        Tooltips().set_tip(self.visibility_checkbox, _('Show plain text'))
        self.widget.pack_start(self.visibility_checkbox, expand=False)

    def _readonly_set(self, value):
        super(Char, self)._readonly_set(value)
        self.entry.set_editable(not value)
        self.visibility_checkbox.props.visible = not value
        if value:
            self.widget.set_focus_chain([])
        else:
            self.widget.set_focus_chain([self.entry, self.visibility_checkbox])

    def toggle_visibility(self, button):
        self.entry.props.visibility = not self.entry.props.visibility
