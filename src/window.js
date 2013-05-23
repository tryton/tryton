/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.Window = {};

    Sao.Window.Form = Sao.class_(Object, {
        init: function(screen, callback, kwargs) {
            kwargs = kwargs || {};
            this.screen = screen;
            this.screen.screen_container.alternate_view = true;
            var view_type = kwargs.view_type || 'form';

            var form_prm = jQuery.when();
            var screen_views = [];
            for (var i = 0, len = this.screen.views.length; i < len; i++) {
                screen_views.push(this.screen.views[i].view_type);
            }
            if (screen_views.indexOf(view_type) == -1 &&
                this.screen.view_to_load.indexOf(view_type) == -1) {
                form_prm = this.screen.add_view_id(null, view_type);
            }

            var switch_prm = form_prm.then(function() {
                return this.screen.switch_view(view_type).done(function() {
                    if (kwargs.new_) {
                        this.screen.new_();
                    }
                }.bind(this));
            }.bind(this));
            this.many = kwargs.many || 0;
            this.domain = kwargs.domain || null;
            this.context = kwargs.context || null;
            this.save_current = kwargs.save_current;
            this.prev_view = screen.current_view;
            this.callback = callback;
            this.el = jQuery('<div/>');

            if (view_type == 'tree') {
                // TODO
            }

            var buttons = [];
            buttons.push({
                text: 'Cancel',
                click: function() {
                    this.response('RESPONSE_CANCEL');
                }.bind(this)
            });

            if (this.save_current) {
                buttons.push({
                    text: 'Save',
                    click: function() {
                        this.response('RESPONSE_OK');
                    }.bind(this)
                });
            } else {
                buttons.push({
                    text: 'OK',
                    click: function() {
                        this.response('RESPONSE_OK');
                    }.bind(this)
                });
            }

            switch_prm.done(function() {
                this.el.dialog({
                    autoOpen: false,
                    buttons: buttons,
                    title: '' // this.screen.current_view
                });
                this.el.append(this.screen.screen_container.alternate_viewport);
                this.el.dialog('open');
                this.screen.display();
            }.bind(this));

        },
        response: function(response_id) {
            var result;
            var closing_prm = jQuery.when();
            this.screen.current_view.set_value();

            if (response_id == 'RESPONSE_OK' &&
                    this.screen.current_record !== null) {
                var validate = this.screen.current_record.validate();
                // TODO pre-validate
                if (validate && this.save_current) {
                    closing_prm = this.screen.save_current();
                } else if (validate &&
                        this.screen.current_view.view_type == 'form') {
                    var view = this.screen.current_view;
                    for (var name in this.widgets) {
                        var widget = this.widgets[name];
                        if (widget.screen && widget.screen.pre_validate) {
                            var record = widget.screen.current_record;
                            if (record) {
                                validate = record.pre_validate();
                            }
                        }
                    }
                }
                if (!validate) {
                    closing_prm.reject();
                }

                closing_prm.fail(function() {
                    // TODO set_cursor
                    this.screen.display();
                }.bind(this));

                // TODO Add support for many
            }

            if (response_id == 'RESPONSE_CANCEL' &&
                    this.screen.current_record !== null) {
                if ((this.screen.current_record.id < 0) || this.save_current) {
                    var index = this.screen.group.indexOf(
                            this.screen.current_record);
                    this.screen.group.splice(index, 1);
                } else if (this.screen.current_record.has_changed()) {
                    this.screen.current_record.cancel();
                    this.screen.current_record.reload();
                }
                closing_prm = jQuery.Deferred();
                closing_prm.resolve();
                result = false;
            } else {
                result = response_id != 'RESPONSE_CANCEL';
            }

            closing_prm.done(function() {
                this.callback(result);
                this.destroy();
            }.bind(this));
        },
        destroy: function() {
            this.screen.screen_container.alternate_view = false;
            this.screen.screen_container.alternate_viewport.children()
                .detach();
            this.el.dialog('destroy');
        }
    });

    Sao.Window.Search = Sao.class_(Object, {
        init: function(model, callback, kwargs) {
            kwargs = kwargs || {};
            var views_preload = kwargs.views_preload || {};
            this.model_name = model;
            this.domain = kwargs.domain || [];
            this.context = kwargs.context || {};
            this.sel_multi = kwargs.sel_multi;
            this.callback = callback;
            this.el = jQuery('<div/>');

            var buttons = [];
            buttons.push({
                text: 'Cancel',
                click: function() {
                    this.response('RESPONSE_CANCEL');
                }.bind(this)
            });
            buttons.push({
                text: 'Find',
                click: function() {
                    this.response('RESPONSE_APPLY');
                }.bind(this)
            });
            if (kwargs.new_) { // TODO Add Model Acces
                buttons.push({
                    text: 'New',
                    click: function() {
                        this.response('RESPONSE_ACCEPT');
                    }.bind(this)
                });
            }
            buttons.push({
                text: 'OK',
                click: function() {
                    this.response('RESPONSE_OK');
                }.bind(this)
            });

            this.el.dialog({
                title: 'Search',  // TODO translate
                autoOpen: false,
                buttons: buttons
            });
            this.screen = new Sao.Screen(model, {
                mode: ['tree'],
                context: this.context,
                view_ids: kwargs.view_ids,
                views_preload: views_preload
            });
            if (!jQuery.isEmptyObject(kwargs.ids)) {
                this.screen.new_group(kwargs.ids);
            }
            this.screen.load_next_view().done(function() {
                this.screen.switch_view().done(function() {
                    this.el.append(this.screen.screen_container.el);
                    this.el.dialog('open');
                    this.screen.display();
                }.bind(this));
            }.bind(this));
        },
        response: function(response_id) {
            var records;
            var value = [];
            if (response_id == 'RESPONSE_OK') {
                records = this.screen.current_view.selected_records();
            } else if (response_id == 'RESPONSE_APPLY') {
                this.screen.search_filter();
                return;
            } else if (response_id == 'RESPONSE_ACCEPT') {
                var screen = new Sao.Screen(this.model_name, {
                    domain: this.domain,
                    context: this.context,
                    mode: ['form']
                });

                var callback = function(result) {
                    if (result) {
                        screen.save_current().then(function() {
                            var record = screen.current_record;
                            this.callback([[record.id,
                                record._values.rec_name || '']]);
                        }.bind(this), function() {
                            this.callback(null);
                        }.bind(this));
                    } else {
                        this.callback(null);
                    }
                };
                this.el.dialog('destroy');
                new Sao.Window.Form(screen, callback.bind(this), {
                    new_: true
                });
                return;
            }
            if (records) {
                var index, record;
                for (index in records) {
                    record = records[index];
                    value.push([record.id, record._values.rec_name || '']);
                }
            }
            this.callback(value);
            this.el.dialog('destroy');
        }
    });

    Sao.Window.Preferences = Sao.class_(Object, {
        init: function(callback) {
            this.callback = callback;
            this.el = jQuery('<div/>');

            var buttons = [];
            buttons.push({
                text: 'Cancel',  // TODO translate
                click: function() {
                    this.response('RESPONSE_CANCEL');
                }.bind(this)
            });
            buttons.push({
                text: 'Ok',  // TODO translate
                click: function() {
                    this.response('RESPONSE_OK');
                }.bind(this)
            });

            this.el.dialog({
                title: 'Preferences',  // TODO translate
                autoOpen: false,
                buttons: buttons
            });

            this.screen = new Sao.Screen('res.user', {
                mode: []
            });
            // TODO fix readonly from modelaccess

            var set_view = function(view) {
                this.screen.add_view(view);
                this.screen.switch_view().done(function() {
                    this.screen.new_(false);
                    this.screen.model.execute('get_preferences', [false], {})
                    .then(set_preferences.bind(this), this.destroy);
                }.bind(this));
            };
            var set_preferences = function(preferences) {
                this.screen.current_record.set(preferences);
                this.screen.current_record.id =
                    this.screen.model.session.user_id;
                this.screen.current_record.validate(null, true);
                this.screen.display();
                this.el.append(this.screen.screen_container.el);
                this.el.dialog('open');
            };

            this.screen.model.execute('get_preferences_fields_view', [], {})
                .then(set_view.bind(this), this.destroy);
        },
        response: function(response_id) {
            if (response_id == 'RESPONSE_OK') {
                if (this.screen.current_record.validate()) {
                    var values = jQuery.extend({}, this.screen.get());
                    var password = false;
                    if ('password' in values) {
                        // TODO translate
                        password = window.prompt('Current Password:');
                        if (!password) {
                            return;
                        }
                    }
                    this.screen.model.execute('set_preferences',
                            [values, password], {}).done(function() {
                                this.destroy();
                                this.callback();
                            }.bind(this));
                    return;
                }
            }
            this.destroy();
            this.callback();
        },
        destroy: function() {
            this.el.dialog('destroy');
        }
    });

}());
