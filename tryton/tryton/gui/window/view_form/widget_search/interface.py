#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gettext

_ = gettext.gettext


class Interface(object):
    "Interface for search widget"

    def __init__(self, name, parent, attrs=None, context=None, on_change=None):
        if attrs is None:
            attrs = {}
        self._value = None
        self.parent = parent
        self.name = name
        self.model = attrs.get('model', None)
        self.attrs = attrs or {}
        self.context = context or {}
        self.on_change = on_change

    def clear(self):
        self.value = ''

    def _value_get(self):
        return self._value

    def _value_set(self, value):
        self._value = value

    value = property(_value_get, _value_set)

    def _readonly_set(self, value):
        pass

    def sig_activate(self, fct):
        pass
