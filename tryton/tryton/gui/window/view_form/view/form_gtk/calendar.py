#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import time
import datetime
import gtk
import gettext
import locale
from interface import WidgetInterface
import tryton.rpc as rpc
from tryton.common import DT_FORMAT, DHM_FORMAT, HM_FORMAT, message, \
        TRYTON_ICON
from tryton.common import date_widget, Tooltips, datetime_strftime
from tryton.translate import date_format

_ = gettext.gettext


class Calendar(WidgetInterface):
    "Calendar"

    def __init__(self, field_name, model_name, window, attrs=None):
        super(Calendar, self).__init__(field_name, model_name, window,
                attrs=attrs)

        self.format = date_format()
        self.widget = date_widget.ComplexEntry(self.format, spacing=0)
        self.entry = self.widget.widget
        self.entry.set_property('activates_default', True)
        self.entry.connect('key_press_event', self.sig_key_press)
        self.entry.connect('activate', self.sig_activate)
        self.entry.connect('focus-in-event', lambda x, y: self._focus_in())
        self.entry.connect('focus-out-event', lambda x, y: self._focus_out())

        self.but_open = gtk.Button()
        img_find = gtk.Image()
        img_find.set_from_stock('tryton-find', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.but_open.set_image(img_find)
        self.but_open.set_relief(gtk.RELIEF_NONE)
        self.but_open.connect('clicked', self.cal_open)
        self.but_open.set_alignment(0.5, 0.5)
        self.widget.pack_start(self.but_open, expand=False, fill=False)
        self.widget.set_focus_chain([self.entry])

        tooltips = Tooltips()
        tooltips.set_tip(self.but_open, _('Open the calendar'))
        tooltips.enable()

    def _color_widget(self):
        return self.entry

    def _readonly_set(self, value):
        self.entry.set_editable(not value)
        self.but_open.set_sensitive(not value)
        if value:
            self.widget.set_focus_chain([])
        else:
            self.widget.set_focus_chain([self.entry])

    def sig_key_press(self, widget, event):
        if not self.entry.get_editable():
            return False
        if event.keyval == gtk.keysyms.F2:
            self.cal_open(widget)
            return True

    def grab_focus(self):
        return self.entry.grab_focus()

    def get_value(self, record):
        value = self.entry.get_text()
        if value == '':
            return False
        try:
            date = datetime.date(*time.strptime(value, self.format)[:3])
        except Exception:
            return False
        return datetime_strftime(date, DT_FORMAT)

    def set_value(self, record, field):
        field.set_client(record, self.get_value(record))
        return True

    def display(self, record, field):
        if not field:
            self.entry.clear()
            return False
        super(Calendar, self).display(record, field)
        value = field.get_client(record)
        if not value:
            self.entry.clear()
        else:
            if len(value)>10:
                value = value[:10]
            date = datetime.date(*time.strptime(value, DT_FORMAT)[:3])
            value = datetime_strftime(date, self.format)
            if len(value) > self.entry.get_width_chars():
                self.entry.set_width_chars(len(value))
            self.entry.set_text(value)
        return True

    def display_value(self):
        return self.entry.get_text()

    def cal_open(self, widget):
        win = gtk.Dialog(_('Date Selection'), self.window,
                gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_OK, gtk.RESPONSE_OK))
        win.set_has_separator(True)
        win.set_icon(TRYTON_ICON)

        cal = gtk.Calendar()
        cal.set_display_options(gtk.CALENDAR_SHOW_HEADING | \
                gtk.CALENDAR_SHOW_DAY_NAMES | \
                gtk.CALENDAR_SHOW_WEEK_NUMBERS | \
                gtk.CALENDAR_WEEK_START_MONDAY)
        cal.connect('day-selected-double-click',
                lambda *x: win.response(gtk.RESPONSE_OK))
        win.vbox.pack_start(cal, expand=True, fill=True)
        win.show_all()

        try:
            val = self.get_value(self.record)
            if val:
                cal.select_month(int(val[5:7])-1, int(val[0:4]))
                cal.select_day(int(val[8:10]))
        except ValueError:
            pass

        response = win.run()
        if response == gtk.RESPONSE_OK:
            year, month, day = cal.get_date()
            date = datetime.date(year, month + 1, day)
            self.entry.set_text(datetime_strftime(date, self.format))
        self._focus_out()
        self.window.present()
        win.destroy()


class DateTime(WidgetInterface):
    "DateTime"

    def __init__(self, field_name, model_name, window, attrs=None):
        super(DateTime, self).__init__(field_name, model_name, window,
                attrs=attrs)

        self.format = date_format() + ' ' + HM_FORMAT
        self.widget = date_widget.ComplexEntry(self.format, spacing=0)
        self.entry = self.widget.widget
        self.entry.set_property('activates_default', True)
        self.entry.connect('key_press_event', self.sig_key_press)
        self.entry.connect('focus-in-event', lambda x, y: self._focus_in())
        self.entry.connect('focus-out-event', lambda x, y: self._focus_out())

        self.but_open = gtk.Button()
        img_find = gtk.Image()
        img_find.set_from_stock('tryton-find', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.but_open.set_image(img_find)
        self.but_open.set_relief(gtk.RELIEF_NONE)
        self.but_open.connect('clicked', self.cal_open)
        self.but_open.set_alignment(0.5, 0.5)
        self.widget.pack_start(self.but_open, expand=False, fill=False)
        self.widget.set_focus_chain([self.entry])

        tooltips = Tooltips()
        tooltips.set_tip(self.but_open, _('Open the calendar'))
        tooltips.enable()

    def _color_widget(self):
        return self.entry

    def _readonly_set(self, value):
        self.entry.set_editable(not value)
        self.but_open.set_sensitive(not value)
        if value:
            self.widget.set_focus_chain([])
        else:
            self.widget.set_focus_chain([self.entry])

    def sig_key_press(self, widget, event):
        if not self.entry.get_editable():
            return False
        if event.keyval == gtk.keysyms.F2:
            self.cal_open(widget)
            return True

    def grab_focus(self):
        return self.entry.grab_focus()

    def get_value(self, record, timezone=True):
        value = self.entry.get_text()
        if value == '':
            return False
        try:
            date = datetime.datetime(*time.strptime(value, self.format)[:6])
        except Exception:
            return False
        if 'timezone' in rpc.CONTEXT and timezone:
            try:
                import pytz
                lzone = pytz.timezone(rpc.CONTEXT['timezone'])
                szone = pytz.timezone(rpc.TIMEZONE)
                ldt = lzone.localize(date, is_dst=True)
                sdt = ldt.astimezone(szone)
                date = sdt
            except Exception:
                pass
        return datetime_strftime(date, DHM_FORMAT)

    def set_value(self, record, field):
        field.set_client(record, self.get_value(record))
        return True

    def display(self, record, field):
        super(DateTime, self).display(record, field)
        if not field:
            return self.show(False)
        self.show(field.get_client(record))

    def show(self, dt_val, timezone=True):
        if not dt_val:
            self.entry.clear()
        else:
            date = datetime.datetime(*time.strptime(dt_val, DHM_FORMAT)[:6])
            if 'timezone' in rpc.CONTEXT and timezone:
                try:
                    import pytz
                    lzone = pytz.timezone(rpc.CONTEXT['timezone'])
                    szone = pytz.timezone(rpc.TIMEZONE)
                    sdt = szone.localize(date, is_dst=True)
                    ldt = sdt.astimezone(lzone)
                    date = ldt
                except Exception:
                    pass
            value = datetime_strftime(date, self.format)
            if len(value) > self.entry.get_width_chars():
                self.entry.set_width_chars(len(value))
            self.entry.set_text(value)
        return True

    def display_value(self):
        return self.entry.get_text()

    def cal_open(self, widget):
        win = gtk.Dialog(_('Date Time Selection'), self.window,
                gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_OK, gtk.RESPONSE_OK))
        win.set_has_separator(True)
        win.set_icon(TRYTON_ICON)
        win.vbox.set_spacing(2)

        hbox = gtk.HBox(spacing=2)
        hbox.pack_start(gtk.Label(_('Hour:')), expand=False, fill=False)
        widget_hour = gtk.SpinButton(gtk.Adjustment(0, 0, 23, 1, 5), 1, 0)
        hbox.pack_start(widget_hour, expand=True, fill=True)
        hbox.pack_start(gtk.Label(_('Minute:')), expand=False, fill=False)
        widget_minute = gtk.SpinButton(
                gtk.Adjustment(0, 0, 59, 1, 10), 1, 0)
        hbox.pack_start(widget_minute, expand=True, fill=True)
        win.vbox.pack_start(hbox, expand=False, fill=True)

        cal = gtk.Calendar()
        cal.set_display_options(gtk.CALENDAR_SHOW_HEADING | \
                gtk.CALENDAR_SHOW_DAY_NAMES | \
                gtk.CALENDAR_SHOW_WEEK_NUMBERS | \
                gtk.CALENDAR_WEEK_START_MONDAY)
        cal.connect('day-selected-double-click',
                lambda *x: win.response(gtk.RESPONSE_OK))
        win.vbox.pack_start(cal, expand=True, fill=True)
        win.show_all()

        try:
            val = self.get_value(self.record, timezone=False)
            if val:
                widget_hour.set_value(int(val[11:13]))
                widget_minute.set_value(int(val[-5:-3]))
                cal.select_month(int(val[5:7])-1, int(val[0:4]))
                cal.select_day(int(val[8:10]))
            else:
                widget_hour.set_value(time.localtime()[3])
                widget_minute.set_value(time.localtime()[4])
        except ValueError:
            pass
        response = win.run()
        if response == gtk.RESPONSE_OK:
            hour = int(widget_hour.get_value())
            minute = int(widget_minute.get_value())
            year = int(cal.get_date()[0])
            month = int(cal.get_date()[1]) + 1
            day = int(cal.get_date()[2])
            date = datetime.datetime(year, month, day, hour, minute)
            value = datetime_strftime(date, DHM_FORMAT)
            self.show(value, timezone=False)
        self._focus_out()
        self.window.present()
        win.destroy()
