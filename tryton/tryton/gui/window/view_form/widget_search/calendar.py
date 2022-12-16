#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import time
import datetime
import gtk
import gettext
import locale
from interface import Interface
from tryton.common import DT_FORMAT, DHM_FORMAT, TRYTON_ICON
from tryton.common import date_widget, Tooltips, datetime_strftime
from tryton.translate import date_format
import gobject

_ = gettext.gettext


class Calendar(Interface):

    def __init__(self, name, parent, attrs=None, context=None,
            on_change=None):
        super(Calendar, self).__init__(name, parent, attrs=attrs,
                context=context, on_change=on_change)

        tooltips = Tooltips()
        self.widget = gtk.HBox(spacing=3)

        self.format = date_format()

        self.liststore = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        self.combo = gtk.ComboBox(self.liststore)
        cell = gtk.CellRendererText()
        self.combo.pack_start(cell, True)
        self.combo.add_attribute(cell, 'text', 1)
        for oper in (['=', _('is')],
                ['between', _('is between')],
                ['not between', _('is not between')],
                ['!=', _('is not')],
                ):
            self.liststore.append(oper)
        self.combo.set_active(0)
        self.widget.pack_start(self.combo, False, False)
        self.combo.connect('changed', self._changed)
        self.combo.connect('changed', self.on_change)

        self.widget1 = date_widget.ComplexEntry(self.format, spacing=3)
        self.widget1.show()
        self.entry1 = self.widget1.widget
        self.entry1.set_property('width-chars', 10)
        self.entry1.set_property('activates_default', True)
        self.entry1.connect('key_press_event', self.on_change)
        tooltips.set_tip(self.entry1, _('Start date'))
        self.widget.pack_start(self.widget1, expand=False, fill=True)

        self.eb1 = gtk.EventBox()
        tooltips.set_tip(self.eb1, _('Open the calendar'))
        self.eb1.set_events(gtk.gdk.BUTTON_PRESS)
        self.eb1.connect('button_press_event', self.cal_open, self.entry1,
                parent)
        img = gtk.Image()
        img.set_from_stock('tryton-find', gtk.ICON_SIZE_BUTTON)
        img.set_alignment(0.5, 0.5)
        self.eb1.add(img)
        self.widget.pack_start(self.eb1, expand=False, fill=False)

        self.separator = gtk.Label('-')
        self.widget.pack_start(self.separator, expand=False, fill=False)

        self.widget2 = date_widget.ComplexEntry(self.format, spacing=3)
        self.entry2 = self.widget2.widget
        self.entry2.set_property('width-chars', 10)
        self.entry2.set_property('activates_default', True)
        self.entry2.connect('key_press_event', self.on_change)
        tooltips.set_tip(self.entry2, _('End date'))
        self.widget.pack_start(self.widget2, expand=False, fill=True)

        self.eb2 = gtk.EventBox()
        tooltips.set_tip(self.eb2, _('Open the calendar'))
        self.eb2.set_events(gtk.gdk.BUTTON_PRESS)
        self.eb2.connect('button_press_event', self.cal_open, self.entry2,
                parent)
        img = gtk.Image()
        img.set_from_stock('tryton-find', gtk.ICON_SIZE_BUTTON)
        img.set_alignment(0.5, 0.5)
        self.eb2.add(img)
        self.widget.pack_start(self.eb2, expand=False, fill=False)

        self.widget.show_all()
        self._changed(self.combo)

        tooltips.enable()

    def _changed(self, widget):
        oper = self.liststore.get_value(self.combo.get_active_iter(), 0)
        if oper in ('=', '!='):
            self.entry2.hide()
            self.separator.hide()
            self.eb2.hide()
        else:
            self.entry2.show()
            self.separator.show()
            self.eb2.show()

    def _date_get(self, value):
        try:
            date = datetime.date(*time.strptime(value, self.format)[:3])
        except Exception:
            return False
        if self.attrs.get('type', 'date') == 'datetime':
            return datetime_strftime(datetime.datetime.combine(date,
                datetime.time.min), DHM_FORMAT)
        return datetime_strftime(date, DT_FORMAT)

    def _value_get(self):
        oper = self.liststore.get_value(self.combo.get_active_iter(), 0)
        if oper in ('=', '!='):
            value = self._date_get(self.entry1.get_text())
            if value:
                return [(self.name, oper, value)]
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
            val = self._date_get(self.entry1.get_text())
            if val:
                res.append((self.name, oper1, val))
            val = self._date_get(self.entry2.get_text())
            if val:
                res.append((self.name, oper2, val))
            return [res]

    def _value_set(self, value):
        def conv(value):
            if not value:
                return ''
            try:
                return datetime_strftime(value, self.format)
            except Exception:
                return ''

        i = self.liststore.get_iter_root()
        while i:
            if self.liststore.get_value(i, 0) == value[0]:
                self.combo.set_active_iter(i)
                break
            i = self.liststore.iter_next(i)

        self.entry1.set_text(conv(value[1]))
        if len(value) == 2:
            self.entry2.clear()
        else:
            self.entry2.set_text(conv(value[2]))

    value = property(_value_get, _value_set)

    def cal_open(self, widget, event, dest, parent=None):
        win = gtk.Dialog(_('Date selection'), parent,
                gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_OK, gtk.RESPONSE_OK))
        win.set_has_separator(True)
        win.set_icon(TRYTON_ICON)

        cal = gtk.Calendar()
        cal.display_options(gtk.CALENDAR_SHOW_HEADING | \
                        gtk.CALENDAR_SHOW_DAY_NAMES | \
                        gtk.CALENDAR_SHOW_WEEK_NUMBERS)
        cal.connect('day-selected-double-click',
                lambda *x: win.response(gtk.RESPONSE_OK))
        win.vbox.pack_start(cal, expand=True, fill=True)
        win.show_all()

        try:
            val = self._date_get(dest.get_text())
            if val:
                cal.select_month(int(val[5:7])-1, int(val[0:4]))
                cal.select_day(int(val[8:10]))
        except ValueError:
            pass

        response = win.run()
        if response == gtk.RESPONSE_OK:
            year, month, day = cal.get_date()
            date = datetime.date(year, month + 1, day)
            dest.set_text(datetime_strftime(date, self.format))
            self.on_change()
        win.destroy()

    def clear(self):
        self.value = ('=', '')

    def sig_activate(self, fct):
        self.entry1.connect_after('activate', fct)
        self.entry2.connect_after('activate', fct)
