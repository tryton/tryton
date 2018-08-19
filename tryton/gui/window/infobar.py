# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from gi.repository import Gtk


class InfoBar(object):

    def create_info_bar(self):
        self.info_label = Gtk.Label()

        self.info_bar = Gtk.InfoBar()
        self.info_bar.get_content_area().pack_start(
            self.info_label, False, False)
        self.info_bar.set_show_close_button(True)
        self.info_bar.connect('response', lambda i, r: i.hide())

    def response(self, bar, response):
        if response == Gtk.ResponseType.CLOSE:
            bar.hide()

    def message_info(self, message=None, type_=Gtk.MessageType.ERROR):
        if message:
            # Work around https://bugzilla.gnome.org/show_bug.cgi?id=710888
            parent = self.info_bar.get_parent()
            self.info_bar.unparent()
            self.info_bar.set_parent(parent)

            self.info_label.set_label(message)
            self.info_bar.set_message_type(type_)
            self.info_bar.show_all()
        else:
            self.info_bar.hide()
