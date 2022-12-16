#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gettext
from interface import Interface
import gobject

_ = gettext.gettext


class Char(Interface):

    def __init__(self, name, parent, attrs=None, context=None,
            on_change=None):
        super(Char, self).__init__(name, parent, attrs=attrs, context=context,
                on_change=on_change)

        self.widget = gtk.HBox()

        self.liststore = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        self.combo = gtk.ComboBox(self.liststore)
        cell = gtk.CellRendererText()
        self.combo.pack_start(cell, True)
        self.combo.add_attribute(cell, 'text', 1)
        for oper in (
                ['ilike', _('contains')],
                ['not ilike', _('does not contain')],
                ['=', _('equals')],
                ['!=', _('does not equal')],
                ['starts', _('starts with')],
                ['ends', _('ends with')],
                ):
            self.liststore.append(oper)
        self.combo.set_active(0)
        self.combo.connect('changed', self.on_change)
        self.widget.pack_start(self.combo, False, False)

        self.entry = gtk.Entry()
        self.entry.set_max_length(int(self.attrs.get('size', 0)))
        self.entry.set_width_chars(5)
        self.entry.set_property('activates_default', True)
        self.entry.connect('key_press_event', self.on_change)
        self.widget.pack_start(self.entry, True, True)
        self.widget.show_all()

    def _value_get(self):
        value = self.entry.get_text()
        oper = self.liststore.get_value(self.combo.get_active_iter(), 0)
        if value or oper != 'ilike':
            if oper == '=' and not value:
                value = False
            if oper in ('ilike', 'not ilike') \
                    and '%' not in value:
                return [(self.name, oper, '%' + value + '%')]
            elif oper == 'starts':
                return [(self.name, 'ilike', value + '%')]
            elif oper == 'ends':
                return [(self.name, 'ilike', '%' + value)]
            return [(self.name, oper, value)]
        else:
            return []

    def _value_set(self, value):
        i = self.liststore.get_iter_root()
        while i:
            if self.liststore.get_value(i, 0) == value[0]:
                self.combo.set_active_iter(i)
                break
            i = self.liststore.iter_next(i)
        self.entry.set_text(value[1] or '')

    value = property(_value_get, _value_set)

    def clear(self):
        self.value = ['ilike', '']

    def _readonly_set(self, value):
        self.combo.set_sensitive(not value)
        self.entry.set_editable(not value)
        self.entry.set_sensitive(not value)

    def sig_activate(self, fct):
        self.entry.connect_after('activate', fct)
