#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Preference"
import gettext
import gtk
from tryton.rpc import RPCProxy
import tryton.rpc as rpc
import copy
from tryton.gui.window.view_form.screen import Screen
from tryton.config import TRYTON_ICON
import tryton.common as common

_ = gettext.gettext


class Preference(object):
    "Preference window"

    def __init__(self, user, parent):
        self.win = gtk.Dialog(_('Preferences'), parent,
                gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT)
        self.win.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.win.set_has_separator(False)
        self.win.set_icon(TRYTON_ICON)
        self.parent = parent

        self.accel_group = gtk.AccelGroup()
        self.win.add_accel_group(self.accel_group)

        self.but_cancel = self.win.add_button(gtk.STOCK_CANCEL,
                gtk.RESPONSE_CANCEL)
        self.but_ok = self.win.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
        self.but_ok.add_accelerator('clicked', self.accel_group,
                gtk.keysyms.Return, gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)

        self.win.set_default_response(gtk.RESPONSE_OK)

        user = RPCProxy('res.user')

        try:
            res = user.get_preferences_fields_view(rpc.CONTEXT)
        except Exception, exception:
            if not common.process_exception(exception, parent):
                self.win.destroy()
                self.win = None
                return
            try:
                res = user.get_preferences_fields_view(rpc.CONTEXT)
            except Exception, exception:
                common.process_exception(exception, parent)
                self.win.destroy()
                self.win = None
                return

        title = gtk.Label(_('Edit User Preferences'))
        title.show()
        self.win.vbox.pack_start(title, expand=False, fill=True)
        arch = res['arch']
        fields = res['fields']
        self.screen = Screen('res.user', self.win, view_type=[])
        self.screen.new(default=False)
        self.screen.add_view_custom(arch, fields, display=True)

        try:
            preferences = user.get_preferences(False, rpc.CONTEXT)
        except Exception, exception:
            common.process_exception(exception, parent)
            self.win.destroy()
            raise
        self.screen.current_model.set(preferences)

        width, height = self.screen.screen_container.size_get()
        parent_width, parent_height = parent.get_size()
        self.screen.widget.set_size_request(min(parent_width - 20, width + 20),
                min(parent_height - 60, height + 25))
        self.screen.widget.show()
        self.win.vbox.pack_start(self.screen.widget)
        self.win.set_title(_('Preference'))
        self.win.show()

    def run(self):
        "Run the window"
        if not self.win:
            return False
        res = False
        while True:
            if self.win.run() == gtk.RESPONSE_OK:
                if self.screen.current_model.validate():
                    vals = copy.copy(self.screen.get(get_modifiedonly=True))
                    if 'password' in vals:
                        password = common.ask(_('Current Password:'),
                                self.win, visibility=False)
                        if not password:
                            break
                    else:
                        password = False
                    user = RPCProxy('res.user')
                    try:
                        user.set_preferences(vals, password, rpc.CONTEXT)
                    except Exception, exception:
                        common.process_exception(exception, self.win)
                        continue
                    res = True
                    break
            else:
                break
        self.parent.present()
        self.win.destroy()
        return res
