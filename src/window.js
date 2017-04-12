/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.Window = {};

    Sao.Window.InfoBar = Sao.class_(Object, {
        init: function() {
            this.text = jQuery('<span/>');
            this.text.css('white-space', 'pre-wrap');
            this.el= jQuery('<div/>', {
                'class': 'alert infobar',
                'role': 'alert'
            }).append(jQuery('<button/>', {
                'type': 'button',
                'class': 'close',
                'aria-label': Sao.i18n.gettext('Close')
            }).append(jQuery('<span/>', {
                'aria-hidden': true
            }).append('&times;')).click(function() {
                this.el.hide();
            }.bind(this))).append(this.text);
            this.el.hide();
        },
        message: function(message, type) {
            if (message) {
                this.el.removeClass(
                        'alert-success alert-info alert-warning alert-danger');
                this.el.addClass('alert-' + (type || 'info'));
                this.text.text(message);
                this.el.show();
            } else {
                this.el.hide();
            }
        }
    });

    Sao.Window.Form = Sao.class_(Object, {
        init: function(screen, callback, kwargs) {
            kwargs = kwargs || {};
            this.screen = screen;
            this.callback = callback;
            this.many = kwargs.many || 0;
            this.domain = kwargs.domain || null;
            this.context = kwargs.context || null;
            this.save_current = kwargs.save_current;
            var title_prm = jQuery.when(kwargs.title || '');
            title_prm.then(function(title) {
                this.title = title;
            }.bind(this));

            this.prev_view = screen.current_view;
            this.screen.screen_container.alternate_view = true;
            this.info_bar = new Sao.Window.InfoBar();
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
                        this.screen.new_(undefined, kwargs.rec_name);
                    }
                }.bind(this));
            }.bind(this));
            var dialog = new Sao.Dialog('', 'window-form', 'lg');
            this.el = dialog.modal;

            var readonly = (this.screen.attributes.readonly ||
                    this.screen.group.get_readonly());

            if (view_type == 'form') {
                dialog.footer.append(jQuery('<button/>', {
                    'class': 'btn btn-link',
                    'type': 'button'
                }).append(!kwargs.new_ && this.screen.current_record.id < 0 ?
                    Sao.i18n.gettext('Delete') : Sao.i18n.gettext('Cancel'))
                        .click(function() {
                            this.response('RESPONSE_CANCEL');
                        }.bind(this)));
            }

            if (kwargs.new_ && this.many) {
                dialog.footer.append(jQuery('<button/>', {
                    'class': 'btn btn-default',
                    'type': 'button'
                }).append(Sao.i18n.gettext('New')).click(function() {
                    this.response('RESPONSE_ACCEPT');
                }.bind(this)));
            }

            if (this.save_current) {
                dialog.footer.append(jQuery('<button/>', {
                    'class': 'btn btn-primary',
                    'type': 'submit'
                }).append(Sao.i18n.gettext('Save')));
            } else {
                dialog.footer.append(jQuery('<button/>', {
                    'class': 'btn btn-primary',
                    'type': 'submit'
                }).append(Sao.i18n.gettext('OK')));
            }
            dialog.content.submit(function(e) {
                this.response('RESPONSE_OK');
                e.preventDefault();
            }.bind(this));

            if (view_type == 'tree') {
                var menu = jQuery('<div/>', {
                    'class': 'window-form-toolbar'
                }).appendTo(dialog.body);
                var group = jQuery('<div/>', {
                    'class': 'input-group input-group-sm'
                }).appendTo(menu);

                this.wid_text = jQuery('<input/>', {
                    type: 'input'
                }).appendTo(menu);
                this.wid_text.hide();

                var buttons = jQuery('<div/>', {
                    'class': 'input-group-btn'
                }).appendTo(group);
                var access = Sao.common.MODELACCESS.get(this.screen.model_name);
                if (this.domain) {
                    this.wid_text.show();

                    this.but_add = jQuery('<button/>', {
                        'class': 'btn btn-default btn-sm',
                        'type': 'button',
                        'aria-label': Sao.i18n.gettext('Add')
                    }).append(jQuery('<span/>', {
                        'class': 'glyphicon glyphicon-plus'
                    })).appendTo(buttons);
                    this.but_add.click(this.add.bind(this));
                    this.but_add.prop('disabled', !access.read || readonly);

                    this.but_remove = jQuery('<button/>', {
                        'class': 'btn btn-default btn-sm',
                        'type': 'button',
                        'aria-label': Sao.i18n.gettext('Remove')
                    }).append(jQuery('<span/>', {
                        'class': 'glyphicon glyphicon-minus'
                    })).appendTo(buttons);
                    this.but_remove.click(this.remove.bind(this));
                    this.but_remove.prop('disabled', !access.read || readonly);
                }

                this.but_new = jQuery('<button/>', {
                    'class': 'btn btn-default btn-sm',
                    'type': 'button',
                    'aria-label': Sao.i18n.gettext('New')
                }).append(jQuery('<span/>', {
                    'class': 'glyphicon glyphicon-edit'
                })).appendTo(buttons);
                this.but_new.click(this.new_.bind(this));
                this.but_new.prop('disabled', !access.create || readonly);

                this.but_del = jQuery('<button/>', {
                    'class': 'btn btn-default btn-sm',
                    'type': 'button',
                    'aria-label': Sao.i18n.gettext('Delete')
                }).append(jQuery('<span/>', {
                    'class': 'glyphicon glyphicon-trash'
                })).appendTo(buttons);
                this.but_del.click(this.delete_.bind(this));
                this.but_del.prop('disabled', !access['delete'] || readonly);

                this.but_undel = jQuery('<button/>', {
                    'class': 'btn btn-default btn-sm',
                    'type': 'button',
                    'aria-label': Sao.i18n.gettext('Undelete')
                }).append(jQuery('<span/>', {
                    'class': 'glyphicon glyphicon-repeat'
                })).appendTo(buttons);
                this.but_undel.click(this.undelete.bind(this));
                this.but_undel.prop('disabled', !access['delete'] || readonly);

                this.but_previous = jQuery('<button/>', {
                    'class': 'btn btn-default btn-sm',
                    'type': 'button',
                    'aria-label': Sao.i18n.gettext('Previous')
                }).append(jQuery('<span/>', {
                    'class': 'glyphicon glyphicon-chevron-left'
                })).appendTo(buttons);
                this.but_previous.click(this.previous.bind(this));

                this.label = jQuery('<span/>', {
                    'class': 'btn'
                }).appendTo(buttons);
                this.label.text('(0, 0)');

                this.but_next = jQuery('<button/>', {
                    'class': 'btn btn-default btn-sm',
                    'type': 'button',
                    'aria-label': Sao.i18n.gettext('Next')
                }).append(jQuery('<span/>', {
                    'class': 'glyphicon glyphicon-chevron-right'
                })).appendTo(buttons);
                this.but_next.click(this.next.bind(this));

                this.but_switch = jQuery('<button/>', {
                    'class': 'btn btn-default btn-sm',
                    'type': 'button',
                    'aria-label': Sao.i18n.gettext('Switch')
                }).append(jQuery('<span/>', {
                    'class': 'glyphicon glyphicon-list-alt'
                })).appendTo(buttons);
                this.but_switch.click(this.switch_.bind(this));
            }

            var content = jQuery('<div/>').appendTo(dialog.body);

            dialog.body.append(this.info_bar.el);

            switch_prm.done(function() {
                title_prm.done(dialog.add_title.bind(dialog));
                content.append(this.screen.screen_container.alternate_viewport);
                this.el.modal('show');
            }.bind(this));
            this.el.on('shown.bs.modal', function(event) {
                this.screen.display().done(function() {
                    this.screen.set_cursor();
                }.bind(this));
            }.bind(this));
            this.el.on('hidden.bs.modal', function(event) {
                jQuery(this).remove();
            });

        },
        add: function() {
            var domain = jQuery.extend([], this.domain);
            var model_name = this.screen.model_name;
            var value = this.wid_text.val();

            var callback = function(result) {
                var prm = jQuery.when();
                if (!jQuery.isEmptyObject(result)) {
                    var ids = [];
                    for (var i = 0, len = result.length; i < len; i++) {
                        ids.push(result[i][0]);
                    }
                    this.screen.group.load(ids, true);
                    prm = this.screen.display();
                }
                prm.done(function() {
                    this.screen.set_cursor();
                }.bind(this));
                this.entry.val('');
            }.bind(this);
            var parser = new Sao.common.DomainParser();
            var win = new Sao.Window.Search(model_name, callback, {
                sel_multi: true,
                context: this.context,
                domain: domain,
                search_filter: parser.quote(value)
            });
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
                    if (validate && this.screen.attributes.pre_validate) {
                        return this.screen.current_record.pre_validate();
                    }
                    return validate;
                }.bind(this)).then(function(validate) {
                    var closing_prm = jQuery.Deferred();
                    if (validate && this.save_current) {
                        this.screen.save_current().then(closing_prm.resolve,
                            closing_prm.reject);
                    } else if (validate &&
                            this.screen.current_view.view_type == 'form') {
                        var view = this.screen.current_view;
                        var validate_prms = [];
                        for (var name in view.widgets) {
                            var widget = view.widgets[name];
                            if (widget.screen &&
                                widget.screen.attributes.pre_validate) {
                                var record = widget.screen.current_record;
                                if (record) {
                                    validate_prms.push(record.pre_validate());
                                }
                            }
                        }
                        jQuery.when.apply(jQuery, validate_prms).then(
                            closing_prm.resolve, closing_prm.reject);
                    } else if (!validate) {
                        this.info_bar.message(
                            this.screen.invalid_message(), 'danger');
                        closing_prm.reject();
                    } else {
                        this.info_bar.message();
                        closing_prm.resolve();
                    }

                    closing_prm.fail(function() {
                        this.screen.display().done(function() {
                            this.screen.set_cursor();
                        }.bind(this));
                    }.bind(this));

                    // TODO Add support for many
                    closing_prm.done(function() {
                        if (response_id == 'RESPONSE_ACCEPT') {
                            this.screen.new_();
                            this.screen.current_view.display().done(function() {
                                this.screen.set_cursor();
                            }.bind(this));
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
                    this.screen.cancel_current();
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
            if (this.prev_view) {
                // Empty when opening from Many2One
                this.screen.switch_view(this.prev_view.view_type);
            }
            this.el.modal('hide');
        }
    });

    Sao.Window.Attachment = Sao.class_(Sao.Window.Form, {
        init: function(record, callback) {
            this.resource = record.model.name + ',' + record.id;
            this.attachment_callback = callback;
            var context = jQuery.extend({}, record.get_context());
            var screen = new Sao.Screen('ir.attachment', {
                domain: [['resource', '=', this.resource]],
                mode: ['tree', 'form'],
                context: context,
                exclude_field: 'resource'
            });
            screen.switch_view().done(function() {
                screen.search_filter();
            });
            var title = record.rec_name().then(function(rec_name) {
                return Sao.i18n.gettext('Attachments (%1)', rec_name);
            });
            Sao.Window.Attachment._super.init.call(this, screen, this.callback,
                {view_type: 'tree', title: title});
        },
        callback: function(result) {
            var prm = jQuery.when();
            if (result) {
                var resource = this.screen.group.model.fields.resource;
                this.screen.group.forEach(function(record) {
                    resource.set_client(record, this.resource);
                }.bind(this));
                prm = this.screen.save_current();
            }
            if (this.attachment_callback) {
                prm.always(this.attachment_callback.bind(this));
            }
        }
    });

    Sao.Window.Note = Sao.class_(Sao.Window.Form, {
        init: function(record, callback) {
            this.resource = record.model.name + ',' + record.id;
            this.note_callback = callback;
            var context = jQuery.extend({}, record.get_context());
            var screen = new Sao.Screen('ir.note', {
                domain: [['resource', '=', this.resource]],
                mode: ['tree', 'form'],
                context: context,
                exclude_field: 'resource'
            });
            screen.switch_view().done(function() {
                screen.search_filter();
            });
            var title = record.rec_name().then(function(rec_name) {
                return Sao.i18n.gettext('Notes (%1)', rec_name);
            });
            Sao.Window.Note._super.init.call(this, screen, this.callback,
                {view_type: 'tree', title: title});
        },
        callback: function(result) {
            var prm = jQuery.when();
            if (result) {
                var resource = this.screen.group.model.fields.resource;
                var unread = this.screen.group.model.fields.unread;
                this.screen.group.forEach(function(record) {
                    if (record.get_loaded() || record.id < 0) {
                        resource.set_client(record, this.resource);
                        if (!record._changed.unread) {
                            unread.set_client(record, false);
                        }
                    }
                }.bind(this));
                prm = this.screen.save_current();
            }
            if (this.note_callback) {
                prm.always(this.note_callback.bind(this));
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
            this.title = kwargs.title || '';
            var dialog = new Sao.Dialog(Sao.i18n.gettext(
                'Search %1', this.title), '', 'lg');
            this.el = dialog.modal;

            jQuery('<button/>', {
                'class': 'btn btn-link',
                'type': 'button'
            }).append(Sao.i18n.gettext('Cancel')).click(function() {
                this.response('RESPONSE_CANCEL');
            }.bind(this)).appendTo(dialog.footer);
            jQuery('<button/>', {
                'class': 'btn btn-default',
                'type': 'button'
            }).append(Sao.i18n.gettext('Find')).click(function() {
                this.response('RESPONSE_APPLY');
            }.bind(this)).appendTo(dialog.footer);
            if (kwargs.new_ && Sao.common.MODELACCESS.get(model).create) {
                jQuery('<button/>', {
                    'class': 'btn btn-default',
                    'type': 'button'
                }).append(Sao.i18n.gettext('New')).click(function() {
                    this.response('RESPONSE_ACCEPT');
                }.bind(this)).appendTo(dialog.footer);
            }
            jQuery('<button/>', {
                'class': 'btn btn-primary',
                'type': 'submit'
            }).append(Sao.i18n.gettext('OK')).appendTo(dialog.footer);
            dialog.content.submit(function(e) {
                this.response('RESPONSE_OK');
                e.preventDefault();
            }.bind(this));

            this.screen = new Sao.Screen(model, {
                mode: ['tree'],
                context: this.context,
                domain: this.domain,
                view_ids: kwargs.view_ids,
                views_preload: views_preload,
                row_activate: this.activate.bind(this)
            });
            this.screen.load_next_view().done(function() {
                this.screen.switch_view().done(function() {
                    dialog.body.append(this.screen.screen_container.el);
                    this.el.modal('show');
                    this.screen.display();
                    if (kwargs.search_filter !== undefined) {
                        this.screen.search_filter(kwargs.search_filter);
                    }
                }.bind(this));
            }.bind(this));
            this.el.on('hidden.bs.modal', function(event) {
                jQuery(this).remove();
            });
        },
        activate: function() {
            this.response('RESPONSE_OK');
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
                        var record = screen.current_record;
                        this.callback([[record.id,
                            record._values.rec_name || '']]);
                    } else {
                        this.callback(null);
                    }
                };
                this.el.modal('hide');
                new Sao.Window.Form(screen, callback.bind(this), {
                    new_: true,
                    save_current: true,
                    title: this.title
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
            this.el.modal('hide');
        }
    });

    Sao.Window.Preferences = Sao.class_(Object, {
        init: function(callback) {
            this.callback = callback;
            var dialog = new Sao.Dialog('Preferences', '', 'lg');
            this.el = dialog.modal;

            jQuery('<button/>', {
                'class': 'btn btn-link',
                'type': 'button'
            }).append(Sao.i18n.gettext('Cancel')).click(function() {
                this.response('RESPONSE_CANCEL');
            }.bind(this)).appendTo(dialog.footer);
            jQuery('<button/>', {
                'class': 'btn btn-primary',
                'type': 'submit'
            }).append(Sao.i18n.gettext('OK')).appendTo(dialog.footer);
            dialog.content.submit(function(e) {
                this.response('RESPONSE_OK');
                e.preventDefault();
            }.bind(this));

            this.screen = new Sao.Screen('res.user', {
                mode: []
            });
            // Reset readonly set automaticly by MODELACCESS
            this.screen.attributes.readonly = false;
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
                var prm;
                this.screen.current_record.cancel();
                prm = this.screen.current_record.set(preferences);
                this.screen.current_record.id =
                    this.screen.model.session.user_id;
                prm.then(function() {
                    this.screen.current_record.validate(null, true).then(
                        function() {
                            this.screen.display(true);
                        }.bind(this));
                }.bind(this));
                dialog.body.append(this.screen.screen_container.el);
                this.el.modal('show');
            };
            this.el.on('hidden.bs.modal', function(event) {
                jQuery(this).remove();
            });

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
                            var context = jQuery.extend({},
                                    Sao.Session.current_session.context);
                            var func = function(parameters) {
                                return {
                                    'id': 0,
                                    'method': 'model.res.user.set_preferences',
                                    'params': [values, parameters, context]
                                };
                            };
                            return new Sao.Login(func).run();
                        }
                    }.bind(this));
            }
            prm.done(end);
        },
        destroy: function() {
            this.el.modal('hide');
        }
    });

    Sao.Window.Revision = Sao.class_(Object, {
        init: function(revisions, callback) {
            this.callback = callback;
            var dialog = new Sao.Dialog(
                    Sao.i18n.gettext('Revision'), '', 'lg');
            this.el = dialog.modal;

            jQuery('<button/>', {
                'class': 'btn btn-link',
                'type': 'button'
            }).append(Sao.i18n.gettext('Cancel')).click(function() {
                this.response('RESPONSE_CANCEL');
            }.bind(this)).appendTo(dialog.footer);
            jQuery('<button/>', {
                'class': 'btn btn-primary',
                'type': 'submit'
            }).append(Sao.i18n.gettext('OK')).appendTo(dialog.footer);
            dialog.content.submit(function(e) {
                this.response('RESPONSE_OK');
                e.preventDefault();
            }.bind(this));

            var group = jQuery('<div/>', {
                'class': 'form-group'
            }).appendTo(dialog.body);
            jQuery('<label/>', {
                'for': 'revision',
                'text': 'Revision'
            }).appendTo(group);
            this.select = jQuery('<select/>', {
                'class': 'form-control',
                id: 'revision',
                'placeholder': Sao.i18n.gettext('Revision')
            }).appendTo(group);
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
                        date_format, time_format, revision) + ' ' + this.title
                }));
            }.bind(this));
            this.el.modal('show');
            this.el.on('hidden.bs.modal', function(event) {
                jQuery(this).remove();
            });
        },
        response: function(response_id) {
            var revision = null;
            if (response_id == 'RESPONSE_OK') {
                revision = this.select.val();
                if (revision) {
                    revision = Sao.DateTime(parseInt(revision, 10));
                }
            }
            this.el.modal('hide');
            this.callback(revision);
        }
    });

    Sao.Window.CSV = Sao.class_(Object, {
        init: function(title) {
            this.encodings = ["866", "ansi_x3.4-1968", "arabic", "ascii",
            "asmo-708", "big5", "big5-hkscs", "chinese", "cn-big5", "cp1250",
            "cp1251", "cp1252", "cp1253", "cp1254", "cp1255", "cp1256",
            "cp1257", "cp1258", "cp819", "cp866", "csbig5", "cseuckr",
            "cseucpkdfmtjapanese", "csgb2312", "csibm866", "csiso2022jp",
            "csiso2022kr", "csiso58gb231280", "csiso88596e", "csiso88596i",
            "csiso88598e", "csiso88598i", "csisolatin1", "csisolatin2",
            "csisolatin3", "csisolatin4", "csisolatin5", "csisolatin6",
            "csisolatin9", "csisolatinarabic", "csisolatincyrillic",
            "csisolatingreek", "csisolatinhebrew", "cskoi8r", "csksc56011987",
            "csmacintosh", "csshiftjis", "cyrillic", "dos-874", "ecma-114",
            "ecma-118", "elot_928", "euc-jp", "euc-kr", "gb18030", "gb2312",
            "gb_2312", "gb_2312-80", "gbk", "greek", "greek8", "hebrew",
            "hz-gb-2312", "ibm819", "ibm866", "iso-2022-cn", "iso-2022-cn-ext",
            "iso-2022-jp", "iso-2022-kr", "iso-8859-1", "iso-8859-10",
            "iso-8859-11", "iso-8859-13", "iso-8859-14", "iso-8859-15",
            "iso-8859-16", "iso-8859-2", "iso-8859-3", "iso-8859-4",
            "iso-8859-5", "iso-8859-6", "iso-8859-6-e", "iso-8859-6-i",
            "iso-8859-7", "iso-8859-8", "iso-8859-8-e", "iso-8859-8-i",
            "iso-8859-9", "iso-ir-100", "iso-ir-101", "iso-ir-109",
            "iso-ir-110", "iso-ir-126", "iso-ir-127", "iso-ir-138",
            "iso-ir-144", "iso-ir-148", "iso-ir-149", "iso-ir-157", "iso-ir-58",
            "iso8859-1", "iso8859-10", "iso8859-11", "iso8859-13", "iso8859-14",
            "iso8859-15", "iso8859-2", "iso8859-3", "iso8859-4", "iso8859-5",
            "iso8859-6", "iso8859-7", "iso8859-8", "iso8859-9", "iso88591",
            "iso885910", "iso885911", "iso885913", "iso885914", "iso885915",
            "iso88592", "iso88593", "iso88594", "iso88595", "iso88596",
            "iso88597", "iso88598", "iso88599", "iso_8859-1", "iso_8859-15",
            "iso_8859-1:1987", "iso_8859-2", "iso_8859-2:1987", "iso_8859-3",
            "iso_8859-3:1988", "iso_8859-4", "iso_8859-4:1988", "iso_8859-5",
            "iso_8859-5:1988", "iso_8859-6", "iso_8859-6:1987", "iso_8859-7",
            "iso_8859-7:1987", "iso_8859-8", "iso_8859-8:1988", "iso_8859-9",
            "iso_8859-9:1989", "koi", "koi8", "koi8-r", "koi8-ru", "koi8-u",
            "koi8_r", "korean", "ks_c_5601-1987", "ks_c_5601-1989", "ksc5601",
            "ksc_5601", "l1", "l2", "l3", "l4", "l5", "l6", "l9", "latin1",
            "latin2", "latin3", "latin4", "latin5", "latin6", "logical", "mac",
            "macintosh", "ms932", "ms_kanji", "shift-jis", "shift_jis", "sjis",
            "sun_eu_greek", "tis-620", "unicode-1-1-utf-8", "us-ascii",
            "utf-16", "utf-16be", "utf-16le", "utf-8", "utf8", "visual",
            "windows-1250", "windows-1251", "windows-1252", "windows-1253",
            "windows-1254", "windows-1255", "windows-1256", "windows-1257",
            "windows-1258", "windows-31j", "windows-874", "windows-949",
            "x-cp1250", "x-cp1251", "x-cp1252", "x-cp1253", "x-cp1254",
            "x-cp1255", "x-cp1256", "x-cp1257", "x-cp1258", "x-euc-jp", "x-gbk",
            "x-mac-cyrillic", "x-mac-roman", "x-mac-ukrainian", "x-sjis",
            "x-user-defined", "x-x-big5"];
            this.dialog = new Sao.Dialog(title, 'csv', 'lg');
            this.el = this.dialog.modal;

            this.fields = {};
            this.fields_model = {};
            jQuery('<button/>', {
                'class': 'btn btn-link',
                'type': 'button'
            }).append(Sao.i18n.gettext('Cancel')).click(function(){
                this.response('RESPONSE_CANCEL');
            }.bind(this)).appendTo(this.dialog.footer);

            jQuery('<button/>', {
                'class': 'btn btn-primary',
                'type': 'submit'
            }).append(Sao.i18n.gettext('OK')).click(function(e){
                this.response('RESPONSE_OK');
                e.preventDefault();
            }.bind(this)).appendTo(this.dialog.footer);

            var row_fields = jQuery('<div/>', {
                'class': 'row'
            }).appendTo(this.dialog.body);

            jQuery('<hr/>').appendTo(this.dialog.body);

            var column_fields_all = jQuery('<div/>', {
                'class': 'col-md-4 column-fields'
            }).append(jQuery('<label/>', {
                'text': Sao.i18n.gettext('All Fields')
            })).appendTo(row_fields);

            this.fields_all = jQuery('<ul/>', {
                'class': 'list-unstyled'
            }).css('cursor', 'pointer')
            .appendTo(column_fields_all);

            var prm = this.get_fields(this.screen.model_name)
                .then(function(fields){
                    this.model_populate(fields);
                    this.view_populate(this.fields_model, this.fields_all);
                }.bind(this));

            this.column_buttons = jQuery('<div/>', {
                'class': 'col-md-4'
            }).append('<label/>').appendTo(row_fields);

            var button_add = jQuery('<button/>', {
                'class': 'btn btn-default btn-block',
                'type': 'button'
            }).append(jQuery('<i/>', {
                    'class': 'glyphicon glyphicon-plus'
            })).click(function(){
                this.fields_all.find('.bg-primary').each(function(i, el_field) {
                    this.sig_sel_add(el_field);
                }.bind(this));
            }.bind(this)).append(' '+Sao.i18n.gettext('Add'))
            .appendTo(this.column_buttons);

            jQuery('<button/>', {
                'class': 'btn btn-default btn-block',
                'type': 'button'
            }).append(jQuery('<i/>', {
                    'class': 'glyphicon glyphicon-minus'
            })).click(function(){
                // sig_unsel
                this.fields_selected.children('li.bg-primary').remove();
            }.bind(this)).append(' '+Sao.i18n.gettext('Remove'))
            .appendTo(this.column_buttons);

            jQuery('<button/>', {
                'class': 'btn btn-default btn-block',
                'type': 'button'
            }).append(jQuery('<i/>', {
                    'class': 'glyphicon glyphicon-remove'
            })).click(function(){
                this.fields_selected.empty();
            }.bind(this)).append(' '+Sao.i18n.gettext('Clear'))
            .appendTo(this.column_buttons);

            jQuery('<hr>').appendTo(this.column_buttons);

            var column_fields_selected = jQuery('<div/>', {
                'class': 'col-md-4 column-fields'
            }).append(jQuery('<label/>', {
                'text': Sao.i18n.gettext('Fields Selected')
            })).appendTo(row_fields);

            // TODO: Make them draggable to re-order
            this.fields_selected = jQuery('<ul/>', {
                'class': 'list-unstyled'
            }).css('cursor', 'pointer').appendTo(column_fields_selected);

            this.chooser_form = jQuery('<div/>', {
                'class': 'form-inline'
            }).appendTo(this.dialog.body);

            var row_csv_param = jQuery('<div/>', {
                'class': 'row'
            }).appendTo(this.dialog.body);

            var expander_icon = jQuery('<span/>', {
                'class': 'glyphicon glyphicon-plus',
            }).css('cursor', 'pointer').html('&nbsp;');

            var csv_param_label = jQuery('<label/>', {
                'text': Sao.i18n.gettext('CSV Parameters')
            }).css('cursor', 'pointer');

            jQuery('<div/>', {
                'class': 'col-md-12'
            }).append(expander_icon).append(csv_param_label)
            .on('click', function(){
                expander_icon.toggleClass('glyphicon-plus')
                .toggleClass('glyphicon-minus');
                this.expander_csv.collapse('toggle');
            }.bind(this)).appendTo(row_csv_param);

            this.expander_csv = jQuery('<div/>', {
                'id': 'expander_csv',
                'class': 'collapse'
            }).appendTo(row_csv_param);

            var delimiter_label = jQuery('<label/>', {
                'text': Sao.i18n.gettext('Delimiter:'),
                'class': 'col-sm-2 control-label',
                'for': 'input-delimiter'
            });

            this.el_csv_delimiter = jQuery('<input/>', {
                'type': 'text',
                'class': 'form-control',
                'id': 'input-delimiter',
                'size': '1',
                'maxlength': '1',
                'value': ','
            });

            jQuery('<div/>', {
                'class': 'form-group'
            }).append(delimiter_label).append(jQuery('<div/>', {
                'class': 'col-sm-4'
            }).append(this.el_csv_delimiter)).appendTo(this.expander_csv);

            var quotechar_label = jQuery('<label/>', {
                'text': Sao.i18n.gettext('Quote Char:'),
                'class': 'col-sm-2 control-label',
                'for': 'input-quotechar'
            });

            this.el_csv_quotechar = jQuery('<input/>', {
                'type': 'text',
                'class': 'form-control',
                'id': 'input-quotechar',
                'size': '1',
                'maxlength': '1',
                'value': '\"',
            });

            jQuery('<div/>', {
                'class': 'form-group'
            }).append(quotechar_label).append(jQuery('<div/>', {
                'class': 'col-sm-4'
            }).append(this.el_csv_quotechar))
            .appendTo(this.expander_csv);

            var encoding_label = jQuery('<label/>', {
                'text': Sao.i18n.gettext('Encoding:'),
                'class': 'col-sm-2 control-label',
                'for': 'input-encoding'
            });

            this.el_csv_encoding = jQuery('<select/>', {
                'class': 'form-control',
                'id': 'input-encoding'
            });

            for(var i=0; i<this.encodings.length; i++) {
                jQuery('<option/>', {
                    'val': this.encodings[i]
                }).html(this.encodings[i]).appendTo(this.el_csv_encoding);
            }

            var enc = 'utf-8';
            if (navigator.platform == 'Win32' ||
                navigator.platform == 'Windows') {
                enc = 'cp1252';
            }
            this.el_csv_encoding.children('option[value="' + enc + '"]')
            .attr('selected', 'selected');

            jQuery('<div/>', {
                'class': 'form-group'
            }).append(encoding_label).append(jQuery('<div/>', {
                'class': 'col-sm-4'
            }).append(this.el_csv_encoding))
            .appendTo(this.expander_csv);

            this.el.modal('show');
            this.el.on('hidden.bs.modal', function() {
                jQuery(this).remove();
            });
            return prm;
        },
        get_fields: function(model) {
            return Sao.rpc({
                'method': 'model.' + model + '.fields_get'
            }, this.session);
        },
        on_row_expanded: function(node) {
            var container_view = jQuery('<ul/>').css('list-style', 'none')
                .insertAfter(node.view);
            this.children_expand(node).done(function() {
                this.view_populate(node.children, container_view);
            }.bind(this));
        },
        destroy: function() {
            this.el.modal('hide');
        }
    });

    Sao.Window.Import = Sao.class_(Sao.Window.CSV, {
        init: function(screen) {
            this.screen = screen;
            this.session = Sao.Session.current_session;
            this.fields_data = {}; // Ask before Removing this.
            this.fields_invert = {};
            Sao.Window.Import._super.init.call(this,
                Sao.i18n.gettext('Import from CSV'));

            jQuery('<button/>', {
                'class': 'btn btn-default btn-block',
                'type': 'button'
            }).append(jQuery('<i/>', {
                    'class': 'glyphicon glyphicon-search'
            })).click(function(){
                this.autodetect();
            }.bind(this)).append(' '+Sao.i18n.gettext('Auto-Detect'))
            .appendTo(this.column_buttons);

            var chooser_label = jQuery('<label/>', {
                'text': Sao.i18n.gettext('File to Import'),
                'class': 'col-sm-6 control-label',
                'for': 'input-csv-file'
            });

            this.file_input = jQuery('<input/>', {
                'type': 'file',
                'id': 'input-csv-file'
            });

            jQuery('<div/>', {
                'class': 'form-group'
            }).append(chooser_label).append(jQuery('<div/>', {
                'class': 'col-sm-6'
            }).append(this.file_input))
            .appendTo(this.chooser_form);

            jQuery('<hr>').insertAfter(this.chooser_form);

            var skip_label = jQuery('<label/>', {
                'text': Sao.i18n.gettext('Lines to Skip:'),
                'class': 'col-sm-2 control-label',
                'for': 'input-skip'
            });

            this.el_csv_skip = jQuery('<input/>', {
                'type': 'number',
                'class': 'form-control',
                'id': 'input-skip',
                'value': '0'
            });

            jQuery('<div/>', {
                'class': 'form-group'
            }).append(skip_label).append(jQuery('<div/>', {
                'class': 'col-sm-4'
            }).append(this.el_csv_skip))
            .appendTo(this.expander_csv);
        },
        sig_sel_add: function(el_field) {
            el_field = jQuery(el_field);
            var field = el_field.attr('field');
            var node = jQuery('<li/>', {
                'field': field,
            }).html(el_field.attr('name')).click(function(e) {
                if (e.ctrlKey) {
                    node.toggleClass('bg-primary');
                } else {
                    jQuery(e.target).addClass('bg-primary')
                        .siblings().removeClass('bg-primary');
                }
            }).appendTo(this.fields_selected);
        },
        view_populate: function (parent_node, parent_view) {
            var fields_order = Object.keys(parent_node).sort(function(a,b) {
                if (parent_node[b].string < parent_node[a].string) {
                    return -1;
                }
                else {
                    return 1;
                }
            }).reverse();

            fields_order.forEach(function(field) {
                var name = parent_node[field].string || field;
                var node = jQuery('<li/>', {
                    'field': parent_node[field].field,
                    'name': parent_node[field].name
                }).html(name).click(function(e) {
                    if(e.ctrlKey) {
                        node.toggleClass('bg-primary');
                    } else {
                        this.fields_all.find('li').removeClass('bg-primary');
                        node.addClass('bg-primary');
                    }
                }.bind(this)).appendTo(parent_view);
                parent_node[field].view = node;

                if (parent_node[field].relation) {
                    node.prepend(' ');
                    var expander_icon = jQuery('<i/>', {
                        'class': 'glyphicon glyphicon-plus'
                    }).click(function(e) {
                        e.stopPropagation();
                        expander_icon.toggleClass('glyphicon-plus')
                        .toggleClass('glyphicon-minus');
                        if(expander_icon.hasClass('glyphicon-minus')) {
                            this.on_row_expanded(parent_node[field]);
                        }
                        else {
                            node.next('ul').remove();
                        }
                    }.bind(this)).prependTo(node);
                }
            }.bind(this));
        },
        model_populate: function (fields, parent_node, prefix_field,
            prefix_name) {
            parent_node = parent_node || this.fields_model;
            prefix_field = prefix_field || '';
            prefix_name = prefix_name || '';

            Object.keys(fields).forEach(function(field) {
                if(!fields[field].readonly) {
                    var name = fields[field].string || field;
                    name = prefix_name + name;
                    // Only One2Many can be nested for import
                    var relation;
                    if (fields[field].type == 'one2many') {
                        relation = fields[field].relation;
                    } else {
                        relation = null;
                    }
                    var node = {
                        name: name,
                        field: prefix_field + field,
                        relation: relation,
                        string: fields[field].string
                    };
                    parent_node[field] = node;
                    this.fields[prefix_field + field] = node;
                    this.fields_invert[name] = prefix_field + field;
                    if (relation) {
                        node.children = {};
                    }
                }
            }.bind(this));
        },
        children_expand: function(node) {
            var dfd = jQuery.Deferred();
            if (jQuery.isEmptyObject(node.children)) {
                this.get_fields(node.relation).done(function(fields) {
                    this.model_populate(fields, node.children,
                        node.field + '/', node.name + '/');
                    dfd.resolve(this);
                }.bind(this));
            } else {
                dfd.resolve(this);
            }
            return dfd.promise();
        },
        autodetect: function() {
            var fname = this.file_input.val();
            if(!fname) {
                Sao.common.message.run(
                    Sao.i18n.gettext('You must select an import file first'));
                return;
            }
            this.fields_selected.empty();
            this.el_csv_skip.val(1);
            Papa.parse(this.file_input[0].files[0], {
                config: {
                    delimiter: this.el_csv_delimiter.val(),
                    quoteChar: this.el_csv_quotechar.val(),
                    preview: 1,
                    encoding: this.el_csv_encoding.val()
                },
                error: function(err, file, inputElem, reason) {
                    Sao.common.warning(
                        Sao.i18n.gettext('Error occured in loading the file'));
                },
                complete: function(results) {
                    results.data[0].forEach(function(word) {
                        if(word in this.fields_invert || word in this.fields) {
                            this.auto_select(word);
                        }
                        else {
                            var fields = this.fields_model;
                            var prefix = '';
                            var parents = word.split('/');
                            this.traverse(fields, prefix, parents, 0);
                        }
                    }.bind(this));
                }.bind(this)
            });
        },
        auto_select: function(word) {
            var name,field;
            if(word in this.fields_invert) {
                name = word;
                field = this.fields_invert[word];
            }
            else if (word in this.fields) {
                name = this.fields[word].name;
                field = [word];
            }
            else {
                Sao.common.warning.run(
                    Sao.i18n.gettext(
                        'Error processing the file at field %1.', word),
                        Sao.i18n.gettext('Error'));
                return;
            }
            var node = jQuery('<li/>', {
                'field': field
            }).html(name).click(function(){
                node.addClass('bg-primary')
                    .siblings().removeClass('bg-primary');
            }).appendTo(this.fields_selected);
        },
        traverse: function(fields, prefix, parents, i) {
            if(i >= parents.length - 1) {
                this.auto_select(parents.join('/'));
                return;
            }
            var field, item;
            var names = Object.keys(fields);
            for(item = 0; item<names.length; item++) {
                field = fields[names[item]];
                if(field.name == (prefix+parents[i]) ||
                    field.field == (prefix+parents[i])) {
                    this.children_expand(field).done(callback);
                    break;
                }
            }
            if(item == names.length) {
                this.auto_select(parents.join('/'));
                return;
            }
            function callback(self) {
                fields = field.children;
                prefix += parents[i] + '/';
                self.traverse(fields, prefix, parents, ++i);
            }
        },
        response: function(response_id) {
            if(response_id == 'RESPONSE_OK') {
                var fields = [];
                this.fields_selected.children('li').each(function(i, field_el) {
                    fields.push(field_el.getAttribute('field'));
                });
                var fname = this.file_input.val();
                if(fname) {
                    this.import_csv(fname, fields).then(function() {
                        this.destroy();
                    }.bind(this));
                } else {
                    this.destroy();
                }
            }
            else {
                this.destroy();
            }
        },
        import_csv: function(fname, fields) {
            var skip = this.el_csv_skip.val();
            var encoding = this.el_csv_encoding.val();
            var prm = jQuery.Deferred();

            Papa.parse(this.file_input[0].files[0], {
                config: {
                    delimiter: this.el_csv_delimiter.val(),
                    quoteChar: this.el_csv_quotechar.val(),
                    encoding: encoding
                },
                error: function(err, file, inputElem, reason) {
                    Sao.common.warning.run(
                        Sao.i18n.gettext('Error occured in loading the file'))
                        .always(prm.reject);
                },
                complete: function(results) {
                    function encode_utf8(s) {
                        return unescape(encodeURIComponent(s));
                    }
                    var data = [];
                    results.data.pop('');
                    results.data.forEach(function(line, i) {
                        if(i < skip) {
                            return;
                        }
                        var arr = [];
                        line.forEach(function(x){
                            arr.push(encode_utf8(x));
                        });
                        data.push(arr);
                    });
                    Sao.rpc({
                        'method': 'model.' + this.screen.model_name +
                        '.import_data',
                        'params': [fields, data, {}]
                    }, this.session).then(function(count) {
                        return Sao.common.message.run(
                            Sao.i18n.ngettext('%1 record imported',
                                '%1 records imported', count));
                    }).then(prm.resolve, prm.reject);
                }.bind(this)
            });
            return prm.promise();
        }
    });

    Sao.Window.Export = Sao.class_(Sao.Window.CSV, {
        init: function(screen, ids, names, context) {
            this.ids = ids;
            this.screen = screen;
            this.session = Sao.Session.current_session;
            this.context = context;
            Sao.Window.Export._super.init.call(this,
                Sao.i18n.gettext('Export to CSV')).then(function() {
                    names.forEach(function(name) {
                        this.sel_field(name);
                    }.bind(this));
                }.bind(this));

            var row_header = jQuery('<div/>', {
                'class': 'row'
            }).prependTo(this.dialog.body);

            var predefined_exports_column = jQuery('<div/>', {
                'class': 'col-md-12'
            }).append(jQuery('<label/>', {
                'text': Sao.i18n.gettext('Predefined Exports')
            })).appendTo(row_header);

            this.predef_exports_list = jQuery('<ul/>', {
                'class': 'list-unstyled predef-exports'
            }).css('cursor', 'pointer')
            .appendTo(predefined_exports_column);

            predefined_exports_column.append('<hr/>');

            this.predef_exports = {};
            this.fill_predefwin();

            jQuery('<button/>', {
                'class': 'btn btn-default btn-block',
                'type': 'button'
            }).append(jQuery('<i/>', {
                    'class': 'glyphicon glyphicon-floppy-save'
            })).click(function(){
                this.addreplace_predef();
            }.bind(this)).append(' '+Sao.i18n.gettext('Save Export'))
            .appendTo(this.column_buttons);

            jQuery('<button/>', {
                'class': 'btn btn-default btn-block',
                'type': 'button'
            }).append(jQuery('<i/>', {
                    'class': 'glyphicon glyphicon-floppy-remove'
            })).click(function(){
                this.remove_predef();
            }.bind(this)).append(' '+Sao.i18n.gettext('Delete Export'))
            .appendTo(this.column_buttons);

            this.el_add_field_names = jQuery('<input/>', {
                'type': 'checkbox',
                'checked': 'checked'
            });

            jQuery('<div/>', {
                'class': 'form-group'
            }).append(jQuery('<div/>', {
                'class': 'col-md-6'
            }).append(jQuery('<label/>', {
                'text': ' '+Sao.i18n.gettext('Add Field Names')
            }).prepend(this.el_add_field_names))).appendTo(this.expander_csv);
        },
        view_populate: function(parent_node, parent_view) {
            var names = Object.keys(parent_node).sort(function(a, b) {
                if (parent_node[b].string < parent_node[a].string) {
                    return -1;
                }
                else {
                    return 1;
                }
            }).reverse();

            names.forEach(function(name) {
                var path = parent_node[name].path;
                var node = jQuery('<li/>', {
                    'path': path
                }).html(parent_node[name].string).click(function(e) {
                    if(e.ctrlKey) {
                        node.toggleClass('bg-primary');
                    } else {
                        this.fields_all.find('li')
                            .removeClass('bg-primary');
                        node.addClass('bg-primary');
                    }
                }.bind(this)).appendTo(parent_view);
                parent_node[name].view = node;

                if (parent_node[name].children) {
                    node.prepend(' ');
                    var expander_icon = jQuery('<i/>', {
                        'class': 'glyphicon glyphicon-plus'
                    }).click(function(e){
                        e.stopPropagation();
                        expander_icon.toggleClass('glyphicon-plus')
                        .toggleClass('glyphicon-minus');
                        if(expander_icon.hasClass('glyphicon-minus')) {
                            this.on_row_expanded(parent_node[name]);
                        }
                        else {
                            node.next('ul').remove();
                        }
                    }.bind(this)).prependTo(node);
                }
            }.bind(this));
        },
        model_populate: function(fields, parent_node, prefix_field,
            prefix_name) {
            parent_node = parent_node || this.fields_model;
            prefix_field = prefix_field || '';
            prefix_name = prefix_name || '';

            Object.keys(fields).forEach(function(name) {
                var field = fields[name];
                var string = field.string || name;
                var items = [{ name: name, field: field, string: string }];

                if (field.type == 'selection') {
                    items.push({
                        name: name+'.translated',
                        field: field,
                        string: Sao.i18n.gettext('%1 (string)', string)
                    });
                }

                items.forEach(function(item) {
                    var path = prefix_field + item.name;
                    var long_string = item.string;

                    if (prefix_field) {
                        long_string = prefix_name + item.string;
                    }

                    var node = {
                        path: path,
                        string: item.string,
                        long_string: long_string,
                        relation: item.field.relation
                    };
                    parent_node[item.name] = node;
                    this.fields[path] = node;

                    // Insert relation only to real field
                    if (item.name.indexOf('.') == -1 && item.field.relation) {
                        node.children = {};
                    }
                }.bind(this));
            }.bind(this));
        },
        children_expand: function(node) {
            var dfd = jQuery.Deferred();
            if(jQuery.isEmptyObject(node.children)) {
                this.get_fields(node.relation).done(function(fields) {
                    this.model_populate(fields, node.children,
                        node.path + '/', node.string + '/');
                    dfd.resolve(this);
                }.bind(this));
            } else {
                dfd.resolve(this);
            }
            return dfd.promise();
        },
        sig_sel_add: function(el_field) {
            el_field = jQuery(el_field);
            var name = el_field.attr('path');
            this.sel_field(name);
        },
        fill_predefwin: function() {
            Sao.rpc({
                'method': 'model.ir.export.search',
                'params': [['resource', '=', this.screen.model_name], {}]
            }, this.session).done(function(export_ids) {
                Sao.rpc({
                    'method': 'model.ir.export.read',
                    'params': [export_ids, {}]
                }, this.session).done(function(exports) {
                    var arr = [];
                    exports.forEach(function(o) {
                        for (var i = 0; i < o.export_fields.length; 
                            arr.push(o.export_fields[i++]));
                    });
                    Sao.rpc({
                        'method': 'model.ir.export.line.read',
                        'params': [arr, {}]
                    }, this.session).done(function(lines) {
                        var id2lines = {};
                        lines.forEach(function(line) {
                            id2lines[line.export] = id2lines[line.export] || [];
                            id2lines[line.export].push(line);
                        });
                        exports.forEach(function(export_) {
                            this.predef_exports[export_.id] =
                                id2lines[export_.id].map(function(obj) {
                                    if(obj.export == export_.id)
                                        return obj.name;
                                });
                            this.add_to_predef(export_.id, export_.name);
                        }.bind(this));
                        this.predef_exports_list.children('li').first().focus();
                    }.bind(this));
                }.bind(this));
            }.bind(this));
        },
        add_to_predef: function(id, name) {
            var node = jQuery('<li/>', {
                'text': name,
                'export_id': id,
                'tabindex': 0
            }).on('keypress', function(e) {
                var keyCode = (e.keyCode ? e.keyCode : e.which);
                if(keyCode == 13 || keyCode == 32) {
                    node.click();
                }
            }).click(function(event) {
                node.addClass('bg-primary')
                    .siblings().removeClass('bg-primary');
                this.sel_predef(jQuery(event.target).attr('export_id'));
            }.bind(this));
            this.predef_exports_list.append(node);
        },
        addreplace_predef: function() {
            var fields = [];
            var selected_fields = this.fields_selected.children('li');
            for(var i=0; i<selected_fields.length; i++) {
                fields.push(selected_fields[i].getAttribute('path'));
            }
            if(fields.length === 0) {
                return;
            }
            var pref_id, name;
            var selection = this.predef_exports_list.children('li.bg-primary');
            if (selection.length === 0) {
                pref_id = null;
                Sao.common.ask.run(
                    Sao.i18n.gettext('What is the name of this export?'))
                .then(function(name) {
                    if (!name) {
                        return;
                    }
                    this.save_predef(name, fields, selection);
                }.bind(this));
            }
            else {
                pref_id = selection.attr('export_id');
                name = selection.text();
                Sao.common.sur.run(
                    Sao.i18n.gettext('Override %1 definition?', name))
                .done(function() {
                    this.save_predef(name, fields, selection);
                    Sao.rpc({
                        'method': 'model.ir.export.delete',
                        'params': [[pref_id], {}]
                    }, this.session).then(function() {
                        delete this.predef_exports[pref_id];
                    }.bind(this));
                }.bind(this));
            }
        },
        save_predef: function(name, fields, selection) {
            Sao.rpc({
                'method': 'model.ir.export.create',
                'params': [[{
                    'name': name,
                    'resource': this.screen.model_name,
                    'export_fields': [['create', fields.map(function(x) {
                        return {
                            'name': x
                        };
                    })]]
                }], {}]
            }, this.session).then(function(new_id) {
                this.predef_exports[new_id] = fields;
                if (selection.length === 0) {
                    this.add_to_predef(new_id, name);
                }
                else {
                    this.predef_exports[new_id] = fields;
                    selection.attr('export_id', new_id);
                }
            }.bind(this));
        },
        remove_predef: function() {
            var selection = this.predef_exports_list.children('li.bg-primary');
            if (selection.length === 0) {
                return;
            }
            var export_id = jQuery(selection).attr('export_id');
            Sao.rpc({
                'method': 'model.ir.export.delete',
                'params': [[export_id], {}]
            }, this.session).then(function() {
                delete this.predef_exports[export_id];
                selection.remove();
            }.bind(this));
        },
        sel_predef: function(export_id) {
            this.fields_selected.empty();
            this.predef_exports[export_id].forEach(function(name) {
                if (!(name in this.fields)) {
                    var fields = this.fields_model;
                    var prefix = '';
                    var parents = name.split('/');
                    this.traverse(fields, prefix, parents, 0);
                }
                if(!(name in this.fields)) {
                    return;
                }
                this.sel_field(name);
            }.bind(this));
        },
        traverse: function(fields, prefix, parents, i) {
            if(i >= parents.length-1) {
                this.sel_field(parents.join('/'));
                return;
            }
            var field, item;
            var names = Object.keys(fields);
            for(item = 0; item < names.length; item++) {
                field = fields[names[item]];
                if(field.path == (prefix+parents[i])) {
                    this.children_expand(field).done(callback);
                    break;
                }
            }
            if(item == names.length) {
                this.sel_field(parents.join('/'));
                return;
            }
            function callback(self){
                fields = field.children;
                prefix += parents[i] + '/';
                self.traverse(fields, prefix, parents, ++i);
            }
        },
        sel_field: function(name) {
            var long_string = this.fields[name].long_string;
            var relation = this.fields[name].relation;
            if (relation) {
                return;
            }
            var node = jQuery('<li/>', {
                'path': name,
            }).html(long_string).click(function(e) {
                if(e.ctrlKey) {
                    node.toggleClass('bg-primary');
                } else {
                    jQuery(e.target).addClass('bg-primary')
                        .siblings().removeClass('bg-primary');
                }
            }).appendTo(this.fields_selected);
        },
        response: function(response_id) {
            if(response_id == 'RESPONSE_OK') {
                var fields = [];
                var fields2 = [];
                this.fields_selected.children('li').each(function(i, field) {
                    fields.push(field.getAttribute('path'));
                    fields2.push(field.innerText);
                });
                Sao.rpc({
                    'method': 'model.' + this.screen.model_name +
                        '.export_data',
                    'params': [this.ids, fields, this.context]
                }, this.session).then(function(data) {
                    this.export_csv(fields2, data).then(function() {
                        this.destroy();
                    }.bind(this));
                }.bind(this));
            } else {
                this.destroy();
            }
        },
        export_csv: function(fields, data) {
            var encoding = this.el_csv_encoding.val();
            var unparse_obj = {};
            unparse_obj.data = data;
            if (this.el_add_field_names.is(':checked')) {
                unparse_obj.fields = fields;
            }
            var csv = Papa.unparse(unparse_obj, {
                quoteChar: this.el_csv_quotechar.val(),
                delimiter: this.el_csv_delimiter.val()
            });
            var blob = new Blob([csv], {type: 'text/csv;charset=' + encoding});
            var blob_url = window.URL.createObjectURL(blob);
            if (this.blob_url) {
                window.URL.revokeObjectURL(this.blob_url);
            }
            this.blob_url = blob_url;
            window.open(blob_url);

            return Sao.common.message.run(
                Sao.i18n.ngettext('%1 record saved', '%1 records saved',
                    data.length));
        }
    });

}());
