# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from functools import wraps

import datetime
import gettext

from gi.repository import Gtk

from . import View, XMLViewParser
try:
    from .calendar_gtk.calendar_ import Calendar_
    from .calendar_gtk.toolbar import Toolbar
except ImportError as e:
    Calendar_ = None
    Toolbar = None

_ = gettext.gettext


def goocalendar_required(func):
    "Decorator for goocalendar required"
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if 'goocalendar' not in self.widgets:
            return
        return func(self, *args, **kwargs)
    return wrapper


class CalendarXMLViewParser(XMLViewParser):

    def __init__(self, view, exclude_field, field_attrs):
        super().__init__(view, exclude_field, field_attrs)
        self.calendar_fields = []

    def _parse_calendar(self, node, attributes):
        for child in node.childNodes:
            self.parse(child)
        goocalendar = Calendar_(
            self.view.attributes, self.view, self.calendar_fields)
        toolbar = Toolbar(goocalendar)
        self.view.scroll.add(goocalendar)
        self.view.widget.pack_start(
            toolbar, expand=False, fill=False, padding=0)
        self.view.widgets['goocalendar'] = goocalendar
        self.view.widgets['toolbar'] = toolbar

    def _parse_field(self, node, attributes):
        self.calendar_fields.append(attributes)


class ViewCalendar(View):
    editable = False
    view_type = 'calendar'
    xml_parser = CalendarXMLViewParser

    def __init__(self, view_id, screen, xml):
        self.widget = Gtk.VBox()

        if not Calendar_:
            self.widgets = {}
            return

        self.scroll = scrolledWindow = Gtk.ScrolledWindow()
        self.widget.pack_end(
            scrolledWindow, expand=True, fill=True, padding=0)

        super().__init__(view_id, screen, xml)

        goocalendar = self.widgets['goocalendar']
        toolbar = self.widgets['toolbar']
        goocalendar.connect('view-changed', self.on_view_changed, toolbar)
        goocalendar.connect('page-changed', self.on_page_changed, toolbar)
        goocalendar.connect('event-pressed', self.on_event_pressed)
        goocalendar.connect('event-activated', self.on_event_activated)
        goocalendar.connect('event-released', self.on_event_released)
        goocalendar.connect('day-pressed', self.on_day_pressed)
        goocalendar.connect('day-activated', self.on_day_activated)

    def on_page_changed(self, goocalendar, day, toolbar):
        toolbar.update_displayed_date()
        if goocalendar.update_domain():
            self.screen.search_filter()

    def on_view_changed(self, goocalendar, view, toolbar):
        toolbar.update_displayed_date()
        if goocalendar.update_domain():
            self.screen.search_filter()

    def on_event_pressed(self, goocalendar, event):
        self.record = event.record

    def on_event_activated(self, goocalendar, event):
        self.screen.switch_view('form')

    def on_event_released(self, goocalendar, event):
        dtstart = self.attributes['dtstart']
        dtend = self.attributes.get('dtend')
        record = event.record
        group = record.group
        previous_start = record[dtstart].get(record)
        new_start = event.start
        new_end = event.end
        if not isinstance(previous_start, datetime.datetime):
            new_start = event.start.date()
            new_end = event.end.date() if event.end else None
        if previous_start <= new_start:
            if dtend:
                group.fields[dtend].set_client(record, new_end)
            group.fields[dtstart].set_client(record, new_start)
        else:
            group.fields[dtstart].set_client(record, new_start)
            if dtend:
                group.fields[dtend].set_client(record, new_end)
        goocalendar.select(new_start)
        record.save()

    def on_day_pressed(self, goocalendar, day):
        self.record = None

    def on_day_activated(self, goocalendar, day):
        self.screen.new()

    def __getitem__(self, name):
        return None

    @goocalendar_required
    def destroy(self):
        self.widget.destroy()
        self.widgets['goocalendar'].destroy()

    @goocalendar_required
    def get_selected_date(self):
        return self.widgets['goocalendar'].selected_date

    @goocalendar_required
    def set_default_date(self, record, selected_date):
        self.widgets['goocalendar'].set_default_date(record, selected_date)

    def current_domain(self):
        if 'goocalendar' in self.widgets:
            return self.widgets['goocalendar'].current_domain()
        else:
            # No need to load any record as nothing will be shown
            return [('id', '=', -1)]

    def set_value(self):
        pass

    def reset(self):
        pass

    @goocalendar_required
    def display(self):
        self.widgets['goocalendar'].display(self.group)

    def set_cursor(self, new=False, reset_view=True):
        pass

    def get_fields(self):
        return []
