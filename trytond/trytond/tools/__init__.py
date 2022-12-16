#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from .misc import *
from .datetime_strftime import *


class ClassProperty(property):
    def __get__(self, cls, owner):
        return self.fget.__get__(None, owner)()
