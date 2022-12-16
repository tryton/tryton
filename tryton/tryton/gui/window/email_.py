# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import gettext

from gi.repository import Gtk

from tryton.common import get_toplevel_window, IconFactory
from tryton.common.underline import set_underline
from tryton.config import TRYTON_ICON, CONFIG
from tryton.gui import Main

_ = gettext.gettext


class Email(object):

    def __init__(self):
        self.parent = get_toplevel_window()
        self.win = Gtk.Dialog(
            title=_('Email'), transient_for=self.parent, modal=True,
            destroy_with_parent=True)
        Main().add_window(self.win)
        cancel_button = self.win.add_button(
            set_underline(_("Cancel")), Gtk.ResponseType.CANCEL)
        cancel_button.set_image(
            IconFactory.get_image('tryton-cancel', Gtk.IconSize.BUTTON))
        cancel_button.set_always_show_image(True)
        ok_button = self.win.add_button(
            set_underline(_("OK")), Gtk.ResponseType.OK)
        ok_button.set_image(
            IconFactory.get_image('tryton-ok', Gtk.IconSize.BUTTON))
        ok_button.set_always_show_image(True)
        self.win.set_default_response(Gtk.ResponseType.OK)
        self.win.set_icon(TRYTON_ICON)
        self.win.vbox.set_spacing(3)
        self.win.vbox.pack_start(Gtk.Label(
            _('Email Program Settings')), expand=False, fill=True, padding=0)
        self.win.vbox.pack_start(
            Gtk.HSeparator(), expand=True, fill=True, padding=0)
        hbox = Gtk.HBox(spacing=3)
        label = Gtk.Label(label=_('Command Line:'))
        hbox.pack_start(label, expand=True, fill=True, padding=0)
        self.entry = Gtk.Entry()
        self.entry.set_property('activates_default', True)
        self.entry.set_width_chars(50)
        self.entry.set_text(CONFIG['client.email'])
        label.set_mnemonic_widget(label)
        hbox.pack_start(self.entry, expand=True, fill=True, padding=0)
        self.win.vbox.pack_start(hbox, expand=True, fill=True, padding=0)

        label = Gtk.Label(
            label=_('Legend of Available Placeholders:'),
            halign=Gtk.Align.START, margin_top=10, margin_bottom=5)
        self.win.vbox.pack_start(label, expand=False, fill=True, padding=0)

        hbox = Gtk.HBox(spacing=3)
        vboxl = Gtk.VBox(homogeneous=True, spacing=3)
        label = Gtk.Label(label=_('To:'), halign=Gtk.Align.START)
        vboxl.pack_start(label, expand=False, fill=False, padding=0)
        label = Gtk.Label(label=_('CC:'), halign=Gtk.Align.START)
        vboxl.pack_start(label, expand=False, fill=False, padding=0)
        label = Gtk.Label(label=_('Subject:'), halign=Gtk.Align.START)
        vboxl.pack_start(label, expand=False, fill=False, padding=0)
        label = Gtk.Label(label=_('Body:'), halign=Gtk.Align.START)
        vboxl.pack_start(label, expand=False, fill=False, padding=0)
        label = Gtk.Label(label=_('Attachment:'), halign=Gtk.Align.START)
        vboxl.pack_start(label, expand=False, fill=False, padding=0)

        vboxr = Gtk.VBox(homogeneous=True, spacing=3)
        label = Gtk.Label(label=' ${to}', halign=Gtk.Align.START)
        vboxr.pack_start(label, expand=False, fill=False, padding=0)
        label = Gtk.Label(label=' ${cc}', halign=Gtk.Align.START)
        vboxr.pack_start(label, expand=False, fill=False, padding=0)
        label = Gtk.Label(label=' ${subject}', halign=Gtk.Align.START)
        vboxr.pack_start(label, expand=False, fill=False, padding=0)
        label = Gtk.Label(label=' ${body}', halign=Gtk.Align.START)
        vboxr.pack_start(label, expand=False, fill=False, padding=0)
        label = Gtk.Label(label=' ${attachment}', halign=Gtk.Align.START)
        vboxr.pack_start(label, expand=False, fill=False, padding=0)

        hbox.pack_start(vboxl, expand=False, fill=False, padding=0)
        hbox.pack_start(vboxr, expand=False, fill=False, padding=0)

        self.win.vbox.pack_start(hbox, expand=True, fill=True, padding=0)

        self.win.show_all()

    def run(self):
        "Run the window"
        res = self.win.run()
        if res == Gtk.ResponseType.OK:
            CONFIG['client.email'] = self.entry.get_text()
            CONFIG.save()
        self.parent.present()
        self.win.destroy()
        return res
