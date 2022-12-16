#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import time
import datetime as DT
import gtk
import gettext
import locale
from interface import WidgetInterface
import tryton.rpc as rpc
from tryton.common import DT_FORMAT, DHM_FORMAT, HM_FORMAT, message, \
        TRYTON_ICON
from tryton.common import date_widget, Tooltips
from tryton.translate import date_format
import mx.DateTime

_ = gettext.gettext


class Calendar(WidgetInterface):
    "Calendar"

    def __init__(self, window, parent=None, model=None, attrs=None):
        super(Calendar, self).__init__(window, parent, model=model, attrs=attrs)

        self.format = date_format()
        self.widget = date_widget.ComplexEntry(self.format, spacing=0)
        self.entry = self.widget.widget
        self.entry.set_property('activates_default', True)
        self.entry.connect('key_press_event', self.sig_key_press)
        self.entry.connect('populate-popup', self._populate_popup)
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

    def get_value(self, model):
        value = self.entry.get_text()
        if value == '':
            return False
        try:
            date = mx.DateTime.strptime(value, self.format)
        except:
            return False
        return date.strftime(DT_FORMAT)

    def set_value(self, model, model_field):
        model_field.set_client(model, self.get_value(model))
        return True

    def display(self, model, model_field):
        if not model_field:
            self.entry.clear()
            return False
        super(Calendar, self).display(model, model_field)
        value = model_field.get_client(model)
        if not value:
            self.entry.clear()
        else:
            if len(value)>10:
                value = value[:10]
            date = mx.DateTime.strptime(value, DT_FORMAT)
            format = self.format
            if date.year < 10:
                format = format.replace('%Y', '000%Y')
            elif date.year < 100:
                format = format.replace('%Y', '00%Y')
            elif date.year < 1000:
                format = format.replace('%Y', '0%Y')
            value = date.strftime(format)
            if len(value) > self.entry.get_width_chars():
                self.entry.set_width_chars(len(value))
            self.entry.set_text(value)
        return True

    def display_value(self):
        return self.entry.get_text()

    def cal_open(self, widget):
        win = gtk.Dialog(_('Date Selection'), self._window,
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
            val = self.get_value(self.model)
            if val:
                cal.select_month(int(val[5:7])-1, int(val[0:4]))
                cal.select_day(int(val[8:10]))
        except ValueError:
            pass

        response = win.run()
        if response == gtk.RESPONSE_OK:
            year, month, day = cal.get_date()
            date = mx.DateTime.DateTime(year, month + 1, day)
            format = self.format
            if date.year < 10:
                format = format.replace('%Y', '000%Y')
            elif date.year < 100:
                format = format.replace('%Y', '00%Y')
            elif date.year < 1000:
                format = format.replace('%Y', '0%Y')
            self.entry.set_text(date.strftime(format))
        self._focus_out()
        self._window.present()
        win.destroy()


class DateTime(WidgetInterface):
    "DateTime"

    def __init__(self, window, parent, model, attrs=None):
        super(DateTime, self).__init__(window, parent, model, attrs=attrs)

        self.format = date_format() + ' ' + HM_FORMAT
        self.widget = date_widget.ComplexEntry(self.format, spacing=0)
        self.entry = self.widget.widget
        self.entry.set_property('activates_default', True)
        self.entry.connect('key_press_event', self.sig_key_press)
        self.entry.connect('populate-popup', self._populate_popup)
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

    def get_value(self, model, timezone=True):
        value = self.entry.get_text()
        if value == '':
            return False
        try:
            date = mx.DateTime.strptime(value, self.format)
        except:
            return False
        if 'timezone' in rpc.CONTEXT and timezone:
            try:
                import pytz
                lzone = pytz.timezone(rpc.CONTEXT['timezone'])
                szone = pytz.timezone(rpc.TIMEZONE)
                datetime = DT.datetime(date.year, date.month, date.day,
                        date.hour, date.minute, int(date.second))
                ldt = lzone.localize(datetime, is_dst=True)
                sdt = ldt.astimezone(szone)
                date = mx.DateTime.DateTime(*(sdt.timetuple()[:6]))
            except:
                pass
        return date.strftime(DHM_FORMAT)

    def set_value(self, model, model_field):
        model_field.set_client(model, self.get_value(model))
        return True

    def display(self, model, model_field):
        super(DateTime, self).display(model, model_field)
        if not model_field:
            return self.show(False)
        self.show(model_field.get_client(model))

    def show(self, dt_val, timezone=True):
        if not dt_val:
            self.entry.clear()
        else:
            date = mx.DateTime.strptime(dt_val, DHM_FORMAT)
            if 'timezone' in rpc.CONTEXT and timezone:
                try:
                    import pytz
                    lzone = pytz.timezone(rpc.CONTEXT['timezone'])
                    szone = pytz.timezone(rpc.TIMEZONE)
                    datetime = DT.datetime(date.year, date.month, date.day,
                            date.hour, date.minute, int(date.second))
                    sdt = szone.localize(datetime, is_dst=True)
                    ldt = sdt.astimezone(lzone)
                    date = mx.DateTime.DateTime(*(ldt.timetuple()[:6]))
                except:
                    pass
            format = self.format
            if date.year < 10:
                format = format.replace('%Y', '000%Y')
            elif date.year < 100:
                format = format.replace('%Y', '00%Y')
            elif date.year < 1000:
                format = format.replace('%Y', '0%Y')
            value = date.strftime(format)
            if len(value) > self.entry.get_width_chars():
                self.entry.set_width_chars(len(value))
            self.entry.set_text(value)
        return True

    def display_value(self):
        return self.entry.get_text()

    def cal_open(self, widget):
        win = gtk.Dialog(_('Date Time Selection'), self._window,
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
            val = self.get_value(self.model, timezone=False)
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
            date = mx.DateTime.DateTime(year, month, day, hour, minute)
            value = date.strftime(DHM_FORMAT)
            self.show(value, timezone=False)
        self._focus_out()
        self._window.present()
        win.destroy()
