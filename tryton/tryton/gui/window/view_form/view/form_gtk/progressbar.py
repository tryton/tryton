# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
from .widget import Widget
import locale


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
        self.widget = gtk.ProgressBar()
        orientation = self.orientations.get(attrs.get('orientation',
            'left_to_right'), gtk.PROGRESS_LEFT_TO_RIGHT)
        self.widget.set_orientation(orientation)

    def display(self, record, field):
        super(ProgressBar, self).display(record, field)
        if not field:
            self.widget.set_text('')
            self.widget.set_fraction(0.0)
            return False
        value = float(field.get(record) or 0.0)
        digits = field.digits(record)
        self.widget.set_text(locale.format('%.*f', (digits[1], value), True))
        self.widget.set_fraction(value / 100.0)
