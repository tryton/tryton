# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext
import locale
import math
from decimal import Decimal, InvalidOperation

from gi.repository import Gdk, GObject, Gtk

__all__ = ['NumberEntry']

_ = gettext.gettext


class NumberEntry(Gtk.Entry, Gtk.Editable):
    # Override Editable to avoid modify the base implementation of Entry
    __gtype_name__ = 'NumberEntry'
    __digits = None

    def __init__(self, *args, **kwargs):
        self.monetary = kwargs.pop('monetary', False)
        self.convert = kwargs.pop('convert', float)
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
                return self.convert(locale.delocalize(text, self.monetary))
            except ValueError:
                pass
        return None

    @property
    def __decimal_point(self):
        return locale.localeconv()[
            self.monetary and 'mon_decimal_point' or 'decimal_point']

    @property
    def __thousands_sep(self):
        return locale.localeconv()[
            self.monetary and 'mon_thousands_sep' or 'thousands_sep']

    # XXX: Override vfunc because position is inout
    # https://gitlab.gnome.org/GNOME/pygobject/issues/12
    def do_insert_text(self, new_text, length, position):
        buffer_ = self.get_buffer()
        text = self.get_buffer().get_text()
        text = text[:position] + new_text + text[position:]
        value = None
        if text not in ['-', self.__decimal_point, self.__thousands_sep]:
            try:
                value = Decimal(locale.delocalize(text, self.monetary))
            except (ValueError, InvalidOperation):
                return position
        if self.__digits:
            int_size, dec_size = self.__digits
            try:
                if int_size is not None and value:
                    if math.ceil(math.log10(abs(value))) > int_size:
                        return position
                if dec_size is not None:
                    if (round(value, dec_size) != value
                            or value.as_tuple().exponent < -dec_size):
                        return position
            except InvalidOperation:
                return position
        length = len(new_text.encode('utf-8'))
        buffer_.insert_text(position, new_text, length)
        return position + length

    def __key_press_event(self, event):
        for name in ['KP_Decimal', 'KP_Separator']:
            if event.keyval == Gdk.keyval_from_name(name):
                text = self.__decimal_point
                if self.get_selection_bounds():
                    self.delete_text(*self.get_selection_bounds())
                self.do_insert_text(
                    text, len(text), self.props.cursor_position)
                self.set_position(self.props.cursor_position + len(text))
                return True


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
