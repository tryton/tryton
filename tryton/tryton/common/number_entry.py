# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext
import locale

from gi.repository import Gdk, GObject, Gtk

__all__ = ['NumberEntry']

_ = gettext.gettext


class NumberEntry(Gtk.Entry, Gtk.Editable):
    # Override Editable to avoid modify the base implementation of Entry
    __gtype_name__ = 'NumberEntry'
    __digits = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_alignment(1.0)
        self.connect('key-press-event', self.__class__.__key_press_event)

    @GObject.Property(
        default=None, nick=_("Digits"), blurb=_("The number of decimal"))
    def digits(self):
        return self.__digits

    @digits.setter
    def digits(self, value):
        self.__digits = value

    @GObject.Property
    def value(self):
        text = self.get_text()
        if text:
            try:
                return locale.atof(text)
            except ValueError:
                pass
        return None

    @property
    def __decimal_point(self):
        return locale.localeconv()['decimal_point']

    # XXX: Override vfunc because position is inout
    # https://gitlab.gnome.org/GNOME/pygobject/issues/12
    def do_insert_text(self, new_text, length, position):
        buffer_ = self.get_buffer()
        text = self.get_buffer().get_text()
        text = text[:position] + new_text + text[position:]
        value = None
        if text not in ['-', self.__decimal_point]:
            try:
                value = locale.atof(text)
            except ValueError:
                return position
        if (value and self.__digits is not None
                and round(value, self.__digits) != value):
            return position
        buffer_.insert_text(position, new_text, len(new_text))
        return position + len(new_text)

    def __key_press_event(self, event):
        for name in ['KP_Decimal', 'KP_Separator']:
            if event.keyval == Gdk.keyval_from_name(name):
                event.keyval = Gdk.unicode_to_keyval(ord(self.__decimal_point))


GObject.type_register(NumberEntry)


if __name__ == '__main__':
    win = Gtk.Window()
    win.connect('delete-event', Gtk.main_quit)
    vbox = Gtk.VBox()
    e = NumberEntry()
    vbox.pack_start(NumberEntry(), expand=False, fill=False, padding=0)
    vbox.pack_start(NumberEntry(digits=2), expand=False, fill=False, padding=0)
    vbox.pack_start(NumberEntry(digits=0), expand=False, fill=False, padding=0)
    vbox.pack_start(
        NumberEntry(digits=-2), expand=False, fill=False, padding=0)
    win.add(vbox)
    win.show_all()
    Gtk.main()
