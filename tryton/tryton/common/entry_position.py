#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import string

import gtk


class PositionManager(object):
    position = None

    def reset_position(self, entry):
        if entry.get_alignment() <= 0.5:
            entry.set_position(0)
        else:
            entry.set_position(-1)

    def focus_out(self, entry, event):
        self.position = entry.get_position()
        self.reset_position(entry)

    def focus_in(self, entry, event):
        if self.position is None:
            self.reset_position(entry)
        else:
            entry.set_position(self.position)

    def changed(self, entry):
        if not entry.has_focus():
            self.reset_position(entry)


def manage_entry_position(entry):
    manager = PositionManager()
    entry.connect('focus-out-event', manager.focus_out)
    entry.connect('focus-in-event', manager.focus_in)
    entry.connect('changed', manager.changed)


if __name__ == '__main__':
    win = gtk.Window()
    win.set_title('Manage Entry Position')
    win.connect('delete-event', lambda *a: gtk.main_quit())
    vbox = gtk.VBox()
    win.add(vbox)

    entry1 = gtk.Entry()
    vbox.pack_start(entry1, expand=False, fill=False)
    manage_entry_position(entry1)
    entry1.set_text(string.ascii_letters)

    entry2 = gtk.Entry()
    entry2.set_alignment(1.0)
    vbox.pack_start(entry2, expand=False, fill=False)
    manage_entry_position(entry2)
    entry2.set_text(string.ascii_letters)

    win.show_all()
    gtk.main()
