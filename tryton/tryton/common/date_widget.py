#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Date Widget"

import gobject
import gtk
import re
import time
import datetime
import gettext

from dateutil.relativedelta import relativedelta

from datetime_strftime import datetime_strftime
from common import TRYTON_ICON

_ = gettext.gettext

__all__ = ['DateEntry']

MAPPING = {
    '%y': ('__', '([_ 0-9][_ 0-9])'),
    '%Y': ('____', '([_ 0-9][_ 0-9][_ 0-9][_ 0-9])'),
    '%m': ('__', '([_ 0-9][_ 0-9])'),
    '%d': ('__', '([_ 0-9][_ 0-9])'),
    '%H': ('__', '([_ 0-9][_ 0-9])'),
    '%I': ('__', '([_ 0-9][_ 0-9])'),
    '%M': ('__', '([_ 0-9][_ 0-9])'),
    '%S': ('__', '([_ 0-9][_ 0-9])'),
    '%p': ('__', '([_ AP][_ M])'),
    }
OPERATORS = {
    gtk.keysyms.S: relativedelta(seconds=-1),
    gtk.keysyms.s: relativedelta(seconds=1),
    gtk.keysyms.I: relativedelta(minutes=-1),
    gtk.keysyms.i: relativedelta(minutes=1),
    gtk.keysyms.H: relativedelta(hours=-1),
    gtk.keysyms.h: relativedelta(hours=1),
    gtk.keysyms.D: relativedelta(days=-1),
    gtk.keysyms.d: relativedelta(days=1),
    gtk.keysyms.W: relativedelta(weeks=-1),
    gtk.keysyms.w: relativedelta(weeks=1),
    gtk.keysyms.M: relativedelta(months=-1),
    gtk.keysyms.m: relativedelta(months=1),
    gtk.keysyms.Y: relativedelta(years=-1),
    gtk.keysyms.y: relativedelta(years=1),
    }


class DateEntry(gtk.Entry):

    def __init__(self, format):
        super(DateEntry, self).__init__()

        self.set_format(format)

        self.connect('key-press-event', self._on_key_press)
        self.connect('insert-text', self._on_insert_text)
        self.connect('delete-text', self._on_delete_text)

        self.connect('focus-in-event', self._focus_in)
        self.connect('focus-out-event', self._focus_out)

        if hasattr(self, 'set_icon_from_stock'):
            self.set_icon_from_stock(gtk.ENTRY_ICON_SECONDARY, 'tryton-find')
            self.set_icon_tooltip_text(gtk.ENTRY_ICON_SECONDARY,
                _('Open the calendar <F2>'))
            self.connect('icon-press', DateEntry.cal_open)

        self._interactive_input = True
        self.idle_set_position(0)

    def set_format(self, format):
        self.format = format
        self.regex = self.initial_value = format
        for key, val in MAPPING.items():
            self.regex = self.regex.replace(key, val[1])
            self.initial_value = self.initial_value.replace(key, val[0])

        self.regex = re.compile(self.regex)

        assert self.regex.match(self.initial_value), \
            'Error, the initial value should be validated by regex'
        self.set_width_chars(len(self.initial_value) + 3)  # space for icon
        self.set_max_length(len(self.initial_value))

    def idle_set_position(self, value):
        def idle_func():
            with gtk.gdk.lock:
                self.set_position(value)
                return False
        gobject.idle_add(idle_func)

    def _on_insert_text(self, editable, value, length, position):
        if not self._interactive_input:
            return

        pos = self.get_position()

        text = self.get_text()
        if not text:
            text = self.initial_value
        if text == self.initial_value and pos >= len(self.initial_value):
            pos = 0

        for char in value:
            if pos >= len(self.initial_value):
                continue
            if char not in ('_', ' ') and char in self.initial_value[pos:]:
                pos += self.initial_value[pos:].index(char)
            else:
                while self.initial_value[pos] not in ('_', ' '):
                    pos += 1
                text = text[:pos] + char + text[pos + 1:]
            pos += 1

        if self.regex.match(text) and self.test_date(text):
            self.set_text(text)
            self.idle_set_position(pos)
        self.stop_emission('insert-text')
        self.show()
        return

    def _on_delete_text(self, editable, start, end):
        if not self._interactive_input:
            return

        if start > len(self.initial_value):
            start = len(self.initial_value)
        if start < 0:
            start = 0
        if end > len(self.initial_value):
            end = len(self.initial_value)
        if end < 0:
            end = 0
        while (start > 0
                and self.initial_value[start] not in ['_', ' ', '0', 'X']):
            start -= 1
        text = self.get_text()
        text = text[:start] + self.initial_value[start:end] + text[end:]
        self.set_text(text)
        self.idle_set_position(start)
        self.stop_emission('delete-text')
        return

    def _focus_in(self, editable, event):
        if not self.get_text():
            self.set_text(self.initial_value)

    def _focus_out(self, editable, event):
        if self.get_text() == self.initial_value or not self.date_get():
            self.set_text('')

    def set_text(self, text):
        self._interactive_input = False
        try:
            gtk.Entry.set_text(self, text)
        finally:
            self._interactive_input = True

    def date_set(self, dt):
        if dt:
            self.set_text(datetime_strftime(dt, self.format))
        else:
            if self.is_focus():
                self.set_text(self.initial_value)
            else:
                self.set_text('')

    def compute_date(self, text, default=None, year=None):
        if default is None:
            default = datetime_strftime(datetime.datetime.now(), self.format)
        if text == self.initial_value or not text:
            return ''

        match = self.regex.match(text)
        if not match:
            return ''
        for i in range(len(match.groups())):
            val = match.group(i + 1)
            n = len(val)
            val = val.strip()
            val = val.strip('_')
            if n != 4:
                val = val.lstrip('0')
            if not val:
                continue
            fchar = '0'
            if n == 4:
                fchar = '_'
                if len(val) == 1:
                    val = '0' + val
            if year and n == 4 and len(val) != 4:
                val = year
            val = (fchar * (n - len(val))) + val
            start = match.start(i + 1)
            end = match.end(i + 1)
            text = text[:start] + val + text[end:]

        for a in range(len(self.initial_value)):
            if self.initial_value[a] == text[a]:
                text = text[:a] + default[a] + text[a + 1:]
        return text

    def test_date(self, text):
        default = datetime_strftime(datetime.datetime(2000, 1, 1),
                self.format)
        try:
            time.strptime(
                self.compute_date(text, default=default, year='2000'),
                self.format)
        except ValueError:
            return False
        return True

    def date_get(self, set_text=True):
        res = None
        date = self.compute_date(self.get_text())
        try:
            res = datetime.datetime(*time.strptime(date, self.format)[:6])
        except ValueError:
            return None
        if set_text:
            self.set_text(date)
        return res

    def delete_text(self, start, end):
        self._interactive_input = False
        try:
            gtk.Entry.delete_text(self, start, end)
        finally:
            self._interactive_input = True

    def insert_text(self, text, position=0):
        self._interactive_input = False
        try:
            gtk.Entry.insert_text(self, text, position)
        finally:
            self._interactive_input = True

    def clear(self):
        if self.is_focus():
            self.set_text(self.initial_value)
        else:
            self.set_text('')

    def _on_key_press(self, editable, event):
        if not self.get_editable():
            return False
        if event.keyval in (gtk.keysyms.KP_Equal, gtk.keysyms.equal):
            now = datetime.datetime.now()
            self.date_set(now)
            self.stop_emission("key-press-event")
            return True
        elif event.keyval == gtk.keysyms.F2:
            DateEntry.cal_open(editable)
            self.stop_emission("key-press-event")
            return True
        elif event.keyval in OPERATORS:
            date = self.date_get()
            if date:
                self.date_set(date + OPERATORS[event.keyval])
            self.stop_emission("key-press-event")
            return True
        return False

    def cal_open(self, *args):
        if not self.get_editable():
            return False
        parent = self.get_toplevel()
        dialog = gtk.Dialog(_('Date Selection'), parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_OK, gtk.RESPONSE_OK))
        dialog.set_has_separator(True)
        dialog.set_icon(TRYTON_ICON)
        dialog.set_default_response(gtk.RESPONSE_OK)

        calendar = gtk.Calendar()
        calendar.set_display_options(
            gtk.CALENDAR_SHOW_HEADING |
            gtk.CALENDAR_SHOW_DAY_NAMES |
            gtk.CALENDAR_SHOW_WEEK_NUMBERS |
            gtk.CALENDAR_WEEK_START_MONDAY)
        calendar.connect('day-selected-double-click',
            lambda *x: dialog.response(gtk.RESPONSE_OK))
        dialog.vbox.pack_start(calendar, expand=True, fill=True)

        date = self.date_get()
        if date:
            calendar.select_month(date.month - 1, date.year)
            calendar.select_day(date.day)
        else:
            date = datetime.datetime.now()

        x, y = self.window.get_origin()
        allocation = self.get_allocation()
        dialog.move(x, y + allocation.height)

        dialog.show_all()

        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            year, month, day = calendar.get_date()
            date += relativedelta(year=year, month=month + 1, day=day)
            self.date_set(date)

        parent.present()
        self.grab_focus()
        dialog.destroy()

if __name__ == '__main__':
    win = gtk.Window()
    win.set_title('DateEntry')

    def cb(window, event):
        gtk.main_quit()
    win.connect('delete-event', cb)
    vbox = gtk.VBox()
    win.add(vbox)

    for format in (
            '%d.%m.%Y %H:%M:%S',
            '%m/%d/%Y %H:%M:%S',
            '%d/%m/%Y %H:%M:%S',
            '%Y-%m-%d %H:%M%S',
            '%d.%m.%Y',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%Y-%m-%d',
            ):
        widget = DateEntry(format)
        vbox.pack_start(widget, False, False)

    win.show_all()
    gtk.main()
