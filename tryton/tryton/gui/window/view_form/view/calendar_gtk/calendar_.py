# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import calendar
import datetime
import goocalendar
from dates_period import DatesPeriod


class Calendar_(goocalendar.Calendar):
    'Calendar'

    def __init__(self, attrs, screen, fields, event_store=None):
        super(Calendar_, self).__init__(
            event_store, attrs.get('mode', 'month'))
        self.attrs = attrs
        self.screen = screen
        self.fields = fields
        self.event_store = event_store
        self.current_domain_period = self.get_displayed_period()

    def set_default_date(self, record, selected_date):
        dtstart = self.attrs['dtstart']
        record[dtstart].set(record, datetime.datetime.combine(selected_date,
            datetime.time(0)))

    def get_displayed_period(self):
        cal = calendar.Calendar(self.firstweekday)
        if self.view == 'week':
            week = goocalendar.util.my_weekdatescalendar(cal,
                self.selected_date)
            first_date = week[0]
            last_date = week[6]
            last_date += datetime.timedelta(1)
        elif self.view == 'month':
            weeks = goocalendar.util.my_monthdatescalendar(cal,
                self.selected_date)
            first_date = weeks[0][0]
            last_date = weeks[5][6]
            last_date += datetime.timedelta(1)
        displayed_period = DatesPeriod(first_date, last_date)
        return displayed_period

    def update_domain(self):
        displayed_period = self.get_displayed_period()
        if not displayed_period.is_in(self.current_domain_period):
            self.current_domain_period = displayed_period
            return True
        return False

    def current_domain(self):
        first_datetime, last_datetime = \
            self.current_domain_period.get_dates(True)
        dtstart = self.attrs['dtstart']
        dtend = self.attrs.get('dtend') or dtstart
        domain = ['OR',
            ['AND', (dtstart, '>=', first_datetime),
                (dtstart, '<', last_datetime)],
            ['AND', (dtend, '>=', first_datetime),
                (dtend, '<', last_datetime)],
            ['AND', (dtstart, '<', first_datetime),
                (dtend, '>', last_datetime)]]
        return domain

    def get_colors(self, record):
        text_color = None
        if self.attrs.get('color'):
            text_color = record[self.attrs['color']].get(record)
        bg_color = 'lightblue'
        if self.attrs.get('background_color'):
            bg_color = record[self.attrs['background_color']].get(
                record)
        return text_color, bg_color

    def display(self, group):
        dtstart = self.attrs['dtstart']
        dtend = self.attrs.get('dtend')
        if self.screen.current_record:
            record = self.screen.current_record
            date = record[dtstart].get(record)
            if date:  # select the day of the current record
                self.select(date)

        if self._event_store:
            self._event_store.clear()
        else:
            event_store = goocalendar.EventStore()
            self.event_store = event_store

        for record in group:
            if not record[dtstart].get(record):
                continue

            start = record[dtstart].get_client(record)
            if dtend:
                end = record[dtend].get_client(record)
            else:
                end = None
            midnight = datetime.time(0)
            all_day = False
            if not isinstance(start, datetime.datetime):
                start = datetime.datetime.combine(start, midnight)
            if end and not isinstance(end, datetime.datetime):
                end = datetime.datetime.combine(end, midnight)
                all_day = True
            elif not end:
                all_day = True

            # Skip invalid event
            if end is not None and start > end:
                continue

            text_color, bg_color = self.get_colors(record)
            label = '\n'.join(record[attrs['name']].get_client(record)
                for attrs in self.fields).rstrip()
            event = goocalendar.Event(label, start, end, text_color=text_color,
                bg_color=bg_color, all_day=all_day)
            event.record = record
            self._event_store.add(event)

        self.grab_focus(self.get_root_item())
