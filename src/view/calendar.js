/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.View.Calendar = Sao.class_(Sao.View, {
    /* Fullcalendar works with utc date, the default week start day depends on
       the user language, the events dates are handled by moment object. */
        init: function(screen, xml) {
            Sao.View.Calendar._super.init.call(this, screen, xml);
            // Used to check if the events are still processing
            this.processing = true;
            this.view_type = 'calendar';
            this.el = jQuery('<div/>', {
                'class': 'calendar'
            });
            var lang = Sao.i18n.getlang();
            lang = lang.slice(0, 2);
            var defaultview = 'month';
            if (this.attributes.mode == 'week') {
                defaultview = this.get_week_view();
            }
            this.el.fullCalendar({
                defaultView: defaultview,
                header: {
                    left:   'prev,next',
                    center: 'title',
                    right: ' month,' + this.get_week_view()
                },
                timeFormat: 'H:mm',
                events: this.get_events.bind(this),
                locale: lang,
                buttonIcons: false,
                eventRender: this.event_render.bind(this),
                eventResize: this.event_resize.bind(this),
                eventDrop: this.event_drop.bind(this),
                eventClick: this.event_click.bind(this),
                dayClick: this.day_click.bind(this),
            });
            this.fields = [];
            xml.find('calendar').children().each(function(pos, child){
                if (child.tagName == 'field') {
                    this.fields.push(child.attributes.name.value);
                }
            }.bind(this));
            this.el.fullCalendar('changeView', defaultview);
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
            var allDay = true;
            var description = [];
            for (var i = 1; i < this.fields.length; i++) {
                description.push(
                    this.screen.model.fields[this.fields[i]].get_client(
                        record));
            }
            description = description.join('\n');
            if (date_start) {
                if (date_end && date_end.isDateTime) {
                    allDay = false;
                } else if (date_end && !date_end.isSame(date_start)  &&
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
            if (this.screen.current_view.view_type != 'form') {
                var search_string = this.screen.screen_container.get_text();
                prm = this.screen.search_filter(search_string);
            }
            this.events =  [];
            var promisses = [];
            prm.then(function()  {
                this.screen.group.forEach(function(record) {
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
                    this.proccessing = false;
                });
            }.bind(this));
        },
        get_week_view: function() {
            if (this.screen.model.fields[this.attributes.dtstart]
                    .description.type == "datetime") {
                return 'agendaWeek';
            } else {
                return 'basicWeek';
            }
        },
        event_click: function(calEvent, jsEvent, view) {
            // Prevent opening the wrong event while the calendar event clicked
            // when loading
            if (!this.clicked_event) {
                this.clicked_event = true;
                this.screen.set_current_record(calEvent.record);
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
            element.append(event.description);
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
                this.date = date;
                this.screen.set_current_record(null);
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
            if (record.model.fields[dtstart].description.type == 'datetime') {
                selected_date = Sao.DateTime(selected_date.format()).utc();
            }
            record.field_set_client(dtstart, selected_date);
        },
    });

}());
