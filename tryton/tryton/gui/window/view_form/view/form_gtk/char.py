# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext

from gi.repository import GLib, Gtk

from .widget import Widget, TranslateMixin
from tryton.common import Tooltips, IconFactory
from tryton.common.entry_position import reset_position
from tryton.common.selection import PopdownMixin, selection_shortcuts

_ = gettext.gettext


class Char(Widget, TranslateMixin, PopdownMixin):
    "Char"

    def __init__(self, view, attrs):
        super(Char, self).__init__(view, attrs)

        self.widget = Gtk.HBox()
        self.autocomplete = bool(attrs.get('autocomplete'))
        if self.autocomplete:
            self.entry = Gtk.ComboBox(has_entry=True)
            selection_shortcuts(self.entry)
            focus_entry = self.entry.get_child()
            self.set_popdown([], self.entry)
            self.entry.connect('changed', self.changed)
            self.entry.connect('move-active', self._move_active)
            self.entry.connect(
                'scroll-event',
                lambda c, e: c.stop_emission_by_name('scroll-event'))
        else:
            self.entry = Gtk.Entry()
            focus_entry = self.entry
        self.mnemonic_widget = focus_entry

        focus_entry.set_property('activates_default', True)
        focus_entry.connect('activate', self.sig_activate)
        focus_entry.connect('focus-out-event', lambda x, y: self._focus_out())
        focus_entry.connect('key-press-event', self.send_modified)
        expand, fill = True, True
        if attrs.get('size'):
            expand, fill = False, False
        self.widget.pack_start(self.entry, expand=expand, fill=fill, padding=0)

        if attrs.get('translate'):
            self.entry.set_icon_from_pixbuf(
                Gtk.EntryIconPosition.SECONDARY,
                IconFactory.get_pixbuf('tryton-translate', Gtk.IconSize.MENU))
            self.entry.connect('icon-press', self.translate)

    def translate_widget(self):
        entry = Gtk.Entry()
        entry.set_property('activates_default', True)
        if self.record:
            field_size = self.record.expr_eval(self.attrs.get('size'))
            entry.set_width_chars(
                min(120, field_size or self.default_width_chars))
            entry.set_max_length(field_size or 0)
        return entry

    def translate_widget_set(self, widget, value):
        widget.set_text(value)
        reset_position(widget)

    def translate_widget_get(self, widget):
        return widget.get_text()

    def translate_widget_set_readonly(self, widget, value):
        widget.set_editable(not value)
        widget.props.sensitive = not value

    def changed(self, combobox):
        def focus_out():
            if combobox.props.window:
                self._focus_out()
        # Only when changed from pop list
        if not combobox.get_child().has_focus():
            # Must be deferred because it triggers a display of the form
            GLib.idle_add(focus_out)

    @property
    def modified(self):
        if self.record and self.field:
            value = self.get_client_value()
            return value != self.get_value()
        return False

    def set_value(self):
        entry = self.entry.get_child() if self.autocomplete else self.entry
        value = entry.get_text() or ''
        return self.field.set_client(self.record, value)

    def get_value(self):
        entry = self.entry.get_child() if self.autocomplete else self.entry
        return entry.get_text()

    def get_client_value(self):
        if not self.field:
            value = ''
        else:
            value = self.field.get_client(self.record)
        return value

    def display(self):
        super(Char, self).display()
        if self.autocomplete:
            if self.record:
                if self.field_name not in self.record.autocompletion:
                    self.record.do_autocomplete(self.field_name)
                selection = self.record.autocompletion.get(self.field_name, [])
            else:
                selection = []
            self.set_popdown([(x, x) for x in selection], self.entry)

        # Set size
        if self.autocomplete:
            size_entry = self.entry.get_child()
        else:
            size_entry = self.entry
        if self.record:
            field_size = self.record.expr_eval(self.attrs.get('size'))
            size_entry.set_width_chars(
                min(120, field_size or self.default_width_chars))
            size_entry.set_max_length(field_size or 0)
        else:
            size_entry.set_width_chars(self.default_width_chars)
            size_entry.set_max_length(0)

        value = self.get_client_value()
        if not self.autocomplete:
            self.entry.set_text(value)
            reset_position(self.entry)
        else:
            self.entry.handler_block_by_func(self.changed)
            if not self.set_popdown_value(self.entry, value) or not value:
                child = self.entry.get_child()
                child.set_text(value)
                reset_position(child)
            self.entry.handler_unblock_by_func(self.changed)

    def _move_active(self, combobox, scroll_type):
        if not combobox.get_child().get_editable():
            combobox.stop_emission_by_name('move-active')

    def _readonly_set(self, value):
        sensitivity = {
            True: Gtk.SensitivityType.OFF,
            False: Gtk.SensitivityType.AUTO,
            }
        super(Char, self)._readonly_set(value)
        if self.autocomplete:
            entry_editable = self.entry.get_child()
            self.entry.set_button_sensitivity(sensitivity[value])
        else:
            entry_editable = self.entry
        entry_editable.set_editable(not value)


class Password(Char):

    def __init__(self, view, attrs):
        super(Password, self).__init__(view, attrs)
        self.entry.props.visibility = False

        self.visibility_checkbox = Gtk.CheckButton()
        self.visibility_checkbox.connect('toggled', self.toggle_visibility)
        Tooltips().set_tip(self.visibility_checkbox, _('Show plain text'))
        self.widget.pack_start(
            self.visibility_checkbox, expand=False, fill=True, padding=0)

    def _readonly_set(self, value):
        super(Char, self)._readonly_set(value)
        self.entry.set_editable(not value)
        self.visibility_checkbox.props.visible = not value

    def toggle_visibility(self, button):
        self.entry.props.visibility = not self.entry.props.visibility
