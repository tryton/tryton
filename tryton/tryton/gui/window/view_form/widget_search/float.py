#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import locale
from integer import Integer
import gettext

_ = gettext.gettext


class Float(Integer):

    def __init__(self, name, parent, attrs=None, context=None):
        super(Float, self).__init__(name, parent, attrs=attrs, context=context)
        if isinstance(self.attrs.get('digits'), str):
            self.digits = (16, 2)
        else:
            self.digits = self.attrs.get('digits', (16, 2))

    def _value_get(self):
        try:
            value1 = locale.atof(self.entry1.get_text())
        except:
            value1 = False
        try:
            value2 = locale.atof(self.entry2.get_text())
        except:
            value2 = False
        return self._get_clause(value1, value2)

    def _value_set(self, value):
        def conv(value):
            if value == False:
                return ''
            else:
                return locale.format('%.' + str(self.digits[1]) + 'f',
                value or 0.0, True)

        i = self.liststore.get_iter_root()
        while i:
            if self.liststore.get_value(i, 0) == value[0]:
                self.combo.set_active_iter(i)
                break
            i = self.liststore.iter_next(i)

        self.entry1.set_text(conv(value[1]))
        if len(value) == 2:
            self.entry2.set_text('')
        else:
            self.entry2.set_text(conv(value[2]))

    value = property(_value_get, _value_set)

    def clear(self):
        self.value = ('=', False, False)

    def sig_insert_text(self, widget, new_text, new_text_length, position):
        value = widget.get_text()
        position = widget.get_position()
        new_value = value[:position] + new_text + value[position:]
        try:
            if new_value == '-':
                return
            if len(str(int(locale.atof(new_value)))) > self.digits[0]:
                widget.stop_emission('insert-text')
        except:
            widget.stop_emission('insert-text')
