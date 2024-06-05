/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    function set_calendar_height(el) {
        var height = window.innerHeight - 15;
        if (el.parents('.modal-body').length) {
            var modal_height = parseInt(
                el.parents('.modal-body').css('max-height'), 10);
            if (isNaN(modal_height)) {
                height -= 200;
            } else {
                height = modal_height;
            }
        }
        height -= el.find('.fc-toolbar').height();
        el.parents('.panel-body').each(function(i, panel) {
            panel = jQuery(panel);
            height -= parseInt(panel.css('padding-top'), 10);
            height -= parseInt(panel.css('padding-bottom'), 10);
        });
        el.parents('.panel').each(function(i, panel) {
            panel = jQuery(panel);
            var lengths = panel.css('box-shadow').match(/\d+px/g);
            if (lengths && lengths.length) {
                lengths = lengths.map(function(length) {
                    length = parseInt(length, 10);
                    return isNaN(length) ? 0 : length;
                });
                height -= Math.max.apply(null, lengths);
            }
        });
        height -= el[0].getBoundingClientRect().y;
        el.fullCalendar('option', 'contentHeight', height);
    }

    jQuery(window).resize(function() {
        jQuery('.calendar').each(function(i, el) {
            set_calendar_height(jQuery(el));
        });
    });

    Sao.View.CalendarXMLViewParser = Sao.class_(Sao.View.XMLViewParser, {
        _parse_calendar: function(node, attributes) {
            for (const child of node.childNodes) {
                this.parse(child);
            }

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
                scrollTime: (
                    this.view.screen.context.calendar_scroll_time ||
                    Sao.Time(6)).toString(),
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

            if (attributes.height !== undefined) {
                this.view.el.css('min-height', attributes.height + 'px');
            }
            if (attributes.width !== undefined) {
                this.view.el.css('min-width', attributes.width + 'px');
            }
        },
        _parse_field: function(node, attributes) {
            this.view.fields.push(attributes.name);
        },
    });

    Sao.View.Calendar = Sao.class_(Sao.View, {
    /* Fullcalendar works with utc date, the default week start day depends on
       the user language, the events dates are handled by moment object. */
        editable: false,
        creatable: false,
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
            colors.text_color = Sao.config.calendar_colors[0];
            if (this.attributes.color) {
                colors.text_color = record.field_get(
                    this.attributes.color);
            }
            colors.background_color = Sao.config.calendar_colors[1];
            if (this.attributes.background_color) {
                colors.background_color = record.field_get(
                    this.attributes.background_color);
            }
            return colors;
        },
        display: function() {
            this.el.fullCalendar('render');
            set_calendar_height(this.el);
            // Don't refetch events from server when get_events is processing
            if (!this.processing) {
                this.el.fullCalendar('refetchEvents');
            }
        },
        insert_event: function(record) {
            var description_fields = jQuery.extend([], this.fields);
            var title_field = description_fields.shift();
            var title = this.screen.model.fields[title_field].get_client(
                record);
            var field_start = record.model.fields[this.attributes.dtstart];
            var date_start = field_start.get_client(record);
            field_start.set_state(record);
            var date_end = null;
            var field_end;
            if (this.attributes.dtend) {
                field_end = record.model.fields[this.attributes.dtend];
                date_end = field_end.get_client(record);
                field_end.set_state(record);
            }

            var model_access = Sao.common.MODELACCESS.get(
                this.screen.model_name);
            var editable = (
                parseInt(this.attributes.editable || 1, 10) &&
                model_access.write);

            var description = [];
            for (const field of description_fields) {
                description.push(
                    this.screen.model.fields[field].get_client( record));
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
                var event_editable = (
                    editable &&
                    !field_start.get_state_attrs(record).readonly &&
                    (!date_end || !field_end.get_state_attrs(record).readonly));
                var colors = this.get_colors(record);
                var values = {
                    title: title,
                    start: date_start,
                    end: date_end,
                    allDay: allDay,
                    editable: event_editable,
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
            prm.then(() => {
                this.group.forEach(record => {
                    var record_promisses = [];
                    for (const name of this.fields) {
                        record_promisses.push(record.load(name));
                    }
                    var prm = jQuery.when.apply(jQuery, record_promisses).then(
                        () => {
                            this.insert_event(record);
                        });
                    promisses.push(prm);
                });
                return jQuery.when.apply(jQuery, promisses).then(() => {
                    callback(this.events);
                }).always(() => {
                    this.processing = false;
                });
            });
        },
        event_click: function(calEvent, jsEvent, view) {
            // Prevent opening the wrong event while the calendar event clicked
            // when loading
            if (!this.clicked_event) {
                this.clicked_event = true;
                this.screen.current_record = calEvent.record;
                this.screen.switch_view().always(() => {
                    this.clicked_event = false;
                });
            }
        },
        event_drop: function(event, delta, revertFunc, jsEvent, ui, view) {
            var dtstart = this.attributes.dtstart;
            var dtend = this.attributes.dtend;
            var record = event.record;
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
            element.css('white-space', 'pre')
                .css('overflow', 'hidden')
                .css('text-overflow', 'ellipsis')
                .attr('title', [event.title, event.description]
                    .filter(function(e) {
                        return e;
                    }).join('\n'));
        },
        day_click: function(date, jsEvent, view){
            var model_access = Sao.common.MODELACCESS.get(
                this.screen.model_name);
            if (parseInt(this.attributes.editable || 1, 10) &&
                model_access.create) {
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
            var start = Sao.DateTime(this.start);
            var end = Sao.DateTime(this.end);
            var dtstart = this.attributes.dtstart;
            var dtend = this.attributes.dtend || dtstart;
            var fields = this.screen.model.fields;
            if (fields[dtstart].description.type == 'date') {
                start = start.todate();
            }
            if (fields[dtend].description.type == 'date') {
                end = end.todate();
            }
            return [
                [dtstart, '!=', null],
                [dtend, '!=', null],
                ['OR',
                    ['AND', [dtstart, '>=', start], [dtstart,  '<', end]],
                    ['AND', [dtend, '>=', start], [dtend, '<', end]],
                    ['AND',  [dtstart, '<', start], [dtend, '>', end]],
                ],
            ];
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
        },
        get listed_records() {
            return this.events.map(e => e.record);
        },
    });

}());
