# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext

from gi.repository import Gtk

from tryton.common import (get_toplevel_window, IconFactory,
    timezoned_date, untimezoned_date)
from tryton.common.datetime_ import date_parse
from tryton.common.underline import set_underline
from tryton.config import TRYTON_ICON
from tryton.gui import Main

_ = gettext.gettext


class Revision(object):
    'Ask revision'

    def __init__(self, revisions, revision=None, format_='%x %H:%M:%S.%f'):
        self.parent = get_toplevel_window()
        self.win = Gtk.Dialog(
            title=_('Revision'), transient_for=self.parent, modal=True,
            destroy_with_parent=True)
        Main().add_window(self.win)
        cancel_button = self.win.add_button(
            set_underline(_("Cancel")), Gtk.ResponseType.CANCEL)
        cancel_button.set_image(IconFactory.get_image(
                'tryton-cancel', Gtk.IconSize.BUTTON))
        cancel_button.set_always_show_image(True)
        ok_button = self.win.add_button(
            set_underline(_("OK")), Gtk.ResponseType.OK)
        ok_button.set_image(IconFactory.get_image(
                'tryton-ok', Gtk.IconSize.BUTTON))
        ok_button.set_always_show_image(True)
        self.win.set_default_response(Gtk.ResponseType.OK)
        self.win.set_icon(TRYTON_ICON)
        self.win.vbox.set_spacing(3)
        self.win.vbox.pack_start(Gtk.Label(
                label=_('Select a revision')),
            expand=False, fill=True, padding=0)
        self.win.vbox.pack_start(
            Gtk.HSeparator(), expand=True, fill=True, padding=0)
        hbox = Gtk.HBox(spacing=3)
        label = Gtk.Label(label=_('Revision:'))
        hbox.pack_start(label, expand=True, fill=True, padding=0)
        list_store = Gtk.ListStore(str, str)
        # Set model on instantiation to get the default cellrenderer as text
        combobox = Gtk.ComboBox(model=list_store, has_entry=True)
        self.entry = combobox.get_child()
        self.entry.connect('focus-out-event', self.focus_out)
        self.entry.connect('activate', self.activate)
        label.set_mnemonic_widget(self.entry)
        combobox.connect('changed', self.changed)
        self.entry.set_property('activates_default', True)
        self._format = format_
        if revision:
            self.entry.set_text(revision.strftime(self._format))
            self._value = revision
            active = -1
        else:
            self._value = None
            active = 0
        list_store.append(('', ''))
        for i, (rev, id_, name) in enumerate(revisions, 1):
            list_store.append(
                (timezoned_date(rev).strftime(self._format), name))
            if rev == revision:
                active = i
        combobox.set_active(active)
        cell = Gtk.CellRendererText()
        combobox.pack_start(cell, expand=True)
        combobox.add_attribute(cell, 'text', 1)
        hbox.pack_start(combobox, expand=True, fill=True, padding=0)
        combobox.set_entry_text_column(0)
        self.win.vbox.pack_start(hbox, expand=True, fill=True, padding=0)
        self.win.show_all()

    def focus_out(self, entry, event):
        self.parse()
        self.update()
        return False

    def activate(self, entry):
        self.parse()
        self.update()
        return False

    def changed(self, combobox):
        # "changed" signal is also triggered by text editing
        # so only parse when a row is active
        if combobox.get_active_iter():
            self.parse()
            self.update()
        return False

    def parse(self):
        text = self.entry.get_text()
        value = None
        if text:
            try:
                value = untimezoned_date(date_parse(text, self._format))
            except ValueError:
                pass
        self._value = value

    def update(self):
        if not self._value:
            self.entry.set_text('')
        else:
            self.entry.set_text(self._value.strftime(self._format))

    def run(self):
        response = self.win.run()
        revision = None
        if response == Gtk.ResponseType.OK:
            revision = self._value
        self.parent.present()
        self.win.destroy()
        return revision
