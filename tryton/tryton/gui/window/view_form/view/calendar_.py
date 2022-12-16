# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from functools import wraps

import gtk
import datetime
import gettext

from tryton.common import node_attributes
from . import View
try:
    from .calendar_gtk.calendar_ import Calendar_
    from .calendar_gtk.toolbar import Toolbar
except ImportError:
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


class ViewCalendar(View):

    def __init__(self, screen, xml):
        super(ViewCalendar, self).__init__(screen, xml)
        self.view_type = 'calendar'
        self.editable = False
        self.widgets = {}
        self.widget = self.parse(xml)

    def parse(self, node):
        vbox = gtk.VBox()
        if not Calendar_:
            return vbox
        fields = []
        for node in node.childNodes:
            if node.nodeType != node.ELEMENT_NODE:
                continue
            if node.tagName == 'field':
                fields.append(node_attributes(node))
        goocalendar = Calendar_(attrs=self.attributes, screen=self.screen,
            fields=fields)
        toolbar = Toolbar(goocalendar)
        self.widgets['toolbar'] = toolbar
        goocalendar.connect('view-changed', self.on_view_changed, toolbar)
        goocalendar.connect('page-changed', self.on_page_changed, toolbar)
        goocalendar.connect('event-pressed', self.on_event_pressed)
        goocalendar.connect('event-activated', self.on_event_activated)
        goocalendar.connect('event-released', self.on_event_released)
        goocalendar.connect('day-pressed', self.on_day_pressed)
        goocalendar.connect('day-activated', self.on_day_activated)
        self.widgets['goocalendar'] = goocalendar
        scrolledWindow = gtk.ScrolledWindow()
        scrolledWindow.add_with_viewport(goocalendar)
        vbox.pack_start(toolbar, False, False)
        vbox.pack_start(scrolledWindow, True, True)
        return vbox

    def on_page_changed(self, goocalendar, day, toolbar):
        toolbar.update_displayed_date()
        if goocalendar.update_domain():
            self.screen.search_filter()

    def on_view_changed(self, goocalendar, view, toolbar):
        toolbar.update_displayed_date()
        if goocalendar.update_domain():
            self.screen.search_filter()

    def on_event_pressed(self, goocalendar, event):
        self.screen.current_record = event.record

    def on_event_activated(self, goocalendar, event):
        self.screen.switch_view('form')

    def on_event_released(self, goocalendar, event):
        dtstart = self.attributes.get('dtstart')
        dtend = self.attributes.get('dtend') or dtstart
        record = event.record
        group = record.group
        previous_start = record[dtstart].get(record)
        new_start = event.start
        new_end = event.end
        if not isinstance(previous_start, datetime.datetime):
            new_start = event.start.date()
            new_end = event.end.date() if event.end else None
        if previous_start <= new_start:
            if new_end:
                group.fields[dtend].set_client(record, new_end)
            group.fields[dtstart].set_client(record, new_start)
        else:
            group.fields[dtstart].set_client(record, new_start)
            if new_end:
                group.fields[dtend].set_client(record, new_end)
        goocalendar.select(new_start)
        record.save()

    def on_day_pressed(self, goocalendar, day):
        self.screen.current_record = None

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
        self.widgets['goocalendar'].display(self.screen.group)
        gtkcal = self.widgets['toolbar'].gtkcal
        if gtkcal and not gtkcal.is_drawable():
            import goocanvas
            # disable gtk.Calendar if it is not drawable anymore
            self.widgets['toolbar'].gtkcal_item.set_property('visibility',
                goocanvas.ITEM_INVISIBLE)
            self.widgets['toolbar'].current_page.set_active(False)

    def set_cursor(self, new=False, reset_view=True):
        pass

    def get_fields(self):
        return []
