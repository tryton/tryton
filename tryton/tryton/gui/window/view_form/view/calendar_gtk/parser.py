#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
import gettext
import gtk
from tryton.gui.window.view_form.view.interface import ParserInterface
import tryton.common as common
try:
    from calendar_ import Calendar_
    from toolbar import Toolbar
except ImportError:
    Calendar_ = None
    Toolbar = None

_ = gettext.gettext


class ParserCalendar(ParserInterface):

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

    def on_event_released(self, goocalendar, event, attrs):
        dtstart = attrs.get('dtstart')
        dtend = attrs.get('dtend') or dtstart
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

    def parse(self, model, root_node, fields):
        attrs = common.node_attributes(root_node)
        self.title = attrs.get('string', 'Unknown')
        vbox = gtk.VBox()
        if not Calendar_:
            return vbox, {}, [], '', [], None
        goocalendar = Calendar_(attrs=attrs, model=model, root_node=root_node,
            fields=fields, screen=self.screen)
        toolbar = Toolbar(goocalendar)
        goocalendar.connect('view-changed', self.on_view_changed, toolbar)
        goocalendar.connect('page-changed', self.on_page_changed, toolbar)
        goocalendar.connect('event-pressed', self.on_event_pressed)
        goocalendar.connect('event-activated', self.on_event_activated)
        goocalendar.connect('event-released', self.on_event_released, attrs)
        goocalendar.connect('day-pressed', self.on_day_pressed)
        goocalendar.connect('day-activated', self.on_day_activated)
        scrolledWindow = gtk.ScrolledWindow()
        scrolledWindow.add_with_viewport(goocalendar)
        vbox.pack_start(toolbar, False, False)
        vbox.pack_start(scrolledWindow, True, True)
        return vbox, {'root': scrolledWindow, 'toolbar': toolbar,
            'goocalendar': goocalendar}, [], '', [], None
