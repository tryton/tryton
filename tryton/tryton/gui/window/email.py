# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import gtk
import gettext

from tryton.common import get_toplevel_window, IconFactory
from tryton.common.underline import set_underline
from tryton.config import TRYTON_ICON, CONFIG
from tryton.gui import Main

_ = gettext.gettext


class Email(object):

    def __init__(self):
        self.parent = get_toplevel_window()
        self.win = gtk.Dialog(_('Email'), self.parent,
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
            _('Email Program Settings')), expand=False, fill=True)
        self.win.vbox.pack_start(gtk.HSeparator())
        hbox = gtk.HBox(spacing=3)
        label = gtk.Label(_('Command Line:'))
        hbox.pack_start(label, expand=True, fill=True)
        self.entry = gtk.Entry()
        self.entry.set_property('activates_default', True)
        self.entry.set_width_chars(50)
        self.entry.set_text(CONFIG['client.email'])
        label.set_mnemonic_widget(label)
        hbox.pack_start(self.entry, expand=True, fill=True)
        self.win.vbox.pack_start(hbox, expand=True, fill=True)

        label = gtk.Label(_('Legend of Available Placeholders:'))
        label.set_alignment(0.0, 0.5)
        label.set_padding(0, 10)
        self.win.vbox.pack_start(label, expand=False, fill=True)

        hbox = gtk.HBox(spacing=3)
        vboxl = gtk.VBox(homogeneous=True, spacing=3)
        label = gtk.Label(_('To:'))
        label.set_alignment(0, 0)
        label.set_padding(10, 0)
        vboxl.pack_start(label, expand=False, fill=False)
        label = gtk.Label(_('CC:'))
        label.set_alignment(0, 0)
        label.set_padding(10, 0)
        vboxl.pack_start(label, expand=False, fill=False)
        label = gtk.Label(_('Subject:'))
        label.set_alignment(0, 0)
        label.set_padding(10, 0)
        vboxl.pack_start(label, expand=False, fill=False)
        label = gtk.Label(_('Body:'))
        label.set_alignment(0, 0)
        label.set_padding(10, 0)
        vboxl.pack_start(label, expand=False, fill=False)
        label = gtk.Label(_('Attachment:'))
        label.set_alignment(0, 0)
        label.set_padding(10, 0)
        vboxl.pack_start(label, expand=False, fill=False)

        vboxr = gtk.VBox(homogeneous=True, spacing=3)
        label = gtk.Label(' ${to}')
        label.set_alignment(0, 0)
        vboxr.pack_start(label, expand=False, fill=False)
        label = gtk.Label(' ${cc}')
        label.set_alignment(0, 0)
        vboxr.pack_start(label, expand=False, fill=False)
        label = gtk.Label(' ${subject}')
        label.set_alignment(0, 0)
        vboxr.pack_start(label, expand=False, fill=False)
        label = gtk.Label(' ${body}')
        label.set_alignment(0, 0)
        vboxr.pack_start(label, expand=False, fill=False)
        label = gtk.Label(' ${attachment}')
        label.set_alignment(0, 0)
        vboxr.pack_start(label, expand=False, fill=False)

        hbox.pack_start(vboxl, expand=False, fill=False)
        hbox.pack_start(vboxr, expand=False, fill=False)

        self.win.vbox.pack_start(hbox, expand=True, fill=True)

        self.win.show_all()

    def run(self):
        "Run the window"
        res = self.win.run()
        if res == gtk.RESPONSE_OK:
            CONFIG['client.email'] = self.entry.get_text()
            CONFIG.save()
        self.parent.present()
        self.win.destroy()
        return res
