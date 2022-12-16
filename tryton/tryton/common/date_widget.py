#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Date Widget"
import gobject
import pango
import gtk
import re

import time
from mx.DateTime import RelativeDateTime
from mx.DateTime import DateTime
from mx.DateTime import now
import mx.DateTime

mapping = {
    '%y': ('__', '([_ 0-9][_ 0-9])'),
    '%Y': ('____', '([_ 0-9][_ 0-9][_ 0-9][_ 0-9])'),
    '%m': ('__', '([_ 0][_ 0-9]|[_ 1][_ 0-2])'),
    '%d': ('__', '([_ 0][_ 0-9]|[_ 1-2][_ 0-9]|[_ 3][_ 0-1])'),
    '%H': ('__', '([_ 0-1][_ 0-9]|[_ 2][_ 0-4])'),
    '%I': ('__', '([_ 0][_ 0-9]|[_ 1][_ 0-2])'),
    '%M': ('__', '([_ 0-5][_ 0-9]|[_ 6][_ 0])'),
    '%S': ('__', '([_ 0-5][_ 0-9]|[_ 6][_ 0])'),
    '%p': ('__', '([_ AP][_ M])'),
}

class DateEntry(gtk.Entry):

    def __init__(self, format, callback=None, callback_process=None):
        super(DateEntry, self).__init__()
        self.modify_font(pango.FontDescription("monospace"))

        self.format = format
        self.regex = self.initial_value = format
        for key,val in mapping.items():
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
        gobject.idle_add(self.set_position, 0)

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

        if self.regex.match(text):
            self.set_text(text)
            gobject.idle_add(self.set_position, pos)
        else:
            text = text[:pos] + '0' + text[pos + 1:]
            if self.regex.match(text):
                self.set_text(text)
                gobject.idle_add(self.set_position, pos)
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
        gobject.idle_add(self.set_position, start)
        self.stop_emission('delete-text')
        return

    def _focus_in(self, editable, event):
        if not self.get_text():
            self.set_text(self.initial_value)

    def _focus_out(self, editable, event):
        self.date_get()
        if self.mode_cmd:
            self.mode_cmd = False
            if self.callback_process: self.callback_process(False, self, event)
        if self.get_text() == self.initial_value:
            self.set_text('')

    def set_text(self, text):
        self._interactive_input = False
        try:
            gtk.Entry.set_text(self, text)
        finally:
            self._interactive_input = True

    def date_set(self, dt):
        if dt:
            format = self.format
            if dt.year < 10:
                format = format.replace('%Y', '000%Y')
            elif dt.year < 100:
                format = format.replace('%Y', '00%Y')
            elif dt.year < 1000:
                format = format.replace('%Y', '0%Y')
            self.set_text(dt.strftime(format))
        else:
            if self.is_focus():
                self.set_text(self.initial_value)
            else:
                self.set_text('')

    def date_get(self):
        tt = time.strftime(self.format, time.localtime())
        tc = self.get_text()
        if tc == self.initial_value or not tc:
            return False

        match = self.regex.match(tc)
        for i in range(len(match.groups())):
            val = match.group(i + 1)
            n = len(val)
            val = val.strip()
            val = val.strip('_')
            val = val.lstrip('0')
            if not val:
                continue
            fchar = '0'
            if n == 4:
                fchar = '_'
            val = (fchar * (n - len(val))) + val
            start = match.start(i + 1)
            end = match.end(i + 1)
            tc = tc[:start] + val + tc[end:]

        for a in range(len(self.initial_value)):
            if self.initial_value[a] == tc[a]:
                tc = tc[:a] + tt[a] + tc[a+1:]
        try:
            self.set_text(tc)
            return mx.DateTime.strptime(tc, self.format)
        except:
            tc = tt
        self.set_text(tc)
        return mx.DateTime.strptime(tc, self.format)

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
                self.date_get()
                if self.get_text() == self.initial_value:
                    self.set_text('')
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
        self.pack_start(self.widget, expand=True, fill=True)
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
                dt = self.widget.date_get()
                res = compute_date(cmd, dt, self.widget.format)
                if res:
                    self.widget.date_set(res)
            self.widget_cmd.set_text('')
            self.widget_cmd.hide()

def compute_date(cmd, dt, format):
    lst = {
        '^=(\d+)d$': lambda dt, r: dt + \
                RelativeDateTime(day=int(r.group(1))),
        '^=(\d+)m$': lambda dt, r: dt + \
                RelativeDateTime(month=int(r.group(1))),
        '^=(\d\d)y$': lambda dt, r: dt + \
                RelativeDateTime(year=int(str(dt.year)[:-2] + r.group(1))),
        '^=(\d+)y$': lambda dt, r: dt + \
                RelativeDateTime(year=int(r.group(1))),
        '^=(\d+)h$': lambda dt, r: dt + \
                RelativeDateTime(hour=int(r.group(1))),
        '^([\\+-]\d+)h$': lambda dt, r: dt + \
                RelativeDateTime(hours=int(r.group(1))),
        '^([\\+-]\d+)w$': lambda dt, r: dt + \
                RelativeDateTime(weeks=int(r.group(1))),
        '^([\\+-]\d+)d$': lambda dt, r: dt + \
                RelativeDateTime(days=int(r.group(1))),
        '^([\\+-]\d+)$': lambda dt, r: dt + \
                RelativeDateTime(days=int(r.group(1))),
        '^([\\+-]\d+)m$': lambda dt, r: dt + \
                RelativeDateTime(months=int(r.group(1))),
        '^([\\+-]\d+)y$': lambda dt, r: dt + \
                RelativeDateTime(years=int(r.group(1))),
        '^=$': lambda dt,r: now(),
        '^-$': lambda dt,r: False
    }
    for r, f in lst.items():
        groups = re.match(r, cmd)
        if groups:
            if not dt:
                dt = time.strftime(format, time.localtime())
                dt = mx.DateTime.strptime(dt, format)
            try:
                return f(dt, groups)
            except:
                continue

if __name__ == '__main__':
    import sys

    def main(args):
        win = gtk.Window()
        win.set_title('gtk.Entry subclass')
        def cb(window, event):
            gtk.main_quit()
        win.connect('delete-event', cb)

        widget = ComplexEntry('%d/%m/%Y %H:%M:%S')
        win.add(widget)

        win.show_all()
        gtk.main()

    sys.exit(main(sys.argv))
