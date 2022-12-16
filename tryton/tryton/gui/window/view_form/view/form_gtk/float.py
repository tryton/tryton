# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from .integer import Integer


class Float(Integer):
    "Float"

    @property
    def digits(self):
        if self.field and self.record:
            return self.field.digits(self.record, factor=self.factor)

    @property
    def width(self):
        digits = self.digits
        if digits:
            return sum(digits)
        else:
            return 18

    def display(self):
        digits = self.digits
        if digits:
            self.entry.digits = digits[1]
        else:
            self.entry.digits = None
        super(Float, self).display()
