/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

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
            this.current_view = null;
            this.current_record = null;
            this.context = attributes.context || {};
            if (!attributes.row_activate) {
                this.row_activate = this.default_row_activate;
            } else {
                this.row_activate = attributes.row_activate;
            }
            this.el = jQuery('<div/>', {
                'class': 'screen'
            });
        },
        load_next_view: function() {
            if (this.view_to_load) {
                var view_id;
                if (this.view_ids) {
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
            // TODO loading lazy/eager
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

            if (this.current_view) {
                this.current_view.el.detach();
            }
            this.current_view = view_widget;
            this.el.append(view_widget.el);
            return view_widget;
        },
        number_of_views: function() {
            return this.views.length + this.view_to_load.length;
        },
        switch_view: function(view_type) {
            // TODO check validity
            var self = this;
            if ((!view_type) || (!this.current_view) ||
                    (this.current_view.view_type != view_type)) {
                var switch_current_view = function() {
                    self.current_view = self.views.slice(-1);
                    return self.switch_view(view_type);
                };
                for (var i = 0; i < this.number_of_views(); i++) {
                    if (this.view_to_load.length) {
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
            this.el.children().detach();
            this.el.append(this.current_view.el);
            this.display();
            // TODO cursor
            return jQuery.when();
        },
        search_filter: function() {
            var domain = [];
            // TODO domain parser

            if (domain.length && this.attributes.domain) {
                domain.unshift('AND');
                domain.push(this.attributes.domain);
            } else
                domain = this.attributes.domain || [];
            var grp_prm = this.model.find(domain, this.attributes.offset,
                    this.attributes.limit, this.attributes.order,
                    this.context);
            var group_setter = function(group) {
                if (this.group) {
                    this.group.screens.splice(
                        this.group.screens.indexOf(this), 1);
                }
                group.screens.push(this);
                this.group = group;
            };
            grp_prm.done(group_setter.bind(this));
            return grp_prm;
        },
        display: function() {
            if (this.views) {
                for (var i = 0; i < this.views.length; i++)
                    if (this.views[i])
                        this.views[i].display();
            }
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
                this.current_record = record;
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
            return jQuery.when(prms);
        },
        save_current: function() {
            if (!this.current_record) {
                if ((this.current_view.view_type == 'tree') &&
                        (!jQuery.isEmptyObject(this.group))) {
                    this.current_record = this.group[0];
                } else {
                    return true;
                }
            }
            this.current_view.set_value();
            var fields = this.current_view.get_fields();
            // TODO path
            var prm;
            if (this.current_view.view_type == 'tree') {
                prm = this.group.save();
            } else if (this.current_record.validate(fields)) {
                prm = this.current_record.save();
            } else {
                // TODO set_cursor
                this.current_view.display();
                prm = jQuery.when();
                prm.reject();
                return prm;
            }
            prm.always(function() {
                this.display();
            }.bind(this));
            return prm;
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
        remove: function(delete_, remove, force_remove) {
            var result = jQuery.Deferred();
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
            prm.done(function() {
                records.forEach(function(record) {
                    record.group.remove(record, remove, true, force_remove);
                });
                var prms = [];
                if (delete_) {
                    records.forEach(function(record) {
                        if (record.parent) {
                            prms.push(record.parent.save());
                        }
                        if (record in record.group.record_deleted) {
                            record.group.record_deleted.splice(
                                record.group.record_deleted.indexOf(record), 1);
                        }
                        if (record in record.group.record_removed) {
                            record.group.record_removed.splice(
                                record.group.record_removed.indexOf(record), 1);
                        }
                        // TODO destroy
                    });
                }
                // TODO set current_record
                this.current_record = null;
                // TODO set_cursor
                jQuery.when(prms).done(function() {
                    this.display();
                    result.resolve();
                }.bind(this));
            }.bind(this));
            return result;
        }
    });
}());
