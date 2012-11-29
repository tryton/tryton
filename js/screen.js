/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
'use strict';

Sao.Screen = Class(Object, {
    init: function(model_name, attributes) {
              this.model_name = model_name;
              this.model = new Sao.Model(model_name, attributes);
              this.attributes = jQuery.extend({}, attributes);
              this.view_ids = jQuery.extend([], attributes.view_ids);
              this.view_to_load = jQuery.extend([],
                  attributes.mode || ['tree', 'form']);
              this.views = [];
              this.current_view = null;
              this.context = attributes.context || {};
              this.el = $('<div/>', {
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
                  this.model.add_fields(fields);
                  var view = Sao.View.parse(this, xml_view);
                  this.views.push(view);
                  return view;
              },
    number_of_views: function() {
                         return this.views.length + this.view_to_load.length;
                     },
    switch_view: function(view_type) {
                     // TODO check validity
                     var self = this;
                     if ((!view_type) ||
                             (!this.current_view) ||
                             (this.current_view.view_type != view_type)) {
                         for (var i = 0; i < this.number_of_views(); i++) {
                             if (this.view_to_load.length) {
                                 return this.load_next_view().done(function() {
                                     self.current_view = self.views.slice(-1);
                                     return self.switch_view(view_type);
                                 });
                             }
                             this.current_view = this.views[
                                 (this.views.indexOf(this.current_view) + 1) %
                                 this.views.length];
                             if (!view_type) {
                                 break;
                             } else if (this.current_view.view_type ==
                                     view_type) {
                                 break;
                             }
                         }
                     }
                     this.el.remove();
                     this.el.append(this.current_view.el);
                     // TODO display and cursor
                     return jQuery.when();
                 }
});
