# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from gi.repository import Gtk


class InfoBar(object):

    toolbar = None

    def create_info_bar(self):
        self.__box = Gtk.VBox()
        self.__box.show()
        self.__messages = set()
        return self.__box

    def info_bar_add(self, message, type_=Gtk.MessageType.ERROR):
        key = (message, type_)
        if key not in self.__messages:
            info_bar = Gtk.InfoBar()
            self.__box.pack_start(info_bar, False, False, 0)
            area = info_bar.get_content_area()
            area.add(Gtk.Label(label=message))
            info_bar.set_show_close_button(True)
            info_bar.connect('response', self.__response, key)
            info_bar.set_message_type(type_)
            info_bar.show_all()

    def __response(self, widget, response, key):
        self.__messages.add(key)
        self.__box.remove(widget)

    def info_bar_refresh(self):
        for child in self.__box.get_children():
            self.__box.remove(child)

    def info_bar_clear(self):
        self.info_bar_refresh()
        self.__messages.clear()
