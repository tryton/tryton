# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext
import datetime

from gi.repository import Gdk, GObject, Gtk

from dateutil.relativedelta import relativedelta
from dateutil.parser import parse

from .common import IconFactory

__all__ = ['Date', 'CellRendererDate', 'Time', 'CellRendererTime', 'DateTime']

_ = gettext.gettext


def _fix_format(format_):
    if '%Y' in format_:
        if (datetime.date.min.strftime('%Y') != '0001'
                and datetime.date.min.strftime('%4Y') == '0001'):
            format_ = format_.replace('%Y', '%4Y')
    return format_


def date_parse(text, format_='%x'):
    try:
        return datetime.datetime.strptime(text, format_)
    except ValueError:
        pass
    formatted_date = datetime.date(1988, 7, 16).strftime(format_)
    try:
        dayfirst = formatted_date.index('16') == 0
    except ValueError:
        dayfirst = False
    try:
        monthfirst = formatted_date.index('7') <= 1
    except ValueError:
        monthfirst = False
    yearfirst = not dayfirst and not monthfirst
    return parse(text, dayfirst=dayfirst, yearfirst=yearfirst, ignoretz=True)


class Date(Gtk.Entry):
    __gtype_name__ = 'Date'
    __gproperties__ = {
        'value': (GObject.TYPE_PYOBJECT,
            _('Value'),
            _('Displayed value'),
            GObject.ParamFlags.READABLE | GObject.ParamFlags.WRITABLE),
        'format': (GObject.TYPE_STRING,
            '%x',
            _('Format'),
            _('Display format'),
            GObject.ParamFlags.READABLE | GObject.ParamFlags.WRITABLE),
        }
    __gsignals__ = {
        'date-changed': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            GObject.TYPE_NONE, ()),
        }

    def __init__(self):
        self.__date = None
        self.__format = '%x'

        Gtk.Entry.__init__(self)

        self.set_width_chars(20)

        self.connect('focus-out-event', self.focus_out)
        self.connect('activate', self.activate)

        # Calendar Popup
        self.set_icon_from_pixbuf(
            Gtk.EntryIconPosition.PRIMARY,
            IconFactory.get_pixbuf('tryton-date', Gtk.IconSize.MENU))
        self.set_icon_tooltip_text(
            Gtk.EntryIconPosition.PRIMARY,
            _('Open the calendar'))
        self.connect('icon-press', self.icon_press)

        self.__cal_popup = Gtk.Window(type=Gtk.WindowType.POPUP)
        self.__cal_popup.set_events(
            self.__cal_popup.get_events() | Gdk.EventMask.KEY_PRESS_MASK)
        self.__cal_popup.set_resizable(False)
        self.__cal_popup.connect('delete-event', self.cal_popup_closed)
        self.__cal_popup.connect('key-press-event', self.cal_popup_key_pressed)
        self.__cal_popup.connect('button-press-event',
            self.cal_popup_button_pressed)

        self.__calendar = Gtk.Calendar()
        cal_options = (
            Gtk.CalendarDisplayOptions.SHOW_DAY_NAMES
            | Gtk.CalendarDisplayOptions.SHOW_HEADING
            | Gtk.CalendarDisplayOptions.SHOW_WEEK_NUMBERS)
        self.__calendar.set_display_options(cal_options)
        self.__cal_popup.add(self.__calendar)
        self.__calendar.connect('day-selected', self.cal_popup_changed)
        self.__calendar.connect('day-selected-double-click',
            self.cal_popup_double_click)
        self.__calendar.show()

    def parse(self):
        text = self.get_text()
        date = None
        if text:
            try:
                date = date_parse(text, self.__format).date()
            except (ValueError, OverflowError):
                pass

        self.__date = date

    def update_label(self):
        if not self.__date:
            self.set_text('')
            return
        self.set_text(self.__date.strftime(self.__format))

    def icon_press(self, entry, icon_pos, event):
        self.grab_focus()
        if icon_pos == Gtk.EntryIconPosition.PRIMARY:
            self.cal_popup_open()

    def cal_popup_open(self):
        self.parse()
        if self.__date:
            self.__calendar.select_month(
                self.__date.month - 1, self.__date.year)
            self.__calendar.select_day(self.__date.day)
        self.__cal_popup.set_transient_for(self.get_toplevel())
        popup_position(self, self.__cal_popup)
        popup_show(self.__cal_popup)

    def cal_popup_changed(self, calendar):
        year, month, day = self.__calendar.get_date()
        self.__date = datetime.date(year, month + 1, day)

        self.update_label()

        self.emit('date-changed')

    def cal_popup_double_click(self, calendar):
        self.cal_popup_hide()

    def cal_popup_key_pressed(self, calendar, event):
        if event.keyval != Gdk.KEY_Escape:
            return False

        self.stop_emission_by_name('key-press-event')
        self.cal_popup_hide()
        return True

    def cal_popup_button_pressed(self, calendar, event):
        child = event.window
        window = calendar.get_window()
        if child != window:
            while child:
                if child == window:
                    return False
                child = child.get_parent()
        self.cal_popup_hide()
        return True

    def cal_popup_closed(self, popup):
        self.cal_popup_hide()
        return True

    def cal_popup_hide(self):
        popup_hide(self.__cal_popup)
        self.grab_focus()
        self.emit('date-changed')

    def cal_popup_is_visible(self):
        return self.__cal_popup.is_visible()

    def focus_out(self, entry, event):
        previous_date = self.__date
        self.parse()
        self.update_label()
        if self.__date != previous_date:
            self.emit('date-changed')
        return False

    def activate(self, entry=None):
        self.parse()
        self.update_label()
        self.emit('date-changed')
        return False

    def do_set_property(self, prop, value):
        if prop.name == 'value':
            if isinstance(value, str):
                self.set_text(value)
                self.parse()
                value = self.__date
            if value:
                if isinstance(value, datetime.datetime):
                    value = value.date()
                assert isinstance(value, datetime.date), value
            self.__date = value
            self.update_label()
            self.emit('date-changed')
        elif prop.name == 'format':
            self.__format = _fix_format(value)
            self.update_label()

    def do_get_property(self, prop):
        if prop.name == 'value':
            return self.__date
        elif prop.name == 'format':
            return self.__format


GObject.type_register(Date)


class CellRendererDate(Gtk.CellRendererText):
    __gproperties__ = {
        'format': (GObject.TYPE_STRING,
            _('Format'),
            _('Display format'),
            '%x',
            GObject.ParamFlags.READABLE | GObject.ParamFlags.WRITABLE),
        }

    def __init__(self):
        self.__format = '%x'
        self.__entry = None
        self.__focus_out_id = 0

        Gtk.CellRendererText.__init__(self)

    def do_set_property(self, prop, value):
        if prop.name == 'format':
            self.__format = _fix_format(value)
            return
        Gtk.CellRendererText.set_property(self, prop, value)

    def do_get_property(self, prop):
        if prop.name == 'format':
            return self.__format
        return Gtk.CellRendererText.get_property(self, prop)

    def do_start_editing(
            self, event, widget, path, background_area, cell_area, flags):
        if not self.props.editable:
            return
        self.__entry = add_operators(Date())  # TODO add_operators has option
        self.__entry.props.format = self.props.format
        self.__entry.props.value = self.props.text
        self.__entry.set_has_frame(False)
        self.__entry.connect('editing-done', self.__editing_done)
        self.__focus_out_id = self.__entry.connect(
            'focus-out-event', self.__focus_out_event)
        # XXX focus-out-event
        self.__entry.show()
        return self.__entry

    def __editing_done(self, entry):
        self.__entry = None
        if self.__focus_out_id:
            entry.disconnect(self.__focus_out_id)
        canceled = entry.props.editing_canceled
        self.stop_editing(canceled)
        if canceled:
            return
        # TODO emit edited

    def __focus_out_event(self, entry, event):
        if entry.cal_popup_is_visible():
            return True
        entry.props.editing_canceled = True
        entry.editing_done()
        entry.remove_widget()
        return False


GObject.type_register(CellRendererDate)


class Time(Gtk.ComboBox):
    __gtype_name__ = 'Time'
    __gproperties__ = {
        'value': (GObject.TYPE_PYOBJECT,
            _('Value'),
            _('Displayed value'),
            GObject.ParamFlags.READABLE | GObject.ParamFlags.WRITABLE),
        'format': (GObject.TYPE_STRING,
            _('Format'),
            _('Display format'),
            '%X',
            GObject.ParamFlags.READABLE | GObject.ParamFlags.WRITABLE),
        }
    __gsignals__ = {
        'time-changed': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            GObject.TYPE_NONE, ()),
        }

    def __init__(self):
        self.__time = None
        self.__format = '%X'

        Gtk.ComboBox.__init__(self, has_entry=True)

        self.__entry = self.get_child()
        self.__entry.set_width_chars(10)

        self.__entry.connect('focus-out-event', self.focus_out)
        self.__entry.connect('activate', self.activate)
        self.connect('changed', self.changed)

        self.__model = Gtk.ListStore(
            GObject.TYPE_STRING, GObject.TYPE_PYOBJECT)
        self.update_model()
        self.set_model(self.__model)
        self.set_entry_text_column(0)

    def parse(self):
        text = self.__entry.get_text()
        time = None
        if text:
            try:
                time = date_parse(text).time()
            except (ValueError, OverflowError):
                pass

        self.__time = time

    def update_label(self):
        if self.__time is None:
            self.__entry.set_text('')
            return

        self.__entry.set_text(self.__time.strftime(self.__format))

    def update_model(self):
        self.__model.clear()
        timelist_set_list(
            self.__model, datetime.time(0, 0), datetime.time(23, 59),
            self.__format)

    def focus_out(self, entry, event):
        self.parse()
        self.update_label()
        self.emit('time-changed')
        return False

    def activate(self, entry=None):
        self.parse()
        self.update_label()
        self.emit('time-changed')
        return False

    def changed(self, combobox):
        # "changed" signal is also triggered by text editing
        # so only parse when a row is active
        if combobox.get_active_iter():
            self.parse()
            self.update_label()
            self.emit('time-changed')
        return False

    def do_set_property(self, prop, value):
        if prop.name == 'value':
            if isinstance(value, str):
                self.__entry.set_text(value)
                self.parse()
                value = self.__time
            if value:
                if isinstance(value, datetime.datetime):
                    value = value.time()
            self.__time = value
            self.update_label()
            self.emit('time-changed')
        elif prop.name == 'format':
            self.__format = _fix_format(value)
            self.update_label()
            self.update_model()

    def do_get_property(self, prop):
        if prop.name == 'value':
            return self.__time
        elif prop.name == 'format':
            return self.__format


GObject.type_register(Time)


class CellRendererTime(Gtk.CellRendererCombo):
    __gproperties__ = {
        'format': (GObject.TYPE_STRING,
            '%X',
            _('Format'),
            _('Display format'),
            GObject.ParamFlags.READABLE | GObject.ParamFlags.WRITABLE),
        }

    def __init__(self):
        self.__format = '%X'
        self.__combo = None
        self.__focus_out_id = 0

        Gtk.CellRendererText.__init__(self)

    def do_set_property(self, prop, value):
        if prop.name == 'format':
            self.__format = _fix_format(value)
            return
        Gtk.CellRendererText.set_property(self, prop, value)

    def do_get_property(self, prop):
        if prop.name == 'format':
            return self.__format
        return Gtk.CellRendererText.get_property(self, prop)

    def do_start_editing(
            self, event, widget, path, background_area, cell_area, flags):
        if not self.props.editable:
            return
        self.__combo = add_operators(Time())  # TODO add_operators has option
        self.__combo.props.format = self.props.format
        self.__combo.props.value = self.props.text
        self.__combo.props.has_frame = False
        self.__combo.connect('editing-done', self.__editing_done)
        # TODO: connect to changed
        self.__focus_out_id = self.__combo.connect(
            'focus-out-event', self.__focus_out_event)
        self.__combo.show()
        return self.__combo

    def __editing_done(self, combo):
        self.__combo = None
        canceled = combo.props.editing_canceled
        self.stop_editing(canceled)
        if canceled:
            return
        # TODO emit edited

    def __focus_out_event(self, combo, event):
        self.__editing_done(combo)
        return False


GObject.type_register(CellRendererTime)


class DateTime(Gtk.HBox):
    __gtype_name__ = 'DateTime'
    __gproperties__ = {
        'value': (GObject.TYPE_PYOBJECT,
            _('Value'),
            _('Displayed value'),
            GObject.ParamFlags.READABLE | GObject.ParamFlags.WRITABLE),
        'date-format': (GObject.TYPE_STRING,
            '%x',
            _('Date Format'),
            _('Displayed date format'),
            GObject.ParamFlags.READABLE | GObject.ParamFlags.WRITABLE),
        'time-format': (GObject.TYPE_STRING,
            '%X',
            _('Date Format'),
            _('Displayed date format'),
            GObject.ParamFlags.READABLE | GObject.ParamFlags.WRITABLE),
        }
    __gsignals__ = {
        'datetime-changed': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            GObject.TYPE_NONE, ()),
        }

    def __init__(self):
        Gtk.HBox.__init__(self, spacing=4)

        self.__date = Date()
        self.pack_start(self.__date, expand=True, fill=True, padding=0)
        self.__date.show()
        self.__date.connect('date-changed',
            lambda e: self.emit('datetime-changed'))

        self.__time = Time()
        self.pack_start(self.__time, expand=True, fill=True, padding=0)
        self.__time.show()
        self.__time.connect('time-changed',
            lambda e: self.emit('datetime-changed'))

    def parse(self):
        self.__date.parse()
        self.__time.parse()

    def do_set_property(self, prop, value):
        if prop.name == 'value':
            self.__date.props.value = value
            self.__time.props.value = value
        elif prop.name == 'date-format':
            self.__date.props.format = value
        elif prop.name == 'time-format':
            self.__time.props.format = value

    def do_get_property(self, prop):
        if prop.name == 'value':
            date = self.__date.props.value
            time = self.__time.props.value or datetime.time()
            if date:
                return datetime.datetime.combine(date, time)
            else:
                return
        elif prop.name == 'date-format':
            return self.__date.props.format
        elif prop.name == 'time-format':
            return self.__time.props.format

    def modify_bg(self, state, color):
        self.__date.modify_bg(state, color)
        self.__time.child.modify_bg(state, color)

    def modify_base(self, state, color):
        self.__date.modify_base(state, color)
        self.__time.child.modify_base(state, color)

    def modify_fg(self, state, color):
        self.__date.modify_fg(state, color)
        self.__time.child.modify_fg(state, color)

    def modify_text(self, state, color):
        self.__date.modify_text(state, color)
        self.__time.child.modify_text(state, color)


GObject.type_register(DateTime)


def popup_position(widget, popup):
    allocation = widget.get_allocation()
    x, y = widget.get_window().get_root_coords(allocation.x, allocation.y)
    popup.move(x, y + allocation.height)


def popup_show(popup):
    popup.show()
    popup.grab_focus()
    popup.grab_add()

    window = popup.get_window()
    display = window.get_display()
    seat = display.get_default_seat()
    seat.grab(window, Gdk.SeatCapabilities.ALL, True, None, None, None, None)


def popup_hide(popup):
    popup.hide()
    popup.grab_remove()
    window = popup.get_window()
    display = window.get_display()
    seat = display.get_default_seat()
    seat.ungrab()


def timelist_set_list(model, min_, max_, format_):
    time = min_
    delta = 30
    while time < max_:
        model.append((time.strftime(format_), time))
        hour = time.hour
        minute = time.minute + delta
        hour, minute = divmod(minute, 60)
        hour += time.hour
        if hour >= 24:
            break
        time = datetime.time(hour, minute)


def add_operators(widget):
    def key_press(editable, event):
        if not editable.get_editable():
            return False
        if event.keyval in OPERATORS:
            value = widget.props.value
            if value:
                if isinstance(value, datetime.time):
                    value = datetime.datetime.combine(
                        datetime.date.today(), value)
                try:
                    widget.props.value = value + OPERATORS[event.keyval]
                except TypeError:
                    return False
            return True
        elif event.keyval in (Gdk.KEY_KP_Equal, Gdk.KEY_equal):
            widget.props.value = datetime.datetime.now()
            return True
        return False

    if isinstance(widget, DateTime):
        for child in widget.get_children():
            add_operators(child)
        return widget
    if isinstance(widget, Gtk.ComboBox):
        editable = widget.get_child()
    else:
        editable = widget
    editable.connect('key-press-event', key_press)
    return widget


OPERATORS = {
    Gdk.KEY_S: relativedelta(seconds=-1),
    Gdk.KEY_s: relativedelta(seconds=1),
    Gdk.KEY_I: relativedelta(minutes=-1),
    Gdk.KEY_i: relativedelta(minutes=1),
    Gdk.KEY_H: relativedelta(hours=-1),
    Gdk.KEY_h: relativedelta(hours=1),
    Gdk.KEY_D: relativedelta(days=-1),
    Gdk.KEY_d: relativedelta(days=1),
    Gdk.KEY_W: relativedelta(weeks=-1),
    Gdk.KEY_w: relativedelta(weeks=1),
    Gdk.KEY_M: relativedelta(months=-1),
    Gdk.KEY_m: relativedelta(months=1),
    Gdk.KEY_Y: relativedelta(years=-1),
    Gdk.KEY_y: relativedelta(years=1),
    }

if __name__ == '__main__':
    win = Gtk.Window()
    win.connect('delete-event', Gtk.main_quit)

    v = Gtk.VBox()
    v.show()

    d = add_operators(Date())
    d.show()
    v.pack_start(d, expand=False, fill=False, padding=0)

    t = add_operators(Time())
    t.show()
    v.pack_start(t, expand=False, fill=False, padding=0)

    t = add_operators(Time())
    t.props.format = '%H:%M'
    t.show()
    v.pack_start(t, expand=False, fill=False, padding=0)

    dt = add_operators(DateTime())
    dt.show()
    v.pack_start(dt, expand=False, fill=False, padding=0)

    win.add(v)
    win.show()

    Gtk.main()
