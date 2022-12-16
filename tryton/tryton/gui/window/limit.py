# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import sys
import gettext

from gi.repository import Gtk

from tryton.common import get_toplevel_window, IconFactory
from tryton.common.underline import set_underline
from tryton.config import TRYTON_ICON, CONFIG
from tryton.gui import Main

_ = gettext.gettext


class Limit(object):
    'Set Search Limit'

    def __init__(self):
        self.parent = get_toplevel_window()
        self.win = Gtk.Dialog(
            title=_('Limit'), transient_for=self.parent, modal=True,
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
            label=_('Search Limit Settings')),
            expand=False, fill=True, padding=0)
        self.win.vbox.pack_start(
            Gtk.HSeparator(), expand=True, fill=True, padding=0)
        hbox = Gtk.HBox(spacing=3)
        label = Gtk.Label(label=_('Limit:'))
        hbox.pack_start(label, expand=True, fill=True, padding=0)
        adjustment = Gtk.Adjustment(
            value=CONFIG['client.limit'],
            lower=1, upper=sys.maxsize,
            step_incr=10, page_incr=100)
        self.spin_limit = Gtk.SpinButton()
        self.spin_limit.configure(adjustment, climb_rate=1, digits=0)
        self.spin_limit.set_numeric(False)
        self.spin_limit.set_activates_default(True)
        label.set_mnemonic_widget(self.spin_limit)
        hbox.pack_start(self.spin_limit, expand=True, fill=True, padding=0)
        self.win.vbox.pack_start(hbox, expand=True, fill=True, padding=0)

        self.win.show_all()

    def run(self):
        'Run the window'
        res = self.win.run()
        if res == Gtk.ResponseType.OK:
            CONFIG['client.limit'] = self.spin_limit.get_value_as_int()
            CONFIG.save()
        self.parent.present()
        self.win.destroy()
        return res
