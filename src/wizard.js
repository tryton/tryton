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
            Sao.rpc({
                'method': 'wizard.' + this.action + '.create',
                'params': [this.session.context]
            }, this.session).then(function(result) {
                this.session_id = result[0];
                this.start_state = this.state = result[1];
                this.end_state = result[2];
                this.process();
            }.bind(this), function() {
                this.destroy();
            }.bind(this));
        },
        process: function() {
            if (this.__processing || this.__waiting_response) {
                return;
            }
            var process = function() {
                if (this.state == this.end_state) {
                    this.end();
                    return;
                }
                var ctx = jQuery.extend({}, this.context);
                var data = {};
                if (this.screen) {
                    data[this.screen_state] = this.screen.get_on_change_value();
                }
                Sao.rpc({
                    'method': 'wizard.' + this.action + '.execute',
                    'params': [this.session_id, data, this.state, ctx]
                }, this.session).then(function(result) {
                    if (result.view) {
                        this.clean();
                        var view = result.view;
                        this.update(view.fields_view, view.buttons);

                        this.screen.new_(false).then(function() {
                            this.screen.current_record.set_default(view.defaults);
                            this.update_buttons();
                            this.screen.set_cursor();
                        }.bind(this));

                        this.screen_state = view.state;
                        this.__waiting_response = true;
                    } else {
                        this.state = this.end_state;
                    }

                    var execute_actions = function execute_actions() {
                        if (result.actions) {
                            result.actions.forEach(function(action) {
                                var context = jQuery.extend({}, this.context);
                                // Remove wizard keys added by run
                                delete context.active_id;
                                delete context.active_ids;
                                delete context.active_model;
                                delete context.action_id;
                                Sao.Action.exec_action(action[0], action[1],
                                    context);
                            }.bind(this));
                        }
                    }.bind(this);

                    if (this.state == this.end_state) {
                        this.end().then(execute_actions);
                    } else {
                        execute_actions();
                    }
                    this.__processing = false;
                }.bind(this), function(result) {
                    // TODO end for server error.
                    this.__processing = false;
                }.bind(this));
            };
            process.call(this);
        },
        destroy: function(action) {
            // TODO
        },
        end: function() {
            return Sao.rpc({
                'method': 'wizard.' + this.action + '.delete',
                'params': [this.session_id, this.session.context]
            }, this.session).then(function(action) {
                this.destroy(action);
            }.bind(this));
        },
        clean: function() {
            this.widget.empty();
            this.states = {};
        },
        response: function(state) {
            this.__waiting_response = false;
            this.screen.current_view.set_value();
            return this.screen.current_record.validate().then(function(validate) {
                if ((!validate) && state != this.end_state) {
                    this.screen.display(true);
                    this.info_bar.message(
                        this.screen.invalid_message(), 'danger');
                    return;
                }
                this.info_bar.message();
                this.state = state;
                this.process();
            }.bind(this));
        },
        _get_button: function(definition) {
            var button = new Sao.common.Button(definition);
            this.states[definition.state] = button;
            if (definition.default) {
                button.el.addClass('btn-primary');
            } else if (definition.state == this.end_state) {
                button.el.addClass('btn-link');
            }
            return button;
        },
        update_buttons: function() {
            var record = this.screen.current_record;
            for (var state in this.states) {
                var button = this.states[state];
                button.set_state(record);
            }
        },
        update: function(view, buttons) {
            buttons.forEach(function(button) {
                this._get_button(button);
            }.bind(this));
            this.screen = new Sao.Screen(view.model,
                    {mode: [], context: this.context});
            this.screen.add_view(view);
            this.screen.switch_view();
            this.screen.group_changed_callback = this.update_buttons.bind(this);
            this.header.append(jQuery('<h4/>', {
                'class': 'model-title',
                'title': this.name,
            }).append(Sao.common.ellipsize(this.name, 80)));
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
        win.run(attributes);
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
            button.el.click(function() {
                this.response(definition.state);
            }.bind(this));
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
            return Sao.Wizard.Form._super.end.call(this).always(function() {
                return this.tab.close();
            }.bind(this));
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
            this.dialog.on('keydown', function(e) {
                if (e.which == Sao.common.ESC_KEYCODE) {
                    e.preventDefault();
                    if (this.end_state in this.states) {
                        this.response(this.end_state);
                    }
                }
            }.bind(this));
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
                this.content.submit(function(e) {
                    this.response(definition.state);
                    e.preventDefault();
                }.bind(this));
                button.el.attr('type', 'submit');
            } else {
                button.el.click(function() {
                    this.response(definition.state);
                }.bind(this));
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
            var destroy = function() {
                this.dialog.remove();
                var dialog = jQuery('.wizard-dialog').filter(':visible')[0];
                var is_menu = false;
                var screen;
                if (!dialog) {
                    dialog = Sao.Tab.tabs.get_current();
                    if (dialog) {
                        if (dialog.screen &&
                               dialog.screen.model_name != this.model) {
                            is_menu = true;
                            screen = Sao.main_menu_screen;
                        }
                    } else {
                        is_menu = true;
                        screen = Sao.main_menu_screen;
                    }
                }
                if (dialog && dialog.screen) {
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
            }.bind(this);
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
                for (var i = 0; i < fields.length; i++) {
                    var name = fields[i];
                    var widgets = view.widgets[name];
                    for (var j = 0; j < widgets.length; j++) {
                        var widget = widgets[j];
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
