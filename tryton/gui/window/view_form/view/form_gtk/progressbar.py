# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gettext

from .widget import Widget

_ = gettext.gettext


class ProgressBar(Widget):
    'Progress Bar'
    orientations = {
        'left_to_right': gtk.PROGRESS_LEFT_TO_RIGHT,
        'right_to_left': gtk.PROGRESS_RIGHT_TO_LEFT,
        'bottom_to_top': gtk.PROGRESS_BOTTOM_TO_TOP,
        'top_to_bottom': gtk.PROGRESS_TOP_TO_BOTTOM,
        }

    def __init__(self, view, attrs):
        super(ProgressBar, self).__init__(view, attrs)
        self.widget = self.mnemonic_widget = gtk.ProgressBar()
        orientation = self.orientations.get(attrs.get('orientation',
            'left_to_right'), gtk.PROGRESS_LEFT_TO_RIGHT)
        self.widget.set_orientation(orientation)

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
