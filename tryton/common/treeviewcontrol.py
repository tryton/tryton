# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
import gtk
import gobject

MOVEMENT_KEYS = {gtk.keysyms.Up, gtk.keysyms.Down, gtk.keysyms.space,
    gtk.keysyms.Left, gtk.keysyms.KP_Left,
    gtk.keysyms.Right, gtk.keysyms.KP_Right,
    gtk.keysyms.Home, gtk.keysyms.KP_Home,
    gtk.keysyms.End, gtk.keysyms.KP_End}

__all__ = ['TreeViewControl']


class TreeViewControl(gtk.TreeView):
    __gsignals__ = {
        'button-press-event': 'override',
        'key-press-event': 'override',
        }

    def do_button_press_event(self, event):
        self.grab_focus()  # grab focus because it doesn't whith CONTROL MASK
        if event.button == 1:
            event.state ^= gtk.gdk.CONTROL_MASK
        return gtk.TreeView.do_button_press_event(self, event)

    def do_key_press_event(self, event):
        if event.keyval in MOVEMENT_KEYS:
            event.state ^= gtk.gdk.CONTROL_MASK
        return gtk.TreeView.do_key_press_event(self, event)

gobject.type_register(TreeViewControl)
