# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext

from gi.repository import Gtk

from .widget import Widget

_ = gettext.gettext


class ProgressBar(Widget):
    'Progress Bar'
    orientations = {
        'left_to_right': (Gtk.Orientation.HORIZONTAL, False),
        'right_to_left': (Gtk.Orientation.HORIZONTAL, True),
        'bottom_to_top': (Gtk.Orientation.VERTICAL, True),
        'top_to_bottom': (Gtk.Orientation.VERTICAL, False),
        }

    def __init__(self, view, attrs):
        super(ProgressBar, self).__init__(view, attrs)
        self.widget = self.mnemonic_widget = Gtk.ProgressBar()
        orientation, inverted = self.orientations.get(
            attrs.get('orientation', 'left_to_right'))
        self.widget.set_orientation(orientation)
        self.widget.set_inverted(inverted)

    def display(self):
        super(ProgressBar, self).display()
        if not self.field:
            self.widget.set_text('')
            self.widget.set_fraction(0.0)
            return False
        text = self.field.get_client(self.record, factor=100)
        if text:
            text = _('%s%%') % text
        self.widget.set_text(text)
        value = self.field.get(self.record) or 0.0
        self.widget.set_fraction(value)
