# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
from gi.repository import Gdk, GObject, Gtk

MOVEMENT_KEYS = {
    Gdk.KEY_Up,
    Gdk.KEY_Down,
    Gdk.KEY_space,
    Gdk.KEY_Left,
    Gdk.KEY_KP_Left,
    Gdk.KEY_Right,
    Gdk.KEY_KP_Right,
    Gdk.KEY_Home,
    Gdk.KEY_KP_Home,
    Gdk.KEY_End,
    Gdk.KEY_KP_End,
    }

__all__ = ['TreeViewControl']


class TreeViewControl(Gtk.TreeView):

    def do_button_press_event(self, event):
        self.grab_focus()  # grab focus because it doesn't whith CONTROL MASK
        if event.button == 1:
            event.state ^= Gdk.ModifierType.CONTROL_MASK
        return Gtk.TreeView.do_button_press_event(self, event)

    def do_key_press_event(self, event):
        if event.keyval in MOVEMENT_KEYS:
            event.state ^= Gdk.ModifierType.CONTROL_MASK
        return Gtk.TreeView.do_key_press_event(self, event)


GObject.type_register(TreeViewControl)
