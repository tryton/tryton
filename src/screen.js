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
            this.el = jQuery('<div/>', {
                'class': 'screen-container'
            });
            this.filter_box = jQuery('<div/>', {
                'class': 'row filter-box'
            });
            this.el.append(this.filter_box);
            this.filter_button = jQuery('<button/>', {
                type: 'button',
                'class': 'btn btn-default'
            }).append(Sao.i18n.gettext('Filters'));
            this.filter_button.click(this.search_box.bind(this));
            this.search_entry = jQuery('<input/>', {
                'class': 'form-control',
                'placeholder': Sao.i18n.gettext('Search')
            });
            this.search_list = jQuery('<datalist/>');
            this.search_list.uniqueId();
            this.search_entry.attr('list', this.search_list.attr('id'));
            this.search_entry.keypress(this.key_press.bind(this));
            this.search_entry.on('input', this.update.bind(this));

            this.but_bookmark = jQuery('<button/>', {
                type: 'button',
                'class': 'btn btn-default dropdown-toggle',
                'data-toggle': 'dropdown',
                'aria-expanded': false,
                'aria-label': Sao.i18n.gettext('Bookmarks'),
                'id': 'bookmarks'
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-bookmark',
                'aria-hidden': true
            }));
            var dropdown_bookmark = jQuery('<ul/>', {
                'class': 'dropdown-menu',
                'role': 'menu',
                'aria-labelledby': 'bookmarks'
            });
            this.but_bookmark.click(function() {
                dropdown_bookmark.children().remove();
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
                'class': 'btn btn-default',
            }).append(jQuery('<span/>', {
                'class': 'glyphicon',
                'aria-hidden': true
            })).click(this.star_click.bind(this));
            this.set_star();

            jQuery('<div/>', {
                'class': 'input-group'
            })
            .append(jQuery('<span/>', {
                'class': 'input-group-btn'
            }).append(this.filter_button))
            .append(this.search_entry)
            .append(this.search_list)
            .append(jQuery('<span/>', {
                'class': 'input-group-btn'
            }).append(this.but_star)
                    .append(this.but_bookmark)
                    .append(dropdown_bookmark))
            .appendTo(jQuery('<div/>', {
                'class': 'col-md-8'
            }).appendTo(this.filter_box));


            this.but_prev = jQuery('<button/>', {
                type: 'button',
                'class': 'btn btn-default',
                'aria-label': Sao.i18n.gettext('Previous')
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-menu-left',
                'aria-hidden': true
            }));
            this.but_prev.click(this.search_prev.bind(this));
            this.but_next = jQuery('<button/>', {
                type: 'button',
                'class': 'btn btn-default',
                'aria-label': Sao.i18n.gettext('Next')
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-menu-right',
                'aria-hidden': true
            }));
            this.but_next.click(this.search_next.bind(this));

            jQuery('<div/>', {
                'class': 'btn-group',
                role: 'group',
            })
            .append(this.but_prev)
            .append(this.but_next)
            .appendTo(jQuery('<div/>', {
                'class': 'col-md-4'
            }).appendTo(this.filter_box));

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
                    var page = jQuery('<li/>', {
                        role: 'presentation',
                        id: 'nav-' + i
                    }).append(jQuery('<a/>', {
                        'aria-controls':  i,
                        role: 'tab',
                        'data-toggle': 'tab',
                        'href': '#' + i
                    }).append(name)).appendTo(nav);
                }.bind(this));
                nav.find('a:first').tab('show');
                var self = this;
                nav.find('a').click(function(e) {
                    e.preventDefault();
                    jQuery(this).tab('show');
                    self.do_search();
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
            var completions = this.screen.domain_parser().completion(
                    this.get_text());
            this.search_list.children().remove();
            completions.forEach(function(e) {
                jQuery('<option/>', {
                    'value': e.trim()
                }).appendTo(this.search_list);
            }, this);
        },
        set_star: function(star) {
            var glyphicon = this.but_star.children('span.glyphicon');
            if (star) {
                glyphicon.removeClass('glyphicon-star-empty');
                glyphicon.addClass('glyphicon-star');
                this.but_star.attr('aria-label',
                        Sao.i18n.gettext('Remove this bookmark'));
            } else {
                glyphicon.removeClass('glyphicon-star');
                glyphicon.addClass('glyphicon-star-empty');
                this.but_star.attr('aria-label',
                       Sao.i18n.gettext('Bookmark this filter'));
            }
        },
        get_star: function() {
            var glyphicon = this.but_star.children('span.glyphicon');
            return glyphicon.hasClass('glyphicon-star');
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
                        var domain = this.screen.domain_parser().parse(text);
                        Sao.common.VIEW_SEARCH.add(model_name, name, domain)
                        .then(function() {
                            refresh();
                        });
                        this.set_text(
                            this.screen.domain_parser().string(domain));
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
                return this.screen.domain_parser().stringable(search[2]);
            }.bind(this));
        },
        bookmark_activate: function(e) {
            var domain = e.data;
            this.set_text(this.screen.domain_parser().string(domain));
            this.do_search();
        },
        bookmark_match: function() {
            var current_text = this.get_text();
            var current_domain = this.screen.domain_parser().parse(current_text);
            this.but_star.prop('disabled', !current_text);
            var star = this.get_star();
            var bookmarks = this.bookmarks();
            for (var i=0; i < bookmarks.length; i++) {
                var id = bookmarks[i][0];
                var name = bookmarks[i][1];
                var domain = bookmarks[i][2];
                var text = this.screen.domain_parser().string(domain);
                if ((text === current_text) ||
                        (Sao.common.compare(domain, current_domain))) {
                    this.set_star(true);
                    return id;
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
        get_tab_domain: function() {
            if (!this.tab) {
                return [];
            }
            var i = this.tab.find('li').index(this.tab.find('li.active'));
            return this.tab_domain[i][1];
        },
        do_search: function() {
            return this.screen.search_filter(this.get_text());
        },
        key_press: function(e) {
            if (e.which == Sao.common.RETURN_KEYCODE) {
                this.do_search();
                return false;
            }
            // Wait the current event finished
            window.setTimeout(function() {
                this.bookmark_match();
            }.bind(this));
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
            var domain_parser = this.screen.domain_parser();
            var search = function() {
                this.search_modal.modal('hide');
                var text = '';
                var quote = domain_parser.quote.bind(domain_parser);
                for (var i = 0; i < this.search_form.fields.length; i++) {
                    var label = this.search_form.fields[i][0];
                    var entry = this.search_form.fields[i][1];
                    var value;
                    switch(entry.type) {
                        case 'selection':
                        case 'date':
                        case 'datetime':
                        case 'time':
                            value = entry.get_value(quote);
                            break;
                        default:
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
                    if (field.searchable || field.searchable === undefined) {
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
                            entry = new Sao.ScreenContainer.Selection(
                                    field.selection, prefix + field.name);
                            input = entry.el;
                            break;
                        case 'date':
                        case 'datetime':
                        case 'time':
                            var format;
                            var date_format = Sao.common.date_format();
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
                    this.search_form.fields.push([field.string, entry]);
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
                this.search_form.fields[0][1].focus();
            }
        }
    });

    Sao.ScreenContainer.DateTimes = Sao.class_(Object, {
        type: 'date',
        init: function(format, id) {
            this.el = jQuery('<div/>', {
                'class': 'row',
                id: id
            });
            var build_entry = function(placeholder) {
                var entry = jQuery('<div/>', {
                    'class': 'input-group input-group-sm'
                });
                jQuery('<input/>', {
                    'class': 'form-control input-sm',
                    type: 'text',
                    placeholder: placeholder,
                    id: id + '-from'
                }).appendTo(entry);
                jQuery('<span/>', {
                    'class': 'input-group-btn'
                }).append(jQuery('<button/>', {
                    'class': 'btn btn-default',
                    type: 'button'
                }).append(jQuery('<span/>', {
                    'class': 'glyphicon glyphicon-calendar'
                }))).appendTo(entry);
                entry.datetimepicker();
                entry.data('DateTimePicker').format(format);
                return entry;
            };
            this.from = build_entry('From').appendTo(jQuery('<div/>', {
                'class': 'col-md-5'
            }).appendTo(this.el));
            jQuery('<p/>', {
                'class': 'text-center'
            }).append('..').appendTo(jQuery('<div/>', {
                'class': 'col-md-1'
            }).appendTo(this.el));
            this.to = build_entry('To').appendTo(jQuery('<div/>', {
                'class': 'col-md-5'
            }).appendTo(this.el));
        },
        _get_value: function(entry) {
            return entry.find('input').val();
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
        set_value: function(from, to) {
            this.from.data('DateTimePicker').date(from);
            this.to.data('DateTimePicker').date(to);
        }
    });

    Sao.ScreenContainer.Selection = Sao.class_(Object, {
        type: 'selection',
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
            if (value) {
                value = jQuery.map(value, quote).reduce(function(a, b) {
                    if (a) {a += ';';}
                    return a + b;
                });
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
            this.attributes.limit = this.attributes.limit || Sao.config.limit;
            this.view_ids = jQuery.extend([], attributes.view_ids);
            this.view_to_load = jQuery.extend([],
                attributes.mode || ['tree', 'form']);
            this.views = [];
            this.views_preload = attributes.views_preload || {};
            this.exclude_field = attributes.exclude_field;
            this.context = attributes.context || {};
            this.new_group();
            this.current_view = null;
            this.current_record = null;
            this.domain = attributes.domain || [];
            this.size_limit = null;
            this.limit = attributes.limit || Sao.config.limit;
            this.offset = 0;
            var access = Sao.common.MODELACCESS.get(model_name);
            if (!(access.write || access.create)) {
                this.attributes.readonly = true;
            }
            this.search_count = 0;
            this.screen_container = new Sao.ScreenContainer(
                attributes.tab_domain);
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
            this.model.add_fields(fields);
            var view_widget = Sao.View.parse(this, xml_view, view.field_childs);
            view_widget.view_id = view_id;
            this.views.push(view_widget);

            return view_widget;
        },
        number_of_views: function() {
            return this.views.length + this.view_to_load.length;
        },
        switch_view: function(view_type) {
            if (this.current_view) {
                if (!this.group.parent && this.modified()) {
                    return jQuery.when();
                }
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
            var _switch = function() {
                if ((!view_type) || (!this.current_view) ||
                        (this.current_view.view_type != view_type)) {
                    var switch_current_view = (function() {
                        this.current_view = this.views[this.views.length - 1];
                        return _switch();
                    }.bind(this));
                    for (var i = 0; i < this.number_of_views(); i++) {
                        if (this.view_to_load.length) {
                            if (!view_type) {
                                view_type = this.view_to_load[0];
                            }
                            return this.load_next_view().then(
                                    switch_current_view);
                        }
                        this.current_view = this.views[
                            (this.views.indexOf(this.current_view) + 1) %
                            this.views.length];
                        if (!view_type) {
                            break;
                        } else if (this.current_view.view_type == view_type) {
                            break;
                        }
                    }
                }
                this.screen_container.set(this.current_view.el);
                return this.display().done(function() {
                    this.set_cursor();
                }.bind(this));
            }.bind(this);
            return _switch();
        },
        search_filter: function(search_string) {
            var domain = [];
            var domain_parser = this.domain_parser();

            if (domain_parser && !this.group.parent) {
                if (search_string || search_string === '') {
                    domain = domain_parser.parse(search_string);
                } else {
                    domain = this.attributes.search_value;
                }
                this.screen_container.set_text(
                        domain_parser.string(domain));
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

            var tab_domain = this.screen_container.get_tab_domain();
            if (!jQuery.isEmptyObject(tab_domain)) {
                domain = ['AND', domain, tab_domain];
            }

            var grp_prm = this.model.find(domain, this.offset, this.limit,
                    this.attributes.order, this.context);
            var count_prm = this.model.execute('search_count', [domain],
                    this.context);
            count_prm.done(function(count) {
                this.search_count = count;
            }.bind(this));
            grp_prm.done(this.set_group.bind(this));
            grp_prm.done(this.display.bind(this));
            jQuery.when(grp_prm, count_prm).done(function(group, count) {
                this.screen_container.but_next.prop('disabled',
                        !(group.length == this.limit &&
                            count > this.limit + this.offset));
            }.bind(this));
            this.screen_container.but_prev.prop('disabled', this.offset <= 0);
            return grp_prm;
        },
        set_group: function(group) {
            if (this.group) {
                jQuery.extend(group.model.fields, this.group.model.fields);
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
            this.group = group;
            this.model = group.model;
            if (jQuery.isEmptyObject(group)) {
                this.set_current_record(null);
            } else {
                this.set_current_record(group[0]);
            }
        },
        new_group: function(ids) {
            var group = new Sao.Group(this.model, this.context, []);
            group.set_readonly(this.attributes.readonly || false);
            if (ids) {
                group.load(ids);
            }
            this.set_group(group);
        },
        set_current_record: function(record) {
            this.current_record = record;
            // TODO position
            if (this.tab) {
                if (record) {
                    record.get_attachment_count().always(
                            this.tab.attachment_count.bind(this.tab));
                } else {
                    this.tab.attachment_count(0);
                }
                this.tab.record_message();
            }
        },
        display: function(set_cursor) {
            var deferreds = [];
            if (this.current_record &&
                    ~this.current_record.group.indexOf(this.current_record)) {
            } else if (!jQuery.isEmptyObject(this.group) &&
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
                    if (this.views[i]) {
                        deferreds.push(this.views[i].display());
                    }
                }
            }
            return jQuery.when.apply(jQuery, deferreds).then(function() {
                this.set_tree_state();
                this.set_current_record(this.current_record);
                // set_cursor must be called after set_tree_state because
                // set_tree_state redraws the tree
                if (set_cursor) {
                    this.set_cursor(false, false);
                }
            }.bind(this));
        },
        display_next: function() {
            var view = this.current_view;
            view.set_value();
            this.set_cursor(false, false);
            if (~['tree', 'form'].indexOf(view.view_type) &&
                    this.current_record && this.current_record.group) {
                var group = this.current_record.group;
                var record = this.current_record;
                while (group) {
                    var index = group.indexOf(record);
                    if (index < group.length - 1) {
                        record = group[index + 1];
                        break;
                    } else if (group.parent &&
                            (record.group.model_name ==
                             group.parent.group.model_name)) {
                        record = group.parent;
                        group = group.parent.group;
                    } else {
                        break;
                    }
                }
                this.set_current_record(record);
            } else {
                this.set_current_record(this.group[0]);
            }
            this.set_cursor(false, false);
            view.display();
        },
        display_previous: function() {
            var view = this.current_view;
            view.set_value();
            this.set_cursor(false, false);
            if (~['tree', 'form'].indexOf(view.view_type) &&
                    this.current_record && this.current_record.group) {
                var group = this.current_record.group;
                var record = this.current_record;
                while (group) {
                    var index = group.indexOf(record);
                    if (index > 0) {
                        record = group[index - 1];
                        break;
                    } else if (group.parent &&
                            (record.group.model_name ==
                             group.parent.group.model_name)) {
                        record = group.parent;
                        group = group.parent.group;
                    } else {
                        break;
                    }
                }
                this.set_current_record(record);
            } else {
                this.set_current_record(this.group[0]);
            }
            this.set_cursor(false, false);
            view.display();
        },
        default_row_activate: function() {
            if ((this.current_view.view_type == 'tree') &&
                    (this.current_view.attributes.keyword_open == 1)) {
                Sao.Action.exec_keyword('tree_open', {
                    'model': this.model_name,
                    'id': this.get_id(),
                    'ids': [this.get_id()]
                    }, jQuery.extend({}, this.context), false);
            } else {
                this.switch_view('form');
            }
        },
        get_id: function() {
            if (this.current_record) {
                return this.current_record.id;
            }
        },
        new_: function(default_) {
            if (default_ === undefined) {
                default_ = true;
            }
            var prm = jQuery.when();
            if (this.current_view &&
                    ((this.current_view.view_type == 'tree' &&
                      !this.current_view.editable) ||
                     this.current_view.view_type == 'graph')) {
                prm = this.switch_view('form');
            }
            return prm.then(function() {
                var group;
                if (this.current_record) {
                    group = this.current_record.group;
                } else {
                    group = this.group;
                }
                var record = group.new_(default_);
                group.add(record, this.new_model_position());
                this.set_current_record(record);
                this.display().done(function() {
                    this.set_cursor(true, true);
                }.bind(this));
                return record;
            }.bind(this));
        },
        new_model_position: function() {
            var position = -1;
            if (this.current_view && (this.current_view.view_type == 'tree') &&
                    (this.current_view.attributes.editable == 'top')) {
                position = 0;
            }
            return position;
        },
        set_on_write: function(name) {
            if(name) {
                if (!~this.group.on_write.indexOf(name)) {
                    this.group.on_write.push(name);
                }
            }
        },
        cancel_current: function() {
            var prms = [];
            if (this.current_record) {
                this.current_record.cancel();
                if (this.current_record.id < 0) {
                    prms.push(this.remove());
                }
            }
            return jQuery.when.apply(jQuery, prms);
        },
        save_current: function() {
            var current_record = this.current_record;
            if (!current_record) {
                if ((this.current_view.view_type == 'tree') &&
                        (!jQuery.isEmptyObject(this.group))) {
                    this.set_current_record(this.group[0]);
                } else {
                    return jQuery.when();
                }
            }
            this.current_view.set_value();
            var fields = this.current_view.get_fields();
            var path = current_record.get_path(this.group);
            var prm = jQuery.Deferred();
            if (this.current_view.view_type == 'tree') {
                prm = this.group.save();
            } else {
                current_record.validate(fields).then(function(validate) {
                    if (validate) {
                        current_record.save().then(
                            prm.resolve, prm.reject);
                    } else {
                        this.current_view.display().done(
                                this.set_cursor.bind(this));
                        prm.reject();
                    }
                }.bind(this));
            }
            var dfd = jQuery.Deferred();
            prm = prm.then(function() {
                if (path && current_record.id) {
                    path.splice(-1, 1,
                            [path[path.length - 1][0], current_record.id]);
                }
                return this.group.get_by_path(path).then(function(record) {
                    this.set_current_record(record);
                }.bind(this));
            }.bind(this));
            prm.then(function() {
                this.display().always(dfd.resolve);
            }.bind(this), function() {
                this.display().always(dfd.reject);
            }.bind(this));
            return dfd.promise();
        },
        set_cursor: function(new_, reset_view) {
            if (!this.current_view) {
                return;
            } else if (~['tree', 'form'].indexOf(this.current_view.view_type)) {
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
            // TODO test view modified
            return false;
        },
        unremove: function() {
            var records = this.current_view.selected_records();
            records.forEach(function(record) {
                record.group.unremove(record);
            });
        },
        remove: function(delete_, remove, force_remove) {
            var records = null;
            if ((this.current_view.view_type == 'form') &&
                    this.current_record) {
                records = [this.current_record];
            } else if (this.current_view.view_type == 'tree') {
                records = this.current_view.selected_records();
            }
            if (jQuery.isEmptyObject(records)) {
                return;
            }
            var prm = jQuery.when();
            if (delete_) {
                // TODO delete children before parent
                prm = this.model.delete_(records);
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
                        this.set_current_record(record);
                    }.bind(this)));
                } else if (this.group.length) {
                    this.set_current_record(this.group[0]);
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
            var records = this.current_view.selected_records();
            this.model.copy(records, this.context).then(function(new_ids) {
                this.group.load(new_ids);
                if (!jQuery.isEmptyObject(new_ids)) {
                    this.set_current_record(this.group.get(new_ids[0]));
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
        domain_parser: function() {
            var view_id, view_tree;
            if (this.current_view) {
                view_id = this.current_view.view_id;
            } else {
                view_id = null;
            }
            if (view_id in this._domain_parser) {
                return this._domain_parser[view_id];
            }
            if (!(view_id in this.fields_view_tree)) {
                // Fetch default view for the next time
                this.model.execute('fields_view_get', [false, 'tree'],
                        this.context).then(function(view) {
                    this.fields_view_tree[view_id] = view;
                }.bind(this));
                view_tree = {};
                view_tree.fields = {};
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
                var xml_fields = xml_view.find('tree').children()
                    .filter(function(node) {
                        return node.tagName == 'field';
                    }).map(function(node) {
                        return node.getAttribute('name');
                    });
                var dom_fields = {};
                xml_fields.each(function(name) {
                    dom_fields[name] = fields[name];
                });
            }

            // Add common fields
            [
                ['id', Sao.i18n.gettext('ID'), 'integer'],
                ['create_uid', Sao.i18n.gettext('Creation User'),
                    'many2one'],
                ['create_date', Sao.i18n.gettext('Creation Date'),
                    'datetime'],
                ['write_uid', Sao.i18n.gettext('Modification User'),
                     'many2one'],
                ['write_date', Sao.i18n.gettext('Modification Date'),
                     'datetime']
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
            if (!('id' in fields)) {
                fields.id = {
                    'string': Sao.i18n.gettext('ID'),
                    'name': 'id',
                    'type': 'integer'
                };
            }

            var context = jQuery.extend({},
                    this.model.session.context,
                    this.context);
            var domain_parser = new Sao.common.DomainParser(
                    fields, context);
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
            this.offset -= this.limit;
            this.search_filter(search_string);
        },
        search_next: function(search_string) {
            this.offset += this.limit;
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
                        fields.push(Sao.i18n.gettext('"%1" is required', string));
                    } else if (invalid == 'domain') {
                        fields.push(Sao.i18n.gettext(
                                    '"%1" is not valid according to its domain',
                                    string));
                    } else if (invalid == 'children') {
                        fields.push(Sao.i18n.gettext(
                                'The values of "%1" are not valid', string));
                    } else {
                        if (domain_parser.stringable(invalid)) {
                            fields.push(domain_parser.string(invalid));
                        } else {
                            fields.push(Sao.i18n.gettext(
                                    '"%1" is not valid according to its domain'),
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
            if (written) {
                this.group.written(ids);
            }
            if (this.group.parent) {
                this.group.parent.root_parent().reload();
            }
            this.display();
        },
        get_buttons: function() {
            var selected_records = this.current_view.selected_records();
            if (jQuery.isEmptyObject(selected_records)) {
                return [];
            }
            var buttons = this.current_view.get_buttons();
            selected_records.forEach(function(record) {
                buttons = buttons.filter(function(button) {
                    if (record.group.get_readonly() || record.readonly()) {
                        return false;
                    }
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
                this.reload(ids, true);
                if (typeof action == 'string') {
                    this.client_action(action);
                }
                else if (action) {
                    Sao.Action.execute(action, {
                        model: this.model_name,
                        id: this.current_record.id,
                        ids: ids
                    }, null, this.context);
                }
            };

            var selected_records = this.current_view.selected_records();
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
            jQuery.when.apply(jQuery, prms).then(function() {
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

                // TODO confirm
                record = this.current_record;
                if (attributes.type === 'instance') {
                    var args = record.expr_eval(attributes.change || []);
                    var values = record._get_on_change_args(args);
                    record.model.execute(attributes.name, [values], this.context)
                        .then(function(changes) {
                            record.set_on_change(changes);
                            record.group.root_group().screens.forEach(function(screen) {
                                screen.display();
                            });
                        });
                } else {
                    record.save(false).done(function() {
                        var context = jQuery.extend({}, this.context);
                        context._timestamp = {};
                        ids = [];
                        for (i = 0; i < selected_records.length; i++) {
                            record = selected_records[i];
                            jQuery.extend(context._timestamp, record.get_timestamp());
                            ids.push(record.id);
                        }
                        record.model.execute(attributes.name,
                            [ids], context).then(process_action.bind(this));
                    }.bind(this));
                }
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
                var view_type = action.split(' ')[1];
                this.switch_view(view_type);
            } else if (action == 'reload') {
                if (~['tree', 'graph', 'calendar'].indexOf(this.current_view.view_type) &&
                        !this.group.parent) {
                    this.search_filter();
                }
            } else if (action == 'reload menu') {
                Sao.get_preferences().then(function(preferences) {
                    Sao.menu(preferences);
                });
            } else if (action == 'reload context') {
                Sao.get_preferences();
            }
        },
        save_tree_state: function(store) {
            var prms = [];
            var prm;
            store = (store === undefined) ? true : store;
            var i, len, view, widgets, wi, wlen;
            var parent_ = this.group.parent ? this.group.parent.id : null;
            var timestamp = this.group.parent ?
                this.group.parent._timestamp : null;
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
                            timestamp, [], [[this.current_record.id]]];
                    }
                } else if (view.view_type == 'tree') {
                    var paths = view.get_expanded_paths();
                    var selected_paths = view.get_selected_paths();
                    if (!(parent_ in this.tree_states)) {
                        this.tree_states[parent_] = {};
                    }
                    this.tree_states[parent_][view.children_field || null] = [
                        timestamp, paths, selected_paths];
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
            var parent_, timestamp, state, state_prm, tree_state_model;
            var view = this.current_view;
            if (!~['tree', 'form'].indexOf(view.view_type)) {
                return;
            }

            if (~this.tree_states_done.indexOf(view)) {
                return;
            }
            if (view.view_type == 'form' &&
                    !jQuery.isEmptyObject(this.tree_states_done)) {
                return;
            }

            parent_ = this.group.parent ? this.group.parent.id : null;
            timestamp = parent ? parent._timestamp : null;
            if (!(parent_ in this.tree_states)) {
                this.tree_states[parent_] = {};
            }
            state = this.tree_states[parent_][view.children_field || null];
            if (state) {
                if (timestamp != state[0]) {
                    state = undefined;
                }
            }
            if (state === undefined) {
                tree_state_model = new Sao.Model('ir.ui.view_tree_state');
                state_prm = tree_state_model.execute('get', [
                        this.model_name,
                        this.get_tree_domain(parent_),
                        view.children_field], {})
                    .then(function(state) {
                        return [timestamp,
                            JSON.parse(state[0]), JSON.parse(state[1])];
                    });
            } else {
                state_prm = jQuery.when(state);
            }
            state_prm.done(function(state) {
                var expanded_nodes, selected_nodes, record;
                this.tree_states[parent_][view.children_field || null] = state;
                expanded_nodes = state[1];
                selected_nodes = state[2];
                if (view.view_type == 'tree') {
                    view.display(selected_nodes, expanded_nodes);
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
                            this.set_current_record(record);
                            // Force a display of the view to synchronize the
                            // widgets with the new record
                            view.display();
                        }
                    }
                }
            }.bind(this));
            this.tree_states_done.push(view);
        }
    });
}());
