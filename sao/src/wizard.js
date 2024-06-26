/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.Wizard = Sao.class_(Object, {
        init: function(name) {
            this.widget = jQuery('<div/>', {
                'class': 'wizard'
            });
            this.name = name || Sao.i18n.gettext('Wizard');
            this.action_id = null;
            this.id = null;
            this.ids = null;
            this.action = null;
            this.context = null;
            this.states = {};
            this.session_id = null;
            this.start_state = null;
            this.end_state = null;
            this.screen = null;
            this.screen_state = null;
            this.state = null;
            this.session = Sao.Session.current_session;
            this.__processing = false;
            this.__waiting_response = false;
            this.info_bar = new Sao.Window.InfoBar();
        },
        run: function(attributes) {
            this.action = attributes.action;
            this.action_id = attributes.data.action_id;
            this.id = attributes.data.id;
            this.ids = attributes.data.ids;
            this.model = attributes.data.model;
            this.context = jQuery.extend({}, attributes.context);
            this.context.active_id = this.id;
            this.context.active_ids = this.ids;
            this.context.active_model = this.model;
            this.context.action_id = this.action_id;
            return Sao.rpc({
                'method': 'wizard.' + this.action + '.create',
                'params': [this.session.context]
            }, this.session).then(result => {
                this.session_id = result[0];
                this.start_state = this.state = result[1];
                this.end_state = result[2];
                return this.process();
            }, () => {
                this.destroy();
            });
        },
        process: function() {
            if (this.__processing || this.__waiting_response) {
                return jQuery.when();
            }
            var process = function() {
                if (this.state == this.end_state) {
                    return this.end();
                }
                var ctx = jQuery.extend({}, this.context);
                var data = {};
                if (this.screen) {
                    data[this.screen_state] = this.screen.get_on_change_value();
                }
                return Sao.rpc({
                    'method': 'wizard.' + this.action + '.execute',
                    'params': [this.session_id, data, this.state, ctx]
                }, this.session).then(result => {
                    var prms = [];
                    if (result.view) {
                        this.clean();
                        var view = result.view;
                        this.update(view.fields_view, view.buttons);

                        prms.push(this.screen.new_(false).then(() => {
                            this.screen.current_record.set_default(
                                view.defaults || {})
                                .then(() => {
                                    this.screen.current_record.set(
                                        view.values || {});
                                    this.update_buttons();
                                    this.screen.set_cursor();
                                });
                        }));

                        this.screen_state = view.state;
                        this.__waiting_response = true;
                    } else {
                        this.state = this.end_state;
                    }

                    const execute_actions = () => {
                        var prms = [];
                        if (result.actions) {
                            for (const action of result.actions) {
                                var context = jQuery.extend({}, this.context);
                                // Remove wizard keys added by run
                                delete context.active_id;
                                delete context.active_ids;
                                delete context.active_model;
                                delete context.action_id;
                                prms.push(Sao.Action.execute(
                                    action[0], action[1], context));
                            }
                        }
                        return jQuery.when.apply(jQuery, prms);
                    };

                    if (this.state == this.end_state) {
                        prms.push(this.end().then(execute_actions));
                    } else {
                        prms.push(execute_actions());
                    }
                    this.__processing = false;
                    return jQuery.when.apply(jQuery, prms);
                }, result => {
                    // TODO end for server error.
                    this.__processing = false;
                });
            };
            return process.call(this);
        },
        destroy: function(action) {
            // TODO
        },
        end: function() {
            return Sao.rpc({
                'method': 'wizard.' + this.action + '.delete',
                'params': [this.session_id, this.session.context]
            }, this.session).then(action => {
                this.destroy(action);
            })
            .fail(() => {
                Sao.Logger.warn(
                    "Unable to delete session %s of wizard %s",
                    this.session_id, this.action);
            });
        },
        clean: function() {
            this.widget.empty();
            this.states = {};
        },
        response: function(definition) {
            this.__waiting_response = false;
            this.screen.current_view.set_value();
            if (definition.validate && !this.screen.current_record.validate(
                    null, null, null, true)) {
                this.screen.display(true);
                this.info_bar.add(this.screen.invalid_message(), 'danger');
                return;
            }
            this.info_bar.clear();
            this.state = definition.state;
            this.process();
        },
        _get_button: function(definition) {
            var style = 'btn-default';
            if (definition.default) {
                style = 'btn-primary';
            } else if (definition.state == this.end_state) {
                style = 'btn-link';
            }
            var button = new Sao.common.Button(
                definition, undefined, undefined, style);
            this.states[definition.state] = button;
            return button;
        },
        record_modified: function() {
            this.update_buttons();
            this.info_bar.refresh();
        },
        update_buttons: function() {
            var record = this.screen.current_record;
            for (var state in this.states) {
                var button = this.states[state];
                button.set_state(record);
            }
        },
        update: function(view, buttons) {
            for (const button of buttons) {
                this._get_button(button);
            }
            if (this.screen) {
                this.screen.windows.splice(
                    this.screen.windows.indexOf(this), 1);
            }
            this.screen = new Sao.Screen(view.model,
                    {mode: [], context: this.context});
            this.screen.add_view(view);
            this.screen.switch_view();
            this.screen.windows.push(this);
            this.header.append(jQuery('<h4/>', {
                'class': 'model-title',
                'title': this.name,
            }).text(Sao.common.ellipsize(this.name, 80)));
            this.widget.append(this.screen.screen_container.el);
        }
    });

    Sao.Wizard.create = function(attributes) {
        var win;
        if (attributes.window) {
            win = new Sao.Wizard.Form(attributes.name);
            var tab = new Sao.Tab.Wizard(win);
            Sao.Tab.add(tab);
        } else {
            win = new Sao.Wizard.Dialog(attributes.name);
        }
        return win.run(attributes);
    };

    Sao.Wizard.Form = Sao.class_(Sao.Wizard, {
        init: function(name) {
            Sao.Wizard.Form._super.init.call(this, name);
            this.tab = null;  // Filled by Sao.Tab.Wizard

            this.header = jQuery('<div/>', {
                'class': 'modal-header',
            });
            this.form = jQuery('<div/>', {
                'class': 'wizard-form',
            }).append(this.header).append(this.widget);
            this.footer = jQuery('<div/>', {
                'class': 'modal-footer'
            }).appendTo(this.form);
        },
        clean: function() {
            Sao.Wizard.Form._super.clean.call(this);
            this.header.empty();
            this.footer.empty();
        },
        _get_button: function(definition) {
            var button = Sao.Wizard.Form._super._get_button.call(this,
                definition);
            this.footer.append(button.el);
            button.el.click(() => {
                this.response(definition);
            });
            return button;
        },
        destroy: function(action) {
            Sao.Wizard.Form._super.destroy.call(this, action);
            switch (action) {
                case 'reload menu':
                    Sao.Session.current_session.reload_context()
                        .then(function() {
                            Sao.menu();
                        });
                    break;
                case 'reload context':
                    Sao.Session.current_session.reload_context();
                    break;
            }
        },
        end: function() {
            return Sao.Wizard.Form._super.end.call(this).always(
                () => this.tab.close());
        }
    });

    Sao.Wizard.Dialog = Sao.class_(Sao.Wizard, { // TODO nomodal
        init: function(name) {
            Sao.Wizard.Dialog._super.init.call(this, name);
            var dialog = new Sao.Dialog(name, 'wizard-dialog', 'md', false);
            this.dialog = dialog.modal;
            this.header = dialog.header;
            this.content = dialog.content;
            this.footer = dialog.footer;
            this.dialog.on('keydown', e => {
                if (e.which == Sao.common.ESC_KEYCODE) {
                    e.preventDefault();
                    if (this.end_state in this.states) {
                        this.response(this.states[this.end_state].attributes);
                    }
                }
            });
            dialog.body.append(this.widget).append(this.info_bar.el);
        },
        clean: function() {
            Sao.Wizard.Dialog._super.clean.call(this);
            this.header.empty();
            this.footer.empty();
        },
        _get_button: function(definition) {
            var button = Sao.Wizard.Dialog._super._get_button.call(this,
                    definition);
            this.footer.append(button.el);
            if (definition['default']) {
                this.content.unbind('submit');
                this.content.submit(e => {
                    this.response(definition);
                    e.preventDefault();
                });
                button.el.attr('type', 'submit');
            } else {
                button.el.click(() => {
                    this.response(definition);
                });
            }
            return button;
        },
        update: function(view, buttons) {
            this.content.unbind('submit');
            Sao.Wizard.Dialog._super.update.call(this, view, buttons);
            this.show();
        },
        destroy: function(action) {
            Sao.Wizard.Dialog._super.destroy.call(this, action);
            const destroy = () => {
                this.dialog.remove();
                var dialog = jQuery('.wizard-dialog').filter(':visible')[0];
                var is_menu = false;
                var screen;
                if (!dialog) {
                    dialog = Sao.Tab.tabs.get_current();
                }
                if (!dialog ||
                    !this.model ||
                    (Sao.main_menu_screen &&
                    (Sao.main_menu_screen.model_name == this.model))) {
                    is_menu = true;
                    screen = Sao.main_menu_screen;
                } else {
                    screen = dialog.screen;
                }
                if (screen) {
                    var prm = jQuery.when();
                    if (screen.current_record && !is_menu) {
                        var ids;
                        if (screen.model_name == this.model) {
                            ids = this.ids;
                        } else {
                            // Wizard run form a children record so reload
                            // parent record
                            ids = [screen.current_record.id];
                        }
                        prm = screen.reload(ids, true);
                    }
                    if (action) {
                        prm.then(function() {
                            screen.client_action(action);
                        });
                    }
                }
            };
            if ((this.dialog.data('bs.modal') || {}).isShown) {
                this.dialog.on('hidden.bs.modal', destroy);
                this.dialog.modal('hide');
            } else {
                destroy();
            }
        },
        show: function() {
            var view = this.screen.current_view;
            var expand;
            if (view.view_type == 'form') {
                expand = false;
                var fields = view.get_fields();
                for (const name of fields) {
                    var widgets = view.widgets[name];
                    for (const widget of widgets) {
                        if (widget.expand) {
                            expand = true;
                            break;
                        }
                    }
                    if (expand) {
                        break;
                    }
                }
            } else {
                expand = true;
            }
            if (expand) {
                this.dialog.find('.modal-dialog')
                    .removeClass('modal-md modal-sm')
                    .addClass('modal-lg');
            } else {
                this.dialog.find('.modal-dialog')
                    .removeClass('modal-lg modal-sm')
                    .addClass('modal-md');
            }
            this.dialog.modal('show');
        },
        hide: function() {
            this.dialog.modal('hide');
        },
        state_changed: function() {
            this.process();
        }
    });

}());
