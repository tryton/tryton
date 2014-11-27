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
            if (!~screen_views.indexOf(view_type) &&
                !~this.screen.view_to_load.indexOf(view_type)) {
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

            var readonly = (this.screen.attributes.readonly ||
                    this.screen.group.get_readonly());

            var buttons = [];

            if (view_type == 'form') {
                buttons.push({
                    text: (!kwargs.new_ && this.screen.current_record.id < 0 ?
                           'Delete' : 'Cancel'),
                        click: function() {
                            this.response('RESPONSE_CANCEL');
                        }.bind(this)
                });
            }

            if (kwargs.new_ && this.many) {
                buttons.push({
                    text: 'New',
                    click: function() {
                        this.response('RESPONSE_ACCEPT');
                    }.bind(this)
                });
            }

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

            var menu;
            if (view_type == 'tree') {
                menu = jQuery('<div/>');
                var access = Sao.common.MODELACCESS.get(this.screen.model_name);
                if (this.domain) {
                    this.wid_text = jQuery('<input/>', {
                        type: 'input'
                    });
                    menu.append(this.wid_text);

                    this.but_add = jQuery('<button/>').button({
                        icons: {
                            primary: 'ui-icon-plus'
                        },
                        label: 'Add'
                    });
                    this.but_add.click(this.add.bind(this));
                    menu.append(this.but_add);
                    this.but_add.prop('disabled', !access.read || readonly);

                    this.but_remove = jQuery('<button/>').button({
                        icons: {
                            primary: 'ui-icon-minus'
                        },
                        label: 'Remove'
                    });
                    this.but_remove.click(this.remove.bind(this));
                    menu.append(this.but_remove);
                    this.but_remove.prop('disabled', !access.read || readonly);
                }

                this.but_new = jQuery('<button/>').button({
                    icons: {
                        primary: 'ui-icon-document'
                    },
                    label: 'New'
                });
                this.but_new.click(this.new_.bind(this));
                menu.append(this.but_new);
                this.but_new.prop('disabled', !access.create || readonly);

                this.but_del = jQuery('<button/>').button({
                    icons: {
                        primary: 'ui-icon-trash'
                    },
                    label: 'Delete'
                });
                this.but_del.click(this.delete_.bind(this));
                menu.append(this.but_del);
                this.but_del.prop('disabled', !access['delete'] || readonly);

                this.but_undel = jQuery('<button/>').button({
                    icons: {
                        primary: 'ui-icon-arrowreturn-1-s'
                    },
                    label: 'Undelete'
                });
                this.but_undel.click(this.undelete.bind(this));
                menu.append(this.but_undel);
                this.but_undel.prop('disabled', !access['delete'] || readonly);

                this.but_previous = jQuery('<button/>').button({
                    icons: {
                        primary: 'ui-icon-arrowthick-1-w'
                    },
                    label: 'Previous'
                });
                this.but_previous.click(this.previous.bind(this));
                menu.append(this.but_previous);

                this.label = jQuery('<span/>');
                this.label.text('(0, 0)');
                menu.append(this.label);

                this.but_next = jQuery('<button/>').button({
                    icons: {
                        primary: 'ui-icon-arrowthick-1-e'
                    },
                    label: 'Next'
                });
                this.but_next.click(this.next.bind(this));
                menu.append(this.but_next);

                this.but_switch = jQuery('<button/>').button({
                    icons: {
                        primary: 'ui-icon-newwin'
                    },
                    label: 'Switch'
                });
                this.but_switch.click(this.switch_.bind(this));
                menu.append(this.but_switch);
            }


            switch_prm.done(function() {
                this.el.dialog({
                    modal: true,
                    autoOpen: false,
                    buttons: buttons,
                    title: '' // this.screen.current_view
                });
                Sao.common.center_dialog(this.el);
                if (menu) {
                    this.el.append(menu);
                }
                this.el.append(this.screen.screen_container.alternate_viewport);
                this.el.dialog('open');
                this.screen.display();
            }.bind(this));

        },
        add: function() {
            // TODO
        },
        remove: function() {
            this.screen.remove(false, true, false);
        },
        new_: function() {
            this.screen.new_();
        },
        delete_: function() {
            this.screen.remove(false, false, false);
        },
        undelete: function() {
            this.screen.unremove();
        },
        previous: function() {
            this.screen.display_previous();
        },
        next: function() {
            this.screen.display_next();
        },
        switch_: function() {
            this.screen.switch_view();
        },
        response: function(response_id) {
            var result;
            this.screen.current_view.set_value();
            var readonly = this.screen.group.get_readonly();
            if (~['RESPONSE_OK', 'RESPONSE_ACCEPT'].indexOf(response_id) &&
                    !readonly &&
                    this.screen.current_record) {
                this.screen.current_record.validate().then(function(validate) {
                    var closing_prm = jQuery.Deferred();
                    if (validate && this.save_current) {
                        this.screen.save_current().then(closing_prm.resolve,
                            closing_prm.reject);
                    } else if (validate &&
                            this.screen.current_view.view_type == 'form') {
                        var view = this.screen.current_view;
                        var validate_prms = [];
                        for (var name in this.widgets) {
                            var widget = this.widgets[name];
                            if (widget.screen && widget.screen.pre_validate) {
                                var record = widget.screen.current_record;
                                if (record) {
                                    validate_prms.push(record.pre_validate());
                                }
                            }
                        }
                        jQuery.when.apply(jQuery, validate_prms).then(
                            closing_prm.resolve, closing_prm.reject);
                    } else if (!validate) {
                        closing_prm.reject();
                    } else {
                        closing_prm.resolve();
                    }

                    closing_prm.fail(function() {
                        // TODO set_cursor
                        this.screen.display();
                    }.bind(this));

                    // TODO Add support for many
                    closing_prm.done(function() {
                        if (response_id == 'RESPONSE_ACCEPT') {
                            this.screen.new_();
                            this.screen.current_view.display();
                            // TODO set_cursor
                            this.many -= 1;
                            if (this.many === 0) {
                                this.but_new.prop('disabled', true);
                            }
                        } else {
                            result = true;
                            this.callback(result);
                            this.destroy();
                        }
                    }.bind(this));
                }.bind(this));
                return;
            }

            if (response_id == 'RESPONSE_CANCEL' &&
                    !readonly &&
                    this.screen.current_record) {
                result = false;
                if ((this.screen.current_record.id < 0) || this.save_current) {
                    this.screen.group.remove(this.screen.current_record, true);
                } else if (this.screen.current_record.has_changed()) {
                    this.screen.current_record.cancel();
                    this.screen.current_record.reload().always(function() {
                        this.callback(result);
                        this.destroy();
                    }.bind(this));
                    return;
                }
            } else {
                result = response_id != 'RESPONSE_CANCEL';
            }
            this.callback(result);
            this.destroy();
        },
        destroy: function() {
            this.screen.screen_container.alternate_view = false;
            this.screen.screen_container.alternate_viewport.children()
                .detach();
            this.el.dialog('destroy');
        }
    });

    Sao.Window.Attachment = Sao.class_(Sao.Window.Form, {
        init: function(record, callback) {
            this.resource = record.model.name + ',' + record.id;
            this.attachment_callback = callback;
            var context = jQuery.extend({}, record.get_context());
            context.resource = this.resource;
            var screen = new Sao.Screen('ir.attachment', {
                domain: [['resource', '=', this.resource]],
                mode: ['tree', 'form'],
                context: context,
                exclude_field: 'resource'
            });
            screen.switch_view().done(function() {
                screen.search_filter();
                screen.group.parent = record;
            });
            Sao.Window.Attachment._super.init.call(this, screen, this.callback,
                {view_type: 'tree'});
        },
        callback: function(result) {
            if (result) {
                this.screen.group.save();
            }
            if (this.attachment_callback) {
                this.attachment_callback();
            }
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
            if (kwargs.new_ && Sao.common.MODELACCESS.get(model).create) {
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
                modal: true,
                title: 'Search',  // TODO translate
                autoOpen: false,
                buttons: buttons
            });
            Sao.common.center_dialog(this.el);
            this.screen = new Sao.Screen(model, {
                mode: ['tree'],
                context: this.context,
                domain: this.domain,
                view_ids: kwargs.view_ids,
                views_preload: views_preload
            });
            this.screen.load_next_view().done(function() {
                this.screen.switch_view().done(function() {
                    this.el.append(this.screen.screen_container.el);
                    this.el.dialog('open');
                    this.screen.display();
                    if (kwargs.search_filter !== undefined) {
                        this.screen.search_filter(kwargs.search_filter);
                    }
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
                modal: true,
                title: 'Preferences',  // TODO translate
                autoOpen: false,
                buttons: buttons
            });
            Sao.common.center_dialog(this.el);

            this.screen = new Sao.Screen('res.user', {
                mode: []
            });
            this.screen.group.set_readonly(false);
            this.screen.group.skip_model_access = true;

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
                this.screen.current_record.validate(null, true).then(
                        function() {
                            this.screen.display();
                        }.bind(this));
                this.el.append(this.screen.screen_container.el);
                this.el.dialog('open');
            };

            this.screen.model.execute('get_preferences_fields_view', [], {})
                .then(set_view.bind(this), this.destroy);
        },
        response: function(response_id) {
            var end = function() {
                this.destroy();
                this.callback();
            }.bind(this);
            var prm = jQuery.when();
            if (response_id == 'RESPONSE_OK') {
                prm = this.screen.current_record.validate()
                    .then(function(validate) {
                        if (validate) {
                            var values = jQuery.extend({}, this.screen.get());
                            var set_preferences = function(password) {
                                return this.screen.model.execute(
                                    'set_preferences', [values, password], {});
                            }.bind(this);
                            if ('password' in values) {
                                return Sao.common.ask.run(
                                    'Current Password:', false)
                                    .then(function(password) {
                                        return set_preferences(password);
                                    });
                            } else {
                                return set_preferences(false);
                            }
                        }
                    }.bind(this));
            }
            prm.done(end);
        },
        destroy: function() {
            this.el.dialog('destroy');
        }
    });

    Sao.Window.Revision = Sao.class_(Object, {
        init: function(revisions, callback) {
            this.callback = callback;
            this.el = jQuery('<div/>');

            var buttons = [];
            buttons.push({
                text: 'Cancel', // TODO translate
                click: function() {
                    this.response('RESPONSE_CANCEL');
                }.bind(this)
            });
            buttons.push({
                text: 'Ok', // TODO translate
                click: function() {
                    this.response('RESPONSE_OK');
                }.bind(this)
            });

            this.el.dialog({
                model: true,
                title: 'Revision', // TODO translate
                autoOpen: false,
                buttons: buttons
            });
            Sao.common.center_dialog(this.el);

            this.el.append(jQuery('<label/>', {
                'text': 'Revision:' // TODO translate
            }));
            this.select = jQuery('<select/>');
            var date_format = Sao.common.date_format();
            var time_format = '%H:%M:%S.%f';
            this.select.append(jQuery('<option/>', {
                value: null,
                text: ''
            }));
            revisions.forEach(function(revision) {
                var name = revision[2];
                revision = revision[0];
                this.select.append(jQuery('<option/>', {
                    value: revision.valueOf(),
                    text: Sao.common.format_datetime(
                        date_format, time_format, revision) + ' ' + name
                }));
            }.bind(this));
            this.el.append(this.select);
            this.el.dialog('open');
        },
        response: function(response_id) {
            var revision = null;
            if (response_id == 'RESPONSE_OK') {
                revision = this.select.val();
                if (revision) {
                    revision = Sao.DateTime(parseInt(revision, 10));
                }
            }
            this.el.dialog('destroy');
            this.callback(revision);
        }
    });
}());
