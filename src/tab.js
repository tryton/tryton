/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.Tab = Sao.class_(Object, {
        init: function() {
            Sao.Tab.tabs.push(this);
            this.buttons = {};
            this.menu_buttons = {};
            this.id = 'tab-' + Sao.Tab.counter++;
            this.name = '';
            this.name_el = jQuery('<span/>');
            this.view_prm = jQuery.when();
        },
        menu_def: function() {
            return [
                {
                    id: 'switch_',
                    icon: 'tryton-switch',
                    label: Sao.i18n.gettext('Switch'),
                    tooltip: Sao.i18n.gettext('Switch view'),
                }, {
                    id: 'previous',
                    icon: 'tryton-back',
                    label: Sao.i18n.gettext('Previous'),
                    tooltip: Sao.i18n.gettext('Previous Record')
                }, {
                    id: 'next',
                    icon: 'tryton-forward',
                    label: Sao.i18n.gettext('Next'),
                    tooltip: Sao.i18n.gettext('Next Record'),
                }, {
                    id: 'search',
                    icon: 'tryton-search',
                    label: Sao.i18n.gettext('Search'),
                }, null, {
                    id: 'new_',
                    icon: 'tryton-create',
                    label: Sao.i18n.gettext('New'),
                    tooltip: Sao.i18n.gettext('Create a new record'),
                }, {
                    id: 'save',
                    icon: 'tryton-save',
                    label: Sao.i18n.gettext('Save'),
                    tooltip: Sao.i18n.gettext('Save this record'),
                }, {
                    id: 'reload',
                    icon: 'tryton-refresh',
                    label: Sao.i18n.gettext('Reload/Undo'),
                    tooltip: Sao.i18n.gettext('Reload'),
                }, {
                    id: 'copy',
                    icon: 'tryton-copy',
                    label: Sao.i18n.gettext('Duplicate'),
                }, {
                    id: 'delete_',
                    icon: 'tryton-delete',
                    label: Sao.i18n.gettext('Delete'),
                }, null, {
                    id: 'logs',
                    icon: 'tryton-log',
                    label: Sao.i18n.gettext('View Logs...'),
                }, {
                    id: (this.screen &&
                        Sao.common.MODELHISTORY.contains(this.screen.model_name)) ?
                        'revision': null,
                    icon: 'tryton-history',
                    label: Sao.i18n.gettext('Show revisions...'),
                }, null, {
                    id: 'attach',
                    icon: 'tryton-attach',
                    label: Sao.i18n.gettext('Attachment'),
                    tooltip: Sao.i18n.gettext('Add an attachment to the record'),
                    dropdown: true,
                }, {
                    id: 'note',
                    icon: 'tryton-note',
                    label: Sao.i18n.gettext('Note'),
                    tooltip: Sao.i18n.gettext('Add a note to the record'),
                }, {
                    id: 'action',
                    icon: 'tryton-launch',
                    label: Sao.i18n.gettext('Action'),
                }, null, {
                    id: 'relate',
                    icon: 'tryton-link',
                    label: Sao.i18n.gettext('Relate'),
                }, {
                    id: 'print',
                    icon: 'tryton-print',
                    label: Sao.i18n.gettext('Print'),
                }, null, {
                    id: 'export',
                    icon: 'tryton-export',
                    label: Sao.i18n.gettext('Export'),
                }, {
                    id: 'import',
                    icon: 'tryton-import',
                    label: Sao.i18n.gettext('Import'),
                }, null, {
                    id: 'close',
                    icon: 'tryton-close',
                    label: Sao.i18n.gettext('Close Tab'),
                },
            ];
        },
        create_tabcontent: function() {
            this.el = jQuery('<div/>', {
                'class': this.class_
            });

            var toolbar = this.create_toolbar().appendTo(this.el);
            this.title = toolbar.find('.title');

            this.content = jQuery('<div/>').appendTo(this.el);

            if (this.info_bar) {
                this.el.append(this.info_bar.el);
            }
        },
        set_menu: function(menu) {
            var previous;
            this.menu_def().forEach(function(item) {
                var menuitem;
                if (item) {
                    if (!this[item.id]) {
                        return;
                    }
                    menuitem = jQuery('<li/>', {
                        'role': 'presentation'
                    });
                    var link = jQuery('<a/>', {
                        'id': item.id,
                        'role': 'menuitem',
                        'href': '#',
                        'tabindex': -1
                    }).append(Sao.common.ICONFACTORY.get_icon_img(item.icon, {
                        'aria-hidden': 'true',
                    })).append(' ' + item.label).appendTo(menuitem);
                    this.menu_buttons[item.id] = menuitem;
                    link.click(function(evt) {
                        evt.preventDefault();
                        this[item.id]();
                    }.bind(this));
                } else if (!item && previous) {
                    menuitem = jQuery('<li/>', {
                        'role': 'separator',
                        'class': 'divider hidden-xs',
                    });
                } else {
                    return;
                }
                previous = menuitem;
                menuitem.appendTo(menu);
            }.bind(this));
        },
        create_toolbar: function() {
            var toolbar = jQuery('<nav/>', {
                'class': 'toolbar navbar navbar-default',
                'role': 'toolbar'
            }).append(jQuery('<div/>', {
                'class': 'container-fluid'
            }).append(jQuery('<div/>', {
                'class': 'dropdown navbar-header navbar-left flip'
            }).append(jQuery('<a/>', {
                'href': "#",
                'class': "navbar-brand dropdown-toggle",
                'data-toggle': 'dropdown',
                'role': 'button',
                'aria-expanded': false,
                'aria-haspopup': true
            }).append(jQuery('<span/>', {
                'class': 'title'
            })).append(jQuery('<span/>', {
                'class': 'caret'
            }))).append(jQuery('<ul/>', {
                'class': 'dropdown-menu',
                'role': 'menu'
            })).append(jQuery('<button/>', {
                'type': 'button',
                'class': 'close visible-xs visible-sm',
                'aria-label': Sao.i18n.gettext('Close')
            }).append(jQuery('<span/>', {
                'aria-hidden': true
            }).append('&times;')).click(function() {
                this.close();
            }.bind(this)))).append(jQuery('<div/>', {
                'class': 'btn-toolbar navbar-right flip',
                'role': 'toolbar'
            })));
            var wrapper = jQuery('<div/>', {
                'class': 'toolbar-wrapper'
            }).append(toolbar);
            this.set_menu(toolbar.find('ul[role*="menu"]'));

            var group;
            var add_button = function(item) {
                if (!item || !item.tooltip) {
                    group = null;
                    return;
                }
                if (!item.id || !this[item.id]) {
                    return;
                }
                if (!group) {
                    group = jQuery('<div/>', {
                        'class': 'btn-group',
                        'role': 'group'
                    }).appendTo(toolbar.find('.btn-toolbar'));
                }
                var attributes = {
                    'type': 'button',
                    'class': 'btn btn-default navbar-btn',
                    'title': item.label,
                    'id': item.id
                };
                if (item.dropdown) {
                    attributes['class'] += ' dropdown-toggle';
                    attributes['data-toggle'] = 'dropdown';
                    attributes['aria-expanded'] = false;
                    attributes['aria-haspopup'] = true;
                }
                var button = jQuery('<button/>', attributes)
                    .append(Sao.common.ICONFACTORY.get_icon_img(item.icon, {
                        'aria-hidden': 'true',
                    }));
                this.buttons[item.id] = button;
                if (item.dropdown) {
                    var dropdown = jQuery('<div/>', {
                        'class': 'btn-group dropdown',
                        'role': 'group',
                    }).append(button.append(jQuery('<span/>', {
                        'class': 'caret',
                    }))).append(jQuery('<ul/>', {
                        'class': 'dropdown-menu',
                        'role': 'menu',
                        'aria-labelledby': item.id,
                    })).appendTo(group);
                } else {
                    button.appendTo(group);
                }
                this.buttons[item.id].click(item, function(event) {
                    var item = event.data;
                    var button = this.buttons[item.id];
                    button.prop('disabled', true);
                    (this[item.id](this) || jQuery.when())
                        .always(function() {
                            button.prop('disabled', false);
                        });
                }.bind(this));
            };
            this.menu_def().forEach(add_button.bind(this));
            this.status_label = jQuery('<span/>', {
                'class': 'badge',
            }).appendTo(jQuery('<div/>', {
                'class': 'navbar-text hidden-xs',
            }).insertAfter(this.buttons.previous));
            toolbar.find('.btn-toolbar > .btn-group').last()
                .addClass( 'hidden-xs')
                .find('.dropdown')
                .on('show.bs.dropdown', function() {
                    jQuery(this).parents('.btn-group')
                        .removeClass( 'hidden-xs');
                })
                .on('hide.bs.dropdown', function() {
                    jQuery(this).parents('.btn-group')
                        .addClass('hidden-xs');
                });
            var tabs = jQuery('#tabs');
            toolbar.affix({
                'target': tabs.parent(),
                'offset': {
                    'top': function() {
                        return jQuery('#main_navbar').height();
                    }
                }
            });
            toolbar.on('affix.bs.affix', function() {
                wrapper.height(jQuery('#main_navbar').height());
            });
            toolbar.on('affix-top.bs.affix affix-bottom.bs.affix',
                    function() {
                        wrapper.height('');
                    });
            toolbar.on('affixed.bs.affix', function() {
                Sao.Tab.affix_set_with(toolbar);
            });
            toolbar.on('affixed-top.bs.affix affixed-bottom.bs.affix',
                    function() {
                        Sao.Tab.affix_unset_width(toolbar);
                    });
            return wrapper;
        },
        show: function() {
            jQuery('#tablist').find('a[href="#' + this.id + '"]').tab('show');
        },
        close: function() {
            var tabs = jQuery('#tabs');
            var tablist = jQuery('#tablist');
            var tab = tablist.find('#nav-' + this.id);
            var content = tabs.find('#' + this.id);
            this.show();
            return this._close_allowed().then(function() {
                var next = tab.nextAll('li').first();
                if (!next.length) {
                    next = tab.prevAll('li').first();
                }
                tab.remove();
                content.remove();
                Sao.Tab.tabs.splice(Sao.Tab.tabs.indexOf(this), 1);
                if (next.length) {
                    next.find('a').tab('show');
                } else {
                    Sao.set_url();
                }
                tabs.trigger('ready');
            }.bind(this));
        },
        _close_allowed: function() {
            return jQuery.when();
        },
        set_name: function(name) {
            this.name = name;
            this.name_el.text(Sao.common.ellipsize(name, 20));
            this.name_el.parents('li').first().attr('title', name);
        },
        get_url: function() {
        },
    });

    Sao.Tab.affix_set_with = function(toolbar) {
        var width = jQuery(toolbar.parent()).width();
        toolbar.css('width', width);
    };
    Sao.Tab.affix_unset_width = function(toolbar) {
        toolbar.css('width', '');
    };
    jQuery(window).resize(function() {
        jQuery('.toolbar').each(function(i, toolbar) {
            toolbar = jQuery(toolbar);
            toolbar.affix('checkPosition');
            if (toolbar.hasClass('affix')) {
                Sao.Tab.affix_set_with(toolbar);
            } else {
                Sao.Tab.affix_unset_width(toolbar);
            }
        });
    });

    Sao.Tab.counter = 0;
    Sao.Tab.tabs = [];
    Sao.Tab.tabs.close = function(warning) {
        if (warning && Sao.Tab.tabs.length) {
            return Sao.common.sur.run(
                    Sao.i18n.gettext(
                        'The following action requires to close all tabs.\n' +
                        'Do you want to continue?')).then(function() {
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
            return Sao.main_menu_screen.save_tree_state().then(function() {
                Sao.main_menu_screen = null;
            });
        }
        return jQuery.when();
    };
    Sao.Tab.tabs.get_current = function() {
        var tabs = jQuery('#tablist');
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
        tab.view_prm.done(function() {
            Sao.Tab.add(tab);
        });
    };

    Sao.Tab.add = function(tab) {
        var tabs = jQuery('#tabs');
        var tablist = jQuery('#tablist');
        var tabcontent = jQuery('#tabcontent');
        var tab_link = jQuery('<a/>', {
            'aria-controls': tab.id,
            'role': 'tab',
            'data-toggle': 'tab',
            'href': '#' + tab.id
        }).on('show.bs.tab', function() {
            Sao.set_url(tab.get_url(), tab.name);
        })
        .append(jQuery('<button/>', {
            'class': 'close'
        }).append(jQuery('<span/>', {
            'aria-hidden': true
        }).append('&times;')).append(jQuery('<span/>', {
            'class': 'sr-only'
        }).append(Sao.i18n.gettext('Close'))).click(function(evt) {
            evt.preventDefault();
            tab.close();
        }))
        .append(tab.name_el);
        jQuery('<li/>', {
            'role': 'presentation',
            'data-placement': 'bottom',
            id: 'nav-' + tab.id
        }).append(tab_link)
        .appendTo(tablist);
        jQuery('<div/>', {
            role: 'tabpanel',
            'class': 'tab-pane',
            id: tab.id
        }).html(tab.el)
        .appendTo(tabcontent);
        tab_link.tab('show');
        tabs.trigger('ready');
    };

    Sao.Tab.previous_tab = function() {
        Sao.Tab.move('prevAll');
    };

    Sao.Tab.next_tab = function() {
        Sao.Tab.move('nextAll');
    };

    Sao.Tab.move = function(direction) {
        var current_tab = this.tabs.get_current();
        var tabs = jQuery('#tabs');
        var tablist = jQuery('#tablist');
        var tab = tablist.find('#nav-' + current_tab.id);
        var next = tab[direction]('li').first();
        if (next) {
            next.find('a').tab('show');
            tabs.trigger('ready');
        }
    };

    Sao.Tab.Form = Sao.class_(Sao.Tab, {
        class_: 'tab-form',
        init: function(model_name, attributes) {
            Sao.Tab.Form._super.init.call(this);
            var screen = new Sao.Screen(model_name, attributes);
            screen.tab = this;
            this.screen = screen;
            this.attributes = jQuery.extend({}, attributes);

            this.info_bar = new Sao.Window.InfoBar();
            this.create_tabcontent();

            screen.message_callback = this.record_message.bind(this);
            screen.switch_callback = function() {
                Sao.set_url(this.get_url(), this.name);
            }.bind(this);

            this.set_buttons_sensitive();

            this.view_prm = this.screen.switch_view().done(function() {
                this.set_name(attributes.name || '');
                this.content.append(screen.screen_container.el);
                if (attributes.res_id) {
                    if (!jQuery.isArray(attributes.res_id)) {
                        attributes.res_id = [attributes.res_id];
                    }
                    screen.group.load(attributes.res_id);
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
        create_toolbar: function() {
            var toolbar = Sao.Tab.Form._super.create_toolbar.call(this);
            var screen = this.screen;
            var buttons = this.buttons;
            var prm = screen.model.execute('view_toolbar_get', [],
                screen.context());
            prm.done(function(toolbars) {
                [
                ['action', 'tryton-launch',
                    Sao.i18n.gettext('Launch action')],
                ['relate', 'tryton-link',
                     Sao.i18n.gettext('Open related records')],
                ['print', 'tryton-print',
                     Sao.i18n.gettext('Print report')]
                ].forEach(function(menu_action) {
                    var button = jQuery('<div/>', {
                        'class': 'btn-group dropdown',
                        'role': 'group'
                    })
                    .append(jQuery('<button/>', {
                        'type': 'button',
                        'class': 'btn btn-default navbar-btn dropdown-toggle',
                        'data-toggle': 'dropdown',
                        'aria-expanded': false,
                        'aria-haspopup': true,
                        'title': menu_action[2],
                        'id': menu_action[0],
                    })
                        .append(Sao.common.ICONFACTORY.get_icon_img(
                            menu_action[1], {
                                'aria-hidden': 'true',
                            }))
                        .append(jQuery('<span/>', {
                            'class': 'caret'
                        })))
                    .append(jQuery('<ul/>', {
                        'class': 'dropdown-menu',
                        'role': 'menu',
                        'aria-labelledby': menu_action[0]
                    }))
                    .appendTo(toolbar.find('.btn-toolbar > .btn-group').last());
                    buttons[menu_action[0]] = button;
                    var dropdown = button
                        .on('show.bs.dropdown', function() {
                            jQuery(this).parents('.btn-group').removeClass(
                                    'hidden-xs');
                        }).on('hide.bs.dropdown', function() {
                            jQuery(this).parents('.btn-group').addClass(
                                    'hidden-xs');
                        });
                    var menu = button.find('.dropdown-menu');
                    button.click(function() {
                        menu.find('.' + menu_action[0] + '_button').remove();
                        var buttons = screen.get_buttons();
                        buttons.forEach(function(button) {
                            var button_kw = (button.attributes.keyword ||
                                'action');
                            if (button_kw != menu_action[0]) {
                                return;
                            }
                            var item = jQuery('<li/>', {
                                'role': 'presentation',
                                'class': menu_action[0] + '_button'
                            })
                            .append(
                                jQuery('<a/>', {
                                    'role': 'menuitem',
                                    'href': '#',
                                    'tabindex': -1
                                }).append(
                                    button.attributes.string || ''))
                            .click(function(evt) {
                                evt.preventDefault();
                                screen.button(button.attributes);
                            })
                        .appendTo(menu);
                        });
                    });

                    toolbars[menu_action[0]].forEach(function(action) {
                        var item = jQuery('<li/>', {
                            'role': 'presentation'
                        })
                        .append(jQuery('<a/>', {
                            'role': 'menuitem',
                            'href': '#',
                            'tabindex': -1
                        }).append(action.name))
                        .click(function(evt) {
                            evt.preventDefault();
                            var prm = jQuery.when();
                            if (this.screen.modified()) {
                                prm = this.save();
                            }
                            prm.then(function() {
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
                                    screen.context());
                            });
                        }.bind(this))
                        .appendTo(menu);
                    }.bind(this));
                }.bind(this));
            }.bind(this));
            return toolbar;
        },
        _close_allowed: function() {
            return this.modified_save();
        },
        modified_save: function() {
            this.screen.save_tree_state();
            this.screen.current_view.set_value();
            if (this.screen.modified()) {
                return Sao.common.sur_3b.run(
                        Sao.i18n.gettext('This record has been modified\n' +
                            'do you want to save it?'))
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
                return jQuery.when();
            }
            return this.modified_save().then(function() {
                return this.screen.new_().then(function() {
                    this.info_bar.message();
                }.bind(this));
                // TODO activate_save
            }.bind(this));
        },
        save: function() {
            var access = Sao.common.MODELACCESS.get(this.screen.model_name);
            if (!(access.write || access.create)) {
                return jQuery.Deferred().reject();
            }
            return this.screen.save_current().then(
                    function() {
                        this.info_bar.message(
                                Sao.i18n.gettext('Record saved.'), 'info');
                        this.screen.count_tab_domain();
                    }.bind(this),
                    function() {
                        this.info_bar.message(
                            this.screen.invalid_message(), 'danger');
                        return jQuery.Deferred().reject();
                    }.bind(this));
        },
        switch_: function() {
            return this.modified_save().done(function() {
                this.screen.switch_view();
            }.bind(this));
        },
        reload: function(test_modified) {
            if (test_modified === undefined) {
                test_modified = true;
            }
            var reload = function() {
                return this.screen.cancel_current().then(function() {
                    var set_cursor = false;
                    var record_id = null;
                    if (this.screen.current_record) {
                        record_id = this.screen.current_record.id;
                    }
                    this.screen.save_tree_state(false);
                    if (this.screen.current_view.view_type != 'form') {
                        return this.screen.search_filter(
                            this.screen.screen_container.search_entry.val())
                            .then(function() {
                                this.screen.group.forEach(function(record) {
                                    if (record.id == record_id) {
                                        this.screen.set_current_record(record);
                                        set_cursor = true;
                                    }
                                }.bind(this));
                                return set_cursor;
                            }.bind(this));
                    }
                    return set_cursor;
                }.bind(this))
                .then(function(set_cursor) {
                    return this.screen.display(set_cursor).then(function() {
                        this.info_bar.message();
                        // TODO activate_save
                        this.screen.count_tab_domain();
                    }.bind(this));
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
                return jQuery.when();
            }
            return this.modified_save().then(function() {
                return this.screen.copy().then(function() {
                    this.info_bar.message(
                            Sao.i18n.gettext(
                                'Working now on the duplicated record(s).'),
                            'info');
                    this.screen.count_tab_domain();
                }.bind(this));
            }.bind(this));
        },
        delete_: function() {
            if (!Sao.common.MODELACCESS.get(this.screen.model_name)['delete']) {
                return jQuery.when();
            }
            var msg;
            if (this.screen.current_view.view_type == 'form') {
                msg = Sao.i18n.gettext('Are you sure to remove this record?');
            } else {
                msg = Sao.i18n.gettext('Are you sure to remove those records?');
            }
            return Sao.common.sur.run(msg).then(function() {
                return this.screen.remove(true, false, true).then(
                        function() {
                            this.info_bar.message(
                                    Sao.i18n.gettext('Records removed.'),
                                    'info');
                            this.screen.count_tab_domain();
                        }.bind(this), function() {
                            this.info_bar.message(
                                    Sao.i18n.gettext('Records not removed.'),
                                    'danger');
                        }.bind(this));
            }.bind(this));
        },
        previous: function() {
            return this.modified_save().then(function() {
                this.screen.display_previous();
                this.info_bar.message();
                // TODO activate_save
            }.bind(this));
        },
        next: function() {
            return this.modified_save().then(function() {
                this.screen.display_next();
                this.info_bar.message();
                // TODO activate_save
            }.bind(this));
        },
        search: function() {
            var search_entry = this.screen.screen_container.search_entry;
            if (search_entry.is(':visible')) {
                window.setTimeout(function() {
                    search_entry.focus();
                }, 0);
            }
            return jQuery.when();
        },
        logs: function() {
            var record = this.screen.current_record;
            if ((!record) || (record.id < 0)) {
                this.info_bar.message(
                        Sao.i18n.gettext('You have to select one record.'),
                        'info');
                return jQuery.when();
            }
            var fields = [
                ['id', Sao.i18n.gettext('ID:')],
                ['create_uid.rec_name',
                    Sao.i18n.gettext('Creation User:')],
                ['create_date', Sao.i18n.gettext('Creation Date:')],
                ['write_uid.rec_name',
                    Sao.i18n.gettext('Latest Modification by:')],
                ['write_date', Sao.i18n.gettext('Latest Modification Date:')]
                ];

            return this.screen.model.execute('read', [[record.id],
                    fields.map(function(field) {
                        return field[0];
                    })], this.screen.context())
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
                message += Sao.i18n.gettext('Model: ') + this.screen.model.name;
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
                        revision.add(1, 'milliseconds');
                    }
                    if ((this.screen.current_view.view_type == 'form') &&
                            (revision < revisions[revisions.length - 1][0])) {
                        revision = revisions[revisions.length - 1][0];
                    }
                    if (revision != this.screen.context()._datetime) {
                        this.screen.clear();
                        // Update group context that will be propagated by
                        // recreating new group
                        this.screen.group._context._datetime = revision;
                        if (this.screen.current_view.view_type != 'form') {
                            this.screen.search_filter(
                                    this.screen.screen_container
                                    .search_entry.val());
                        } else {
                            this.screen.group.load([current_id]);
                        }
                        this.screen.display(true);
                        this.update_revision();
                    }
                }.bind(this);
            }.bind(this);
            return this.modified_save().then(function() {
                var ids = this.screen.current_view.selected_records().map(
                    function(record) {
                        return record.id;
                    });
                return this.screen.model.execute('history_revisions',
                    [ids], this.screen.context())
                    .then(function(revisions) {
                        new Sao.Window.Revision(revisions, set_revision(revisions));
                    });
            }.bind(this));
        },
        update_revision: function() {
            var revision = this.screen.context()._datetime;
            var label, title;
            if (revision) {
                var date_format = Sao.common.date_format();
                var time_format = '%H:%M:%S.%f';
                var revision_label = ' @ ' + Sao.common.format_datetime(
                    date_format, time_format, revision);
                label = Sao.common.ellipsize(
                    this.name, 80 - revision_label.length) + revision_label;
                title = this.name + revision_label;
            } else {
                label = Sao.common.ellipsize(this.name, 80);
                title = this.name;
            }
            this.title.text(label);
            this.title.attr('title', title);
            this.set_buttons_sensitive(revision);
        },
        set_buttons_sensitive: function(revision) {
            if (!revision) {
                var access = Sao.common.MODELACCESS.get(this.screen.model_name);
                [['new_', access.create],
                ['save', access.create || access.write],
                ['delete_', access.delete],
                ['copy', access.create],
                ['import', access.create],
                ].forEach(function(e) {
                    var button = e[0];
                    var access = e[1];
                    if (this.buttons[button]) {
                        this.buttons[button].toggleClass('disabled', !access);
                    }
                    if (this.menu_buttons[name]) {
                        this.menu_buttons[name]
                            .toggleClass('disabled', !access);
                    }
                }.bind(this));
            } else {
                ['new_', 'save', 'delete_', 'copy', 'import'].forEach(
                    function(name) {
                        if (this.buttons[name]) {
                            this.buttons[name].addClass('disabled');
                        }
                        if (this.menu_buttons[name]) {
                            this.menu_buttons[name].addClass('disabled');
                        }
                    }.bind(this));
            }
        },
        attach: function(evt) {
            var window_ = function() {
                return new Sao.Window.Attachment(record, function() {
                    this.update_attachment_count(true);
                }.bind(this));
            }.bind(this);
            var dropdown = this.buttons.attach.parents('.dropdown');
            if (!evt) {
                window.setTimeout(function() {
                    this.buttons.attach.click();
                }.bind(this));
                return;
            }
            var record = this.screen.current_record;
            var menu = dropdown.find('.dropdown-menu');
            menu.children().remove();
            Sao.Window.Attachment.get_attachments(record)
                .then(function(attachments) {
                    attachments.forEach(function(value) {
                        var name = value[0],
                            callback = value[1];
                        var link = jQuery('<a/>', {
                            'role': 'menuitem',
                            'href': '#',
                            'tabindex': -1,
                        }).append(name).appendTo(jQuery('<li/>', {
                            'role': 'presentation',
                        }).appendTo(menu));
                        if (typeof callback == 'string') {
                            link.attr('href', callback);
                            link.attr('target', '_new');
                        } else {
                            link.click(function(evt) {
                                evt.preventDefault();
                                callback();
                            });
                        }
                    });
                }).always(function() {
                    menu.append(jQuery('<li/>', {
                        'class': 'divider',
                    }));
                    menu.append(jQuery('<li/>', {
                        'role': 'presentation',
                        'class': 'input-file',
                    }).append(jQuery('<input/>', {
                        'type': 'file',
                        'role': 'menuitem',
                        'tabindex': -1,
                    }).change(function() {
                        Sao.common.get_input_data(
                            jQuery(this), function(data, filename) {
                                window_().add_data(data, filename);
                            });
                    })).append(jQuery('<a/>', {
                        'role': 'menuitem',
                        'href': '#',
                        'tabindex': -1,
                    }).append(Sao.i18n.gettext('Add...'))));
                    menu.append(jQuery('<li/>', {
                        'role': 'presentation',
                    }).append(jQuery('<a/>', {
                        'role': 'menuitem',
                        'href': '#',
                        'tabindex': -1,
                    }).append(Sao.i18n.gettext('Manage...'))
                        .click(function(evt) {
                            evt.preventDefault();
                            window_();
                        })));
                });
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
            var badge = this.buttons.attach.find('.badge');
            if (!badge.length) {
                badge = jQuery('<span/>', {
                    'class': 'badge'
                }).appendTo(this.buttons.attach);
            }
            var text = count || '';
            if (count > 99) {
                text = '99+';
            }
            badge.text(text);
            this.buttons.attach.attr(
                'title', Sao.i18n.gettext("Attachment(%1)", count));
            var record_id = this.screen.get_id();
            this.buttons.attach.prop('disabled',
                record_id < 0 || record_id === null);
        },
        note: function() {
            var record = this.screen.current_record;
            if (!record || (record.id < 0)) {
                return;
            }
            new Sao.Window.Note(record, function() {
                this.update_unread_note(true);
            }.bind(this));
        },
        update_unread_note: function(reload) {
            var record = this.screen.current_record;
            if (record) {
                record.get_unread_note(reload).always(
                        this._unread_note.bind(this));
            } else {
                this._unread_note(0);
            }
        },
        _unread_note: function(unread) {
            var badge = this.buttons.note.find('.badge');
            if (!badge.length) {
                badge = jQuery('<span/>', {
                    'class': 'badge'
                }).appendTo(this.buttons.note);
            }
            var text = unread || '';
            if (unread > 99) {
                text = '99+';
            }
            badge.text(text);
            this.buttons.note.attr(
                'title', Sao.i18n.gettext("Note(%1)", unread));
            var record_id = this.screen.get_id();
            this.buttons.note.prop('disabled',
                    record_id < 0 || record_id === null);
        },
        record_message: function(data) {
            if (data) {
                var name = "_";
                if (data[0] !== 0) {
                    name = data[0];
                }
                var buttons = ['print', 'relate', 'attach'];
                buttons.forEach(function(button_id){
                    var button = this.buttons[button_id];
                    if (button) {
                        var disabled = button.is(':disabled');
                        button.prop('disabled', disabled || data[0] === 0);
                    }
                }.bind(this));
                this.buttons.switch_.prop('disabled',
                    this.attributes.view_ids > 1);
                var msg = name + ' / ' + data[1];
                if (data[1] < data[2]) {
                    msg += Sao.i18n.gettext(' of ') + data[2];
                }
                this.status_label.text(msg).attr('title', msg);
            }
            this.info_bar.message();
            // TODO activate_save
        },
        action: function() {
            window.setTimeout(function() {
                this.buttons.action.find('button').click();
            }.bind(this));
        },
        relate: function() {
            window.setTimeout(function() {
                this.buttons.relate.find('button').click();
            }.bind(this));
        },
        print: function() {
            window.setTimeout(function() {
                this.buttons.print.find('button').click();
            }.bind(this));
        },
        export: function(){
            new Sao.Window.Export(
                this.title.text(), this.screen,
                this.screen.current_view.selected_records().map(function(r) {
                    return r.id;
                }),
                this.screen.current_view.get_fields(),
                this.screen.context());
        },
        import: function(){
            new Sao.Window.Import(this.title.text(), this.screen);
        },
        get_url: function() {
            return this.screen.get_url(this.attributes.name);
        },
    });

    Sao.Tab.Board = Sao.class_(Sao.Tab, {
        class_: 'tab-board',
        init: function(attributes) {
            var UIView, view_prm;
            Sao.Tab.Board._super.init.call(this);
            this.model = attributes.model;
            this.view_id = (attributes.view_ids.length > 0 ?
                    attributes.view_ids[0] : null);
            this.context = attributes.context;
            this.name = attributes.name || '';
            this.dialogs = [];
            this.board = null;
            UIView = new Sao.Model('ir.ui.view');
            this.view_prm = UIView.execute('read', [[this.view_id], ['arch']],
                    this.context);
            this.view_prm.done(function(views) {
                var view, board;
                view = jQuery(jQuery.parseXML(views[0].arch));
                this.board = new Sao.View.Board(view, this.context);
                this.board.actions_prms.done(function() {
                    var i, len, action;
                    for (i = 0, len = this.board.actions.length; i < len; i++) {
                        action = this.board.actions[i];
                        action.screen.tab = this;
                    }
                }.bind(this));
                this.el.append(this.board.el);
            }.bind(this));
            this.create_tabcontent();
            this.set_name(this.name);
            this.title.html(this.name_el.text());
        },
        reload: function() {
            this.board.reload();
        },
        record_message: function() {
            var i, len;
            var action;

            len = this.board.actions.length;
            for (i = 0, len=len; i < len; i++) {
                action = this.board.actions[i];
                action.update_domain(this.board.actions);
            }
        },
        attachment_count: function() {
        },
        note: function() {
        },
        update_unread_note: function() {
        }
    });

    Sao.Tab.Wizard = Sao.class_(Sao.Tab, {
        class_: 'tab-wizard',
        init: function(wizard) {
            Sao.Tab.Wizard._super.init.call(this);
            this.wizard = wizard;
            this.set_name(wizard.name);
            wizard.tab = this;
            this.create_tabcontent();
            this.title.html(this.name_el.text());
            this.el.append(wizard.form);
        },
        create_toolbar: function() {
            return jQuery('<span/>');
        },
        _close_allowed: function() {
            var wizard = this.wizard;
            var prm = jQuery.when();
            if ((wizard.state !== wizard.end_state) &&
                (wizard.end_state in wizard.states)) {
                prm = wizard.response(wizard.end_state);
            }
            var dfd = jQuery.Deferred();
            prm.always(function() {
                if (wizard.state === wizard.end_state) {
                    dfd.resolve();
                } else {
                    dfd.reject();
                }
            });
            return dfd.promise();
        }
    });
}());
