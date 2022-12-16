#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
from interface import Interface
import locale
import gettext
import gobject

_ = gettext.gettext


class Integer(Interface):

    def __init__(self, name, parent, attrs=None, context=None):
        super(Integer, self).__init__(name, parent, attrs=attrs,
                context=context)
        self.widget = gtk.HBox(spacing=3)

        self.liststore = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        self.combo = gtk.ComboBox(self.liststore)
        cell = gtk.CellRendererText()
        self.combo.pack_start(cell, True)
        self.combo.add_attribute(cell, 'text', 1)
        for oper in (['=', _('equals')],
                ['between', _('is between')],
                ['not between', _('is not between')],
                ['!=', _('is different')],
                ):
            self.liststore.append(oper)
        self.combo.set_active(0)
        self.widget.pack_start(self.combo, False, False)
        self.combo.connect('changed', self._changed)

        self.entry1 = gtk.Entry()
        self.entry1.set_max_length(0)
        self.entry1.set_width_chars(5)
        self.entry1.set_activates_default(True)
        self.entry1.set_alignment(1.0)
        self.entry1.connect('insert_text', self.sig_insert_text)
        self.widget.pack_start(self.entry1, expand=True, fill=True)
        self.separator = gtk.Label('-')
        self.widget.pack_start(self.separator, expand=False, fill=False)
        self.entry2 = gtk.Entry()
        self.entry2.set_max_length(0)
        self.entry2.set_width_chars(5)
        self.entry2.set_activates_default(True)
        self.entry2.set_alignment(1.0)
        self.entry2.connect('insert_text', self.sig_insert_text)
        self.widget.pack_start(self.entry2, expand=True, fill=True)

        self.widget.show_all()
        self._changed(self.combo)

    def _changed(self, widget):
        oper = self.liststore.get_value(self.combo.get_active_iter(), 0)
        if oper in ('=', '!='):
            self.entry2.hide()
            self.separator.hide()
        else:
            self.entry2.show()
            self.separator.show()

    def _value_get(self):
        try:
            value1 = locale.atoi(self.entry1.get_text())
        except:
            value1 = False
        try:
            value2 = locale.atoi(self.entry2.get_text())
        except:
            value2 = False
        return self._get_clause(value1, value2)

    def _get_clause(self, value1, value2):
        oper = self.liststore.get_value(self.combo.get_active_iter(), 0)
        if oper in ('=', '!='):
            if self.entry1.get_text():
                return [(self.name, oper, value1 or 0)]
            else:
                return []
        else:
            res = []
            if oper == 'between':
                clause = 'AND'
                oper1 = '>='
                oper2 = '<='
            else:
                clause = 'OR'
                oper1 = '<='
                oper2 = '>='
            res.append(clause)
            if value1 is not False:
                res.append((self.name, oper1, value1))
            if value2 is not False:
                res.append((self.name, oper2, value2))
            return [res]

    def _value_set(self, value):
        def conv(value):
            if value == False:
                return ''
            else:
                return locale.format('%d', value or 0, True)

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

    def sig_activate(self, fct):
        self.entry1.connect_after('activate', fct)
        self.entry2.connect_after('activate', fct)

    def sig_insert_text(self, widget, new_text, new_text_length, position):
        value = widget.get_text()
        position = widget.get_position()
        new_value = value[:position] + new_text + value[position:]
        try:
            if new_value == '-':
                return
            locale.atoi(new_value)
        except:
            widget.stop_emission('insert-text')
