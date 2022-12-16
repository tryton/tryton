# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Preference"
import gettext
import copy

from gi.repository import Gdk, Gtk

import tryton.rpc as rpc
from tryton.common import RPCExecute, RPCException, IconFactory
from tryton.common.underline import set_underline
from tryton.config import TRYTON_ICON
from tryton.gui import Main
from tryton.gui.window.nomodal import NoModal
from tryton.gui.window.view_form.screen import Screen

_ = gettext.gettext


class Preference(NoModal):
    "Preference window"

    def __init__(self, user, callback):
        NoModal.__init__(self)
        self.callback = callback
        self.win = Gtk.Dialog(
            title=_('Preferences'), transient_for=self.parent,
            destroy_with_parent=True)
        Main().add_window(self.win)
        self.win.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.win.set_icon(TRYTON_ICON)

        self.accel_group = Gtk.AccelGroup()
        self.win.add_accel_group(self.accel_group)

        self.but_cancel = self.win.add_button(
            set_underline(_("Cancel")), Gtk.ResponseType.CANCEL)
        self.but_cancel.set_image(
            IconFactory.get_image('tryton-cancel', Gtk.IconSize.BUTTON))
        self.but_cancel.set_always_show_image(True)
        self.but_ok = self.win.add_button(
            set_underline(_("OK")), Gtk.ResponseType.OK)
        self.but_ok.set_image(
            IconFactory.get_image('tryton-ok', Gtk.IconSize.BUTTON))
        self.but_ok.set_always_show_image(True)
        self.but_ok.add_accelerator(
            'clicked', self.accel_group, Gdk.KEY_Return,
            Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)

        self.win.set_default_response(Gtk.ResponseType.OK)
        self.win.connect('response', self.response)

        try:
            view = RPCExecute('model', 'res.user',
                'get_preferences_fields_view')
        except RPCException:
            self.win.destroy()
            self.win = None
            return

        title = Gtk.Label(label=_('Edit User Preferences'))
        title.show()
        self.win.vbox.pack_start(title, expand=False, fill=True, padding=0)
        self.screen = Screen('res.user', mode=[])
        # Reset readonly set automaticly by MODELACCESS
        self.screen.readonly = False
        self.screen.group.readonly = False
        self.screen.group.skip_model_access = True
        self.screen.add_view(view)
        self.screen.switch_view()
        self.screen.new(default=False)

        try:
            preferences = RPCExecute('model', 'res.user', 'get_preferences',
                False)
        except RPCException:
            self.win.destroy()
            self.win = None
            return
        self.screen.current_record.cancel()
        self.screen.current_record.set(preferences)
        self.screen.current_record.id = rpc._USER
        self.screen.current_record.validate(softvalidation=True)
        self.screen.display(set_cursor=True)

        self.screen.widget.show()
        self.win.vbox.pack_start(
            self.screen.widget, expand=True, fill=True, padding=0)
        self.win.set_title(_('Preference'))

        self.win.set_default_size(*self.default_size())

        self.register()
        self.win.show()

    def response(self, win, response_id):
        if response_id == Gtk.ResponseType.OK:
            if self.screen.current_record.validate():
                vals = copy.copy(self.screen.get())
                try:
                    RPCExecute('model', 'res.user', 'set_preferences', vals)
                except RPCException:
                    return
                rpc.context_reset()
        self.parent.present()
        self.destroy()
        self.callback()

    def destroy(self):
        self.screen.destroy()
        self.win.destroy()
        NoModal.destroy(self)
