/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.Wizard = Sao.class_(Object, {
        init: function(name) {
            this.widget = jQuery('<div/>', {
                'class': 'wizard'
            });
            this.name = name;
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
        },
        run: function(attributes) {
            this.action = attributes.action;
            this.action_id = attributes.data.action_id;
            this.id = attributes.data.id;
            this.ids = attributes.data.ids;
            this.model = attributes.data.model;
            this.context = attributes.context;
            Sao.rpc({
                'method': 'wizard.' + this.action + '.create',
                'params': [this.session.context]
            }, this.session).then(function(result) {
                this.session_id = result[0];
                this.start_state = this.state = result[1];
                this.end_state = result[2];
                this.process();
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
                ctx.active_id = this.id;
                ctx.active_ids = this.ids;
                ctx.active_model = this.model;
                ctx.action_id = this.action_id;
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
                        this.update(view.fields_view, view.defaults,
                            view.buttons);
                        this.screen_state = view.state;
                        this.__waiting_response = true;
                    } else {
                        this.state = this.end_state;
                    }

                    var execute_actions = function execute_actions() {
                        if (result.actions) {
                            result.actions.forEach(function(action) {
                                Sao.Action.exec_action(action[0], action[1],
                                    jQuery.extend({}, this.context));
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
        destroy: function() {
            // TODO
        },
        end: function() {
            return Sao.rpc({
                'method': 'wizard.' + this.action + '.delete',
                'params': [this.session_id, this.session.context]
            }, this.session);
        },
        clean: function() {
            this.widget.children().remove();
            this.states = {};
        },
        response: function(state) {
            this.__waiting_response = false;
            this.screen.current_view.set_value();
            return this.screen.current_record.validate().then(function(validate) {
                if ((!validate) && state != this.end_state) {
                    this.screen.display();
                    return;
                }
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
        update: function(view, defaults, buttons) {
            buttons.forEach(function(button) {
                this._get_button(button);
            }.bind(this));
            this.screen = new Sao.Screen(view.model,
                    {mode: [], context: this.context});
            this.screen.add_view(view);
            this.screen.switch_view();
            // TODO record-modified
            // TODO title
            // TODO toolbar
            this.widget.append(this.screen.screen_container.el);

            this.screen.new_(false);
            this.screen.current_record.set_default(defaults);
            // TODO set_cursor
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
            Sao.Wizard.Form._super.init.call(this);
            this.tab = null;  // Filled by Sao.Tab.Wizard
            this.name = name;

            this.form = jQuery('<div/>', {
                'class': 'wizard-form',
            }).append(this.widget);
            this.footer = jQuery('<div/>', {
                'class': 'modal-footer'
            }).appendTo(this.form);
        },
        clean: function() {
            Sao.Wizard.Form._super.clean.call(this);
            this.footer.children().remove();
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
        end: function() {
            return Sao.Wizard.Form._super.end.call(this).always(function() {
                return this.tab.close();
            }.bind(this));
        }
    });

    Sao.Wizard.Dialog = Sao.class_(Sao.Wizard, { // TODO nomodal
        init: function(name) {
            if (!name) {
                name = 'Wizard'; // TODO translate
            }
            Sao.Wizard.Dialog._super.init.call(this);
            this.dialog = jQuery('<div/>', {
                'class': 'wizard-dialog modal fade',
                role: 'dialog'
            });
            var content = this.content = jQuery('<form/>', {
                'class': 'modal-content'
            }).appendTo(jQuery('<div/>', {
                'class': 'modal-dialog modal-lg'
            }).appendTo(this.dialog));
            var header = jQuery('<div/>', {
                'class': 'modal-header'
            }).append(jQuery('<h4/>', {
                'class': 'modal-title'
            }).append(name)).appendTo(content);
            var body = jQuery('<div/>', {
                'class': 'modal-body'
            }).appendTo(content);
            this.footer = jQuery('<div/>', {
                'class': 'modal-footer'
            }).appendTo(content);

            body.append(this.widget);
        },
        clean: function() {
            Sao.Wizard.Dialog._super.clean.call(this);
            this.footer.children().remove();
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
        update: function(view, defaults, buttons) {
            this.content.unbind('submit');
            Sao.Wizard.Dialog._super.update.call(this, view, defaults,
                    buttons);
            this.dialog.modal('show');
        },
        destroy: function(action) {
            Sao.Wizard.Dialog._super.destroy.call(this);
            this.dialog.modal('hide').remove();
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
                if (screen.current_record && !is_menu) {
                    var ids;
                    if (screen.model_name == this.model) {
                        ids = this.ids;
                    } else {
                        // Wizard run form a children record so reload parent
                        // record
                        ids = [screen.current_record.id];
                    }
                    screen.reload(ids, true);
                }
                if (action) {
                    screen.client_action(action);
                }
            }
        },
        end: function() {
            return Sao.Wizard.Dialog._super.end.call(this).then(
                    this.destroy.bind(this));
        },
        show: function() {
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
