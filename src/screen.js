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
                'class': 'filter-box'
            }).submit(function(e) {
                this.do_search();
                e.preventDefault();
            }.bind(this));
            var search_row = jQuery('<div/>', {
                'class': 'row'
            }).appendTo(this.filter_box);
            this.el.append(this.filter_box);
            this.filter_button = jQuery('<button/>', {
                type: 'button',
                'class': 'btn btn-default'
            }).append(Sao.i18n.gettext('Filters'));
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
            but_clear.click(function() {
                this.search_entry.val('').change();
                this.do_search();
            }.bind(this));

            this.search_entry.on('keyup change', function() {
                if (this.search_entry.val()) {
                    but_clear.show();
                } else {
                    but_clear.hide();
                }
                this.bookmark_match();
            }.bind(this));

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
                'id': 'bookmarks'
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-bookmark', {
                'aria-hidden': true,
            }));
            var dropdown_bookmark = jQuery('<ul/>', {
                'class': 'dropdown-menu dropdown-menu-right',
                'role': 'menu',
                'aria-labelledby': 'bookmarks'
            });
            this.but_bookmark.click(function() {
                dropdown_bookmark.empty();
                var bookmarks = this.bookmarks();
                for (var i=0; i < bookmarks.length; i++) {
                    var name = bookmarks[i][1];
                    var domain = bookmarks[i][2];
                    jQuery('<li/>', {
                        'role': 'presentation'
                    })
                    .append(jQuery('<a/>', {
                        'role': 'menuitem',
                        'href': '#',
                        'tabindex': -1
                    }).append(name)
                        .click(domain, this.bookmark_activate.bind(this)))
                    .appendTo(dropdown_bookmark);
                }
            }.bind(this));
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
                var content = jQuery('<div/>', {
                    'class': 'tab-content'
                }).appendTo(this.tab);
                this.tab_domain.forEach(function(tab_domain, i) {
                    var name = tab_domain[0];
                    var counter = jQuery('<span/>', {
                        'class': 'badge'
                    });
                    var page = jQuery('<li/>', {
                        role: 'presentation',
                        id: 'nav-' + i
                    }).append(jQuery('<a/>', {
                        'aria-controls':  i,
                        role: 'tab',
                        'data-toggle': 'tab',
                        'href': '#' + i
                    }).append(name + ' ').append(counter)).appendTo(nav);
                    this.tab_counter.push(counter);
                }.bind(this));
                nav.find('a:first').tab('show');
                var self = this;
                nav.find('a').click(function(e) {
                    e.preventDefault();
                    jQuery(this).tab('show');
                    self.do_search();
                    self.screen.count_tab_domain();
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
            completions.forEach(function(e) {
                jQuery('<option/>', {
                    'value': e.trim()
                }).appendTo(this.search_list);
            }, this);
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
            var refresh = function() {
                this.bookmark_match();
                this.but_bookmark.prop('disabled',
                        jQuery.isEmptyObject(this.bookmarks()));
            }.bind(this);
            if (!star) {
                var text = this.get_text();
                if (!text) {
                    return;
                }
                Sao.common.ask.run(Sao.i18n.gettext('Bookmark Name:'))
                    .then(function(name) {
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
                    }.bind(this));
            } else {
                var id = this.bookmark_match();
                Sao.common.VIEW_SEARCH.remove(model_name, id).then(function() {
                    refresh();
                });
            }
        },
        bookmarks: function() {
            var searches = Sao.common.VIEW_SEARCH.get(this.screen.model_name);
            return searches.filter(function(search) {
                return this.screen.domain_parser.stringable(search[2]);
            }.bind(this));
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
                this.but_star.prop('disabled', !current_text);
                var star = this.get_star();
                var bookmarks = this.bookmarks();
                for (var i=0; i < bookmarks.length; i++) {
                    var id = bookmarks[i][0];
                    var name = bookmarks[i][1];
                    var domain = bookmarks[i][2];
                    var text = this.screen.domain_parser.string(domain);
                    if ((text === current_text) ||
                            (Sao.common.compare(domain, current_domain))) {
                        this.set_star(true);
                        return id;
                    }
                }
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
        get_tab_domain: function() {
            if (!this.tab) {
                return [];
            }
            var i = this.tab.find('li').index(this.tab.find('li.active'));
            return this.tab_domain[i][1];
        },
        set_tab_counter: function(count, idx) {
            if (jQuery.isEmptyObject(this.tab_counter) || !this.tab) {
                return;
            }
            if ((idx === undefined) || (idx === null)) {
                idx = this.tab.find('li').index(this.tab.find('li.active'));
            }
            if (idx < 0) {
                return;
            }
            var counter = this.tab_counter[idx];
            if (count === null) {
                counter.attr('title', '');
                counter.text('');
            } else {
                counter.attr('title', count);
                var text = count;
                if (count > 99) {
                    text = '99+';
                }
                counter.text(text);
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
            var search = function() {
                this.search_modal.modal('hide');
                var text = '';
                var quote = domain_parser.quote.bind(domain_parser);
                for (var i = 0; i < this.search_form.fields.length; i++) {
                    var label = this.search_form.fields[i][0];
                    var entry = this.search_form.fields[i][1];
                    var value;
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
                this.do_search().then(function() {
                    this.last_search_text = this.get_text();
                }.bind(this));
            }.bind(this);
            if (!this.search_modal) {
                var dialog = new Sao.Dialog(
                        Sao.i18n.gettext('Filters'), '', 'lg');
                this.search_modal = dialog.modal;
                this.search_form = dialog.content;
                this.search_form.addClass('form-horizontal');
                this.search_form.submit(function(e) {
                    search();
                    e.preventDefault();
                });

                var fields = [];
                var field;
                for (var f in domain_parser.fields) {
                    field = domain_parser.fields[f];
                    if ((field.searchable || field.searchable === undefined) &&
                        !field.name.contains('.')) {
                        fields.push(field);
                    }
                }

                var boolean_option = function(input) {
                    return function(e) {
                        jQuery('<option/>', {
                            value: e,
                            text: e
                        }).appendTo(input);
                    };
                };
                var selection_option = function(input) {
                    return function(s) {
                        jQuery('<option/>', {
                            value: s[1],
                            text: s[1]
                        }).appendTo(input);
                    };
                };

                var prefix = 'filter-' + this.screen.model_name + '-';
                this.search_form.fields = [];
                for (var i = 0; i < fields.length; i++) {
                    field = fields[i];
                    var form_group = jQuery('<div/>', {
                        'class': 'form-group form-group-sm'
                    }).append(jQuery('<label/>', {
                        'class': 'col-sm-4 control-label',
                        'for': prefix + field.name,
                        text: field.string
                    })).appendTo(dialog.body);

                    var input;
                    var entry;
                    switch (field.type) {
                        case 'boolean':
                            entry = input = jQuery('<select/>', {
                                'class': 'form-control input-sm',
                                id: prefix + field.name
                            });
                            ['',
                            Sao.i18n.gettext('True'),
                            Sao.i18n.gettext('False')].forEach(
                                    boolean_option(input));
                            break;
                        case 'selection':
                        case 'multiselection':
                            entry = new Sao.ScreenContainer.Selection(
                                    field.selection, prefix + field.name);
                            input = entry.el;
                            break;
                        case 'date':
                        case 'datetime':
                        case 'time':
                            var format;
                            var date_format = Sao.common.date_format(
                                this.screen.context.date_format);
                            if (field.type == 'date') {
                                format = date_format;
                            } else {
                                var time_format = new Sao.PYSON.Decoder({}).decode(
                                        field.format);
                                time_format = Sao.common.moment_format(time_format);
                                if (field.type == 'time') {
                                    format = time_format;
                                } else if (field.type == 'datetime') {
                                    format = date_format + ' ' + time_format;
                                }
                            }
                            entry = new Sao.ScreenContainer.DateTimes(
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
                    type: 'submit'
                }).append(Sao.i18n.gettext('Find'))
                .click(search).appendTo(dialog.footer);
            }
            this.search_modal.modal('show');
            if (this.last_search_text.trim() !== this.get_text().trim()) {
                for (var j = 0; j < this.search_form.fields.length; j++) {
                    var fentry = this.search_form.fields[j][1];
                    switch(fentry.type) {
                        case 'selection':
                            fentry.set_value([]);
                            break;
                        case 'date':
                        case 'datetime':
                        case 'time':
                            fentry.set_value(null, null);
                            break;
                        default:
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
            this._set_value(self.from, from);
            this._set_value(self.to, to);
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
            this.from.on('dp.change', this._from_changed.bind(this));
        },
        _get_value: function(entry, value) {
            return entry.find('input').val();
        },
        _set_value: function(entry, value) {
            entry.data('DateTimePicker').date(value);
        },
    });

    Sao.ScreenContainer.DateTimes = Sao.class_(
        Sao.ScreenContainer.BetweenDates, {
        build_entry: function(placeholder, el) {
                var entry = jQuery('<div/>', {
                    'class': 'input-group input-group-sm'
                }).appendTo(el);
                jQuery('<span/>', {
                    'class': 'input-group-btn'
                }).append(jQuery('<button/>', {
                    'class': 'datepickerbutton btn btn-default',
                    type: 'button',
                    'tabindex': -1,
                    'aria-label': Sao.i18n.gettext("Open the calendar"),
                    'title': Sao.i18n.gettext("Open the calendar"),
                }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-date')
                )).appendTo(entry);
                jQuery('<input/>', {
                    'class': 'form-control input-sm',
                    type: 'text',
                    placeholder: placeholder,
                }).appendTo(entry);
                entry.datetimepicker({
                    'locale': moment.locale(),
                    'keyBinds': null,
                });
                entry.data('DateTimePicker').format(this.format);
                // We must set the overflow of the modal-body
                // containing the input to visible to prevent vertical scrollbar
                // inherited from the auto overflow-x
                // (see http://www.w3.org/TR/css-overflow-3/#overflow-properties)
                entry.on('dp.hide', function() {
                    entry.closest('.modal-body').css('overflow', '');
                });
                entry.on('dp.show', function() {
                    entry.closest('.modal-body').css('overflow', 'visible');
                });

                var mousetrap = new Mousetrap(el[0]);

                mousetrap.bind('enter', function(e, combo) {
                    entry.data('DateTimePicker').date();
                });
                mousetrap.bind('=', function(e, combo) {
                    e.preventDefault();
                    entry.data('DateTimePicker').date(moment());
                });

                Sao.common.DATE_OPERATORS.forEach(function(operator) {
                    mousetrap.bind(operator[0], function(e, combo) {
                        e.preventDefault();
                        var dp = entry.data('DateTimePicker');
                        var date = dp.date();
                        date.add(operator[1]);
                        dp.date(date);
                    });
                });
                return entry;
        },
    });

    Sao.ScreenContainer.Numbers = Sao.class_(Sao.ScreenContainer.BetweenDates, {
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
            selections.forEach(function(s) {
                jQuery('<option/>', {
                    value: s[1],
                    text: s[1]
                }).appendTo(this.el);
            }.bind(this));
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
            this.model = new Sao.Model(model_name, attributes);
            this.attributes = jQuery.extend({}, attributes);
            this.view_ids = jQuery.extend([], attributes.view_ids);
            this.view_to_load = jQuery.extend([],
                attributes.mode || ['tree', 'form']);
            this.views = [];
            this.views_preload = attributes.views_preload || {};
            this.exclude_field = attributes.exclude_field;
            this.new_group(attributes.context || {});
            this.current_view = null;
            this.current_record = null;
            this.domain = attributes.domain || [];
            this.context_domain = attributes.context_domain;
            this.size_limit = null;
            if ((this.attributes.limit === undefined) ||
                (this.attributes.limit === null)) {
                this.limit = Sao.config.limit;
            } else {
                this.limit = attributes.limit;
            }
            this.offset = 0;
            this.order = this.default_order = attributes.order;
            var access = Sao.common.MODELACCESS.get(model_name);
            if (!(access.write || access.create)) {
                this.attributes.readonly = true;
            }
            this.search_count = 0;
            this.screen_container = new Sao.ScreenContainer(
                attributes.tab_domain);

            this.context_screen = null;
            if (attributes.context_model) {
                this.context_screen = new Sao.Screen(
                        attributes.context_model, {
                            'mode': ['form'],
                            'context': attributes.context });

                this.context_screen_prm = this.context_screen.switch_view()
                    .then(function() {
                        jQuery('<div/>', {
                            'class': 'row'
                        }).append(jQuery('<div/>', {
                            'class': 'col-md-12'
                        }).append(this.context_screen.screen_container.el))
                        .prependTo(this.screen_container.filter_box);
                        return this.context_screen.new_(false).then(function(record) {
                            // Set manually default to get context_screen_prm
                            // resolved when default is set.
                            return record.default_get();
                        });
                    }.bind(this));
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
            this.tab = null;
            this.message_callback = null;
            this.switch_callback = null;
            this.group_changed_callback = null;
            // count_tab_domain is called in Sao.Tab.Form.init after
            // switch_view to avoid unnecessary call to fields_view_get by
            // domain_parser.
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
        switch_view: function(view_type, view_id, display) {
            display = display === undefined ? true : display;
            if ((view_id !== undefined) && (view_id !== null)) {
                view_id = Number(view_id);
            } else {
                view_id = null;
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
                    return this.current_view.display().done(function() {
                        this.set_cursor();
                    }.bind(this));
                }
            }
            var found = function() {
                if (!this.current_view) {
                    return false;
                }
                else if (!view_type && (view_id === null)) {
                    return false;
                }
                else if (view_id !== null) {
                    return this.current_view.view_id == view_id;
                } else {
                    return this.current_view.view_type == view_type;
                }
            }.bind(this);
            var _switch = function() {
                var set_container = function() {
                    this.screen_container.set(this.current_view.el);
                    var prm;
                    if (display) {
                        prm = this.display().done(function() {
                            this.set_cursor();
                        }.bind(this));
                    } else {
                        prm = jQuery.when();
                    }
                    return prm.done(function() {
                            if (this.switch_callback) {
                                this.switch_callback();
                            }
                        }.bind(this));
                }.bind(this);
                var continue_loop = function() {
                    if (!view_type && (view_id === null)) {
                        return false;
                    }
                    if (view_type && !view_id && !this.view_to_load.length) {
                        return false;
                    }
                    return true;
                }.bind(this);
                var set_current_view = function() {
                    this.current_view = this.views[this.views.length - 1];
                }.bind(this);
                var switch_current_view = (function() {
                    set_current_view();
                    if (continue_loop()) {
                        return _switch();
                    } else {
                        return set_container();
                    }
                }.bind(this));
                var is_view_id = function(view) {
                    return view.view_id == view_id;
                };

                while (!found()) {
                    if (this.view_to_load.length) {
                        return this.load_next_view().then(switch_current_view);
                    } else if ((view_id !== null) &&
                        !this.views.find(is_view_id)) {
                        return this.add_view_id(view_id, view_type)
                            .then(set_current_view);
                    } else {
                        var i = this.views.indexOf(this.current_view);
                        this.current_view = this.views[
                            (i + 1) % this.views.length];
                    }
                    if (!continue_loop()) {
                        break;
                    }
                }
                return set_container();
            }.bind(this);
            return _switch();
        },
        search_filter: function(search_string, only_ids) {
            only_ids = only_ids || false;
            if (this.context_screen && !only_ids) {
                if (this.context_screen_prm.state() == 'pending') {
                    return this.context_screen_prm.then(function() {
                        return this.search_filter(search_string);
                    }.bind(this));
                }
                var context_record = this.context_screen.current_record;
                if (context_record &&
                        !context_record.validate(null, false, null, true)) {
                    this.new_group();
                    this.context_screen.display(true);
                    return jQuery.when();
                }
                this.new_group(jQuery.extend(
                    this.local_context,
                    this.context_screen.get_on_change_value()));
            }

            var domain = this.search_domain(search_string, true);
            if (this.context_domain) {
                var decoder = new Sao.PYSON.Decoder(this.context);
                domain = ['AND', domain, decoder.decode(this.context_domain)];
            }
            var tab_domain = this.screen_container.get_tab_domain();
            if (!jQuery.isEmptyObject(tab_domain)) {
                domain = ['AND', domain, tab_domain];
            }
            var context = this.context;
            if (this.screen_container.but_active.hasClass('active')) {
                context.active_test = false;
            }
            var search = function() {
                return this.model.execute(
                    'search', [domain, this.offset, this.limit, this.order],
                    context)
                    .then(function(ids) {
                        if (ids.length || this.offset <= 0) {
                            return ids;
                        } else {
                            this.offset = Math.max(this.offset - this.limit, 0);
                            return search();
                        }
                    }.bind(this));
            }.bind(this);
            return search().then(function(ids) {
                    var count_prm = jQuery.when(this.search_count);
                    if (!only_ids) {
                        if ((this.limit !== null) &&
                            (ids.length == this.limit)) {
                            count_prm = this.model.execute(
                                'search_count', [domain], context)
                                .then(function(count) {
                                    this.search_count = count;
                                    return this.search_count;
                                }.bind(this), function() {
                                    this.search_count = 0;
                                    return this.search_count;
                                }.bind(this));
                        } else {
                            this.search_count = ids.length;
                        }
                    }
                    return count_prm.then(function(count) {
                        this.screen_container.but_next.prop('disabled',
                            !(this.limit !== undefined &&
                                ids.length == this.limit &&
                                count > this.limit + this.offset));
                        this.screen_container.but_prev.prop('disabled', this.offset <= 0);
                        if (only_ids) {
                            return ids;
                        }
                        this.clear();
                        return this.load(ids).then(function() {
                            this.count_tab_domain();
                        }.bind(this));
                    }.bind(this));
                }.bind(this));
        },
        search_domain: function(search_string, set_text) {
            set_text = set_text || false;
            var domain = [];

            // Test first parent to avoid calling unnecessary domain_parser
            if (!this.group.parent && this.domain_parser) {
                var domain_parser = this.domain_parser;
                if (search_string || search_string === '') {
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
                if (!jQuery.isEmptyObject(this.attributes.domain)) {
                    domain = ['AND', domain, this.attributes.domain];
                }
            } else {
                domain = this.attributes.domain || [];
            }
            if (this.screen_container.but_active.hasClass('active')) {
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
            return domain;
        },
        count_tab_domain: function() {
            var screen_domain = this.search_domain(
                this.screen_container.get_text());
            this.screen_container.tab_domain.forEach(function(tab_domain, i) {
                if (tab_domain[2]) {
                    var domain = ['AND', tab_domain[1], screen_domain];
                    this.screen_container.set_tab_counter(null, i);
                    this.group.model.execute(
                        'search_count', [domain], this.context)
                        .then(function(count) {
                            this.screen_container.set_tab_counter(count, i);
                        }.bind(this));
                }
            }.bind(this));
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
            this.order = null;
            this.group = group;
            this.model = group.model;
            if (group && group.length) {
                this.current_record = group[0];
            } else {
                this.current_record = null;
            }
            this.group.add_fields(fields);
            var views_add = function(view) {
                this.group.model.fields[name].views.add(view);
            }.bind(this);
            for (name in fields_views) {
                var views = fields_views[name];
                views.forEach(views_add);
            }
            this.group.exclude_field = this.exclude_field;
        },
        new_group: function(context) {
            if (!context) {
                context = this.context;
            }
            var group = new Sao.Group(this.model, context, []);
            group.readonly = this.attributes.readonly || false;
            this.set_group(group);
        },
        get current_record() {
            return this.__current_record;
        },
        set current_record(record) {
            this.__current_record = record;
            if (this.message_callback){
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
                var data = [pos || 0, this.group.length + this.offset,
                    this.search_count, record_id];
                this.message_callback(data);
            }
            if (this.switch_callback) {
                this.switch_callback();
            }
            if (this.tab) {
                if (record) {
                    record.get_resources().always(
                        this.tab.update_resources.bind(this.tab));
                } else {
                    this.tab.update_resources();
                }
                this.tab.record_message();
            }
        },
        load: function(ids, set_cursor, modified) {
            if (set_cursor === undefined) {
                set_cursor = true;
            }
            this.tree_states = {};
            this.tree_states_done = [];
            this.group.load(ids, modified);
            if (ids.length && this.current_view.view_type != 'calendar') {
                this.current_record = this.group.get(ids[0]);
            } else {
                this.current_record = null;
            }
            return this.display().then(function() {
                if (set_cursor) {
                    this.set_cursor();
                }
            }.bind(this));
        },
        display: function(set_cursor) {
            var deferreds = [];
            if (this.current_record &&
                    ~this.current_record.group.indexOf(this.current_record)) {
            } else if (this.group && this.group.length &&
                    (this.current_view.view_type != 'calendar')) {
                this.current_record = this.group[0];
            } else {
                this.current_record = null;
            }
            if (this.views) {
                var search_prm = this.search_active(
                        ~['tree', 'graph', 'calendar'].indexOf(
                            this.current_view.view_type));
                deferreds.push(search_prm);
                for (var i = 0; i < this.views.length; i++) {
                    if (this.views[i] &&
                        ((this.views[i] == this.current_view) ||
                            this.views[i].el.parent().length)) {
                        deferreds.push(this.views[i].display());
                    }
                }
            }
            return jQuery.when.apply(jQuery, deferreds).then(function() {
                return this.set_tree_state().then(function() {
                    this.current_record = this.current_record;
                    // set_cursor must be called after set_tree_state because
                    // set_tree_state redraws the tree
                    if (set_cursor) {
                        this.set_cursor(false, false);
                    }
                }.bind(this));
            }.bind(this));
        },
        display_next: function() {
            var view = this.current_view;
            view.set_value();
            this.set_cursor(false, false);
            if (~['tree', 'form', 'list-form'].indexOf(view.view_type) &&
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
                this.current_record = record;
            } else {
                this.current_record = this.group[0];
            }
            this.set_cursor(false, false);
            return view.display();
        },
        display_previous: function() {
            var view = this.current_view;
            view.set_value();
            this.set_cursor(false, false);
            if (~['tree', 'form', 'list-form'].indexOf(view.view_type) &&
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
                this.current_record = record;
            } else {
                this.current_record = this.group[0];
            }
            this.set_cursor(false, false);
            return view.display();
        },
        clear: function() {
            this.current_record = null;
            this.group.clear();
            this.views.map(function(view) {
                view.reset();
            });
        },
        default_row_activate: function() {
            if ((this.current_view.view_type == 'tree') &&
                    (this.current_view.attributes.keyword_open == 1)) {
                Sao.Action.exec_keyword('tree_open', {
                    'model': this.model_name,
                    'id': this.get_id(),
                    'ids': [this.get_id()]
                }, this.local_context, false);
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
        new_: function(default_, rec_name) {
            var previous_view = this.current_view;
            if (default_ === undefined) {
                default_ = true;
            }
            var prm = jQuery.when();
            if (this.current_view.view_type == 'calendar') {
                var selected_date = this.current_view.get_selected_date();
                prm = this.switch_view('form', undefined, false);
            }
            if (this.current_view &&
                    ((this.current_view.view_type == 'tree' &&
                      !this.current_view.editable) ||
                     this.current_view.view_type == 'graph')) {
                prm = this.switch_view('form', undefined, false);
            }
            return prm.then(function() {
                var group;
                if (this.current_record) {
                    group = this.current_record.group;
                } else {
                    group = this.group;
                }
                var record = group.new_(false, undefined, rec_name);
                var prm;
                if (default_) {
                    prm = record.default_get(rec_name);
                } else {
                    prm = jQuery.when();
                }
                return prm.then(function() {
                    group.add(record, this.new_position);
                    this.current_record = record;
                    if (previous_view.view_type == 'calendar') {
                        previous_view.set_default_date(record, selected_date);
                    }
                    this.display().done(function() {
                        this.set_cursor(true, true);
                    }.bind(this));
                    return record;
                }.bind(this));
            }.bind(this));
        },
        get new_position() {
            if (this.order) {
                for (var j = 0; j < this.order.length; j++) {
                    var oexpr = this.order[j][0],
                        otype = this.order[j][1];
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
                if ((this.current_view.view_type == 'tree') &&
                        this.group && this.group.length) {
                    this.current_record = this.group[0];
                    current_record = this.current_record;
                } else {
                    return jQuery.when();
                }
            }
            this.current_view.set_value();
            var fields = this.current_view.get_fields();
            var path = current_record.get_path(this.group);
            var prm = jQuery.Deferred();
            if (this.current_view.view_type == 'tree') {
                prm = this.group.save().then(function() {
                    return this.current_record;
                }.bind(this));
            } else if (current_record.validate(fields, null, null, true)) {
                prm = current_record.save().then(function() {
                    return current_record;
                });
            } else {
                return this.current_view.display().then(function() {
                    this.set_cursor();
                    return jQuery.Deferred().reject();
                }.bind(this));
            }
            var display = function() {
                // Return the original promise to keep succeed/rejected state
                return this.display().then(function() {
                    return prm;
                }, function() {
                    return prm;
                });
            }.bind(this);
            return prm.then(function(current_record) {
                if (path && current_record && current_record.id) {
                    path.splice(-1, 1,
                            [path[path.length - 1][0], current_record.id]);
                }
                return this.group.get_by_path(path).then(function(record) {
                    this.current_record = record;
                }.bind(this));
            }.bind(this)).then(display, display);
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
                return (record.has_changed() || record.id < 0);
            };
            if (this.current_view.view_type != 'tree') {
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
            if (this.current_view.modified) {
                return true;
            }
            return false;
        },
        unremove: function() {
            var records = this.current_view.selected_records;
            records.forEach(function(record) {
                record.group.unremove(record);
            });
        },
        remove: function(delete_, remove, force_remove, records) {
            var prm = jQuery.when();
            records = records || this.current_view.selected_records;
            if (jQuery.isEmptyObject(records)) {
                return prm;
            }
            if (delete_) {
                // TODO delete children before parent
                prm = this.group.delete_(records);
            }
            var top_record = records[0];
            var top_group = top_record.group;
            var idx = top_group.indexOf(top_record);
            var path = top_record.get_path(this.group);
            return prm.then(function() {
                records.forEach(function(record) {
                    record.group.remove(record, remove, true, force_remove);
                });
                var prms = [];
                if (delete_) {
                    records.forEach(function(record) {
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
                    });
                }
                if (idx > 0) {
                    var record = top_group[idx - 1];
                    path.splice(-1, 1, [path[path.length - 1][0], record.id]);
                } else {
                    path.splice(-1, 1);
                }
                if (!jQuery.isEmptyObject(path)) {
                    prms.push(this.group.get_by_path(path).then(function(record) {
                        this.current_record = record;
                    }.bind(this)));
                } else if (this.group.length) {
                    this.current_record = this.group[0];
                }

                return jQuery.when.apply(jQuery, prms).then(function() {
                    this.display().done(function() {
                        this.set_cursor();
                    }.bind(this));
                }.bind(this));
            }.bind(this));
        },
        copy: function() {
            var dfd = jQuery.Deferred();
            var records = this.current_view.selected_records;
            this.model.copy(records, this.context)
                .then(function(new_ids) {
                this.group.load(new_ids);
                if (!jQuery.isEmptyObject(new_ids)) {
                    this.current_record = this.group.get(new_ids[0]);
                }
                this.display().always(dfd.resolve);
            }.bind(this), dfd.reject);
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

            var set_selection = function(props) {
                return function(selection) {
                    props.selection = selection;
                };
            };
            for (var name in fields) {
                var props = fields[name];
                if ((props.type != 'selection') &&
                        (props.type != 'reference')) {
                    continue;
                }
                if (props.selection instanceof Array) {
                    continue;
                }
                this.get_selection(props).then(set_selection(props));
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
                            ['string', 'factor'].forEach(function(attr) {
                                if (node.getAttribute(attr)) {
                                    dom_fields[name][attr] = node.getAttribute(attr);
                                }
                            });
                        }
                    }
                });
                fields = dom_fields;
            }

            if ('active' in view_tree.fields) {
                this.screen_container.but_active.show();
            } else {
                this.screen_container.but_active.hide();
            }

            // Add common fields
            [
                ['id', Sao.i18n.gettext('ID'), 'integer'],
                ['create_uid', Sao.i18n.gettext('Created by'), 'many2one'],
                ['create_date', Sao.i18n.gettext('Created at'), 'datetime'],
                ['write_uid', Sao.i18n.gettext('Modified by'), 'many2one'],
                ['write_date', Sao.i18n.gettext('Modified at'), 'datetime']
                    ] .forEach(function(e) {
                        var name = e[0];
                        var string = e[1];
                        var type = e[2];
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
                    });

            domain_parser = new Sao.common.DomainParser(fields, this.context);
            this._domain_parser[view_id] = domain_parser;
            return domain_parser;
        },
        get_selection: function(props) {
            var prm;
            var change_with = props.selection_change_with;
            if (!jQuery.isEmptyObject(change_with)) {
                var values = {};
                change_with.forEach(function(p) {
                    values[p] = null;
                });
                prm = this.model.execute(props.selection,
                        [values]);
            } else {
                prm = this.model.execute(props.selection,
                        []);
            }
            return prm.then(function(selection) {
                return selection.sort(function(a, b) {
                    return a[1].localeCompare(b[1]);
                });
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
            Object.keys(invalid_fields).sort().forEach(
                function(field) {
                    var invalid = invalid_fields[field];
                    var string = record.model.fields[field].description.string;
                    if ((invalid == 'required') ||
                            (Sao.common.compare(invalid,
                                                [[field, '!=', null]]))) {
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
                });
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
            this.current_view.set_value();
            return this.current_record.get();
        },
        get_on_change_value: function() {
            if (!this.current_record) {
                return null;
            }
            this.current_view.set_value();
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
            return jQuery.when.apply(jQuery, promises).then(function() {
                this.display();
            }.bind(this));
        },
        get_buttons: function() {
            var selected_records = this.current_view.selected_records;
            if (jQuery.isEmptyObject(selected_records)) {
                return [];
            }
            var buttons = this.current_view.get_buttons();
            selected_records.forEach(function(record) {
                buttons = buttons.filter(function(button) {
                    if (button.attributes.type === 'instance') {
                        return false;
                    }
                    var states = record.expr_eval(
                        button.attributes.states || {});
                    return !(states.invisible || states.readonly);
                });
            });
            return buttons;
        },
        button: function(attributes) {
            var ids;
            var process_action = function(action) {
                return this.reload(ids, true).then(function() {
                    if (typeof action == 'string') {
                        this.client_action(action);
                    }
                    else if (action) {
                        Sao.Action.execute(action, {
                            model: this.model_name,
                            id: this.current_record.id,
                            ids: ids
                        }, null, this.context, true);
                    }
                }.bind(this));
            };

            var selected_records = this.current_view.selected_records;
            this.current_view.set_value();
            var fields = this.current_view.get_fields();

            var prms = [];
            var reset_state = function(record) {
                return function() {
                    this.display(true);
                    // Reset valid state with normal domain
                    record.validate(fields);
                }.bind(this);
            }.bind(this);
            for (var i = 0; i < selected_records.length; i++) {
                var record = selected_records[i];
                var domain = record.expr_eval(
                    (attributes.states || {})).pre_validate || [];
                prms.push(record.validate(fields, false, domain));
            }
            return jQuery.when.apply(jQuery, prms).then(function() {
                var record;
                for (var i = 0; i < selected_records.length; i++) {
                    record = selected_records[i];
                    var result = arguments[i];
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
                return prm.then(function() {
                    var record = this.current_record;
                    if (attributes.type === 'instance') {
                        var args = record.expr_eval(attributes.change || []);
                        var values = record._get_on_change_args(args);
                        return record.model.execute(attributes.name, [values],
                            this.context).then(function(changes) {
                            record.set_on_change(changes);
                            record.group.root_group.screens.forEach(
                                function(screen) {
                                    screen.display();
                            });
                        });
                    } else {
                        return record.save(false).then(function() {
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
                                [ids], context).then(process_action.bind(this));
                        }.bind(this));
                    }
                }.bind(this));
            }.bind(this));
        },
        client_action: function(action) {
            var access = Sao.common.MODELACCESS.get(this.model_name);
            if (action == 'new') {
                if (access.create) {
                    this.new_();
                }
            } else if (action == 'delete') {
                if (access['delete']) {
                    this.remove(!this.group.parent, false, !this.group.parent);
                }
            } else if (action == 'remove') {
                if (access.write && access.read && this.group.parent) {
                    this.remove(false, true, false);
                }
            } else if (action == 'copy') {
                if (access.create) {
                    this.copy();
                }
            } else if (action == 'next') {
                this.display_next();
            } else if (action == 'previous') {
                this.display_previous();
            } else if (action == 'close') {
                Sao.Tab.close_current();
            } else if (action.startsWith('switch')) {
                this.switch_view.apply(this, action.split(' ', 3).slice(1));
            } else if (action == 'reload') {
                if (~['tree', 'graph', 'calendar'].indexOf(this.current_view.view_type) &&
                        !this.group.parent) {
                    this.search_filter();
                }
            } else if (action == 'reload menu') {
                Sao.Session.current_session.reload_context()
                    .then(function() {
                        Sao.menu();
                    });
            } else if (action == 'reload context') {
                Sao.Session.current_session.reload_context();
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
            if (!jQuery.isEmptyObject(this.attributes.tab_domain)) {
                query_string.push([
                    'tab_domain', dumps(this.attributes.tab_domain)]);
            }
            var path = ['model', this.model_name];
            var view_ids = this.views.map(
                function(v) {return v.view_id;}).concat(this.view_ids);
            if (this.current_view.view_type != 'form') {
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
                var i = view_ids.indexOf(this.current_view.view_id);
                view_ids = view_ids.slice(i).concat(view_ids.slice(0, i));
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
        save_tree_state: function(store) {
            var prms = [];
            var prm;
            store = (store === undefined) ? true : store;
            var i, len, view, widgets, wi, wlen;
            var parent_ = this.group.parent ? this.group.parent.id : null;
            for (i = 0, len = this.views.length; i < len; i++) {
                view = this.views[i];
                if (view.view_type == 'form') {
                    for (var wid_key in view.widgets) {
                        if (!view.widgets.hasOwnProperty(wid_key)) {
                            continue;
                        }
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
                } else if (view.view_type == 'tree') {
                    var paths = view.get_expanded_paths();
                    var selected_paths = view.get_selected_paths();
                    if (!(parent_ in this.tree_states)) {
                        this.tree_states[parent_] = {};
                    }
                    this.tree_states[parent_][view.children_field || null] = [
                        paths, selected_paths];
                    if (store && view.attributes.tree_state) {
                        var tree_state_model = new Sao.Model(
                                'ir.ui.view_tree_state');
                        prm = tree_state_model.execute('set', [
                                this.model_name,
                                this.get_tree_domain(parent_),
                                view.children_field,
                                JSON.stringify(paths),
                                JSON.stringify(selected_paths)], {});
                        prms.push(prm);
                    }
                }
            }
            return jQuery.when.apply(jQuery, prms).then(function() {
                Sao.Session.current_session.cache.clear(
                    'model.ir.ui.view_tree_state.get');
            });
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
            if (!~['tree', 'form'].indexOf(view.view_type)) {
                return jQuery.when();
            }

            if (~this.tree_states_done.indexOf(view)) {
                return jQuery.when();
            }
            if (view.view_type == 'form' &&
                    !jQuery.isEmptyObject(this.tree_states_done)) {
                return jQuery.when();
            }
            if (view.view_type == 'tree' && !view.attributes.tree_state) {
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
            if (state === undefined) {
                tree_state_model = new Sao.Model('ir.ui.view_tree_state');
                state_prm = tree_state_model.execute('get', [
                        this.model_name,
                        this.get_tree_domain(parent_),
                        view.children_field], {})
                    .then(function(state) {
                        state = [JSON.parse(state[0]), JSON.parse(state[1])];
                        if (!(parent_ in this.tree_states)) {
                            this.tree_states[parent_] = {};
                        }
                        this.tree_states[parent_][view.children_field || null] = state;
                        return state;
                    }.bind(this));
            } else {
                state_prm = jQuery.when(state);
            }
            this.tree_states_done.push(view);
            return state_prm.done(function(state) {
                var expanded_nodes, selected_nodes, record;
                expanded_nodes = state[0];
                selected_nodes = state[1];
                if (view.view_type == 'tree') {
                    return view.display(selected_nodes, expanded_nodes);
                } else {
                    if (!jQuery.isEmptyObject(selected_nodes)) {
                        for (var i = 0; i < selected_nodes[0].length; i++) {
                            var new_record = this.group.get(selected_nodes[0][i]);
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
            }.bind(this));
        }
    });
}());
