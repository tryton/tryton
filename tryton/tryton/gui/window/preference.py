# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Preference"
import gettext
import gtk
import copy
from tryton.gui.window.view_form.screen import Screen
from tryton.config import TRYTON_ICON
from tryton.common import RPCExecute, RPCException, Login
from tryton.gui.window.nomodal import NoModal
from tryton.exceptions import TrytonError
import tryton.rpc as rpc

_ = gettext.gettext


class Preference(NoModal):
    "Preference window"

    def __init__(self, user, callback):
        NoModal.__init__(self)
        self.callback = callback
        self.win = gtk.Dialog(_('Preferences'), self.parent,
            gtk.DIALOG_DESTROY_WITH_PARENT)
        self.win.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.win.set_icon(TRYTON_ICON)

        self.accel_group = gtk.AccelGroup()
        self.win.add_accel_group(self.accel_group)

        self.but_cancel = self.win.add_button(gtk.STOCK_CANCEL,
                gtk.RESPONSE_CANCEL)
        self.but_cancel.set_always_show_image(True)
        self.but_ok = self.win.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
        self.but_ok.set_always_show_image(True)
        self.but_ok.add_accelerator('clicked', self.accel_group,
                gtk.keysyms.Return, gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)

        self.win.set_default_response(gtk.RESPONSE_OK)
        self.win.connect('response', self.response)

        try:
            view = RPCExecute('model', 'res.user',
                'get_preferences_fields_view')
        except RPCException:
            self.win.destroy()
            self.win = None
            return

        title = gtk.Label(_('Edit User Preferences'))
        title.show()
        self.win.vbox.pack_start(title, expand=False, fill=True)
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
        self.win.vbox.pack_start(self.screen.widget)
        self.win.set_title(_('Preference'))

        width, height = self.parent.get_size()
        self.win.set_default_size(width, height)

        self.register()
        self.win.show()

    def response(self, win, response_id):
        if response_id == gtk.RESPONSE_OK:
            if self.screen.current_record.validate():
                vals = copy.copy(self.screen.get())
                context = rpc.CONTEXT.copy()
                func = lambda parameters: rpc.execute(
                    'model', 'res.user', 'set_preferences', vals, parameters,
                    context)
                try:
                    Login(func)
                except TrytonError, exception:
                    if exception.faultCode == 'QueryCanceled':
                        return
                    raise
        self.parent.present()
        self.destroy()
        self.callback()

    def destroy(self):
        self.screen.destroy()
        self.win.destroy()
        NoModal.destroy(self)
