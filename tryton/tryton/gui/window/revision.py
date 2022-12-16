# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gettext

from tryton.common import (get_toplevel_window, IconFactory,
    timezoned_date, untimezoned_date)
from tryton.common.datetime_ import date_parse
from tryton.common.datetime_strftime import datetime_strftime
from tryton.common.underline import set_underline
from tryton.config import TRYTON_ICON
from tryton.gui import Main

_ = gettext.gettext


class Revision(object):
    'Ask revision'

    def __init__(self, revisions, revision=None, format_='%x %H:%M:%S.%f'):
        self.parent = get_toplevel_window()
        self.win = gtk.Dialog(_('Revision'), self.parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)
        Main().add_window(self.win)
        cancel_button = self.win.add_button(
            set_underline(_("Cancel")), gtk.RESPONSE_CANCEL)
        cancel_button.set_image(IconFactory.get_image(
                'tryton-cancel', gtk.ICON_SIZE_BUTTON))
        cancel_button.set_always_show_image(True)
        ok_button = self.win.add_button(
            set_underline(_("OK")), gtk.RESPONSE_OK)
        ok_button.set_image(IconFactory.get_image(
                'tryton-ok', gtk.ICON_SIZE_BUTTON))
        ok_button.set_always_show_image(True)
        self.win.set_default_response(gtk.RESPONSE_OK)
        self.win.set_icon(TRYTON_ICON)
        self.win.vbox.set_spacing(3)
        self.win.vbox.pack_start(gtk.Label(
                _('Select a revision')), expand=False, fill=True)
        self.win.vbox.pack_start(gtk.HSeparator())
        hbox = gtk.HBox(spacing=3)
        label = gtk.Label(_('Revision:'))
        hbox.pack_start(label, expand=True, fill=True)
        list_store = gtk.ListStore(str, str)
        # Set model on instantiation to get the default cellrenderer as text
        combobox = gtk.ComboBoxEntry(model=list_store)
        self.entry = combobox.get_child()
        self.entry.connect('focus-out-event', self.focus_out)
        self.entry.connect('activate', self.activate)
        label.set_mnemonic_widget(self.entry)
        combobox.connect('changed', self.changed)
        self.entry.set_property('activates_default', True)
        self._format = format_
        if revision:
            self.entry.set_text(datetime_strftime(revision, self._format))
            self._value = revision
            active = -1
        else:
            self._value = None
            active = 0
        list_store.append(('', ''))
        for i, (rev, id_, name) in enumerate(revisions, 1):
            list_store.append(
                (datetime_strftime(timezoned_date(rev), self._format), name))
            if rev == revision:
                active = i
        combobox.set_active(active)
        cell = gtk.CellRendererText()
        combobox.pack_start(cell, True)
        combobox.add_attribute(cell, 'text', 1)
        hbox.pack_start(combobox, expand=True, fill=True)
        combobox.set_entry_text_column(0)
        self.win.vbox.pack_start(hbox, expand=True, fill=True)
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
            self.entry.set_text(datetime_strftime(self._value, self._format))

    def run(self):
        response = self.win.run()
        revision = None
        if response == gtk.RESPONSE_OK:
            revision = self._value
        self.parent.present()
        self.win.destroy()
        return revision
