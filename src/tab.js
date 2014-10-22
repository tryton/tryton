/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.Tab = Sao.class_(Object, {
        init: function() {
            Sao.Tab.tabs.push(this);
            this.buttons = {};
        },
        create_tabcontent: function() {
            this.el = jQuery('<div/>', {
                'class': this.class_
            });

            this.title = this.make_title_bar();
            this.el.append(this.title);

            var toolbar = this.create_toolbar();
            this.el.append(toolbar);
        },
        make_title_bar: function() {
            var title = jQuery('<div/>', {
                'class': 'tab-title-bar ui-widget-header ui-corner-all'
            });

            var menu = this.set_menu();
            title.append(menu);
            title.append(jQuery('<button/>', {
                'class': 'tab-title'
            }).button({
                label: this.name,
                text: true,
                icons: {
                    primary: 'ui-icon-triangle-1-s'
                }
            }).click(function() {
                menu.toggle().position({
                    my: 'left top',
                    at: 'left bottom',
                    of: jQuery(this)
                });
                // Bind hide after the processing of the current click
                window.setTimeout(function() {
                    jQuery(document).one('click', function() {
                        menu.hide();
                    });
                }, 0);
            }));

            this.status = jQuery('<span/>', {
                'class': 'tab-status'
            });
            title.append(this.status);

            this.info = jQuery('<span/>', {
                'class': 'tab-info'
            });
            title.append(this.info);
            return title;
        },
        set_menu: function() {
            var menu = jQuery('<ul/>');
            this.menu_def.forEach(function(definition) {
                var icon = definition[0];
                var name = definition[1];
                var func = definition[2];
                if (!func) {
                    return;
                }
                var item = jQuery('<li/>').append(
                    jQuery('<a/>').append(jQuery('<span/>', {
                        'class': 'ui-icon ' + icon
                    })).append(name));
                menu.append(item);
                item.click(function() {
                    this[func]();
                }.bind(this));
            }.bind(this));
            menu.menu({}).hide().css({
                position: 'absolute',
                'z-index': 100
            });
            return menu;
        },
        create_toolbar: function() {
            var toolbar = jQuery('<div/>', {
                'class': 'tab-toolbar ui-widget-header ui-corner-all'
            });
            var add_button = function(tool) {
                var click_func = function() {
                    this[tool[4]]();
                };
                var button = jQuery('<button/>').button({
                    id: tool[0],
                    text: tool[2],
                    icons: {
                        primary: tool[1]
                    },
                    label: tool[2]
                })
                .click(click_func.bind(this));
                toolbar.append(button);
                // TODO tooltip
                this.buttons[tool[0]] = button;
            };
            this.toolbar_def.forEach(add_button.bind(this));
            return toolbar;
        },
        close: function() {
            var tabs = jQuery('#tabs > div');
            var tab = tabs.find(
                    '.ui-tabs-nav li[aria-controls="' + this.id + '"]');
            tabs.tabs('option', 'active',
                    tabs.find('li').index(jQuery('#nav-' + this.id)));
            tabs.tabs('refresh');
            return this.modified_save().then(function() {
                tab.remove();
                jQuery('#' + this.id).remove();
                tabs.tabs('refresh');
                if (!tabs.find('> ul').children().length) {
                    tabs.remove();
                }
                Sao.Tab.tabs.splice(Sao.Tab.tabs.indexOf(this), 1);
            }.bind(this));
        }
    });

    Sao.Tab.counter = 0;
    Sao.Tab.tabs = [];
    Sao.Tab.tabs.close = function(warning) {
        if (warning && Sao.Tab.tabs.length) {
            return Sao.common.sur.run(
                    'The following action requires to close all tabs.\n' +
                    'Do you want to continue?').then(function() {
                        return Sao.Tab.tabs.close(false);
                    });
        }
        if (Sao.Tab.tabs.length) {
            var tab = Sao.Tab.tabs[0];
            return tab.close().then(function() {
                if (!~Sao.Tab.tabs.indexOf(tab)) {
                    return Sao.Tab.tabs.close();
                } else {
                    return jQuery.Deferred().reject();
                }
            });
        }
        if (Sao.main_menu_screen) {
            Sao.main_menu_screen.save_tree_state();
            Sao.main_menu_screen = null;
        }
        return jQuery.when();
    };
    Sao.Tab.tabs.get_current = function() {
        var tabs = jQuery('#tabs > div');
        return Sao.Tab.tabs[tabs.tabs('option', 'active')];
    };
    Sao.Tab.tabs.close_current = function() {
        var tab = this.get_current();
        tab.close();
    };

    Sao.Tab.create = function(attributes) {
        if (attributes.context === undefined) {
            attributes.context = {};
        }
        var tab;
        if (attributes.model) {
            tab = new Sao.Tab.Form(attributes.model, attributes);
        } else {
            tab = new Sao.Tab.Board(attributes);
        }
        if (!jQuery('#tabs').children().length) {
            jQuery('#tabs').append(jQuery('<div/>').append(jQuery('<ul/>')));
        }
        var tabs = jQuery('#tabs > div');
        tabs.tabs();
        tab.id = 'tab-' + Sao.Tab.counter++;
        var tab_link = jQuery('<a/>', {
            href: '#' + tab.id
        }).append(tab.name);
        var close_link = jQuery('<a/>', {
            href: '#',
            'class': 'ui-tabs-anchor'
        }).append(jQuery('<span/>', {
            'class': 'ui-icon ui-icon-circle-close'
        })).hover(
        function() {
            jQuery(this).css('cursor', 'pointer');
        },
        function() {
            jQuery(this).css('cursor', 'default');
        })
        .click(function() {
            tab.close();
        });
        jQuery('<li/>', {
            id: 'nav-' + tab.id
        }).append(tab_link).append(close_link)
        .appendTo(tabs.find('> .ui-tabs-nav'));
        jQuery('<div/>', {
            id: tab.id
        }).html(tab.el).appendTo(tabs);
        tabs.tabs('refresh');
        tabs.tabs('option', 'active', -1);
        jQuery(window).resize();
    };

    Sao.Tab.Form = Sao.class_(Sao.Tab, {
        class_: 'tab-form',
        init: function(model_name, attributes) {
            Sao.Tab.Form._super.init.call(this);
            var screen = new Sao.Screen(model_name, attributes);
            screen.tab = this;
            this.screen = screen;
            this.attributes = jQuery.extend({}, attributes);
            this.name = attributes.name; // XXX use screen current view title

            if (!Sao.common.MODELHISTORY.contains(model_name)) {
                this.menu_def = jQuery.extend([], this.menu_def);
                this.menu_def[10] = jQuery.extend([], this.menu_def[10]);
                // Remove callback to revision
                this.menu_def[10][2] = null;
            }

            this.create_tabcontent();

            var access = Sao.common.MODELACCESS.get(model_name);
            [['new', 'create'], ['save', 'write']].forEach(function(e) {
                var button = e[0];
                var access_type = e[1];
                this.buttons[button].prop('disabled', !access[access_type]);
            }.bind(this));

            this.view_prm = this.screen.switch_view().done(function() {
                this.el.append(screen.screen_container.el);
                if (attributes.res_id) {
                    screen.group.load([attributes.res_id]);
                    screen.set_current_record(
                        screen.group.get(attributes.res_id));
                    screen.display();
                } else {
                    if (screen.current_view.view_type == 'form') {
                        screen.new_();
                    }
                    if (~['tree', 'graph', 'calendar'].indexOf(
                            screen.current_view.view_type)) {
                        screen.search_filter();
                    }
                }
                this.update_revision();
            }.bind(this));
        },
        // TODO translate labels
        toolbar_def: [
            ['new', 'ui-icon-document', 'New', 'Create a new record', 'new_'],
            ['save', 'ui-icon-disk', 'Save', 'Save this record', 'save'],
            ['switch', 'ui-icon-arrow-4-diag', 'Switch', 'Switch view',
            'switch_'],
            ['reload', 'ui-icon-refresh', 'Reload', 'Reload', 'reload'],
            ['previous', 'ui-icon-arrowthick-1-w', 'Previous',
            'Previous Record', 'previous'],
            ['next', 'ui-icon-arrowthick-1-e', 'Next', 'Next Record', 'next'],
            ['attach', 'ui-icon-pin-w', 'Attachment',
            'Add an attachment to the record', 'attach']
            ],
        menu_def: [
            ['ui-icon-document', 'New', 'new_'],
            ['ui-icon-disk', 'Save', 'save'],
            ['ui-icon-arrow-4-diag', 'Switch', 'switch_'],
            ['ui-icon-refresh', 'Reload/Undo', 'reload'],
            ['ui-icon-copy', 'Duplicate', 'copy'],
            ['ui-icon-trash', 'Delete', 'delete_'],
            ['ui-icon-arrowthick-1-w', 'Previous', 'previous'],
            ['ui-icon-arrowthick-1-e', 'Next', 'next'],
            ['ui-icon-search', 'Search', 'search'],
            ['ui-icon-clock', 'View Logs...', 'logs'],
            ['ui-icon-clock', 'Show revisions...', 'revision'],
            ['ui-icon-circle-close', 'Close Tab', 'close'],
            ['ui-icon-pin-w', 'Attachment', 'attach'],
            ['ui-icon-gear', 'Action', 'action'],
            ['ui-icon-arrowreturn-1-e', 'Relate', 'relate'],
            ['ui-icon-print', 'Print', 'print']
            ],
        create_toolbar: function() {
            var toolbar = Sao.Tab.Form._super.create_toolbar.call(this);
            var screen = this.screen;
            var buttons = this.buttons;
            var prm = screen.model.execute('view_toolbar_get', [],
                    screen.context);
            prm.done(function(toolbars) {
                // TODO translation
                [
                ['action', 'ui-icon-gear', 'Action', 'Launch action'],
                ['relate', 'ui-icon-arrowreturn-1-e', 'Relate',
                'Open related records'],
                ['print', 'ui-icon-print', 'Print', 'Print report']
                ].forEach(function(menu_action) {
                    var button = jQuery('<button/>').button({
                        id: menu_action[0],
                        text: true,
                        icons: {
                            primary: menu_action[1],
                            secondary: 'ui-icon-triangle-1-s'
                        },
                        label: menu_action[2]
                    });
                    buttons[menu_action[0]] = button;
                    toolbar.append(button);
                    var menu = jQuery('<ul/>');
                    button.click(function() {
                        menu.toggle().position({
                            my: 'left top',
                            at: 'left bottom',
                            of: button
                        });
                        if (menu_action[0] == 'action') {
                            menu.find('.action_button').remove();
                            var buttons = screen.get_buttons();
                            buttons.forEach(function(button) {
                                var item = jQuery('<li/>', {
                                    'class': 'ui-menu-item action_button'
                                }).append(
                                    jQuery('<a/>').append(
                                        button.attributes.string || ''));
                                menu.append(item);
                                item.click(function() {
                                    screen.button(button.attributes);
                                });
                            });
                        }
                        // Bind hide after the processing of the current click
                        window.setTimeout(function() {
                            jQuery(document).one('click', function() {
                                menu.hide();
                            });
                        }, 0);
                    });

                    toolbars[menu_action[0]].forEach(function(action) {
                        var item = jQuery('<li/>').append(
                            jQuery('<a/>').append(action.name));
                        menu.append(item);
                        item.click(function() {
                            screen.save_current().then(function() {
                                var exec_action = jQuery.extend({}, action);
                                var record_id = null;
                                if (screen.current_record) {
                                    record_id = screen.current_record.id;
                                }
                                var record_ids = screen.current_view
                                .selected_records().map(function(record) {
                                    return record.id;
                                });
                                exec_action = Sao.Action.evaluate(exec_action,
                                    menu_action[0], screen.current_record);
                                var data = {
                                    model: screen.model_name,
                                    id: record_id,
                                    ids: record_ids
                                };
                                Sao.Action.exec_action(exec_action, data,
                                    screen.context);
                            });
                        });
                    });
                    menu.menu({}).hide().css({
                        position: 'absolute',
                        'z-index': 100
                    });
                    toolbar.append(menu);
                });
            });
            return toolbar;
        },
        modified_save: function() {
            this.screen.save_tree_state();
            this.screen.current_view.set_value();
            if (this.screen.modified()) {
                return Sao.common.sur_3b.run('This record has been modified\n' +
                        'do you want to save it?')
                    .then(function(result) {
                        switch(result) {
                            case 'ok':
                                return this.save();
                            case 'ko':
                                return this.reload(false);
                            default:
                                return jQuery.Deferred().reject();
                        }
                    }.bind(this));
            }
            return jQuery.when();
        },
        new_: function() {
            if (!Sao.common.MODELACCESS.get(this.screen.model_name).create) {
                return;
            }
            this.modified_save().done(function() {
                this.screen.new_();
                // TODO message
                // TODO activate_save
            }.bind(this));
        },
        save: function() {
            if (!Sao.common.MODELACCESS.get(this.screen.model_name).write) {
                return;
            }
            // TODO message
            return this.screen.save_current();
        },
        switch_: function() {
            this.modified_save().done(function() {
                this.screen.switch_view();
            }.bind(this));
        },
        reload: function(test_modified) {
            if (test_modified === undefined) {
                test_modified = true;
            }
            var reload = function() {
                this.screen.cancel_current().then(function() {
                    this.screen.save_tree_state(false);
                    if (this.screen.current_view.view_type != 'form') {
                        this.screen.search_filter(
                            this.screen.screen_container.search_entry.val());
                        // TODO set current_record
                    }
                    this.screen.display();
                    // TODO message
                    // TODO activate_save
                }.bind(this));
            }.bind(this);
            if (test_modified) {
                return this.modified_save().then(reload);
            } else {
                return reload();
            }
        },
        copy: function() {
            if (!Sao.common.MODELACCESS.get(this.screen.model_name).create) {
                return;
            }
            this.modified_save().done(function() {
                this.screen.copy();
                // TODO message
            }.bind(this));
        },
        delete_: function() {
            if (!Sao.common.MODELACCESS.get(this.screen.model_name)['delete']) {
                return;
            }
            var msg;
            if (this.screen.current_view.view_type == 'form') {
                msg = 'Are you sure to remove this record?'; // TODO translate
            } else {
                msg = 'Are you sure to remove those records?';
            }
            Sao.common.sur.run(msg).done(function() {
                this.screen.remove(true, false, true).done(function() {
                    // TODO message
                });
            }.bind(this));
        },
        previous: function() {
            this.modified_save().done(function() {
                this.screen.display_previous();
                // TODO message and activate_save
            }.bind(this));
        },
        next: function() {
            this.modified_save().done(function() {
                this.screen.display_next();
                // TODO message and activate_save
            }.bind(this));
        },
        search: function() {
            var search_entry = this.screen.screen_container.search_entry;
            if (search_entry.is(':visible')) {
                window.setTimeout(function() {
                    search_entry.focus();
                }, 0);
            }
        },
        logs: function() {
            var record = this.screen.current_record;
            if ((!record) || (record.id < 0)) {
                // TODO message
                return;
            }
            // TODO translation
            var fields = [
                ['id', 'ID:'],
                ['create_uid.rec_name', 'Creation User:'],
                ['create_date', 'Creation Date:'],
                ['write_uid.rec_name', 'Latest Modification by:'],
                ['write_date', 'Latest Modification Date:']
                ];

            this.screen.model.execute('read', [[record.id],
                    fields.map(function(field) {
                        return field[0];
                    })], this.screen.context)
            .then(function(result) {
                result = result[0];
                var message = '';
                fields.forEach(function(field) {
                    var key = field[0];
                    var label = field[1];
                    var value = result[key] || '/';
                    if (result[key] &&
                        ~['create_date', 'write_date'].indexOf(key)) {
                        value = Sao.common.format_datetime(
                            Sao.common.date_format(),
                            '%H:%M:%S',
                            value);
                    }
                    message += label + ' ' + value + '\n';
                });
                message += 'Model: ' + this.screen.model.name;
                Sao.common.message.run(message);
            }.bind(this));
        },
        revision: function() {
            var current_id = null;
            if (this.screen.current_record) {
                current_id = this.screen.current_record.id;
            }
            var set_revision = function(revisions) {
                return function(revision) {
                    if (revision) {
                        // Add a millisecond as microseconds are truncated
                        revision.setMilliseconds(revision.getMilliseconds() + 1);
                    }
                    if ((this.screen.current_view.view_type == 'form') &&
                            (revision < revisions[revisions.length - 1][0])) {
                        revision = revisions[revisions.length - 1][0];
                    }
                    if (revision != this.screen.context._datetime) {
                        // Update screen context that will be propagated by
                        // recreating new group
                        this.screen.context._datetime = revision;
                        if (this.screen.current_view.view_type != 'form') {
                            this.screen.search_filter(
                                    this.screen.screen_container
                                    .search_entry.val());
                        } else {
                            // Test if record exist in revisions
                            this.screen.new_group([current_id]);
                        }
                        this.screen.display();
                        this.update_revision();
                    }
                }.bind(this);
            }.bind(this);
            this.modified_save().done(function() {
                var ids = this.screen.current_view.selected_records().map(
                    function(record) {
                        return record.id;
                    });
                this.screen.model.execute('history_revisions',
                    [ids], this.screen.context)
                    .then(function(revisions) {
                        new Sao.Window.Revision(revisions, set_revision(revisions));
                    });
            }.bind(this));
        },
        update_revision: function() {
            var revision = this.screen.context._datetime;
            var label;
            if (revision) {
                var date_format = Sao.common.date_format();
                var time_format = '%H:%M:%S.%f';
                revision = Sao.common.format_datetime(date_format, time_format,
                        revision);
                label = this.name + ' @ '+ revision;
            } else {
                label = this.name;
            }
            this.title.find('button').button({
                label: label
            });
            ['new', 'save'].forEach(function(button) {
                this.buttons[button].prop('disabled', revision);
            }.bind(this));
        },
        attach: function() {
            var record = this.screen.current_record;
            if (!record || (record.id < 0)) {
                return;
            }
            new Sao.Window.Attachment(record, function() {
                this.update_attachment_count(true);
            }.bind(this));
        },
        update_attachment_count: function(reload) {
            var record = this.screen.current_record;
            if (record) {
                record.get_attachment_count(reload).always(
                        this.attachment_count.bind(this));
            } else {
                this.attachment_count(0);
            }
        },
        attachment_count: function(count) {
            var label = 'Attachment(' + count + ')';  // TODO translate
            this.buttons.attach.button('option', 'label', label);
            if (count) {
                this.buttons.attach.button('option', 'icons', {
                    primary: 'ui-icon-pin-s'
                });
            } else {
                this.buttons.attach.button('option', 'icons', {
                    primary: 'ui-icon-pin-w'
                });
            }
            var record_id = this.screen.get_id();
            this.buttons.attach.prop('disabled',
                record_id < 0 || record_id === null);
        },
        action: function() {
            this.buttons.action.click();
        },
        relate: function() {
            this.buttons.relate.click();
        },
        print: function() {
            this.buttons.print.click();
        }
    });
}());
