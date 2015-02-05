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
            }).append('Filters'); // TODO translation
            this.search_entry = jQuery('<input/>', {
                'class': 'form-control'
            });
            this.search_entry.keypress(function(e) {
                if (e.which == 13) {
                    this.do_search();
                    return false;
                }
            }.bind(this));
            this.but_bookmark = jQuery('<button/>', {
                type: 'button',
                'class': 'btn btn-default'
            }).append('Bookmark'); // TODO translation

            jQuery('<div/>', {
                'class': 'input-group'
            })
            .append(jQuery('<span/>', {
                'class': 'input-group-btn'
            }).append(this.filter_button))
            .append(this.search_entry)
            .append(jQuery('<span/>', {
                'class': 'input-group-btn'
            }).append(this.but_bookmark))
            .appendTo(jQuery('<div/>', {
                'class': 'col-md-8'
            }).appendTo(this.filter_box));

            this.but_prev = jQuery('<button/>', {
                type: 'button',
                'class': 'btn btn-default'
            }).append('Previous');
            this.but_prev.click(this.search_prev.bind(this));
            this.but_next = jQuery('<button/>', {
                type: 'button',
                'class': 'btn btn-default'
            }).append('Next');
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
        },
        search_prev: function() {
            this.screen.search_prev(this.search_entry.val());
        },
        search_next: function() {
            this.screen.search_next(this.search_entry.val());
        },
        get_tab_domain: function() {
            if (!this.tab) {
                return [];
            }
            var i = this.tab.find('li').index(this.tab.find('li.active'));
            return this.tab_domain[i][1];
        },
        do_search: function() {
            this.screen.search_filter(this.search_entry.val());
        },
        set_screen: function(screen) {
            this.screen = screen;
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
                // TODO test if widget is content_box widget
                this.alternate_viewport.append(widget);
            } else {
                this.content_box.children().detach();
                this.content_box.append(widget);
            }
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
            this.exclude_field = attributes.exclude_field;
            this.context = attributes.context || {};
            this.new_group();
            this.current_view = null;
            this.current_record = null;
            this.domain = attributes.domain || null;
            this.limit = attributes.limit || Sao.config.limit;
            this.offset = 0;
            if (!Sao.common.MODELACCESS.get(model_name).write) {
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
            this.fields_view_tree = null;
            this.domain_parser = null;
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
            // TODO preload
            var prm = this.model.execute('fields_view_get',
                    [view_id, view_type], this.context);
            return prm.pipe(this.add_view.bind(this));
        },
        add_view: function(view) {
            var arch = view.arch;
            var fields = view.fields;
            var xml_view = jQuery(jQuery.parseXML(arch));

            if (xml_view.children().prop('tagName') == 'tree') {
                this.fields_view_tree = view;
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
            this.views.push(view_widget);

            return view_widget;
        },
        number_of_views: function() {
            return this.views.length + this.view_to_load.length;
        },
        switch_view: function(view_type) {
            // TODO check validity
            if ((!view_type) || (!this.current_view) ||
                    (this.current_view.view_type != view_type)) {
                var switch_current_view = (function() {
                    this.current_view = this.views[this.views.length - 1];
                    return this.switch_view(view_type);
                }.bind(this));
                for (var i = 0; i < this.number_of_views(); i++) {
                    if (this.view_to_load.length) {
                        if (!view_type) {
                            view_type = this.view_to_load[0];
                        }
                        return this.load_next_view().pipe(switch_current_view);
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
            this.display();
            // TODO cursor
            return jQuery.when();
        },
        search_filter: function(search_string) {
            var domain = [];

            if (this.domain_parser && !this.group.parent) {
                if (search_string || search_string === '') {
                    domain = this.domain_parser.parse(search_string);
                } else {
                    domain = this.attributes.search_value;
                }
                this.screen_container.set_text(
                        this.domain_parser.string(domain));
            } else {
                domain = [['id', 'in', this.group.map(function(r) {
                    return r.id;
                })]];
            }

            if (!jQuery.isEmptyObject(domain) && this.attributes.domain) {
                domain = ['AND', domain, this.attributes.domain];
            } else
                domain = this.attributes.domain || [];

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
                this.screen_container.but_next.button('option', 'disabled',
                    !(group.length == this.limit &&
                        count > this.limit + this.offset));
            }.bind(this));
            this.screen_container.but_prev.button('option', 'disabled',
                    this.offset <= 0);
            return grp_prm;
        },
        set_group: function(group) {
            if (this.group) {
                jQuery.extend(group.model.fields, this.group.model.fields);
                this.group.screens.splice(
                        this.group.screens.indexOf(this), 1);
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
            }
        },
        display: function() {
            if (this.views) {
                this.search_active(~['tree', 'graph', 'calendar'].indexOf(
                            this.current_view.view_type));
                for (var i = 0; i < this.views.length; i++) {
                    if (this.views[i]) {
                        this.views[i].display();
                    }
                }
            }
            this.set_tree_state();
        },
        display_next: function() {
            var view = this.current_view;
            view.set_value();
            // TODO set cursor
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
            // TODO set cursor
            view.display();
        },
        display_previous: function() {
            var view = this.current_view;
            view.set_value();
            // TODO set cursor
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
            // TODO set cursor
            view.display();
        },
        default_row_activate: function() {
            if ((this.current_view.view_type == 'tree') &&
                    this.current_view.keyword_open) {
                Sao.Action.exec_keyword('tree_open', {
                    'model': this.model_name,
                    'id': this.get_id(),
                    'ids': [this.get_id()]
                    }, jQuery.extend({}, this.context));
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
            prm.done(function() {
                var group;
                if (this.current_record) {
                    group = this.current_record.group;
                } else {
                    group = this.group;
                }
                var record = group.new_(default_);
                group.add(record, this.new_model_position());
                this.set_current_record(record);
                this.display();
                // TODO set_cursor
            }.bind(this));
        },
        new_model_position: function() {
            var position = -1;
            // TODO editable
            return position;
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
            if (!this.current_record) {
                if ((this.current_view.view_type == 'tree') &&
                        (!jQuery.isEmptyObject(this.group))) {
                    this.set_current_record(this.group[0]);
                }
                return jQuery.when();
            }
            this.current_view.set_value();
            var fields = this.current_view.get_fields();
            // TODO path
            var prm = jQuery.Deferred();
            if (this.current_view.view_type == 'tree') {
                prm = this.group.save();
            } else {
                this.current_record.validate(fields).then(function(validate) {
                    if (validate) {
                        this.current_record.save().then(
                            prm.resolve, prm.reject);
                    } else {
                        // TODO set_cursor
                        this.current_view.display();
                        prm.reject();
                    }
                }.bind(this));
            }
            var display = function() {
                this.display();
            }.bind(this);
            return prm.then(display, display);
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
            return prm.then(function() {
                records.forEach(function(record) {
                    record.group.remove(record, remove, true, force_remove);
                });
                var prms = [];
                if (delete_) {
                    records.forEach(function(record) {
                        if (record.group.parent) {
                            prms.push(record.group.parent.save());
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
                // TODO set current_record
                this.set_current_record(null);
                // TODO set_cursor
                return jQuery.when.apply(jQuery, prms).then(function() {
                    this.display();
                }.bind(this));
            }.bind(this));
        },
        copy: function() {
            var records = this.current_view.selected_records();
            return this.model.copy(records, this.context).then(function(new_ids) {
                this.group.load(new_ids);
                if (!jQuery.isEmptyObject(new_ids)) {
                    this.set_current_record(this.group.get(new_ids[0]));
                }
                this.display();
            }.bind(this));
        },
        search_active: function(active) {
            if (active && !this.group.parent) {
                if (!this.fields_view_tree) {
                    this.model.execute('fields_view_get',
                            [false, 'tree'], this.context)
                        .then(function(view) {
                            this.fields_view_tree = view;
                            this.search_active(active);
                        }.bind(this));
                    return;
                }
                if (!this.domain_parser) {
                    var fields = jQuery.extend({},
                            this.fields_view_tree.fields);

                    var set_selection = function(props) {
                        return function(selection) {
                            props.selection = selection;
                        };
                    };
                    for (var name in fields) {
                        if (!fields.hasOwnProperty(name)) {
                            continue;
                        }
                        var props = fields[name];
                        if ((props.type != 'selection') &&
                                (props.type != 'reference')) {
                            continue;
                        }
                        if (props.selection instanceof Array) {
                            continue;
                        }
                        this.get_selection(props).then(set_selection);
                    }

                    // Filter only fields in XML view
                    var xml_view = jQuery(jQuery.parseXML(
                                this.fields_view_tree.arch));
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
                    [
                        ['id', 'ID', 'integer'],
                        ['create_uid', 'Creation User', 'many2one'],
                        ['create_date', 'Creation Date', 'datetime'],
                        ['write_uid', 'Modification User', 'many2one'],
                        ['write_date', 'Modification Date', 'datetime']
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
                            'string': 'ID',  // TODO translate
                            'name': 'id',
                            'type': 'integer'
                        };
                    }
                    this.domain_parser = new Sao.common.DomainParser(fields);
                }
                this.screen_container.set_screen(this);
                this.screen_container.show_filter();
            } else {
                this.screen_container.hide_filter();
            }
        },
        get_selection: function(props) {
            var prm;
            var change_with = props.selection_change_with;
            if (change_with) {
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
                    if (record.group.get_readonly() || record.readonly) {
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
            // TODO confirm
            var process_action = function(action) {
                this.reload(ids, true);
                if (typeof action == 'string') {
                    this.client_action(action);
                }
                else if (action) {
                    Sao.Action.execute(action, {
                        model: this.model_name,
                        id: record.id,
                        ids: ids
                    }, null, this.context);
                }
            };
            var reload_ids = function() {
                this.reload(ids, true);
            }.bind(this);

            var record = this.current_record;
            var selected_records = this.current_view.selected_records();
            var ids = selected_records.map(
                function(record) {
                    return record.id;
                });
            this.current_view.set_value();
            var fields = this.current_view.get_fields();
            record.save().done(function() {
                var prms = [];
                var reset_state = function(record, domain) {
                    return function(result) {
                        if (!result) {
                            this.display();
                            if (!jQuery.isEmptyObject(domain)) {
                                // Reset valid state with normal domain
                                record.validate(fields);
                            }
                        }
                        return result;
                    }.bind(this);
                }.bind(this);

                for (var i = 0; i < selected_records.length; i++) {
                    var record = selected_records[i];
                    var domain = record.expr_eval(
                        (attributes.states || {})).pre_validate || [];
                    var prm = record.validate(fields, false, domain);
                    prms.push(prm.then(reset_state(record, domain)));
                }
                jQuery.when.apply(jQuery, prms).then(function() {
                    var test = function(result) {
                        return !result;
                    };
                    if (Array.prototype.some.call(arguments, test)) {
                        return;
                    }
                    record.model.execute(attributes.name,
                        [ids], this.context).then(process_action.bind(this))
                        .then(reload_ids);
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
                var view_type = action.split(' ')[1];
                this.switch_view(view_type);
            } else if (action == 'reload menu') {
                Sao.get_preferences().then(function(preferences) {
                    Sao.menu(preferences);
                });
            } else if (action == 'reload context') {
                Sao.get_preferences();
            }
        },
        save_tree_state: function(store) {
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
                                widgets[wi].screen.save_tree_state(store);
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
                    parent_ = this.group.parent ? this.group.parent.id : null;
                    var timestamp = this.parent ? this._timestamp : null;
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
                        tree_state_model.execute('set', [
                                this.model_name,
                                this.get_tree_domain(parent_),
                                view.children_field,
                                JSON.stringify(paths),
                                JSON.stringify(selected_paths)], {});
                    }
                }
            }
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
                expanded_nodes = state[0];
                selected_nodes = state[1];
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
