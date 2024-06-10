/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.ScreenContainer = Sao.class_(Object, {
        init: function(tab_domain) {
            this.alternate_viewport = jQuery('<div/>', {
                'class': 'screen-container'
            });
            this.alternate_view = false;
            this.search_modal = null;
            this.search_form = null;
            this.last_search_text = '';
            this.tab_domain = tab_domain || [];
            this.tab_counter = [];
            this.el = jQuery('<div/>', {
                'class': 'screen-container'
            });
            this.filter_box = jQuery('<form/>', {
                'class': 'filter-box hidden-xs'
            }).submit(e => {
                e.preventDefault();
                this.do_search();
            });
            var search_row = jQuery('<div/>', {
                'class': 'row'
            }).appendTo(this.filter_box);
            this.el.append(this.filter_box);
            this.filter_button = jQuery('<button/>', {
                type: 'button',
                'class': 'btn btn-link',
                'title': Sao.i18n.gettext("Filters"),
            }).text(Sao.i18n.gettext('Filters'));
            this.filter_button.click(this.search_box.bind(this));
            this.search_entry = jQuery('<input/>', {
                'class': 'form-control mousetrap',
                'placeholder': Sao.i18n.gettext('Search'),
                // workaround for
                // https://bugzilla.mozilla.org/show_bug.cgi?id=1474137
                'autocomplete': 'off',
            });
            this.search_list = jQuery('<datalist/>');
            this.search_list.uniqueId();
            this.search_entry.attr('list', this.search_list.attr('id'));
            this.search_entry.on('input', this.update.bind(this));

            var but_clear = jQuery('<button/>', {
                'type': 'button',
                'class': 'btn btn-default hidden-md hidden-lg',
                'aria-label': Sao.i18n.gettext("Clear Search"),
                'title': Sao.i18n.gettext("Clear Search"),
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-clear'));
            but_clear.hide();
            but_clear.click(() => {
                this.search_entry.val('').change();
                this.do_search();
            });

            this.search_entry.on('keyup change', () => {
                if (this.search_entry.val()) {
                    but_clear.show();
                } else {
                    but_clear.hide();
                }
                this.bookmark_match();
            });

            var but_submit = jQuery('<button/>', {
                'type': 'submit',
                'class': 'btn btn-default',
                'aria-label': Sao.i18n.gettext("Search"),
                'title': Sao.i18n.gettext("Search"),
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-search'));

            this.but_active = jQuery('<button/>', {
                type: 'button',
                'class': 'btn btn-default hidden-xs',
                'aria-expanded': false,
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-archive', {
                'aria-hidden': true,
            }));
            this._set_active_tooltip();
            this.but_active.click(this.search_active.bind(this));

            this.but_bookmark = jQuery('<button/>', {
                type: 'button',
                'class': 'btn btn-default dropdown-toggle',
                'data-toggle': 'dropdown',
                'aria-expanded': false,
                'aria-label': Sao.i18n.gettext("Bookmarks"),
                'title': Sao.i18n.gettext("Bookmarks"),
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-bookmark', {
                'aria-hidden': true,
            })).uniqueId();
            var dropdown_bookmark = jQuery('<ul/>', {
                'class': 'dropdown-menu dropdown-menu-right',
                'role': 'menu',
                'aria-labelledby': this.but_bookmark.attr('id'),
            });
            this.but_bookmark.click(() => {
                dropdown_bookmark.empty();
                var bookmarks = this.bookmarks();
                for (const bookmark of bookmarks) {
                    const name = bookmark[1];
                    const domain = bookmark[2];
                    jQuery('<li/>', {
                        'role': 'presentation'
                    })
                    .append(jQuery('<a/>', {
                        'role': 'menuitem',
                        'href': '#',
                        'tabindex': -1
                    }).text(name)
                        .click(domain, this.bookmark_activate.bind(this)))
                    .appendTo(dropdown_bookmark);
                }
            });
            this.but_star = jQuery('<button/>', {
                'class': 'btn btn-default hidden-xs',
                'type': 'button'
            }).append(jQuery('<img/>', {
                'class': 'icon',
                'aria-hidden': true
            }).data('star', false)).click(this.star_click.bind(this));
            this.set_star();

            jQuery('<div/>', {
                'class': 'input-group input-group-sm'
            })
            .append(jQuery('<span/>', {
                'class': 'input-group-btn'
            }).append(this.filter_button))
            .append(this.search_entry)
            .append(this.search_list)
            .append(jQuery('<span/>', {
                'class': 'input-group-btn'
            }).append(but_clear)
                .append(but_submit)
                .append(this.but_star)
                .append(this.but_bookmark)
                .append(dropdown_bookmark)
                .append(this.but_active))
            .appendTo(jQuery('<div/>', {
                'class': 'col-sm-10 col-xs-12'
            }).appendTo(search_row));


            this.but_prev = jQuery('<button/>', {
                type: 'button',
                'class': 'btn btn-default btn-sm',
                'aria-label': Sao.i18n.gettext("Previous"),
                'title': Sao.i18n.gettext("Previous"),
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-back', {
                'aria-hidden': true,
            }));
            this.but_prev.click(this.search_prev.bind(this));
            this.but_next = jQuery('<button/>', {
                type: 'button',
                'class': 'btn btn-default btn-sm',
                'aria-label': Sao.i18n.gettext("Next"),
                'title': Sao.i18n.gettext("Next"),
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-forward', {
                'aria-hidden': true,
            }));
            this.but_next.click(this.search_next.bind(this));

            jQuery('<div/>', {
                'class': 'btn-group',
                role: 'group',
            })
            .append(this.but_prev)
            .append(this.but_next)
            .appendTo(jQuery('<div/>', {
                'class': 'col-sm-2 pull-right'
            }).appendTo(search_row));

            this.content_box = jQuery('<div/>', {
                'class': 'content-box'
            });

            if (!jQuery.isEmptyObject(this.tab_domain)) {
                this.tab = jQuery('<div/>', {
                    'class': 'tab-domain'
                }).appendTo(this.el);
                var nav = jQuery('<ul/>', {
                    'class': 'nav nav-tabs',
                    role: 'tablist'
                }).appendTo(this.tab);
                jQuery('<div/>', {
                    'class': 'tab-content'
                }).appendTo(this.tab);
                this.tab_domain.forEach((tab_domain, i) => {
                    var name = tab_domain[0];
                    var counter = jQuery('<span/>', {
                        'class': 'badge badge-empty'
                    }).html('&nbsp;');
                    counter.css('visibility', 'hidden');
                    jQuery('<li/>', {
                        role: 'presentation',
                        id: 'nav-' + i
                    }).append(jQuery('<a/>', {
                        'aria-controls':  i,
                        role: 'tab',
                        'data-toggle': 'tab',
                        'href': '#' + i
                    }).text(name + ' ').append(counter)).appendTo(nav);
                    this.tab_counter.push(counter);
                });
                nav.find('a:first').tab('show');
                var self = this;
                nav.find('a').click(function(e) {
                    e.preventDefault();
                    jQuery(this).tab('show');
                    self.do_search();
                    self.screen.count_tab_domain(true);
                });
            } else {
                this.tab = null;
            }
            this.el.append(this.content_box);
        },
        set_text: function(value) {
            this.search_entry.val(value);
            this.bookmark_match();
        },
        update: function() {
            var completions = this.screen.domain_parser.completion(
                    this.get_text());
            this.search_list.empty();
            for (const e of completions) {
                jQuery('<option/>', {
                    'value': e.trim()
                }).appendTo(this.search_list);
            }
        },
        set_star: function(star) {
            var img = this.but_star.children('img');
            var title, icon;
            if (star) {
                icon = 'tryton-star';
                title = Sao.i18n.gettext("Remove this bookmark");
            } else {
                icon = 'tryton-star-border';
                title = Sao.i18n.gettext('Bookmark this filter');
            }
            this.but_star.data('star', Boolean(star));
            this.but_star.attr('title', title);
            this.but_star.attr('aria-label', title);
            Sao.common.ICONFACTORY.get_icon_url(icon).then(function(url) {
                img.attr('src', url);
            });
        },
        get_star: function() {
            return this.but_star.data('star');
        },
        star_click: function() {
            var star = this.get_star();
            var model_name = this.screen.model_name;
            const refresh = () => {
                this.bookmark_match();
                this.but_bookmark.prop('disabled',
                        jQuery.isEmptyObject(this.bookmarks()));
            };
            if (!star) {
                var text = this.get_text();
                if (!text) {
                    return;
                }
                Sao.common.ask.run(Sao.i18n.gettext('Bookmark Name:'), 'bookmark')
                    .then(name => {
                        if (!name) {
                            return;
                        }
                        var domain = this.screen.domain_parser.parse(text);
                        Sao.common.VIEW_SEARCH.add(model_name, name, domain)
                        .then(function() {
                            refresh();
                        });
                        this.set_text(
                            this.screen.domain_parser.string(domain));
                    });
            } else {
                var id = this.bookmark_match();
                Sao.common.VIEW_SEARCH.remove(model_name, id).then(function() {
                    refresh();
                });
            }
        },
        bookmarks: function() {
            var searches = Sao.common.VIEW_SEARCH.get(this.screen.model_name);
            return searches.filter(
                search => this.screen.domain_parser.stringable(search[2]));
        },
        bookmark_activate: function(e) {
            e.preventDefault();
            var domain = e.data;
            this.set_text(this.screen.domain_parser.string(domain));
            this.do_search();
        },
        bookmark_match: function() {
            var current_text = this.get_text();
            if (current_text) {
                var current_domain = this.screen.domain_parser.parse(
                        current_text);
                var bookmarks = this.bookmarks();
                for (const bookmark of bookmarks) {
                    const id = bookmark[0];
                    const domain = bookmark[2];
                    const access = bookmark[3];
                    const text = this.screen.domain_parser.string(domain);
                    if ((text === current_text) ||
                            (Sao.common.compare(domain, current_domain))) {
                        this.set_star(true);
                        this.but_star.prop('disabled', !access);
                        return id;
                    }
                }
                this.but_star.prop('disabled', !current_text);
            }
            this.set_star(false);
        },
        search_prev: function() {
            this.screen.search_prev(this.get_text());
        },
        search_next: function() {
            this.screen.search_next(this.get_text());
        },
        search_active: function() {
            this.but_active.toggleClass('active');
            this._set_active_tooltip();
            this.screen.search_filter(this.get_text());
        },
        _set_active_tooltip: function() {
            var tooltip;
            if (this.but_active.hasClass('active')) {
                tooltip = Sao.i18n.gettext('Show active records');
            } else {
                tooltip = Sao.i18n.gettext('Show inactive records');
            }
            this.but_active.attr('aria-label', tooltip);
            this.but_active.attr('title', tooltip);
        },
        get_tab_index: function() {
            if (!this.tab) {
                return -1;
            }
            return this.tab.find('li').index(this.tab.find('li.active'));
        },
        get_tab_domain: function() {
            if (!this.tab) {
                return [];
            }
            var idx = this.get_tab_index();
            if (idx < 0) {
                return [];
            }
            return this.tab_domain[idx][1];
        },
        set_tab_counter: function(count, idx=null) {
            if (jQuery.isEmptyObject(this.tab_counter) || !this.tab) {
                return;
            }
            if (idx === null) {
                idx = this.tab.find('li').index(this.tab.find('li.active'));
            }
            if (idx < 0) {
                return;
            }
            var counter = this.tab_counter[idx];
            if (count === null) {
                counter.attr('title', '');
                counter.html('&nbsp;');
                counter.css('visibility', 'hidden');
            } else {
                var title = Sao.common.humanize(count);
                if (count >= 1000) {
                    title += '+';
                }
                counter.attr('title', title);
                var text = count;
                if (count > 99) {
                    text = '99+';
                }
                counter.text(text);
                counter.css('visibility', 'visible');
            }
        },
        do_search: function() {
            return this.screen.search_filter(this.get_text());
        },
        set_screen: function(screen) {
            this.screen = screen;
            this.but_bookmark.prop('disabled',
                    jQuery.isEmptyObject(this.bookmarks()));
            this.bookmark_match();
        },
        show_filter: function() {
            this.filter_box.show();
            if (this.tab) {
                this.tab.show();
            }
        },
        hide_filter: function() {
            this.filter_box.hide();
            if (this.tab) {
                this.tab.hide();
            }
        },
        set: function(widget) {
            if (this.alternate_view) {
                this.alternate_viewport.children().detach();
                this.alternate_viewport.append(widget);
            } else {
                this.content_box.children().detach();
                this.content_box.append(widget);
            }
        },
        get_text: function() {
            return this.search_entry.val();
        },
        search_box: function() {
            var domain_parser = this.screen.domain_parser;
            const search = () => {
                this.search_modal.modal('hide');
                var text = '';
                var quote = domain_parser.quote.bind(domain_parser);
                for (const field of this.search_form.fields) {
                    const label = field[0];
                    const entry = field[1];
                    let value;
                    if ((entry instanceof Sao.ScreenContainer.Between) ||
                        (entry instanceof Sao.ScreenContainer.Selection)) {
                        value = entry.get_value(quote);
                    } else {
                        value = quote(entry.val());
                    }
                    if (value) {
                        text += quote(label) + ': ' + value + ' ';
                    }
                }
                this.set_text(text);
                this.do_search().then(() => {
                    this.last_search_text = this.get_text();
                });
            };
            if (!this.search_modal) {
                var dialog = new Sao.Dialog(
                        Sao.i18n.gettext('Filters'), '', 'lg');
                this.search_modal = dialog.modal;
                this.search_form = dialog.content;
                this.search_form.addClass('form-horizontal');
                this.search_form.submit(function(e) {
                    e.preventDefault();
                    search();
                });

                var fields = [];
                for (var f in domain_parser.fields) {
                    const field = domain_parser.fields[f];
                    if ((field.searchable || field.searchable === undefined) &&
                        !field.name.contains('.')) {
                        fields.push(field);
                    }
                }

                var prefix = 'filter-' + this.screen.model_name + '-';
                this.search_form.fields = [];
                for (const field of fields) {
                    var form_group = jQuery('<div/>', {
                        'class': 'form-group form-group-sm'
                    }).append(jQuery('<label/>', {
                        'class': 'col-sm-4 control-label',
                        'for': prefix + field.name,
                        text: field.string
                    })).appendTo(dialog.body);

                    var input;
                    var entry;
                    var format, date_format, time_format;
                    switch (field.type) {
                        case 'boolean':
                            entry = input = jQuery('<select/>', {
                                'class': 'form-control input-sm',
                                id: prefix + field.name
                            });
                            for (const e of [
                                '',
                                Sao.i18n.gettext('True'),
                                Sao.i18n.gettext('False')]) {
                                jQuery('<option/>', {
                                    value: e,
                                    text: e
                                }).appendTo(input);
                            }
                            break;
                        case 'selection':
                        case 'multiselection':
                            entry = new Sao.ScreenContainer.Selection(
                                    field.selection, prefix + field.name);
                            input = entry.el;
                            break;
                        case 'date':
                            format = Sao.common.date_format(
                                this.screen.context.date_format);
                            entry = new Sao.ScreenContainer.Dates(
                                format, prefix + field.name);
                            input = entry.el;
                            break;
                        case 'datetime':
                            date_format = Sao.common.date_format(
                                this.screen.context.date_format);
                            time_format = new Sao.PYSON.Decoder({}).decode(
                                field.format);
                            time_format = Sao.common.moment_format(time_format);
                            format = date_format + ' ' + time_format;
                            entry = new Sao.ScreenContainer.DateTimes(
                                format, prefix + field.name);
                            input = entry.el;
                            break;
                        case 'time':
                            time_format = new Sao.PYSON.Decoder({}).decode(
                                field.format);
                            format = Sao.common.moment_format(time_format);
                            entry = new Sao.ScreenContainer.Times(
                                format, prefix + field.name);
                            input = entry.el;
                            break;
                        case 'integer':
                        case 'float':
                        case 'numeric':
                            entry = new Sao.ScreenContainer.Numbers(prefix + field.name);
                            input = entry.el;
                            break;
                        default:
                            entry = input = jQuery('<input/>', {
                                'class': 'form-control input-sm',
                                type: 'text',
                                placeholder: field.string,
                                id: prefix + field.name
                            });
                            break;
                    }
                    jQuery('<div/>', {
                        'class': 'col-sm-8'
                    }).append(input).appendTo(form_group);
                    this.search_form.fields.push([field.string, entry, input]);
                }

                jQuery('<button/>', {
                    'class': 'btn btn-primary',
                    type: 'submit',
                    'title': Sao.i18n.gettext("Find"),
                }).text(Sao.i18n.gettext('Find'))
                .click(search).appendTo(dialog.footer);
            }
            this.search_modal.modal('show');
            if (this.last_search_text.trim() !== this.get_text().trim()) {
                for (var j = 0; j < this.search_form.fields.length; j++) {
                    var fentry = this.search_form.fields[j][1];
                    if (fentry instanceof Sao.ScreenContainer.Selection) {
                        fentry.set_value([]);
                    } else if (fentry instanceof Sao.ScreenContainer.Between) {
                        fentry.set_value(null, null);
                    } else {
                        fentry.val('');
                    }
                }
                this.search_form.fields[0][2].focus();
            }
        }
    });

    Sao.ScreenContainer.Between = Sao.class_(Object, {
        init: function(id) {
            this.el = jQuery('<div/>', {
                'class': 'row',
                id: id
            });
            this.from = this.build_entry(Sao.i18n.gettext("From"),
                jQuery('<div/>', {
                    'class': 'col-md-5'
                }).appendTo(this.el));
            jQuery('<p/>', {
                'class': 'text-center'
            }).append('..').appendTo(jQuery('<div/>', {
                'class': 'col-md-1'
            }).appendTo(this.el));
            this.to = this.build_entry(Sao.i18n.gettext("To"),
                jQuery('<div/>', {
                    'class': 'col-md-5'
                }).appendTo(this.el));
        },
        build_entry: function(placeholder, el) {
        },
        get_value: function(quote) {
            var from = this._get_value(this.from);
            var to = this._get_value(this.to);
            if (from && to) {
                if (from !== to) {
                    return quote(from) + '..' + quote(to);
                } else {
                    return quote(from);
                }
            } else if (from) {
                return '>=' + quote(from);
            } else if (to) {
                return '<=' + quote(to);
            }
        },
        _get_value: function(entry) {
        },
        set_value: function(from, to) {
            this._set_value(this.from, from);
            this._set_value(this.to, to);
        },
        _set_value: function(entry, value) {
        },
        _from_changed: function(evt) {
            this._set_value(this.to, this._get_value(this.from));
        },
    });

    Sao.ScreenContainer.BetweenDates = Sao.class_(Sao.ScreenContainer.Between, {
        init: function(format, id) {
            this.format = format;
            Sao.ScreenContainer.BetweenDates._super.init.call(this, id);
            this.from.change(this._from_changed.bind(this));
        },
        _get_value: function(entry, value) {
            return entry.find('input[type=text]').val();
        },
        _set_value: function(entry, value) {
            entry.find('input[type=text]').val(value);
        },
    });

    Sao.ScreenContainer.Dates = Sao.class_(
        Sao.ScreenContainer.BetweenDates, {
            _input: 'date',
            _input_format: '%Y-%m-%d',
            _format: Sao.common.format_date,
            _parse: Sao.common.parse_date,
            build_entry: function(placeholder, el) {
                var entry = jQuery('<div/>', {
                    'class': ('input-group input-group-sm ' +
                        'input-icon input-icon-secondary ' +
                        'input-' + this._input),
                }).appendTo(el);
                var date = jQuery('<input/>', {
                    'type': 'text',
                    'class': 'form-control input-sm mousetrap',
                }).appendTo(entry);
                var input = jQuery('<input/>', {
                    'type': this._input,
                    'role': 'button',
                    'tabindex': -1,
                });
                input.click(() => {
                    var value = this._parse(this.format, date.val());
                    value = this._format(this._input_format, value);
                    input.val(value);
                });
                input.change(() => {
                    var value = input.val();
                    if (value) {
                        value = this._parse(this._input_format, value);
                        value = this._format(this.format, value);
                        date.val(value);
                        date.focus();
                    }
                });
                if (input[0].type == this._input) {
                    var icon = jQuery('<div/>', {
                        'class': 'icon-input icon-secondary',
                        'aria-label': Sao.i18n.gettext("Open the calendar"),
                        'title': Sao.i18n.gettext("Open the calendar"),
                    }).appendTo(entry);
                    input.appendTo(icon);
                    Sao.common.ICONFACTORY.get_icon_img('tryton-date')
                        .appendTo(icon);
                }
                var mousetrap = new Mousetrap(date[0]);

                mousetrap.bind('enter', (e, combo) => {
                    var value = this._parse(this.format, date.val());
                    value = this._format(this.format, value);
                    date.val(value);
                });
                mousetrap.bind('=', (e, combo) => {
                    e.preventDefault();
                    date.val(this._format(this.format, moment()));
                });

                Sao.common.DATE_OPERATORS.forEach(operator => {
                    mousetrap.bind(operator[0], (e, combo) => {
                        e.preventDefault();
                        var value = (this._parse(this.format, date.val()) ||
                            Sao.DateTime());
                        value.add(operator[1]);
                        date.val(this._format(this.format, value));
                    });
                });
                return entry;
        },
    });

    Sao.ScreenContainer.DateTimes = Sao.class_(
        Sao.ScreenContainer.Dates, {
            _input: 'datetime-local',
            _input_format: '%Y-%m-%dT%H:%M:%S',
            _format: Sao.common.format_datetime,
            _parse: Sao.common.parse_datetime,
        });

    Sao.ScreenContainer.Times = Sao.class_(
        Sao.ScreenContainer.Dates, {
            _input: 'time',
            _input_format: '%H:%M:%S',
            _format: Sao.common.format_time,
            _parse: Sao.common.parse_time,
            build_entry: function(placeholder, el) {
                var entry = Sao.ScreenContainer.Times._super.build_entry.call(
                    this, placeholder, el);
                if (~navigator.userAgent.indexOf("Firefox")) {
                    // time input on Firefox does not have a pop-up
                    entry.find('.icon-input').hide();
                }
                return entry;
            },
        });

    Sao.ScreenContainer.Numbers = Sao.class_(Sao.ScreenContainer.Between, {
        init: function(id) {
            Sao.ScreenContainer.Numbers._super.init.call(this, id);
            this.from.change(this._from_changed.bind(this));
        },
        build_entry: function(placeholder, el) {
            var entry = jQuery('<input/>', {
                'class': 'form-control input-sm',
                'type': 'number',
                'step': 'any',
            }).appendTo(el);
            return entry;
        },
        _get_value: function(entry, value) {
            return entry.val();
        },
        _set_value: function(entry, value) {
            return entry.val(value);
        },
    });

    Sao.ScreenContainer.Selection = Sao.class_(Object, {
        init: function(selections, id) {
            this.el = jQuery('<select/>', {
                'class': 'form-control input-sm',
                multiple: true,
                id: id
            });
            for (const s of selections) {
                jQuery('<option/>', {
                    value: s[1],
                    text: s[1]
                }).appendTo(this.el);
            }
        },
        get_value: function(quote) {
            var value = this.el.val();
            if (!jQuery.isEmptyObject(value)) {
                value = jQuery.map(value, quote).reduce(function(a, b) {
                    if (a) {a += ';';}
                    return a + b;
                });
            } else {
                value = null;
            }
            return value;
        },
        set_value: function(value) {
            this.el.val(value);
        }
    });

    Sao.Screen = Sao.class_(Object, {
        init: function(model_name, attributes) {
            this.model_name = model_name;
            this.windows = [];
            this.model = new Sao.Model(model_name, attributes);
            this.attributes = jQuery.extend({}, attributes);
            this.view_ids = jQuery.extend([], attributes.view_ids);
            this.view_to_load = jQuery.extend([],
                attributes.mode || ['tree', 'form']);
            this.views = [];
            this.views_preload = attributes.views_preload || {};
            this.exclude_field = attributes.exclude_field;
            this.current_view = null;
            this.domain = attributes.domain || [];
            this.context_domain = attributes.context_domain;
            this.size_limit = null;
            if (this.attributes.limit === undefined) {
                this.limit = Sao.config.limit;
            } else {
                this.limit = attributes.limit;
            }
            this._current_domain = [];
            this.offset = 0;
            this.order = this.default_order = attributes.order;
            this.readonly = this.attributes.readonly || false;
            var access = Sao.common.MODELACCESS.get(model_name);
            if (!(access.write || access.create)) {
                this.readonly = true;
            }
            this.search_count = 0;
            this.new_group(attributes.context || {});
            this.current_record = null;
            this.screen_container = new Sao.ScreenContainer(
                attributes.tab_domain);
            this.breadcrumb = attributes.breadcrumb || [];

            this.context_screen = null;
            if (attributes.context_model) {
                this.context_screen = new Sao.Screen(
                        attributes.context_model, {
                            'mode': ['form'],
                            'context': attributes.context });

                this.context_screen_prm = this.context_screen.switch_view()
                    .then(() => {
                        jQuery('<div/>', {
                            'class': 'row'
                        }).append(jQuery('<div/>', {
                            'class': 'col-md-12'
                        }).append(this.context_screen.screen_container.el))
                        .prependTo(this.screen_container.filter_box);
                        return this.context_screen.new_(false).then(
                            // Set manually default to get context_screen_prm
                            // resolved when default is set.
                            record => record.default_get());
                    });
            }

            if (!attributes.row_activate) {
                this.row_activate = this.default_row_activate;
            } else {
                this.row_activate = attributes.row_activate;
            }
            this.tree_states = {};
            this.tree_states_done = [];
            this.fields_view_tree = {};
            this._domain_parser = {};
            this.pre_validate = false;
            this.switch_callback = null;
        },
        get readonly() {
            var readonly_records = this.selected_records.some(function(r) {
                return r.readonly;
            });
            return this.__readonly || readonly_records;
        },
        set readonly(value) {
            this.__readonly = value;
        },
        get deletable() {
            return this.selected_records.every(function(r) {
                return r.deletable;
            });
        },
        get count_limit() {
            return this.limit * 100 + this.offset;
        },
        load_next_view: function() {
            if (!jQuery.isEmptyObject(this.view_to_load)) {
                var view_id;
                if (!jQuery.isEmptyObject(this.view_ids)) {
                    view_id = this.view_ids.shift();
                }
                var view_type = this.view_to_load.shift();
                return this.add_view_id(view_id, view_type);
            }
            return jQuery.when();
        },
        add_view_id: function(view_id, view_type) {
            var view;
            if (view_id && this.views_preload[String(view_id)]) {
                view = this.views_preload[String(view_id)];
            } else if (!view_id && this.views_preload[view_type]) {
                view = this.views_preload[view_type];
            } else {
                var prm = this.model.execute('fields_view_get',
                        [view_id, view_type], this.context);
                return prm.pipe(this.add_view.bind(this));
            }
            this.add_view(view);
            return jQuery.when();
        },
        add_view: function(view) {
            var arch = view.arch;
            var fields = view.fields;
            var view_id = view.view_id;
            var xml_view = jQuery(jQuery.parseXML(arch));

            if (xml_view.children().prop('tagName') == 'tree') {
                this.fields_view_tree[view_id] = view;
            }

            var loading = 'eager';
            if (xml_view.children().prop('tagName') == 'form') {
                loading = 'lazy';
            }
            for (var field in fields) {
                if (!(field in this.model.fields) || loading == 'eager') {
                    fields[field].loading = loading;
                } else {
                    fields[field].loading = this.model.fields[field]
                        .description.loading;
                }
            }
            this.group.add_fields(fields);
            for (field in fields) {
                this.group.model.fields[field].views.add(view_id);
            }
            var view_widget = Sao.View.parse(
                this, view_id, view.type, xml_view, view.field_childs);
            this.views.push(view_widget);

            return view_widget;
        },
        get number_of_views() {
            return this.views.length + this.view_to_load.length;
        },
        get view_index() {
            return this.views.indexOf(this.current_view);
        },
        switch_view: function(
            view_type=null, view_id=null, creatable=null, display=true) {
            if (view_id !== null) {
                view_id = Number(view_id);
            }
            if (this.current_view) {
                this.current_view.set_value();
                if (this.current_record &&
                        !~this.current_record.group.indexOf(
                            this.current_record)) {
                    this.current_record = null;
                }
                var fields = this.current_view.get_fields();
                if (this.current_record && this.current_view.editable &&
                        !this.current_record.validate(
                            fields, false, false, true)) {
                    this.screen_container.set(this.current_view.el);
                    return this.current_view.display().done(() => {
                        this.set_cursor();
                    });
                }
            }
            const found = () => {
                if (!this.current_view) {
                    return false;
                }
                var result = true;
                if (view_type !== null) {
                    result &= this.current_view.view_type == view_type;
                }
                if (view_id !== null) {
                    result &= this.current_view.view_id == view_id;
                }
                if (creatable !== null) {
                    result &= this.current_view.creatable == creatable;
                }
                return result;
            };
            const _switch = () => {
                const set_container = () => {
                    this.screen_container.set(this.current_view.el);
                    var prm;
                    if (display) {
                        prm = this.display().done(() => {
                            this.set_cursor();
                        });
                    } else {
                        prm = jQuery.when();
                    }
                    return prm.done(() => {
                        if (this.switch_callback) {
                            this.switch_callback();
                        }
                        const tab = Sao.Tab.tabs.get_current();
                        Sao.Tab.set_view_type(tab ? tab.current_view_type : null);
                    });
                };
                const set_current_view = () => {
                    this.current_view = this.views[this.views.length - 1];
                };
                const switch_current_view = () => {
                    set_current_view();
                    if (!found()) {
                        return _switch();
                    } else {
                        return set_container();
                    }
                };
                const is_view_id = view => view.view_id == view_id;

                for (var n = 0; n < this.views.length + this.view_to_load.length; n++) {
                    if (this.view_to_load.length) {
                        return this.load_next_view().then(switch_current_view);
                    } else if ((view_id !== null) &&
                        !this.views.find(is_view_id)) {
                        return this.add_view_id(view_id, view_type)
                            .then(set_current_view);
                    } else {
                        this.current_view = this.views[
                            (this.view_index + 1) % this.views.length];
                    }
                    if (found()) {
                        break;
                    }
                }
                return set_container();
            };
            return _switch();
        },
        search_filter: function(search_string, only_ids) {
            only_ids = only_ids || false;
            if (this.context_screen && !only_ids) {
                if (this.context_screen_prm.state() == 'pending') {
                    return this.context_screen_prm.then(
                        () => this.search_filter(search_string));
                }
                var context_record = this.context_screen.current_record;
                if (context_record &&
                        !context_record.validate(null, false, null, true)) {
                    this.new_group();
                    this.context_screen.display(true);
                    return jQuery.when();
                }
                var screen_context = this.context_screen.get_on_change_value();
                delete screen_context.id;
                this.new_group(jQuery.extend(
                    this.local_context, screen_context));
            }

            var inversion = new Sao.common.DomainInversion();
            var domain = this.search_domain(search_string, true);
            var canonicalized = inversion.canonicalize(domain);
            if (!Sao.common.compare(canonicalized, this._current_domain)) {
                this._current_domain = canonicalized;
                this.offset = 0;
            }

            var context = this.context;
            if ((this.screen_container.but_active.css('display') != 'none') &&
                this.screen_container.but_active.hasClass('active')) {
                context.active_test = false;
            }
            const search = () => {
                return this.model.execute(
                    'search', [domain, this.offset, this.limit, this.order],
                    context)
                    .then(ids => {
                        if (ids.length || this.offset <= 0) {
                            return ids;
                        } else {
                            this.offset = Math.max(this.offset - this.limit, 0);
                            return search();
                        }
                    });
            };
            return search().then(ids => {
                    var count_prm = jQuery.when(this.search_count);
                    if (!only_ids) {
                        if ((this.limit !== null) &&
                            (ids.length == this.limit)) {
                            count_prm = this.model.execute(
                                'search_count',
                                [domain, 0, this.count_limit], context,
                                true, false)
                                .then(count => {
                                    this.search_count = count;
                                    return this.search_count;
                                }, () => {
                                    this.search_count = 0;
                                    return this.search_count;
                                });
                        } else {
                            this.search_count = ids.length;
                        }
                    }
                    return count_prm.then(count => {
                        this.screen_container.but_next.prop('disabled',
                            !(this.limit !== undefined &&
                                ids.length == this.limit &&
                                count > this.limit + this.offset));
                        this.screen_container.but_prev.prop('disabled', this.offset <= 0);
                        if (only_ids) {
                            return ids;
                        }
                        this.clear();
                        return this.load(ids).then(() => {
                            this.count_tab_domain();
                        });
                    });
                });
        },
        search_domain: function(search_string=null, set_text=false, with_tab=true) {
            set_text = set_text || false;
            var domain = [];

            // Test first parent to avoid calling unnecessary domain_parser
            if (!this.group.parent && this.domain_parser) {
                var domain_parser = this.domain_parser;
                if (search_string !== null) {
                    domain = domain_parser.parse(search_string);
                } else {
                    domain = this.attributes.search_value;
                    this.attributes.search_value = null;
                }
                if (set_text) {
                    this.screen_container.set_text(
                            domain_parser.string(domain));
                }
            } else {
                domain = [['id', 'in', this.group.map(function(r) {
                    return r.id;
                })]];
            }

            if (!jQuery.isEmptyObject(domain)) {
                if (!jQuery.isEmptyObject(this.domain)) {
                    domain = ['AND', domain, this.domain];
                }
            } else {
                domain = this.domain;
            }
            if ((this.screen_container.but_active.css('display') != 'none') &&
                this.screen_container.but_active.hasClass('active')) {
                if (!jQuery.isEmptyObject(domain)) {
                    domain = [domain, ['active', '=', false]];
                } else {
                    domain = [['active', '=', false]];
                }
            }
            if (this.current_view &&
                    this.current_view.view_type == 'calendar') {
                if (!jQuery.isEmptyObject(domain)) {
                   domain = ['AND', domain,
                        this.current_view.current_domain()];
                } else {
                    domain = this.current_view.current_domain();
                }
            }
            if (this.context_domain) {
                var decoder = new Sao.PYSON.Decoder(this.context);
                domain = ['AND', domain, decoder.decode(this.context_domain)];
            }
            if (with_tab) {
                var tab_domain = this.screen_container.get_tab_domain();
                if (!jQuery.isEmptyObject(tab_domain)) {
                    domain = ['AND', domain, tab_domain];
                }
            }
            return domain;
        },
        count_tab_domain: function(current=false) {
            var screen_domain = this.search_domain(
                this.screen_container.get_text(), false, false);
            var index = this.screen_container.get_tab_index();
            this.screen_container.tab_domain.forEach((tab_domain, i) => {
                if (tab_domain[2] && (!current || (i == index))) {
                    var domain = ['AND', tab_domain[1], screen_domain];
                    this.screen_container.set_tab_counter(null, i);
                    this.group.model.execute(
                        'search_count', [domain, 0, 1000], this.context)
                        .then(count => {
                            this.screen_container.set_tab_counter(count, i);
                        });
                }
            });
        },
        get context() {
            var context = this.group.context;
            if ( this.context_screen ){
                context.context_model = this.context_screen.model_name;
            }
            return context;
        },
        get local_context() {
            var context = this.group.local_context;
            if (this.context_screen) {
                context.context_model = this.context_screen.model_name;
            }
            return context;
        },
        set_group: function(group) {
            var fields = {},
                fields_views = {},
                name;
            if (this.group) {
                for (name in this.group.model.fields) {
                    var field = this.group.model.fields[name];
                    fields[name] = field.description;
                    fields_views[name] = field.views;
                }
                this.group.screens.splice(
                        this.group.screens.indexOf(this), 1);
                jQuery.extend(group.on_write, this.group.on_write);
                group.on_write = group.on_write.filter(function(e, i, a) {
                    return i == a.indexOf(e);
                });
                if (this.group.parent && !group.parent) {
                    group.parent = this.group.parent;
                }
            }
            group.screens.push(this);
            this.tree_states_done = [];
            this.views.map(function(view) {
                view.reset();
            });
            this.group = group;
            this.model = group.model;
            if (this.group.parent) {
                this.order = null;
            }
            this.current_record = null;
            this.group.add_fields(fields);
            for (name in fields_views) {
                var views = fields_views[name];
                for (const view of views) {
                    this.group.model.fields[name].views.add(view);
                }
            }
            this.group.exclude_field = this.exclude_field;
        },
        new_group: function(context) {
            if (!context) {
                context = this.context;
            }
            var group = new Sao.Group(this.model, context, []);
            group.readonly = this.__readonly;
            this.set_group(group);
        },
        record_modified: function(display=true) {
            for (const window_ of this.windows) {
                if (window_.record_modified) {
                    window_.record_modified();
                }
            }
            if (display) {
                return this.display();
            }
        },
        record_notify: function(notifications) {
            for (const window_ of this.windows) {
                if (window_.info_bar) {
                    window_.info_bar.refresh('notification');
                    for (const notification of notifications) {
                        const type = notification[0];
                        const message = notification[1];
                        window_.info_bar.add(message, type, 'notification');
                    }
                }
            }
        },
        record_message: function(position, size, max_size, record_id) {
            for (const window_ of this.windows) {
                if (window_.record_message) {
                    window_.record_message(position, size, max_size, record_id);
                }
            }
        },
        record_saved: function() {
            for (const window_ of this.windows) {
                if (window_.record_saved) {
                    window_.record_saved();
                }
            }
        },
        update_resources: function(resources) {
            for (const window_ of this.windows) {
                if (window_.update_resources) {
                    window_.update_resources(resources);
                }
            }
        },
        has_update_resources: function() {
            return this.windows.some(function(window_) {
                return window_.update_resources;
            });
        },
        get current_record() {
            return this.__current_record;
        },
        set current_record(record) {
            if ((this.__current_record === record) && record) {
                return;
            }
            this.__current_record = record;
            var pos = null;
            var record_id = null;
            if (record) {
                var i = this.group.indexOf(record);
                if (i >= 0) {
                    pos = i + this.offset + 1;
                } else {
                    pos = record.get_index_path();
                }
                record_id = record.id;
            }
            this.record_message(
                pos || 0, this.group.length + this.offset, this.search_count,
                record_id);
            if (this.switch_callback) {
                this.switch_callback();
            }
            if (this.has_update_resources()) {
                if (record) {
                    record.get_resources().always(
                        this.update_resources.bind(this));
                } else {
                    this.update_resources();
                }
            }
        },
        load: function(ids, set_cursor=true, modified=false, position=-1) {
            this.group.load(ids, modified, position, null);
            if (this.current_view) {
                this.current_view.reset();
            }
            this.current_record = null;
            return this.display(set_cursor);
        },
        display: function(set_cursor) {
            var deferreds = [];
            if (this.views && this.current_view) {
                var search_prm = this.search_active(
                        ~['tree', 'graph', 'calendar'].indexOf(
                            this.current_view.view_type));
                deferreds.push(search_prm);
                for (const view of this.views) {
                    if (view &&
                        ((view == this.current_view) ||
                            view.el.parent().length)) {
                        deferreds.push(view.display());
                    }
                }
                if (this.current_view.view_type == 'tree') {
                    let view_tree = this.fields_view_tree[
                        this.current_view.view_id] || {};
                    if ('active' in view_tree.fields) {
                        this.screen_container.but_active.show();
                    } else {
                        this.screen_container.but_active.hide();
                    }
                } else {
                    this.screen_container.but_active.hide();
                }
            }
            return jQuery.when.apply(jQuery, deferreds).then(
                () => this.set_tree_state().then(() => {
                    var record = this.current_record
                    this.current_record = record;
                    // set_cursor must be called after set_tree_state because
                    // set_tree_state redraws the tree
                    if (set_cursor) {
                        this.set_cursor(false, false);
                    }
                }));
        },
        _get_next_record: function() {
            var view = this.current_view;
            if (view &&
                ~['tree', 'form', 'list-form'].indexOf(view.view_type) &&
                this.current_record && this.current_record.group) {
                var group = this.current_record.group;
                var record = this.current_record;
                while (group) {
                    var index = group.indexOf(record);
                    if (index < group.length - 1) {
                        record = group[index + 1];
                        break;
                    } else if (group.parent &&
                            (record.group.model.name ==
                             group.parent.group.model.name)) {
                        record = group.parent;
                        group = group.parent.group;
                    } else {
                        break;
                    }
                }
                return record;
            } else {
                return this.group[0];
            }
        },
        has_next: function() {
            var next_record = this._get_next_record();
            return next_record &&
                (next_record !== this.current_record);
        },
        display_next: function() {
            var view = this.current_view;
            if (view) {
                view.set_value();
            }
            this.set_cursor(false, false);
            this.current_record = this._get_next_record();
            this.set_cursor(false, false);
            return view ? view.display() : jQuery.when();
        },
        _get_previous_record: function() {
            var view = this.current_view;
            if (view &&
                ~['tree', 'form', 'list-form'].indexOf(view.view_type) &&
                this.current_record && this.current_record.group) {
                var group = this.current_record.group;
                var record = this.current_record;
                while (group) {
                    var index = group.indexOf(record);
                    if (index > 0) {
                        record = group[index - 1];
                        break;
                    } else if (group.parent &&
                            (record.group.model.name ==
                             group.parent.group.model.name)) {
                        record = group.parent;
                        group = group.parent.group;
                    } else {
                        break;
                    }
                }
                return record;
            } else {
                return this.group[0];
            }
        },
        has_previous: function() {
            var previous_record = this._get_previous_record();
            return previous_record &&
                (previous_record !== this.current_record);
        },
        display_previous: function() {
            var view = this.current_view;
            if (view) {
                view.set_value();
            }
            this.set_cursor(false, false);
            this.current_record = this._get_previous_record();
            this.set_cursor(false, false);
            return view ? view.display() : jQuery.when();
        },
        get selected_records() {
            if (this.current_view) {
                return this.current_view.selected_records;
            }
            return [];
        },
        get selected_paths() {
            if (this.current_view && this.current_view.view_type == 'tree') {
                return this.current_view.get_selected_paths();
            } else {
                return [];
            }
        },
        get listed_records() {
            if (this.current_view &&
                ~['tree', 'calendar', 'list-form'].indexOf(
                    this.current_view.view_type)) {
                return this.current_view.listed_records;
            } else if (this.current_record) {
                return [this.current_record];
            } else {
                return [];
            }
        },
        get listed_paths() {
            if (this.current_view && this.current_view.view_type == 'tree') {
                return this.current_view.get_listed_paths();
            } else {
                return [];
            }
        },
        clear: function() {
            this.current_record = null;
            this.group.clear();
            this.tree_states_done = [];
            this.views.map(function(view) {
                view.reset();
            });
        },
        default_row_activate: function() {
            if (this.current_view &&
                (this.current_view.view_type == 'tree') &&
                (this.current_view.attributes.keyword_open == 1)) {
                const id = this.get_id();
                if (id) {
                    Sao.Action.exec_keyword('tree_open', {
                        'model': this.model_name,
                        'id': this.get_id(),
                        'ids': [this.get_id()]
                    }, this.local_context, false);
                }
            } else {
                if (!this.modified()) {
                    this.switch_view('form');
                }
            }
        },
        get_id: function() {
            if (this.current_record) {
                return this.current_record.id;
            }
        },
        new_: function(default_=true, defaults=null) {
            var previous_view = this.current_view;
            var prm = jQuery.when();
            if (this.current_view &&
                this.current_view.view_type == 'calendar') {
                var selected_date = this.current_view.get_selected_date();
            }
            if (this.current_view && !this.current_view.creatable) {
                prm = this.switch_view('form', undefined, true, false);
            }
            return prm.then(() => {
                if (!this.current_view || !this.current_view.editable) {
                    return;
                }
                var group;
                if (this.current_record) {
                    group = this.current_record.group;
                } else {
                    group = this.group;
                }
                var record = group.new_(false);
                var prm;
                if (default_) {
                    prm = record.default_get(defaults);
                } else {
                    prm = jQuery.when();
                }
                return prm.then(() => {
                    group.add(record, this.new_position);
                    this.current_record = record;
                    if (previous_view.view_type == 'calendar') {
                        previous_view.set_default_date(record, selected_date);
                    }
                    this.display().done(() => {
                        this.set_cursor(true, true);
                    });
                    return record;
                });
            });
        },
        get new_position() {
            var order;
            if (this.order !== null) {
                order = this.order;
            } else {
                order = this.default_order;
            }
            if (order) {
                for (var j = 0; j < order.length; j++) {
                    var oexpr = order[j][0],
                        otype = order[j][1];
                    if ((oexpr == 'id') && otype) {
                        if (otype.startsWith('DESC')) {
                            return 0;
                        } else if (otype.startsWith('ASC')) {
                            return -1;
                        }
                    }
                }
            }
            if (this.group.parent) {
                return -1;
            } else {
                return 0;
            }
        },
        set_on_write: function(name) {
            if(name) {
                if (!~this.group.on_write.indexOf(name)) {
                    this.group.on_write.push(name);
                }
            }
        },
        cancel_current: function(initial_value) {
            var prms = [];
            if (this.current_record) {
                this.current_record.cancel();
                if (this.current_record.id < 0) {
                    if (initial_value) {
                        this.current_record.reset(initial_value);
                        this.display();
                    } else {
                        prms.push(this.remove(
                            false, false, false, [this.current_record]));
                    }
                }
            }
            return jQuery.when.apply(jQuery, prms);
        },
        save_current: function() {
            var current_record = this.current_record;
            if (!current_record) {
                if (this.current_view &&
                    (this.current_view.view_type == 'tree') &&
                    this.group && this.group.length) {
                    this.current_record = this.group[0];
                    current_record = this.current_record;
                } else {
                    return jQuery.when();
                }
            }
            if (this.current_view) {
                this.current_view.set_value();
                var fields = this.current_view.get_fields();
            }
            var path = current_record.get_path(this.group);
            var prm = jQuery.Deferred();
            if (this.current_view && (this.current_view.view_type == 'tree')) {
                prm = this.group.save().then(() => this.current_record);
            } else if (current_record.validate(fields, null, null, true)) {
                prm = current_record.save().then(() => current_record);
            } else if (this.current_view) {
                return this.current_view.display().then(() => {
                    this.set_cursor();
                    return jQuery.Deferred().reject();
                });
            }
            const display = () => {
                // Return the original promise to keep succeed/rejected state
                return this.display()
                    .always(() => this.record_saved())
                    .then(() => prm, () => prm);
            };
            return prm.then(current_record => {
                if (path && current_record && current_record.id) {
                    path.splice(-1, 1,
                            [path[path.length - 1][0], current_record.id]);
                }
                return this.group.get_by_path(path).then(record => {
                    this.current_record = record;
                });
            }).then(display, display);
        },
        set_cursor: function(new_, reset_view) {
            if (!this.current_view) {
                return;
            } else if (~['tree', 'form', 'list-form'].indexOf(
                    this.current_view.view_type)) {
                this.current_view.set_cursor(new_, reset_view);
            }
        },
        modified: function() {
            var test = function(record) {
                return (record.modified || record.id < 0);
            };
            if (this.current_view && (this.current_view.view_type != 'tree')) {
                if (this.current_record) {
                    if (test(this.current_record)) {
                        return true;
                    }
                }
            } else {
                if (this.group.some(test)) {
                    return true;
                }
            }
            if (this.current_view && this.current_view.modified) {
                return true;
            }
            return false;
        },
        unremove: function() {
            if (this.current_view) {
                var records = this.current_view.selected_records;
                for (const record of records) {
                    record.group.unremove(record);
                }
            }
        },
        remove: function(delete_, remove, force_remove, records) {
            var prm = jQuery.when();
            if (!records && this.current_view) {
                records = this.current_view.selected_records;
            }
            if (jQuery.isEmptyObject(records)) {
                return prm;
            }
            if (delete_) {
                // TODO delete children before parent
                prm = this.group.delete_(records);
            }
            return prm.then(() => {
                for (const record of records) {
                    record.group.remove(record, remove, force_remove, false);
                }
                // trigger changed only once
                records[0].group.record_modified();
                var prms = [];
                if (delete_) {
                    for (const record of records) {
                        if (record.group.parent) {
                            prms.push(record.group.parent.save(false));
                        }
                        if (~record.group.record_deleted.indexOf(record)) {
                            record.group.record_deleted.splice(
                                record.group.record_deleted.indexOf(record), 1);
                        }
                        if (~record.group.record_removed.indexOf(record)) {
                            record.group.record_removed.splice(
                                record.group.record_removed.indexOf(record), 1);
                        }
                        // TODO destroy
                    }
                }
                this.current_record = null;
                return jQuery.when.apply(jQuery, prms).then(() => {
                    return this.display().done(() => {
                        this.set_cursor();
                    });
                });
            });
        },
        copy: function() {
            var dfd = jQuery.Deferred();
            var records = (
                this.current_view ? this.current_view.selected_records : []);
            this.model.copy(records, this.context)
                .then(new_ids => {
                    this.group.load(new_ids, false, this.new_position, null);
                    if (!jQuery.isEmptyObject(new_ids)) {
                        this.current_record = this.group.get(new_ids[0]);
                    }
                    this.display(true).always(dfd.resolve);
                }, dfd.reject);
            return dfd.promise();
        },
        search_active: function(active) {
            if (active && !this.group.parent) {
                this.screen_container.set_screen(this);
                this.screen_container.show_filter();
            } else {
                this.screen_container.hide_filter();
            }
            return jQuery.when();
        },
        get domain_parser() {
            var view_id, view_tree, domain_parser;
            if (this.current_view) {
                view_id = this.current_view.view_id;
            } else {
                view_id = null;
            }
            if (view_id in this._domain_parser) {
                return this._domain_parser[view_id];
            }
            if (!(view_id in this.fields_view_tree)) {
                view_tree = this.model.execute('fields_view_get', [false, 'tree'],
                    this.context, false);
                this.fields_view_tree[view_id] = view_tree;
            } else {
                view_tree = this.fields_view_tree[view_id];
            }
            var fields = jQuery.extend({}, view_tree.fields);

            for (var name in fields) {
                var props = fields[name];
                if ((props.type != 'selection') &&
                    (props.type != 'multiselection') &&
                    (props.type != 'reference')) {
                    continue;
                }
                if (props.selection instanceof Array) {
                    continue;
                }
                props = jQuery.extend({}, props);
                props.selection = this.get_selection(props);
                fields[name] = props;
            }

            if ('arch' in view_tree) {
                // Filter only fields in XML view
                var xml_view = jQuery(jQuery.parseXML(view_tree.arch));
                var dom_fields = {};
                xml_view.find('tree').children().each(function(i, node) {
                    if (node.tagName == 'field') {
                        var name = node.getAttribute('name');
                        // If a field is defined multiple times in the XML,
                        // take only the first definition
                        if (!(name in dom_fields)) {
                            dom_fields[name] = fields[name];
                            for (const attr of ['string', 'factor']) {
                                if (node.getAttribute(attr)) {
                                    dom_fields[name][attr] = node.getAttribute(attr);
                                }
                            }
                        }
                        var symbol = node.getAttribute('symbol');
                        if (symbol && !(symbol in dom_fields)) {
                            dom_fields[symbol] = fields[symbol];
                        }
                    }
                });
                fields = dom_fields;
            }

            // Add common fields
            const common_fields = new Set([
                ['id', Sao.i18n.gettext('ID'), 'integer'],
                ['create_uid', Sao.i18n.gettext('Created by'), 'many2one'],
                ['create_date', Sao.i18n.gettext('Created at'), 'datetime'],
                ['write_uid', Sao.i18n.gettext('Modified by'), 'many2one'],
                ['write_date', Sao.i18n.gettext('Modified at'), 'datetime']
            ]);
            for (const [name, string, type] of common_fields) {
                if (!(name in fields)) {
                    fields[name] = {
                        'string': string,
                        'name': name,
                        'type': type
                    };
                    if (type == 'datetime') {
                        fields[name].format = '"%H:%M:%S"';
                    }
                }
            }

            domain_parser = new Sao.common.DomainParser(fields, this.context);
            this._domain_parser[view_id] = domain_parser;
            return domain_parser;
        },
        get_selection: function(props) {
            var selection;
            var change_with = props.selection_change_with;
            if (!jQuery.isEmptyObject(change_with)) {
                var values = {};
                for (const p of change_with) {
                    values[p] = null;
                }
                selection = this.model.execute(props.selection,
                        [values], undefined, false, true);
            } else {
                selection = this.model.execute(props.selection,
                        [], undefined, false, true);
            }
            return selection.sort(function(a, b) {
                return a[1].localeCompare(b[1]);
            });
        },
        search_prev: function(search_string) {
            if (this.limit) {
                this.offset = Math.max(this.offset - this.limit, 0);
            }
            this.search_filter(search_string);
        },
        search_next: function(search_string) {
            if (this.limit) {
                this.offset += this.limit;
            }
            this.search_filter(search_string);
        },
        invalid_message: function(record) {
            if (!record) {
                record = this.current_record;
            }
            var fields_desc = {};
            for (var fname in record.model.fields) {
                var field = record.model.fields[fname];
                fields_desc[fname] = field.description;
            }
            var domain_parser = new Sao.common.DomainParser(fields_desc);
            var fields = [];
            var invalid_fields = record.invalid_fields();
            for (const field of Object.keys(invalid_fields).sort()) {
                var invalid = invalid_fields[field];
                var string = record.model.fields[field].description.string;
                if ((invalid == 'required') ||
                    (Sao.common.compare(invalid, [[field, '!=', null]]))) {
                    fields.push(Sao.i18n.gettext(
                        '"%1" is required.', string));
                } else if (invalid == 'domain') {
                    fields.push(Sao.i18n.gettext(
                        '"%1" is not valid according to its domain.',
                        string));
                } else if (invalid == 'children') {
                    fields.push(Sao.i18n.gettext(
                        'The values of "%1" are not valid.', string));
                } else {
                    if (domain_parser.stringable(invalid)) {
                        fields.push(domain_parser.string(invalid));
                    } else {
                        fields.push(Sao.i18n.gettext(
                            '"%1" is not valid according to its domain.'),
                            string);
                    }
                }
            }
            if (fields.length > 5) {
                fields.splice(5, fields.length);
                fields.push('...');
            }
            return fields.join('\n');
        },
        get: function() {
            if (!this.current_record) {
                return null;
            }
            if (this.current_view) {
                this.current_view.set_value();
            }
            return this.current_record.get();
        },
        get_on_change_value: function() {
            if (!this.current_record) {
                return null;
            }
            if (this.current_view) {
                this.current_view.set_value();
            }
            return this.current_record.get_on_change_value();
        },
        reload: function(ids, written) {
            this.group.reload(ids);
            var promises = [];
            if (written) {
                promises.push(this.group.written(ids));
            }
            if (this.group.parent) {
                promises.push(this.group.parent.root_parent.reload());
            }
            return jQuery.when.apply(jQuery, promises).then(() => {
                return this.display();
            });
        },
        get_buttons: function() {
            var selected_records = (
                this.current_view ? this.current_view.selected_records : []);
            if (jQuery.isEmptyObject(selected_records)) {
                return [];
            }
            var buttons = (
                this.current_view ? this.current_view.get_buttons() : []);
            for (const record of selected_records) {
                buttons = buttons.filter(function(button) {
                    if (button.attributes.type === 'instance') {
                        return false;
                    }
                    var states = record.expr_eval(
                        button.attributes.states || {});
                    return !(states.invisible || states.readonly);
                });
            }
            return buttons;
        },
        button: function(attributes) {
            var ids;
            const process_action = action => {
                if (typeof action == 'string') {
                    return this.reload(ids, true).then(() => {
                        return this.client_action(action);
                    });
                }
                else if (action) {
                    return Sao.Action.execute(action, {
                        model: this.model_name,
                        id: this.current_record.id,
                        ids: ids
                    }, null, this.context, true).always(() => {
                        return this.reload(ids, true)
                            .always(() => this.record_saved());
                    });
                } else {
                    return this.reload(ids, true)
                        .always(() => this.record_saved());
                }
            };

            if (this.current_view) {
                var selected_records = this.current_view.selected_records;
                this.current_view.set_value();
                var fields = this.current_view.get_fields();
            }

            var prms = [];
            const reset_state = record => {
                return () => {
                    this.display(true);
                    // Reset valid state with normal domain
                    record.validate(fields);
                };
            };
            for (const record of selected_records) {
                const domain = record.expr_eval(
                    (attributes.states || {})).pre_validate || [];
                prms.push(record.validate(fields, false, domain));
            }
            return jQuery.when.apply(jQuery, prms).then((...args) => {
                var record;
                for (var i = 0; i < selected_records.length; i++) {
                    record = selected_records[i];
                    var result = args[i];
                    if (result) {
                        continue;
                    }
                    Sao.common.warning.run(
                            this.invalid_message(record),
                            Sao.i18n.gettext('Pre-validation'))
                        .then(reset_state(record));
                    return;
                }
                var prm = jQuery.when();
                if (attributes.confirm) {
                    prm = Sao.common.sur.run(attributes.confirm);
                }
                return prm.then(() => {
                    var record = this.current_record;
                    if (attributes.type === 'instance') {
                        var args = record.expr_eval(attributes.change || []);
                        var values = record._get_on_change_args(args);
                        return record.model.execute(attributes.name, [values],
                            this.context).then(function(changes) {
                            record.set_on_change(changes);
                            record.set_modified();
                        });
                    } else {
                        return record.save(false).then(() => {
                            var context = this.context;
                            context._timestamp = {};
                            ids = [];
                            for (i = 0; i < selected_records.length; i++) {
                                record = selected_records[i];
                                jQuery.extend(context._timestamp,
                                    record.get_timestamp());
                                ids.push(record.id);
                            }
                            return record.model.execute(attributes.name,
                                [ids], context)
                                .then(process_action)
                                .fail(() => this.reload(ids, true));
                        });
                    }
                });
            });
        },
        client_action: function(action) {
            var access = Sao.common.MODELACCESS.get(this.model_name);
            if (action == 'new') {
                if (access.create) {
                    return this.new_();
                }
            } else if (action == 'delete') {
                if (access['delete'] && (
                        this.current_record ? this.current_record.deletable :
                        true)) {
                    return this.remove(!this.group.parent, false, !this.group.parent);
                }
            } else if (action == 'remove') {
                if (access.write && access.read && this.group.parent) {
                    return this.remove(false, true, false);
                }
            } else if (action == 'copy') {
                if (access.create) {
                    return this.copy();
                }
            } else if (action == 'next') {
                return this.display_next();
            } else if (action == 'previous') {
                return this.display_previous();
            } else if (action == 'close') {
                Sao.Tab.tabs.close_current();
            } else if (action.startsWith('switch')) {
                return this.switch_view.apply(this, action.split(' ', 3).slice(1));
            } else if (action == 'reload') {
                if (this.current_view && 
                    ~['tree', 'graph', 'calendar'].indexOf(this.current_view.view_type) &&
                    !this.group.parent) {
                    return this.search_filter();
                }
            } else if (action == 'reload menu') {
                return Sao.Session.current_session.reload_context()
                    .then(function() {
                        Sao.menu();
                    });
            } else if (action == 'reload context') {
                return Sao.Session.current_session.reload_context();
            }
        },
        get_url: function(name) {
            function dumps(value) {
                return JSON.stringify(Sao.rpc.prepareObject(value));
            }
            var query_string = [];
            if (!jQuery.isEmptyObject(this.domain)) {
                query_string.push(['domain', dumps(this.domain)]);
            }
            var context = this.local_context;  // Avoid rpc context
            if (!jQuery.isEmptyObject(context)) {
                query_string.push(['context', dumps(context)]);
            }
            if (this.context_screen) {
                query_string.push(
                    ['context_model', this.context_screen.model_name]);
            }
            if (name) {
                query_string.push(['name', dumps(name)]);
            }
            var path = ['model', this.model_name];
            var view_ids = this.views.map(
                function(v) {return v.view_id;}).concat(this.view_ids);
            if (this.current_view && (this.current_view.view_type != 'form')) {
                if (!jQuery.isEmptyObject(this.attributes.tab_domain)) {
                    query_string.push([
                        'tab_domain', dumps(this.attributes.tab_domain)]);
                }
                var search_value;
                if (this.attributes.search_value) {
                    search_value = this.attributes.search_value;
                } else {
                    var search_string = this.screen_container.get_text();
                    search_value = this.domain_parser.parse(search_string);
                }
                if (!jQuery.isEmptyObject(search_value)) {
                    query_string.push(['search_value', dumps(search_value)]);
                }
            } else if (this.current_record && (this.current_record.id > -1)) {
                path.push(this.current_record.id);
                if (this.current_view) {
                    var i = view_ids.indexOf(this.current_view.view_id);
                    view_ids = view_ids.slice(i).concat(view_ids.slice(0, i));
                }
            }
            if (!jQuery.isEmptyObject(view_ids)) {
                query_string.push(['views', dumps(view_ids)]);
            }
            query_string = query_string.map(function(e) {
                return e.map(encodeURIComponent).join('=');
            }).join('&');
            path = path.join('/');
            if (query_string) {
                path += ';' + query_string;
            }
            return path;
        },
        save_tree_state: function(store=true) {
            var prms = [];
            var prm;
            var i, len, view, widgets, wi, wlen;
            var parent_ = this.group.parent ? this.group.parent.id : null;
            var clear_cache = function() {
                Sao.Session.current_session.cache.clear(
                    'model.ir.ui.view_tree_state.get');
            };
            const set_session_fail = () => {
                Sao.Logger.warn(
                    "Unable to set view tree state for %s",
                    this.model_name);
            };
            for (i = 0, len = this.views.length; i < len; i++) {
                view = this.views[i];
                if (view.view_type == 'form') {
                    for (var wid_key in view.widgets) {
                        widgets = view.widgets[wid_key];
                        for (wi = 0, wlen = widgets.length; wi < wlen; wi++) {
                            if (widgets[wi].screen) {
                                prm = widgets[wi].screen.save_tree_state(store);
                                prms.push(prm);
                            }
                        }
                    }
                    if ((this.views.length == 1) && this.current_record) {
                        if (!(parent_ in this.tree_states)) {
                            this.tree_states[parent_] = {};
                        }
                        this.tree_states[parent_][
                            view.children_field || null] = [
                                [], [[this.current_record.id]]];
                    }
                } else if (~['tree', 'list-form'].indexOf(view.view_type)) {
                    var paths;
                    if (view.view_type == 'tree') {
                        paths = view.get_expanded_paths();
                    } else {
                        paths = [];
                    }
                    var selected_paths = view.get_selected_paths();
                    if (!(parent_ in this.tree_states)) {
                        this.tree_states[parent_] = {};
                    }
                    this.tree_states[parent_][view.children_field || null] = [
                        paths, selected_paths];
                    if (store && parseInt(view.attributes.tree_state, 10)) {
                        var tree_state_model = new Sao.Model(
                                'ir.ui.view_tree_state');
                        prm = tree_state_model.execute('set', [
                                this.model_name,
                                this.get_tree_domain(parent_),
                                view.children_field,
                                JSON.stringify(paths),
                                JSON.stringify(selected_paths)], {})
                            .then(clear_cache)
                            .fail(set_session_fail);
                        prms.push(prm);
                    }
                }
            }
            return jQuery.when.apply(jQuery, prms);
        },
        get_tree_domain: function(parent_) {
            var domain;
            if (parent_) {
                domain = (this.domain || []).concat([
                        [this.exclude_field, '=', parent_]]);
            } else {
                domain = this.domain;
            }
            return JSON.stringify(Sao.rpc.prepareObject(domain));
        },
        set_tree_state: function() {
            var parent_, state, state_prm, tree_state_model;
            var view = this.current_view;
            if (!view) {
                return jQuery.when();
            }
            if (!~['tree', 'form', 'list-form'].indexOf(view.view_type)) {
                return jQuery.when();
            }

            if (~this.tree_states_done.indexOf(view)) {
                return jQuery.when();
            }
            if (view.view_type == 'form' &&
                    !jQuery.isEmptyObject(this.tree_states_done)) {
                return jQuery.when();
            }
            if ((~['tree', 'list-form'].indexOf(view.view_type)) &&
                !parseInt(view.attributes.tree_state, 10)) {
                this.tree_states_done.push(view);
            }

            parent_ = this.group.parent ? this.group.parent.id : null;
            if (parent_ < 0) {
                return jQuery.when();
            }
            if (!(parent_ in this.tree_states)) {
                this.tree_states[parent_] = {};
            }
            state = this.tree_states[parent_][view.children_field || null];
            if ((state === undefined) &&
                (parseInt(view.attributes.tree_state, 10))) {
                tree_state_model = new Sao.Model('ir.ui.view_tree_state');
                state_prm = tree_state_model.execute('get', [
                        this.model_name,
                        this.get_tree_domain(parent_),
                        view.children_field], {})
                    .then(state => {
                        state = [JSON.parse(state[0]), JSON.parse(state[1])];
                        if (!(parent_ in this.tree_states)) {
                            this.tree_states[parent_] = {};
                        }
                        this.tree_states[parent_][view.children_field || null] = state;
                        return state;
                    })
                    .fail(() => {
                        Sao.Logger.warn(
                            "Unable to get view tree state for %s",
                            this.model_name);
                    });
            } else {
                state_prm = jQuery.when(state);
            }
            this.tree_states_done.push(view);
            return state_prm.done(state => {
                var expanded_nodes = [], selected_nodes = [];
                if (state) {
                    expanded_nodes = state[0];
                    selected_nodes = state[1];
                }
                if (view.view_type == 'tree') {
                    return view.display(selected_nodes, expanded_nodes);
                } else if (view.view_type == 'list-form') {
                    return view.display(selected_nodes);
                } else {
                    var record;
                    if (!jQuery.isEmptyObject(selected_nodes)) {
                        for (const id of selected_nodes[0]) {
                            const new_record = this.group.get(id);
                            if (!new_record) {
                                break;
                            } else {
                                record = new_record;
                            }
                        }
                        if (record && (record != this.current_record)) {
                            this.current_record = record;
                            // Force a display of the view to synchronize the
                            // widgets with the new record
                            view.display();
                        }
                    }
                }
            });
        }
    });
    Sao.Screen.tree_column_optional = {};
}());
