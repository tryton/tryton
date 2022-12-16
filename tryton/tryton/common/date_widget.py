#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Date Widget"

import gobject
import pango
import gtk
import re

import time
import datetime
from dateutil.relativedelta import relativedelta
from datetime_strftime import datetime_strftime

mapping = {
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

class DateEntry(gtk.Entry):

    def __init__(self, format, callback=None, callback_process=None):
        super(DateEntry, self).__init__()
        self.modify_font(pango.FontDescription("monospace"))

        self.format = format
        self.regex = self.initial_value = format
        for key, val in mapping.items():
            self.regex = self.regex.replace(key, val[1])
            self.initial_value = self.initial_value.replace(key, val[0])

        self.regex = re.compile(self.regex)

        assert self.regex.match(self.initial_value), \
                'Error, the initial value should be validated by regex'
        self.set_width_chars(len(self.initial_value))
        self.set_max_length(len(self.initial_value))

        self.connect('key-press-event', self._on_key_press)
        self.connect('insert-text', self._on_insert_text)
        self.connect('delete-text', self._on_delete_text)

        self.connect('focus-in-event', self._focus_in)
        self.connect('focus-out-event', self._focus_out)
        self.callback = callback
        self.callback_process = callback_process

        self._interactive_input = True
        self.mode_cmd = False
        self.idle_set_position(0)

    def idle_set_position(self, value):
        def idle_func():
            with gtk.gdk.lock:
                self.set_position(value)
                return False
        gobject.idle_add(idle_func)

    def _on_insert_text(self, editable, value, length, position):
        if not self._interactive_input:
            return

        if self.mode_cmd:
            if self.callback: self.callback(value)
            self.stop_emission('insert-text')
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
        while (start > 0) and (self.initial_value[start] not in ['_', ' ','0','X']):
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
        if self.mode_cmd:
            self.mode_cmd = False
            if self.callback_process:
                self.callback_process(False, self, event)
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
                text = text[:a] + default[a] + text[a+1:]
        return text

    def test_date(self, text):
        default = datetime_strftime(datetime.datetime(2000, 1, 1),
                self.format)
        try:
            time.strptime(self.compute_date(text, default=default, year='2000'),
                    self.format)
        except ValueError:
            return False
        return True

    def date_get(self):
        res = None
        date = self.compute_date(self.get_text())
        try:
            res = datetime.datetime(*time.strptime(date, self.format)[:6])
        except ValueError:
            return None
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
        if event.keyval in (gtk.keysyms.Tab, gtk.keysyms.Escape,
                gtk.keysyms.Return, gtk.keysyms.KP_Enter):
            if self.mode_cmd:
                self.mode_cmd = False
                if self.callback_process:
                    self.callback_process(False, self, event)
                self.stop_emission("key-press-event")
                return True
            else:
                if self.get_text() != self.initial_value:
                    if not self.date_get():
                        self.stop_emission("key-press-event")
                        return True
        elif event.keyval in (gtk.keysyms.KP_Add, gtk.keysyms.plus,
                gtk.keysyms.KP_Subtract, gtk.keysyms.minus,
                gtk.keysyms.KP_Equal, gtk.keysyms.equal):
            self.mode_cmd = True
            self.date_get()
            if self.callback_process:
                self.callback_process(True, self, event)
            self.stop_emission("key-press-event")
            return True
        elif self.mode_cmd:
            if self.callback:
                self.callback(event)
            return True
        return False


class CmdEntry(gtk.Label):
    pass


class ComplexEntry(gtk.HBox):
    def __init__(self, format, *args, **argv):
        super(ComplexEntry, self).__init__(*args, **argv)
        self.widget = DateEntry(
            format,
            self._date_cb,
            self._process_cb
        )
        self.widget.set_position(0)
        self.widget.select_region(0, 0)
        self.widget_cmd = CmdEntry()
        self.widget_cmd.hide()
        self.pack_start(self.widget, expand=False, fill=False)
        self.pack_start(self.widget_cmd, expand=False, fill=True)

    def _date_cb(self, event):
        if event.keyval in (gtk.keysyms.BackSpace,):
            text = self.widget_cmd.get_text()[:-1]
            self.widget_cmd.set_text(text)
            return True
        text = self.widget_cmd.get_text()
        self.widget_cmd.set_text(text + event.string)
        return True

    def _process_cb(self, ok, widget, event=None):
        if ok:
            self.widget_cmd.show()
            self._date_cb(event)
        else:
            if hasattr(event, 'keyval') and not event.keyval == gtk.keysyms.Escape:
                cmd = self.widget_cmd.get_text()
                dt = self.widget.date_get() or datetime.datetime.now()
                res = compute_date(cmd, dt, self.widget.format)
                if res:
                    self.widget.date_set(res)
            self.widget_cmd.set_text('')
            self.widget_cmd.hide()

def compute_date(cmd, dt, format):
    lst = {
        '^=(\d+)d$': lambda dt, r: dt + \
                relativedelta(day=int(r.group(1))),
        '^=(\d+)m$': lambda dt, r: dt + \
                relativedelta(month=int(r.group(1))),
        '^=(\d\d)y$': lambda dt, r: dt + \
                relativedelta(year=int(str(dt.year)[:-2] + r.group(1))),
        '^=(\d+)y$': lambda dt, r: dt + \
                relativedelta(year=int(r.group(1))),
        '^=(\d+)h$': lambda dt, r: dt + \
                relativedelta(hour=int(r.group(1))),
        '^([\\+-]\d+)h$': lambda dt, r: dt + \
                relativedelta(hours=int(r.group(1))),
        '^([\\+-]\d+)w$': lambda dt, r: dt + \
                relativedelta(weeks=int(r.group(1))),
        '^([\\+-]\d+)d$': lambda dt, r: dt + \
                relativedelta(days=int(r.group(1))),
        '^([\\+-]\d+)$': lambda dt, r: dt + \
                relativedelta(days=int(r.group(1))),
        '^([\\+-]\d+)m$': lambda dt, r: dt + \
                relativedelta(months=int(r.group(1))),
        '^([\\+-]\d+)y$': lambda dt, r: dt + \
                relativedelta(years=int(r.group(1))),
        '^=$': lambda dt,r: datetime.datetime.now(),
        '^-$': lambda dt,r: False
    }
    for r, f in lst.items():
        groups = re.match(r, cmd)
        if groups:
            if not dt:
                dt = datetime.datetime.now()
            try:
                return f(dt, groups)
            except ValueError:
                continue

if __name__ == '__main__':
    win = gtk.Window()
    win.set_title('gtk.Entry subclass')
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
        widget = ComplexEntry(format)
        vbox.pack_start(widget, False, False)

    win.show_all()
    gtk.main()
