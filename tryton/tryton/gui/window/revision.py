#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gettext

from tryton.config import TRYTON_ICON
from tryton.common import get_toplevel_window
from tryton.common.date_widget import DateEntry
from tryton.common.datetime_strftime import datetime_strftime
from tryton.translate import date_format

_ = gettext.gettext


class Revision(object):
    'Ask revision'

    def __init__(self, revisions, revision=None):
        self.parent = get_toplevel_window()
        self.win = gtk.Dialog(_('Revision'), self.parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_OK, gtk.RESPONSE_OK))
        self.win.set_default_response(gtk.RESPONSE_OK)
        self.win.set_icon(TRYTON_ICON)
        self.win.set_has_separator(True)
        self.win.vbox.set_spacing(3)
        self.win.vbox.pack_start(gtk.Label(
                _('Select a revision')), expand=False, fill=True)
        self.win.vbox.pack_start(gtk.HSeparator())
        hbox = gtk.HBox(spacing=3)
        hbox.pack_start(gtk.Label(_('Revision:')), expand=True, fill=True)
        format_ = date_format() + ' %H:%M:%S.%f'
        self.entry = DateEntry(format_)
        if revision:
            self.entry.set_text(datetime_strftime(revision, format_))
        list_store = gtk.ListStore(str, str)
        list_store.append(('', ''))
        for revision, id_, name in revisions:
            list_store.append((datetime_strftime(revision, format_), name))
        combobox = gtk.ComboBoxEntry(list_store)
        combobox.add(self.entry)
        cell = gtk.CellRendererText()
        combobox.pack_start(cell, True)
        combobox.add_attribute(cell, 'text', 1)
        hbox.pack_start(combobox, expand=True, fill=True)
        combobox.set_entry_text_column(0)
        combobox.connect('changed', self.changed)
        self.entry.set_property('activates_default', True)
        self.win.vbox.pack_start(hbox, expand=True, fill=True)
        self.win.show_all()

    def changed(self, combobox):
        # set_text must be called because DateEntry doesn't work correctly with
        # the default insert/delete text behavior of combobox
        model = combobox.get_model()
        idx = combobox.get_active()
        if idx >= 0:
            self.entry.set_text(model[idx][0])

    def run(self):
        response = self.win.run()
        revision = None
        if response == gtk.RESPONSE_OK:
            revision = self.entry.date_get()
        self.parent.present()
        self.win.destroy()
        return revision
