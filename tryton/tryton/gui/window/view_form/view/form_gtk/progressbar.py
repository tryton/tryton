#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
from interface import WidgetInterface
import locale


class ProgressBar(WidgetInterface):
    'Progress Bar'
    orientations = {
        'left_to_right': gtk.PROGRESS_LEFT_TO_RIGHT,
        'right_to_left': gtk.PROGRESS_RIGHT_TO_LEFT,
        'bottom_to_top': gtk.PROGRESS_BOTTOM_TO_TOP,
        'top_to_bottom': gtk.PROGRESS_TOP_TO_BOTTOM,
    }

    def __init__(self, window, parent, model, attrs=None):
        super(ProgressBar, self).__init__(window, parent, model=model, attrs=attrs)
        self.digits = attrs.get('digits', (16, 2))
        self.widget = gtk.ProgressBar()
        orientation = self.orientations.get(attrs.get('orientation',
            'left_to_right'), gtk.PROGRESS_LEFT_TO_RIGHT)
        self.widget.set_orientation(orientation)

    def display(self, model, model_field):
        super(ProgressBar, self).display(model, model_field)
        if not model_field:
            self.widget.set_text('')
            self.widget.set_fraction(0.0)
            return False
        value = float(model_field.get(model) or 0.0)
        if isinstance(self.digits, str):
            digits = self._view.model.expr_eval(self.digits)
        else:
            digits = self.digits
        self.widget.set_text(locale.format('%.' + str(digits[1]) + 'f',
            value, True))
        self.widget.set_fraction(value / 100.0)

    def display_value(self):
        return self.widget.get_text()
