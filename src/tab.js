/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.Tab = Sao.class_(Object, {
        init: function() {
            Sao.Tab.tabs.push(this);
            this.buttons = {};
            this.id = 'tab-' + Sao.Tab.counter++;
        },
        create_tabcontent: function() {
            this.el = jQuery('<div/>', {
                'class': this.class_
            });

            this.title = jQuery('<h4/>').appendTo(this.el);
            this.create_toolbar().appendTo(this.el);
        },
        set_menu: function(menu) {
            this.menu_def.forEach(function(definition) {
                var icon = definition[0];
                var name = definition[1];
                var func = definition[2];
                if (!func) {
                    return;
                }
                var item = jQuery('<li/>').append(
                    jQuery('<a/>').append(jQuery('<span/>', {
                        'class': 'glyphicon ' + icon,
                        'aria-hidden': 'true'
                    })).append(name));
                menu.append(item);
                item.click(function() {
                    this[func]();
                }.bind(this));
            }.bind(this));
        },
        create_toolbar: function() {
            var toolbar = jQuery(
                    '<nav class="navbar navbar-default toolbar" role="navigation">' +
                    '<div class="container-fluid">' +
                    '<div class="navbar-header">' +
                    '<button type="button" class="navbar-toggle collapsed" ' +
                    'data-toggle="collapse" ' +
                    'data-target="#navbar-' + this.id + '">' +
                    '<span class="sr-only">Toggle navigation</span>' +
                    '<span class="icon-bar"></span>' +
                    '<span class="icon-bar"></span>' +
                    '<span class="icon-bar"></span>' +
                    '</div>' +
                    '<div class="collapse navbar-collapse" ' +
                    'id="navbar-' + this.id + '">' +
                    '<ul class="nav navbar-nav">' +
                    '<li class="dropdown">' +
                    '<a href="#" class="dropdown-toggle" ' +
                    'data-toggle="dropdown" role="button" ' +
                    'aria-expanded="false">' +
                    '<span class="glyphicon glyphicon-wrench" ' +
                    'aria-hidden="true"></span>' +
                    '<span class="visible-xs">Menu</span>' +
                    '<span class="caret"></span>' +
                    '</a>' +
                    '<ul class="dropdown-menu" role="menu">' +
                    '</ul>' +
                    '</li>' +
                    '</ul>' +
                    '</div>' +
                    '</div>' +
                    '</nav>'
                    );
            this.set_menu(toolbar.find('ul[role*="menu"]'));

            var add_button = function(tool) {
                this.buttons[tool[0]] = jQuery('<a/>', {
                    href: '#',
                    id: tool[0]
                })
                .append(jQuery('<span/>', {
                    'class': 'glyphicon ' + tool[1],
                    'aria-hidden': 'true'
                }))
                .append(jQuery('<span/>', {
                    'class': 'hidden-sm'
                }).append(' ' + tool[2]))
                .click(this[tool[4]].bind(this))
                .appendTo(jQuery('<li/>')
                        .appendTo(toolbar.find('.navbar-collapse > ul')));
                // TODO tooltip
            };
            this.toolbar_def.forEach(add_button.bind(this));
            return toolbar;
        },
        close: function() {
            var tabs = jQuery('#tabs');
            var tab = tabs.find('#nav-' + this.id);
            var content = tabs.find('#' + this.id);
            tabs.find('a[href="#' + this.id + '"]').tab('show');
            return this.modified_save().then(function() {
                var next = tab.next();
                if (!next.length) {
                    next = tab.prev();
                }
                tab.remove();
                content.remove();
                Sao.Tab.tabs.splice(Sao.Tab.tabs.indexOf(this), 1);
                if (next) {
                    next.find('a').tab('show');
                }
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
        var tabs = jQuery('#tabs > ul');
        var i = tabs.find('li').index(tabs.find('li.active'));
        return Sao.Tab.tabs[i];
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
        var tabs = jQuery('#tabs');
        var tab_link = jQuery('<a/>', {
            'aria-controls': tab.id,
            'role': 'tab',
            'data-toggle': 'tab',
            'href': '#' + tab.id
        })
        .append(jQuery('<button/>', {
            'class': 'close'
        }).append(jQuery('<span/>', {
            'aria-hidden': true
        }).append('&times;')).append(jQuery('<span/>', {
            'class': 'sr-only'
        }).append('Close')).click(function() {
            tab.close();
        }))
        .append(tab.name);
        jQuery('<li/>', {
            'role': 'presentation',
            id: 'nav-' + tab.id
        }).append(tab_link)
        .appendTo(tabs.find('> .nav-tabs'));
        jQuery('<div/>', {
            role: 'tabpanel',
            'class': 'tab-pane',
            id: tab.id
        }).html(tab.el)
        .appendTo(tabs.find('> .tab-content'));
        tab_link.tab('show');
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
            ['new', 'glyphicon-file', 'New', 'Create a new record', 'new_'],
            ['save', 'glyphicon-save', 'Save', 'Save this record', 'save'],
            ['switch', 'glyphicon-move', 'Switch', 'Switch view',
            'switch_'],
            ['reload', 'glyphicon-refresh', 'Reload', 'Reload', 'reload'],
            ['previous', 'glyphicon-chevron-left', 'Previous',
            'Previous Record', 'previous'],
            ['next', 'glyphicon-chevron-right', 'Next', 'Next Record', 'next'],
            ['attach', 'glyphicon-paperclip', 'Attachment',
            'Add an attachment to the record', 'attach']
            ],
        menu_def: [
            ['glyphicon-file', 'New', 'new_'],
            ['glyphicon-save', 'Save', 'save'],
            ['glyphicon-move', 'Switch', 'switch_'],
            ['glyphicon-refresh', 'Reload/Undo', 'reload'],
            ['glyphicon-repeat', 'Duplicate', 'copy'],
            ['glyphicon-trash', 'Delete', 'delete_'],
            ['glyphicon-chevron-left', 'Previous', 'previous'],
            ['glyphicon-chevron-right', 'Next', 'next'],
            ['glyphicon-search', 'Search', 'search'],
            ['glyphicon-time', 'View Logs...', 'logs'],
            ['glyphicon-time', 'Show revisions...', 'revision'],
            ['glyphicon-remove', 'Close Tab', 'close'],
            ['glyphicon-paperclip', 'Attachment', 'attach'],
            ['glyphicon-cog', 'Action', 'action'],
            ['glyphicon-share-alt', 'Relate', 'relate'],
            ['glyphicon-print', 'Print', 'print']
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
                ['action', 'glyphicon-cog', 'Action', 'Launch action'],
                ['relate', 'glyphicon-share-alt', 'Relate',
                'Open related records'],
                ['print', 'glyphicon-print', 'Print', 'Print report']
                ].forEach(function(menu_action) {
                    var button = jQuery('<li/>', {
                        'class': 'dropdown'
                    })
                    .append(jQuery('<a/>', {
                        href: '#',
                        id: menu_action[0],
                        'class': 'dropdown-toggle',
                        'data-toggle': 'dropdown',
                        role: 'button',
                        'aria-expanded': 'false'
                    })
                        .append(jQuery('<span/>', {
                            'class': 'glyphicon ' + menu_action[1],
                            'aria-hidden': 'true'
                        }))
                        .append(jQuery('<span/>', {
                            'class': 'hidden-sm'
                        }).append(' ' + menu_action[2] + ' '))
                        .append(jQuery('<span/>', {
                            'class': 'caret'
                        })))
                    .append(jQuery('<ul/>', {
                        'class': 'dropdown-menu',
                        role: 'menu'
                    }))
                    .appendTo(toolbar.find('.navbar-collapse > ul'));
                    buttons[menu_action[0]] = button;
                    var menu = button.find('ul[role*="menu"]');
                    if (menu_action[0] == 'action') {
                        button.find('a').click(function() {
                            menu.find('.action_button').remove();
                            var buttons = screen.get_buttons();
                            buttons.forEach(function(button) {
                                var item = jQuery('<li/>')
                                .append(
                                    jQuery('<a/>').append(
                                        button.attributes.string || ''))
                                .click(function() {
                                    screen.button(button.attributes);
                                })
                            .appendTo(menu);
                            });
                        });
                    }

                    toolbars[menu_action[0]].forEach(function(action) {
                        var item = jQuery('<li/>')
                        .append(
                            jQuery('<a/>').append(action.name))
                        .click(function() {
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
                        })
                        .appendTo(menu);
                    });
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
                return this.screen.cancel_current().then(function() {
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
            this.title.html(label);
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
            this.buttons.attach.text(label);
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
