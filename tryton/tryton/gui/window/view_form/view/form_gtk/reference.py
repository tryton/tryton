# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext

from gi.repository import Gtk

from .many2one import Many2One
from tryton.common.selection import SelectionMixin, PopdownMixin, \
        selection_shortcuts

_ = gettext.gettext


class Reference(Many2One, SelectionMixin, PopdownMixin):

    def __init__(self, view, attrs):
        super(Reference, self).__init__(view, attrs)

        self.widget_combo = Gtk.ComboBox(has_entry=True)
        child = self.widget_combo.get_child()
        child.connect('activate', lambda *a: self._focus_out())
        child.connect('focus-out-event', lambda *a: self._focus_out())
        child.get_accessible().set_name(attrs.get('string', ''))
        self.widget_combo.connect('changed', self.sig_changed_combo)
        self.widget_combo.connect('move-active', self._move_active)
        self.widget_combo.connect(
            'scroll-event',
            lambda c, e: c.stop_emission_by_name('scroll-event'))
        selection_shortcuts(self.widget_combo)

        self.widget.pack_start(
            self.widget_combo, expand=False, fill=True, padding=0)

        self.init_selection()
        self.set_popdown(self.selection, self.widget_combo)

    def get_model(self):
        active = self.widget_combo.get_active()
        if active < 0:
            return ''
        else:
            model = self.widget_combo.get_model()
            return model[active][1]

    def get_empty_value(self):
        for name, model in self.widget_combo.get_model():
            if model in (None, ''):
                return model, name
        return '', ''

    def _move_active(self, combobox, scroll_type):
        if not combobox.get_child().get_editable():
            combobox.stop_emission_by_name('move-active')

    def _set_button_sensitive(self):
        super(Reference, self)._set_button_sensitive()
        self.widget_combo.get_child().set_editable(not self._readonly)
        self.widget_combo.set_button_sensitivity(
            Gtk.SensitivityType.OFF if self._readonly
            else Gtk.SensitivityType.AUTO)

    @property
    def modified(self):
        if self.record and self.field:
            try:
                model, name = self.field.get_client(self.record)
            except (ValueError, TypeError):
                model, name = self.get_empty_value()
            return (model != self.get_model()
                or name != self.wid_text.get_text())
        return False

    def has_target(self, value):
        if value is None:
            return False
        model, value = value.split(',')
        if not value:
            value = None
        else:
            try:
                value = int(value)
            except ValueError:
                value = None
        result = model == self.get_model() and value >= 0
        return result

    def value_from_id(self, id_, str_=None):
        if str_ is None:
            str_ = ''
        return self.get_model(), (id_, str_)

    @staticmethod
    def id_from_value(value):
        _, value = value.split(',')
        return int(value)

    def sig_changed_combo(self, *args):
        if not self.changed:
            return
        self.wid_text.set_text('')
        model = self.get_model()
        if model:
            value = (model, (-1, ''))
        else:
            value = ('', '')
        self.field.set_client(self.record, value)

    def set_value(self):
        if not self.get_model():
            value = self.wid_text.get_text()
            if not value:
                self.field.set_client(self.record, None)
            else:
                self.field.set_client(self.record, ('', value))
                return
        else:
            try:
                model, name = self.field.get_client(self.record)
            except (ValueError, TypeError):
                model, name = self.get_empty_value()
            if (model != self.get_model()
                    or name != self.wid_text.get_text()):
                self.field.set_client(self.record, None)
                self.set_text(None)

    def set_text(self, value):
        if value:
            model, value = value
        else:
            model, value = None, None
        super(Reference, self).set_text(value)
        self.widget_combo.handler_block_by_func(self.sig_changed_combo)
        if not self.set_popdown_value(self.widget_combo, model):
            text = self.get_inactive_selection(model)
            self.set_popdown(
                self.selection[:] + [(model, text)], self.widget_combo)
            self.set_popdown_value(self.widget_combo, value)
        self.widget_combo.handler_unblock_by_func(self.sig_changed_combo)

    def display(self):
        self.update_selection(self.record, self.field)
        self.set_popdown(self.selection, self.widget_combo)
        super(Reference, self).display()
