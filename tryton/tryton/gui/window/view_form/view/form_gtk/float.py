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
        digits = self.digits or [None, None]
        return sum(v if v is not None else d for v, d in zip(digits, [16, 2]))

    def display(self):
        self.entry.digits = self.digits
        super().display()
