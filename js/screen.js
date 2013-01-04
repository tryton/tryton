/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.Screen = Sao.class_(Object, {
        init: function(model_name, attributes) {
            this.model_name = model_name;
            this.model = new Sao.Model(model_name, attributes);
            this.attributes = jQuery.extend({}, attributes);
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
            prm.done(this.add_view.bind(this));
            return prm;
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
                        return this.load_next_view().done(switch_current_view);
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
            this.el.remove();
            this.el.append(this.current_view.el);
            // TODO display and cursor
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
        }
    });
}());
