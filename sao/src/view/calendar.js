/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.View.CalendarXMLViewParser = Sao.class_(Sao.View.XMLViewParser, {
        _parse_calendar: function(node, attributes) {
            [].forEach.call(node.childNodes, function(child) {
                this.parse(child);
            }.bind(this));

            var view_week;
            if (this.view.screen.model.fields[attributes.dtstart]
                .description.type == "datetime") {
                view_week = 'agendaWeek';
            } else {
                view_week = 'basicWeek';
            }
            var view_day;
            if (this.view.screen.model.fields[attributes.dtstart]
                    .description.type == "datetime") {
                view_day = 'agendaDay';
            } else {
                view_day =  'basicDay';
            }
            var defaultview = 'month';
            if (attributes.mode == 'week') {
                defaultview = view_week;
            }
            if (attributes.mode == 'day') {
                defaultview = view_day;
            }
            var header = {
                left: 'today prev,next',
                center: 'title',
                right: 'month,' + view_week + ',' + view_day,
            };
            if (Sao.i18n.rtl) {
                var header_rtl = jQuery.extend({}, header);
                header_rtl.left = header.right;
                header_rtl.right = header.left;
                header = header_rtl;
            }
            this.view.el.fullCalendar({
                defaultView: defaultview,
                header: header,
                timeFormat: 'H:mm',
                events: this.view.get_events.bind(this.view),
                locale: Sao.i18n.getlang().slice(0, 2),
                isRTL: Sao.i18n.rtl,
                themeSystem: 'bootstrap3',
                bootstrapGlyphicons: {
                    'prev': 'chevron-' + (Sao.i18n.rtl? 'right' : 'left'),
                    'next': 'chevron-' + (Sao.i18n.rtl? 'left' : 'right'),
                },
                buttonTextOverride: {
                    'today': Sao.i18n.gettext("Today"),
                    'month': Sao.i18n.gettext("Month"),
                    'week': Sao.i18n.gettext("Week"),
                    'day': Sao.i18n.gettext("Day"),
                },
                eventRender: this.view.event_render.bind(this.view),
                eventResize: this.view.event_resize.bind(this.view),
                eventDrop: this.view.event_drop.bind(this.view),
                eventClick: this.view.event_click.bind(this.view),
                dayClick: this.view.day_click.bind(this.view),
            });
        },
        _parse_field: function(node, attributes) {
            this.view.fields.push(attributes.name);
        },
    });

    Sao.View.Calendar = Sao.class_(Sao.View, {
    /* Fullcalendar works with utc date, the default week start day depends on
       the user language, the events dates are handled by moment object. */
        editable: false,
        view_type: 'calendar',
        xml_parser: Sao.View.CalendarXMLViewParser,
        init: function(view_id, screen, xml) {
            // Used to check if the events are still processing
            this.processing = true;
            this.fields = [];
            this.el = jQuery('<div/>', {
                'class': 'calendar'
            });
            Sao.View.Calendar._super.init.call(this, view_id, screen, xml);
            //this.el.fullCalendar('changeView', defaultview);
        },
        get_colors: function(record) {
            var colors = {};
            colors.text_color = 'black';
            if (this.attributes.color) {
                colors.text_color = record.field_get(
                    this.attributes.color);
            }
            colors.background_color = 'lightblue';
            if (this.attributes.background_color) {
                colors.background_color = record.field_get(
                    this.attributes.background_color);
            }
            return colors;
        },
        display: function() {
            this.el.fullCalendar('render');
            // Don't refetch events from server when get_events is processing
            if (!this.processing) {
                this.el.fullCalendar('refetchEvents');
            }
        },
        insert_event: function(record) {
            var title = this.screen.model.fields[this.fields[0]].get_client(
                record);
            var date_start = record.field_get_client(this.attributes.dtstart);
            var date_end = null;
            if (this.attributes.dtend) {
                date_end = record.field_get_client(this.attributes.dtend);
            }
            var description = [];
            for (var i = 1; i < this.fields.length; i++) {
                description.push(
                    this.screen.model.fields[this.fields[i]].get_client(
                        record));
            }
            description = description.join('\n');
            if (date_start) {
                var allDay = date_start.isDate &&
                    (!date_end || date_end.isDate);
                if (allDay && date_end && !date_end.isSame(date_start)  &&
                        this.screen.current_view.view_type == "calendar") {
                    // Add one day to allday event that last more than one day.
                    // http://github.com/fullcalendar/fullcalendar/issues/2909
                    date_end.add(1, 'day');
                }
                // Skip invalid event
                if (date_end && date_start > date_end) {
                    return;
                }
                var colors = this.get_colors(record);
                var values = {
                    title: title,
                    start: date_start,
                    end: date_end,
                    allDay: allDay,
                    editable: true,
                    color: colors.background_color,
                    textColor: colors.text_color,
                    record: record,
                    description: description
                };
                this.events.push(values);
            }
        },
        get_events: function(start, end, timezone, callback) {
            this.processing = true;
            this.start = Sao.DateTime(start.utc());
            this.end = Sao.DateTime(end.utc());
            var prm = jQuery.when();
            if (this.screen.current_view &&
                (this.screen.current_view.view_type != 'form')) {
                var search_string = this.screen.screen_container.get_text();
                prm = this.screen.search_filter(search_string);
            }
            this.events =  [];
            var promisses = [];
            prm.then(function()  {
                this.group.forEach(function(record) {
                    var record_promisses = [];
                    this.fields.forEach(function(name) {
                        record_promisses.push(record.load(name));
                    });
                    var prm = jQuery.when.apply(jQuery, record_promisses).then(
                        function(){
                            this.insert_event(record);
                        }.bind(this));
                    promisses.push(prm);
                }.bind(this));
                return jQuery.when.apply(jQuery, promisses).then(function() {
                    callback(this.events);
                }.bind(this)).always(function() {
                    this.processing = false;
                }.bind(this));
            }.bind(this));
        },
        event_click: function(calEvent, jsEvent, view) {
            // Prevent opening the wrong event while the calendar event clicked
            // when loading
            if (!this.clicked_event) {
                this.clicked_event = true;
                this.screen.current_record = calEvent.record;
                this.screen.switch_view().always(function(){
                    this.clicked_event = false;
                }.bind(this));
            }
        },
        event_drop: function(event, delta, revertFunc, jsEvent, ui, view) {
            var dtstart = this.attributes.dtstart;
            var dtend = this.attributes.dtend;
            var record = event.record;
            var group = record.group;
            var previous_start = record.field_get(dtstart);
            var previous_end = previous_start;
            if (dtend) {
                previous_end = record.field_get(dtend);
            }
            var new_start = event.start;
            var new_end = event.end;
            if (new_end == previous_start || !new_end) {
                new_end = new_start;
            }
            if (previous_start.isDateTime) {
                new_end = Sao.DateTime(new_end.format()).utc();
                new_start = Sao.DateTime(new_start.format()).utc();
            } else if (!previous_start.isSame(previous_end)) {
                // Remove the day that was added at the event end.
                new_end.subtract(1, 'day');
                this.el.fullCalendar('refetchEvents');
            }
            if (previous_start <= new_start) {
                if (dtend) {
                    record.field_set_client(dtend, new_end);
                }
                record.field_set_client(dtstart, new_start);
            } else {
                record.field_set_client(dtstart, new_start);
                if (dtend) {
                    record.field_set_client(dtend, new_end);
                }
            }
            record.save();
        },
        event_resize: function(event, delta, revertFunc, jsEvent, ui, view) {
            var dtend = this.attributes.dtend;
            var record = event.record;
            var group = record.group;
            var previous_end = record.field_get(dtend);
            var new_end = event.end;
            if (previous_end.isDateTime === true) {
                new_end = Sao.DateTime(new_end.format()).utc();
            } else {
                // Remove the day that was added at the event end.
                new_end.subtract(1, 'day');
                this.el.fullCalendar('refetchEvents');
            }
            if (new_end == previous_end || !new_end) {
                new_end = previous_end;
            }
            record.field_set_client(dtend, new_end);
            record.save();
        },
        event_render: function(event, element, view) {
            // The description field is added in the calendar events and the
            // event time is not shown in week view.
            if (this.screen.model.fields.date &&
                   this.screen.view_name == 'calendar') {
                element.find('.fc-time').remove();
            }
            element.find('.fc-content')
                .append(jQuery('<div/>', {'class': 'fc-description'})
                    .text(event.description));
            element.css('white-space', 'pre');
            var model_access = Sao.common.MODELACCESS.get(
            	this.screen.model_name);
            if (!model_access.write) {
                event.editable = false;
            }
        },
        day_click: function(date, jsEvent, view){
            var model_access = Sao.common.MODELACCESS.get(
                this.screen.model_name);
            if (model_access.create) {
                // Set the calendar date to the clicked date
                this.el.fullCalendar('gotoDate', date);
                this.screen.current_record = null;
                this.screen.new_();
            }
        },
        current_domain: function() {
            if (!this.start && !this.end) {
                return [['id', '=', -1]];
            }
            var first_datetime = Sao.DateTime(this.start);
            var last_datetime = Sao.DateTime(this.end);
            var dtstart = this.attributes.dtstart;
            var dtend = this.attributes.dtend || dtstart;
            return ['OR',
                    ['AND', [dtstart, '>=', first_datetime],
                        [dtstart,  '<',  last_datetime]],
                    ['AND', [dtend, '>=', first_datetime],
                        [dtend, '<', last_datetime]],
                    ['AND',  [dtstart, '<', first_datetime],
                        [dtend, '>', last_datetime]]];
        },
        get_displayed_period: function(){
            var DatesPeriod = [];
            if (this.start && this.end) {
                DatesPeriod.push(this.start, this.end);
            }
            return DatesPeriod;
        },
        set_default_date: function(record, selected_date){
            var dtstart = this.attributes.dtstart;
            var field = record.model.fields[dtstart];
            if (field instanceof Sao.field.DateTime) {
                selected_date = Sao.DateTime(selected_date);
            } else if (field instanceof Sao.field.Date) {
                selected_date = Sao.Date(selected_date);
            }
            field.set(record, selected_date);
            record.on_change([dtstart]);
            record.on_change_with([dtstart]);
        },
        get_selected_date: function(){
            return this.el.fullCalendar('getDate');
        }
    });

}());
