/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.Tab = Sao.class_(Object, {
        init: function(attributes) {
            Sao.Tab.tabs.push(this);
            this.attributes = jQuery.extend({}, attributes);
            this.buttons = {};
            this.menu_buttons = {};
            this.id = 'tab-' + Sao.Tab.counter++;
            this.name_el = jQuery('<span/>');
            this.name_short_el = jQuery('<span/>', {
                'class': 'hidden-xs hidden-sm hidden-md',
            }).appendTo(this.name_el);
            this.name_long_el = jQuery('<span/>', {
                'class': 'hidden-lg',
            }).appendTo(this.name_el);
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
                }, {
                    id: 'email',
                    icon: 'tryton-email',
                    label: Sao.i18n.gettext('E-Mail...'),
                    tooltip: Sao.i18n.gettext('Send an e-mail using the record'),
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
                'class': 'panel panel-default ' + this.class_,
            });

            var toolbar = this.create_toolbar().appendTo(this.el);
            this.title = toolbar.find('.title');
            this.title_short = toolbar.find('.title-short');
            this.title_long = toolbar.find('.title-long');

            this.main = jQuery('<div/>', {
                'class': 'panel-body row',
            }).appendTo(this.el);
            this.content = jQuery('<div/>').appendTo(this.main);

            if (this.info_bar) {
                this.el.append(this.info_bar.el);
            }
        },
        set_menu: function(menu) {
            var previous;
            this.menu_def().forEach(item => {
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
                    }).text(' ' + item.label).prepend(
                        Sao.common.ICONFACTORY.get_icon_img(item.icon, {
                            'aria-hidden': 'true',
                        })).appendTo(menuitem);
                    this.menu_buttons[item.id] = menuitem;
                    link.click(evt => {
                        evt.preventDefault();
                        if (!menuitem.hasClass('disabled')) {
                            this[item.id]();
                        }
                    });
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
            });
        },
        create_toolbar: function() {
            var toolbar = jQuery('<nav/>', {
                'class': 'toolbar panel-heading',
                'role': 'toolbar'
            }).append(jQuery('<div/>', {
                'class': 'container-fluid navbar-inverse'
            }).append(jQuery('<div/>', {
                'class': 'dropdown navbar-left flip'
            }).append(jQuery('<a/>', {
                'href': "#",
                'class': "navbar-brand dropdown-toggle",
                'data-toggle': 'dropdown',
                'role': 'button',
                'aria-expanded': false,
                'aria-haspopup': true
            }).append(jQuery('<span/>', {
                'class': 'title'
            }).append(jQuery('<span/>', {
                'class': 'title-long hidden-xs hidden-sm hidden-md',
            })).append(jQuery('<span/>', {
                'class': 'title-short hidden-lg',
            }))).append(jQuery('<span/>', {
                'class': 'caret'
            }))).append(jQuery('<ul/>', {
                'class': 'dropdown-menu',
                'role': 'menu'
            })).append(jQuery('<button/>', {
                'type': 'button',
                'class': 'close visible-xs',
                'aria-label': Sao.i18n.gettext("Close"),
                'title': Sao.i18n.gettext("Close"),
            }).append(jQuery('<span/>', {
                'aria-hidden': true
            }).append('&times;')).click(() => {
                this.close();
            }))).append(jQuery('<div/>', {
                'class': 'btn-toolbar navbar-right pull-right flip',
                'role': 'toolbar'
            })));
            this.set_menu(toolbar.find('ul[role*="menu"]'));

            var group;
            const add_button = item => {
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
                    jQuery('<div/>', {
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
                this.buttons[item.id].click(item, event => {
                    var item = event.data;
                    var button = this.buttons[item.id];
                    // Use data instead of disabled prop because the action may
                    // actually disable the button.
                    if (button.data('disabled')) {
                        event.preventDefault();
                        return;
                    }
                    button.data('disabled', true);
                    (this[item.id](this) || jQuery.when())
                        .always(function() {
                            button.data('disabled', false);
                        });
                });
            };
            this.menu_def().forEach(add_button);
            if (this.buttons.previous) {
                this.status_label = jQuery('<span/>', {
                    'class': 'badge',
                }).appendTo(jQuery('<div/>', {
                    'class': 'navbar-text hidden-xs',
                }).insertAfter(this.buttons.previous));
                this.buttons.previous.addClass('hidden-xs');
            }
            if (this.buttons.next) {
                this.buttons.next.addClass('hidden-xs');
            }
            toolbar.find('.btn-toolbar > .btn-group').slice(-2, -1)
                .addClass('hidden-xs')
                .find('.dropdown')
                .on('show.bs.dropdown', function() {
                    jQuery(this).parents('.btn-group')
                        .removeClass('hidden-xs');
                })
                .on('hide.bs.dropdown', function() {
                    jQuery(this).parents('.btn-group')
                        .addClass('hidden-xs');
                });
            toolbar.find('.btn-toolbar > .btn-group').last()
                .addClass('hidden-xs hidden-sm')
                .find('.dropdown')
                .on('show.bs.dropdown', function() {
                    jQuery(this).parents('.btn-group')
                        .removeClass('hidden-xs hidden-sm');
                })
                .on('hide.bs.dropdown', function() {
                    jQuery(this).parents('.btn-group')
                        .addClass('hidden-xs hidden-sm');
                });
            return toolbar;
        },
        show: function() {
            Sao.common.scrollIntoViewIfNeeded(
                jQuery('#tablist').find('a[href="#' + this.id + '"]')
                .tab('show'));
        },
        close: function() {
            var tabs = jQuery('#tabs');
            var tablist = jQuery('#tablist');
            var tab = tablist.find('#nav-' + this.id);
            var content = tabs.find('#' + this.id);
            this.show();
            return this._close_allowed().then(() => {
                var next = tab.nextAll('li').first();
                if (!next.length) {
                    next = tab.prevAll('li').first();
                }
                tab.remove();
                content.remove();
                var i = Sao.Tab.tabs.indexOf(this);
                if (i >= 0) {
                    Sao.Tab.tabs.splice(i, 1);
                }
                if (next.length) {
                    next.find('a').tab('show');
                } else {
                    Sao.set_url();
                }
                tabs.trigger('ready');
            });
        },
        _close_allowed: function() {
            return jQuery.when();
        },
        set_name: function(name) {
            this.name_short_el.text(name.split(' / ').pop());
            this.name_long_el.text(name);
            this.name_el.attr('title', name);
            this.title_short.text(this.name_short);
            this.title_long.text(this.name_long);
        },
        get name_short() {
            return this.name_short_el.text();
        },
        get name_long() {
            return this.name_long_el.text();
        },
        get_url: function() {
        },
        get current_view_type() {
            return 'form';
        },
        compare: function(attributes) {
            return false;
        },
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
        return jQuery('#tablist').find('li.active').data('tab');
    };
    Sao.Tab.tabs.close_current = function() {
        var tab = this.get_current();
        tab.close();
    };

    Sao.Tab.create = function(attributes) {
        var tablist = jQuery('#tablist');
        if (attributes.context === undefined) {
            attributes.context = {};
        }
        for (const other of Sao.Tab.tabs) {
            if (other.compare(attributes)) {
                Sao.common.scrollIntoViewIfNeeded(
                    tablist.find('a[href="#' + other.id + '"]').tab('show'));
                return;
            }
        }
        var tab;
        if (attributes.model) {
            tab = new Sao.Tab.Form(attributes.model, attributes);
        } else {
            tab = new Sao.Tab.Board(attributes);
        }
        return tab.view_prm.then(function() {
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
            Sao.set_url(tab.get_url(), tab.name_long.split(' / ').pop());
            Sao.Tab.set_view_type(tab.current_view_type);
        })
        .append(jQuery('<button/>', {
            'class': 'close',
            'aria-label': Sao.i18n.gettext("Close"),
            'title': Sao.i18n.gettext("Close"),
        }).append(jQuery('<span/>', {
            'aria-hidden': true
        }).append('&times;')).click(function(evt) {
            evt.preventDefault();
            tab.close();
        }))
        .append(tab.name_el);
        jQuery('<li/>', {
            'role': 'presentation',
            'data-placement': 'bottom',
            id: 'nav-' + tab.id
        }).append(tab_link)
        .appendTo(tablist)
        .data('tab', tab);
        jQuery('<div/>', {
            role: 'tabpanel',
            'class': 'tab-pane',
            id: tab.id
        }).append(tab.el)
        .appendTo(tabcontent);
        tab_link.on('hide.bs.tab', function(evt) {
            jQuery(evt.target).data('scrollTop', tabs.scrollTop());
        });
        tab_link.on('shown.bs.tab', function(evt) {
            tabs.scrollTop(jQuery(evt.target).data('scrollTop') || 0);
        });
        Sao.common.scrollIntoViewIfNeeded(tab_link.tab('show'));
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
        if (!next.length) {
            if (direction == 'prevAll') {
                next = tablist.find('li').last();
            } else {
                next = tablist.find('li').first();
            }
        }
        if (next) {
            next.find('a').tab('show');
            tabs.trigger('ready');
        }
    };

    Sao.Tab.set_view_type = function(type) {
        var tabcontent = jQuery('#tabcontent');
        tabcontent.attr('data-view-type', type);
    };

    Sao.Tab.Form = Sao.class_(Sao.Tab, {
        class_: 'tab-form',
        init: function(model_name, attributes) {
            Sao.Tab.Form._super.init.call(this, attributes);
            attributes = jQuery.extend({}, attributes);
            var name = attributes.name;
            if (!name) {
                name = Sao.common.MODELNAME.get(model_name);
            }
            if (attributes.res_id) {
                if (Object.prototype.hasOwnProperty.call(
                    attributes, 'tab_domain')) {
                    delete attributes.tab_domain;
                }
            }
            attributes.breadcrumb = [name];
            var screen = new Sao.Screen(model_name, attributes);
            screen.windows.push(this);
            this.screen = screen;
            this.info_bar = new Sao.Window.InfoBar();
            this.create_tabcontent();
            this.set_name(name);

            this.attachment_screen = null;

            screen.switch_callback = () => {
                if (this === Sao.Tab.tabs.get_current()) {
                    Sao.set_url(
                        this.get_url(), this.name_long.split(' / ').pop());
                }
            };

            this.view_prm = this.screen.switch_view().done(() => {
                this.set_buttons_sensitive();
                this.content.append(screen.screen_container.el);
                if (attributes.res_id) {
                    if (!jQuery.isArray(attributes.res_id)) {
                        attributes.res_id = [attributes.res_id];
                    }
                    screen.load(attributes.res_id);
                    if (attributes.res_id.length) {
                        screen.current_record = screen.group.get(
                            attributes.res_id[0]);
                    }
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
            });
        },
        create_toolbar: function() {
            var toolbar = Sao.Tab.Form._super.create_toolbar.call(this);
            var screen = this.screen;
            var toolbars = screen.model.execute(
                'view_toolbar_get', [], screen.context, false);
            [
                ['action', 'tryton-launch',
                    Sao.i18n.gettext('Launch action')],
                ['relate', 'tryton-link',
                    Sao.i18n.gettext('Open related records')],
                ['print', 'tryton-print',
                    Sao.i18n.gettext('Print report')]
            ].forEach(menu_action => {
                var dropdown = jQuery('<div/>', {
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
                    .insertBefore(toolbar.find('button#email'));
                var button = dropdown.find('button');
                this.buttons[menu_action[0]] = button;
                dropdown
                    .on('show.bs.dropdown', function() {
                        jQuery(this).parents('.btn-group')
                            .removeClass('hidden-xs hidden-sm');
                    }).on('hide.bs.dropdown', function() {
                        jQuery(this).parents('.btn-group')
                            .addClass('hidden-xs hidden-sm');
                    });
                var menu = dropdown.find('.dropdown-menu');
                button.click(function() {
                    menu.find([
                        '.' + menu_action[0] + '_button',
                        '.divider-button',
                        '.' + menu_action[0] + '_plugin',
                        '.divider-plugin'].join(',')).remove();
                    var buttons = screen.get_buttons().filter(
                        function(button) {
                            return menu_action[0] == (
                                button.attributes.keyword || 'action');
                        });
                    if (buttons.length) {
                        menu.append(jQuery('<li/>', {
                            'role': 'separator',
                            'class': 'divider divider-button',
                        }));
                    }
                    buttons.forEach(function(button) {
                        jQuery('<li/>', {
                            'role': 'presentation',
                            'class': menu_action[0] + '_button'
                        })
                            .append(
                                jQuery('<a/>', {
                                    'role': 'menuitem',
                                    'href': '#',
                                    'tabindex': -1
                                }).text(
                                    button.attributes.string || ''))
                            .click(function(evt) {
                                evt.preventDefault();
                                screen.button(button.attributes);
                            })
                            .appendTo(menu);
                    });

                    var kw_plugins = [];
                    for (const plugin of Sao.Plugins) {
                        for (const spec of plugin.get_plugins(
                            screen.model.name)) {
                            var name = spec[0],
                                func = spec[1],
                                keyword = spec[2] || 'action';
                            if (keyword == menu_action[0]) {
                                kw_plugins.push([name, func]);
                            }
                        }
                    }
                    if (kw_plugins.length) {
                        menu.append(jQuery('<li/>', {
                            'role': 'separator',
                            'class': 'divider divider-plugin',
                        }));
                    }
                    kw_plugins.forEach(function(plugin) {
                        var name = plugin[0],
                            func = plugin[1];
                        jQuery('<li/>', {
                            'role': 'presentation',
                            'class': menu_action[0] + '_plugin',
                        }).append(
                            jQuery('<a/>', {
                                'role': 'menuitem',
                                'href': '#',
                                'tabindex': -1,
                            }).text(name))
                            .click(function(evt) {
                                evt.preventDefault();
                                var ids = screen.current_view.selected_records
                                    .map(function(record) {
                                        return record.id;
                                    });
                                var id = screen.current_record ?
                                    screen.current_record.id : null;
                                var model_context = screen.context_screen ?
                                    screen.context_screen.model_name : null;
                                func({
                                    'model': screen.model.name,
                                    'model_context': model_context,
                                    'id': id,
                                    'ids': ids,
                                    'paths': screen.selected_paths,
                                });
                            })
                            .appendTo(menu);
                    });
                });

                toolbars[menu_action[0]].forEach(action => {
                    jQuery('<li/>', {
                        'role': 'presentation'
                    })
                        .append(jQuery('<a/>', {
                            'role': 'menuitem',
                            'href': '#',
                            'tabindex': -1
                        }).text(action.name))
                        .click(evt => {
                            evt.preventDefault();
                            this.modified_save().then(function() {
                                var exec_action = jQuery.extend({}, action);
                                var record_id = null;
                                if (screen.current_record) {
                                    record_id = screen.current_record.id;
                                }
                                var records, paths;
                                if (action.records == 'listed') {
                                    records = screen.listed_records;
                                    paths = screen.listed_paths;
                                } else {
                                    records = screen.selected_records;
                                    paths = screen.selected_paths;
                                }
                                var record_ids = records.map(function(record) {
                                    return record.id;
                                });
                                var model_context = screen.context_screen ?
                                    screen.context_screen.model_name : null;
                                var data = {
                                    'model': screen.model_name,
                                    'model_context': model_context,
                                    'id': record_id,
                                    'ids': record_ids,
                                    'paths': paths,
                                };
                                Sao.Action.execute(exec_action, data,
                                    jQuery.extend({}, screen.local_context));
                            });
                        })
                        .appendTo(menu);
                });

                if (menu_action[0] != 'action') {
                    button._can_be_sensitive = Boolean(
                        menu.children().length);
                }

                if ((menu_action[0] == 'print') &&
                    toolbars.exports.length) {
                    button._can_be_sensitive = true;
                    if (toolbars.print.length) {
                        menu.append(jQuery('<li/>', {
                            'role': 'separator',
                            'class': 'divider',
                        }));
                    }
                    toolbars.exports.forEach(export_ => {
                        jQuery('<li/>', {
                            'role': 'presentation',
                        })
                            .append(jQuery('<a/>', {
                                'role': 'menuitem',
                                'href': '#',
                                'tabindex': -1,
                            }).text(export_.name))
                            .click(evt => {
                                evt.preventDefault();
                                this.do_export(export_);
                            })
                            .appendTo(menu);
                    });
                }
            });
            this.buttons.attach
                .on('dragover', false)
                .on('drop', this.attach_drop.bind(this));
            return toolbar;
        },
        create_tabcontent: function() {
            Sao.Tab.Form._super.create_tabcontent.call(this);
            this.attachment_preview = jQuery('<div/>', {
                'class': 'attachment-preview',
            }).hide().appendTo(this.main);
        },
        compare: function(attributes) {
            if (!attributes) {
                return false;
            }
            var compare = Sao.common.compare;
            return (
                (this.screen.view_index === 0) &&
                (this.screen.model_name === attributes.model) &&
                (this.attributes.res_id === attributes.res_id) &&
                (compare(
                    this.attributes.domain || [], attributes.domain || [])) &&
                (compare(
                    this.attributes.view_ids || [],
                    attributes.view_ids || [])) &&
                (attributes.view_ids ||
                    (compare(
                        this.attributes.mode || ['tree', 'form'],
                        attributes.mode || ['tree', 'form']))) &&
                (JSON.stringify(this.screen.local_context) ===
                    JSON.stringify(attributes.context)) &&
                (compare(
                    this.attributes.search_value || [],
                    attributes.search_value || [])) &&
                (JSON.stringify(this.screen.attributes.tab_domain) ===
                    JSON.stringify(attributes.tab_domain))
            );
        },
        _close_allowed: function() {
            return this.modified_save().then(null, function(result) {
                if (result) {
                    return jQuery.Deferred().resolve();
                } else {
                    return jQuery.Deferred().reject();
                }
            });
        },
        modified_save: function() {
            this.screen.save_tree_state();
            this.screen.current_view.set_value();
            if (this.screen.modified()) {
                return Sao.common.sur_3b.run(
                        Sao.i18n.gettext('This record has been modified\n' +
                            'do you want to save it?'))
                    .then(result => {
                        switch(result) {
                            case 'ok':
                                return this.save();
                            case 'ko':
                                var record_id = this.screen.current_record.id;
                                return this.reload(false).then(() => {
                                    if (record_id < 0) {
                                        return jQuery.Deferred().reject(true);
                                    }
                                    else if (this.screen.current_record) {
                                        if (record_id !=
                                            this.screen.current_record.id) {
                                            return jQuery.Deferred().reject();
                                        }
                                    }
                                });
                            default:
                                return jQuery.Deferred().reject();
                        }
                    });
            }
            return jQuery.when();
        },
        new_: function() {
            if (!Sao.common.MODELACCESS.get(this.screen.model_name).create) {
                return jQuery.when();
            }
            return this.modified_save().then(() => {
                return this.screen.new_().then(() => {
                    this.info_bar.clear();
                    this.set_buttons_sensitive();
                });
            });
        },
        save: function(tab) {
            if (tab) {
                // Called from button so we must save the tree state
                this.screen.save_tree_state();
            }
            var access = Sao.common.MODELACCESS.get(this.screen.model_name);
            if (!(access.write || access.create)) {
                return jQuery.Deferred().reject();
            }
            return this.screen.save_current().then(
                () => {
                    this.info_bar.add(
                        Sao.i18n.gettext('Record saved.'), 'info');
                    this.screen.count_tab_domain(true);
                }, () => {
                    this.info_bar.add(
                        this.screen.invalid_message(), 'danger');
                    return jQuery.Deferred().reject();
                });
        },
        switch_: function() {
            return this.modified_save().then(() => this.screen.switch_view());
        },
        reload: function(test_modified=true) {
            const reload = () => {
                return this.screen.cancel_current().then(() => {
                    var set_cursor = false;
                    var record_id = null;
                    if (this.screen.current_record) {
                        record_id = this.screen.current_record.id;
                    }
                    if (this.screen.current_view.view_type != 'form') {
                        return this.screen.search_filter(
                            this.screen.screen_container.search_entry.val())
                            .then(() => {
                                for (const record of this.screen.group) {
                                    if (record.id == record_id) {
                                        this.screen.current_record = record;
                                        set_cursor = true;
                                    }
                                }
                                return set_cursor;
                            });
                    }
                    return set_cursor;
                })
                .then(set_cursor => {
                    return this.screen.display(set_cursor).then(() => {
                        this.info_bar.clear();
                        this.set_buttons_sensitive();
                        this.screen.count_tab_domain();
                    });
                });
            };
            if (test_modified) {
                return this.modified_save().then(reload);
            } else {
                this.screen.save_tree_state(false);
                return reload();
            }
        },
        copy: function() {
            if (!Sao.common.MODELACCESS.get(this.screen.model_name).create) {
                return jQuery.when();
            }
            return this.modified_save().then(() => {
                return this.screen.copy().then(() => {
                    this.info_bar.add(
                            Sao.i18n.gettext(
                                'Working now on the duplicated record(s).'),
                            'info');
                    this.screen.count_tab_domain(true);
                });
            });
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
            return Sao.common.sur.run(msg).then(() => {
                return this.screen.remove(true, false, true).then(
                    () => {
                        this.info_bar.add(
                            Sao.i18n.gettext("Records removed."),
                            'info');
                        this.screen.count_tab_domain(true);
                    }, () => {
                        this.info_bar.add(
                            Sao.i18n.gettext("Records not removed."),
                            'danger');
                    });
            });
        },
        previous: function() {
            return this.modified_save().then(() => {
                var prm = this.screen.display_previous();
                this.info_bar.clear();
                this.set_buttons_sensitive();
                return prm;
            });
        },
        next: function() {
            return this.modified_save().then(() => {
                var prm = this.screen.display_next();
                this.info_bar.clear();
                this.set_buttons_sensitive();
                return prm;
            });
        },
        search: function() {
            var search_entry = this.screen.screen_container.search_entry;
            search_entry.parents('.filter-box').toggleClass('hidden-xs');
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
                this.info_bar.add(
                        Sao.i18n.gettext('You have to select one record.'),
                        'info');
                return jQuery.when();
            }
            new Sao.Window.Log(record);
        },
        revision: function() {
            var current_id = null;
            if (this.screen.current_record) {
                current_id = this.screen.current_record.id;
            }
            const set_revision = revisions => {
                return revision => {
                    if (revision) {
                        // Add a millisecond as microseconds are truncated
                        revision.add(1, 'milliseconds');
                    }
                    if ((this.screen.current_view.view_type == 'form') &&
                            revision &&
                            (revision < revisions[revisions.length - 1][0])) {
                        revision = revisions[revisions.length - 1][0];
                    }
                    if (revision != this.screen.context._datetime) {
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
                };
            };
            return this.modified_save().then(() => {
                var ids = this.screen.current_view.selected_records.map(
                    record => record.id);
                return this.screen.model.execute('history_revisions',
                    [ids], this.screen.context)
                    .then(revisions => {
                        const revision = this.screen.context._datetime;
                        if (revision) {
                            // Remove a millisecond as microseconds are truncated
                            revision.add(-1, 'milliseconds');
                        }
                        new Sao.Window.Revision(
                            revisions, revision, set_revision(revisions));
                    });
            });
        },
        update_revision: function() {
            var revision = this.screen.context._datetime;
            var label_short, label_long, title;
            if (revision) {
                var date_format = Sao.common.date_format(
                    this.screen.context.date_format);
                var time_format = '%H:%M:%S.%f';
                var revision_label = ' @ ' + Sao.common.format_datetime(
                    date_format + ' ' + time_format, revision);
                label_long = Sao.common.ellipsize(
                    this.name_long, 80 - revision_label.length) + revision_label;
                label_short = Sao.common.ellipsize(
                    this.name_short, 80 - revision_label.length) + revision_label;
                title = this.name_long + revision_label;
            } else {
                label_long = Sao.common.ellipsize(this.name_long, 80);
                label_short = Sao.common.ellipsize(this.name_short, 80);
                title = this.name_long;
            }
            this.title_short.text(label_short);
            this.title_long.text(label_long);
            this.title.attr('title', title);
            this.set_buttons_sensitive();
        },
        set_buttons_sensitive: function() {
            var revision = this.screen.context._datetime;
            if (!revision) {
                var access = Sao.common.MODELACCESS.get(this.screen.model_name);
                var modified = this.screen.modified();
                const accesses = new Map([
                    ['new_', access.create && !modified],
                    ['save',
                        (access.create || access.write) &&
                        modified && !this.screen.readonly],
                    ['delete_', access.delete],
                    ['copy', access.create],
                    ['import', access.create],
                ]);
                for (const [name, access] of accesses) {
                    if (this.buttons[name]) {
                        this.buttons[name].prop('disabled', !access);
                    }
                    if (this.menu_buttons[name]) {
                        this.menu_buttons[name]
                            .toggleClass('disabled', !access);
                    }
                }
            } else {
                for (const name of [
                    'new_', 'save', 'delete_', 'copy', 'import']) {
                    if (this.buttons[name]) {
                        this.buttons[name].prop('disabled', true);
                    }
                    if (this.menu_buttons[name]) {
                        this.menu_buttons[name].addClass('disabled');
                    }
                }
            }
        },
        attach: function(evt) {
            const window_ = () => {
                return new Sao.Window.Attachment(record, () => {
                    this.refresh_resources(true);
                });
            };
            const preview = () => {
                if (this.attachment_preview.children().length) {
                    this.attachment_preview.empty();
                    this.attachment_preview.hide();
                    this.attachment_screen = null;
                } else {
                    this.attachment_preview.append(
                        this._attachment_preview_el());
                    this.attachment_preview.show();
                    this.refresh_attachment_preview();
                }
            };
            var dropdown = this.buttons.attach.parents('.dropdown');
            if (!evt) {
                window.setTimeout(() => {
                    this.buttons.attach.click();
                });
                return;
            }
            var record = this.screen.current_record;
            var menu = dropdown.find('.dropdown-menu');
            menu.empty();
            Sao.Window.Attachment.get_attachments(record)
                .then(function(attachments) {
                    attachments.forEach(function(value) {
                        var name = value[0],
                            callback = value[1];
                        var link = jQuery('<a/>', {
                            'role': 'menuitem',
                            'href': '#',
                            'tabindex': -1,
                        }).text(name).appendTo(jQuery('<li/>', {
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
                        'multiple': true,
                        'tabindex': -1,
                    }).change(function() {
                        var attachment = window_();
                        Sao.common.get_input_data(
                            jQuery(this), function(data, filename) {
                                attachment.add_data(data, filename);
                            });
                    })).append(jQuery('<a/>', {
                        'role': 'menuitem',
                        'href': '#',
                        'tabindex': -1,
                    }).text(Sao.i18n.gettext('Add...'))));
                    menu.append(jQuery('<li/>', {
                        'role': 'presentation',
                    }).append(jQuery('<a/>', {
                        'role': 'menuitem',
                        'href': '#',
                        'tabindex': -1,
                    }).text(Sao.i18n.gettext("Preview"))
                        .click(function(evt) {
                            evt.preventDefault();
                            preview();
                        })));
                    menu.append(jQuery('<li/>', {
                        'role': 'presentation',
                    }).append(jQuery('<a/>', {
                        'role': 'menuitem',
                        'href': '#',
                        'tabindex': -1,
                    }).text(Sao.i18n.gettext('Manage...'))
                        .click(function(evt) {
                            evt.preventDefault();
                            window_();
                        })));
                });
        },
        attach_drop: function(evt) {
            evt.preventDefault();
            evt.stopPropagation();
            evt = evt.originalEvent;
            var record = this.screen.current_record;
            if (!record || record.id < 0) {
                return;
            }

            var i, file;
            var files = [],
                uris = [],
                texts = [];
            if (evt.dataTransfer.items) {
                Sao.Logger.debug("Attach drop items:", evt.dataTransfer.items);
                for (i = 0; i < evt.dataTransfer.items.length; i++) {
                    var item = evt.dataTransfer.items[i];
                    if (item.kind == 'string') {
                        var list;
                        if (item.type == 'text/uri-list') {
                            list = uris;
                        } else if (item.type == 'text/plain') {
                            list = texts;
                        } else {
                            continue;
                        }
                        var prm = jQuery.Deferred();
                        evt.dataTransfer.items[i].getAsString(prm.resolve);
                        list.push(prm);
                        break;
                    } else {
                        file = evt.dataTransfer.items[i].getAsFile();
                        if (file) {
                            files.push(file);
                        }
                    }
                }
            } else {
                for (i = 0; i < evt.dataTransfer.files.length; i++) {
                    file = evt.dataTransfer.files[i];
                    if (file) {
                        files.push(file);
                    }
                }
            }

            var window_ = new Sao.Window.Attachment(record, () => {
                this.refresh_resources(true);
            });
            for (const file of files) {
                Sao.common.get_file_data(file, window_.add_data.bind(window_));
            }
            jQuery.when.apply(jQuery, uris).then(function() {
                function empty(value) {
                    return Boolean(value);
                }
                for (const argument of arguments) {
                    argument.split('\r\n')
                        .filter(empty)
                        .forEach(window_.add_uri, window_);
                }
            });
            jQuery.when.apply(jQuery, texts).then(function() {
                for (const argument of arguments) {
                    window_.add_text(argument);
                }
            });
            if (evt.dataTransfer.items) {
                evt.dataTransfer.items.clear();
            } else {
                evt.dataTransfer.clearData();
            }
        },
        _attachment_preview_el: function() {
            var el = jQuery('<div/>', {
                'class': 'text-center',
            });
            var buttons = jQuery('<div/>', {
                'class': 'btn-group',
            }).appendTo(el);

            var but_prev = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'tabindex': -1,
                'aria-label': Sao.i18n.gettext("Previous"),
                'title': Sao.i18n.gettext("Previous"),
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-back')
            ).appendTo(buttons);

            var label = jQuery('<span/>', {
                'class': 'badge',
            }).text('(0/0)').appendTo(jQuery('<span/>', {
                'class': 'btn btn-sm btn-link',
            }).appendTo(buttons));

            var but_next = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'tabindex': -1,
                'aria-label': Sao.i18n.gettext("Next"),
                'title': Sao.i18n.gettext("Next"),
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-forward')
            ).appendTo(buttons);

            var screen = new Sao.Screen('ir.attachment', {
                'readonly': true,
                'mode': ['form'],
                'context': {
                    'preview': true,
                },
            });
            this.attachment_screen = screen;

            but_prev.click(function() {
                return screen.display_previous();
            });
            but_next.click(function() {
                return screen.display_next();
            });

            var preview = {};
            preview.record_message = function(position, length) {
                var text = (position || '_') + '/' + length;
                label.text(text).attr('title', text);
                but_prev.prop('disabled', !screen.has_previous());
                but_next.prop('disabled', !screen.has_next());
            };
            screen.windows.push(preview);

            screen.switch_view().done(function() {
                el.append(screen.screen_container.el);
            });
            return el;
        },
        refresh_attachment_preview: function(force) {
            if (!this.attachment_screen) {
                return;
            }
            var record = this.screen.current_record;
            if (!record) {
                return;
            }
            var resource = record.model.name + ',' + record.id;
            var domain = [
                ['resource', '=', resource],
                ['type', '=', 'data'],
            ];
            if (!Sao.common.compare(this.attachment_screen.domain, domain) ||
                force) {
                this.attachment_screen.domain = domain;
                this.attachment_screen.search_filter().then(() => {
                    const group = this.attachment_screen.group;
                    if (group.length) {
                        this.attachment_screen.current_record = group[0];
                        this.attachment_screen.display();
                    }
                });
            }
        },
        note: function() {
            var record = this.screen.current_record;
            if (!record || (record.id < 0)) {
                return;
            }
            new Sao.Window.Note(record, () => {
                this.refresh_resources(true);
            });
        },
        email: function() {
            function is_report(action) {
                return action.type == 'ir.action.report';
            }
            if (!this.buttons.email.prop('disabled')) {
                this.modified_save().then(() => {
                    var record = this.screen.current_record;
                    if (!record || (record.id < 0)) {
                        return;
                    }
                    var title = this.name_short;
                    this.screen.model.execute(
                        'view_toolbar_get', [], this.screen.context)
                        .then(function(toolbars) {
                            var prints = toolbars.print.filter(is_report);
                            var emails = {};
                            for (const email of toolbars.emails) {
                                emails[email.name] = email.id;
                            }
                            record.rec_name().then(function(rec_name) {
                                function email(template) {
                                    new Sao.Window.Email(
                                        title + ': ' + rec_name, record,
                                        prints, template);
                                }
                                Sao.common.selection(
                                    Sao.i18n.gettext("Template"), emails, true)
                                    .then(email, email);
                            });
                        });
                });
            }
        },
        refresh_resources: function(reload) {
            var record = this.screen.current_record;
            if (record) {
                record.get_resources(reload).always(
                    this.update_resources.bind(this));
            } else {
                this.update_resources();
            }
            if (reload) {
                this.refresh_attachment_preview(true);
            }
        },
        update_resources: function(resources) {
            if (!resources) {
                resources = {};
            }
            var record_id = this.screen.get_id();
            var disabled = (
                record_id < 0 || record_id === null || record_id === undefined);

            const update = (name, title, text, color) => {
                var button = this.buttons[name];

                var badge = button.find('.badge');
                if (!badge.length) {
                    badge = jQuery('<span/>', {
                        'class': 'badge'
                    }).appendTo(button);
                }
                if (color) {
                    color = Sao.config.icon_colors[color];
                } else {
                    color = '';
                }
                badge.css('background-color', color);
                badge.css('color', '#fff');
                badge.text(text);
                button.attr('title', title);
                button.prop('disabled', disabled);
            };

            var count = resources.attachment_count || 0;
            var badge = count || '';
            if (count > 99) {
                badge = '99+';
            }
            var title= Sao.i18n.gettext("Attachment (%1)", count);
            update('attach', title, badge, 1);

            count = resources.note_count || 0;
            var unread = resources.note_unread || 0;
            badge = '';
            var color = unread > 0 ? 2 : 1;
            if (count) {
                if (count > 9) {
                    badge = '+';
                } else {
                    badge = count;
                }
                if (unread > 9) {
                    badge = '+/' + badge;
                } else {
                    badge = unread + '/' + badge;
                }
            }
            title = Sao.i18n.gettext("Note (%1/%2)", unread, count);
            update('note', title, badge, color);
        },
        record_message: function(position, size, max_size, record_id) {
            const set_sensitive = (button_id, sensitive) => {
                if (this.buttons[button_id]) {
                    this.buttons[button_id].prop('disabled', !sensitive);
                }
                if (this.menu_buttons[button_id]) {
                    this.menu_buttons[button_id].toggleClass('disabled', !sensitive);
                }
            };

            var name = "_";
            if (position) {
                var selected = this.screen.selected_records.length;
                name = '' + position;
                if (selected > 1) {
                    name += '#' + selected;
                }
            }
            const view_type = this.screen.current_view.view_type;
            const has_views = this.screen.number_of_views > 1;
            var buttons = ['print', 'relate', 'email', 'attach'];
            for (const button_id of buttons) {
                const button = this.buttons[button_id];
                let can_be_sensitive = button._can_be_sensitive;
                if (can_be_sensitive === undefined) {
                    can_be_sensitive = true;
                }
                if ((button_id == 'print') ||
                    (button_id == 'relate') ||
                    (button_id == 'email')) {
                    can_be_sensitive |= this.screen.get_buttons().some(
                        function(button) {
                            var keyword = button.attributes.keyword || 'action';
                            return keyword == button_id;
                        });
                }
                set_sensitive(button_id, position && can_be_sensitive);
            }
            set_sensitive(
                'switch_', (position || (view_type == 'form')) && has_views);
            set_sensitive('delete_', this.screen.deletable);
            set_sensitive('previous', this.screen.has_previous());
            set_sensitive('next', this.screen.has_next());

            var msg;
            if (size < max_size) {
                msg = (
                    name + '@' +
                    Sao.common.humanize(size) + '/' +
                    Sao.common.humanize(max_size));
                if (max_size >= this.screen.count_limit) {
                    msg += '+';
                }
            } else {
                msg = name + '/' + Sao.common.humanize(size);
            }
            this.status_label.text(msg).attr('title', msg);
            this.info_bar.clear();
            this.set_buttons_sensitive();
            this.refresh_attachment_preview();
        },
        record_modified: function() {
            this.set_buttons_sensitive();
            this.info_bar.refresh();
        },
        record_saved: function() {
            this.set_buttons_sensitive();
            this.refresh_resources();
        },
        action: function() {
            window.setTimeout(() => {
                this.buttons.action.click();
            });
        },
        relate: function() {
            window.setTimeout(() => {
                this.buttons.relate.click();
            });
        },
        print: function() {
            window.setTimeout(() => {
                this.buttons.print.click();
            });
        },
        export: function(){
            this.modified_save().then(() => {
                new Sao.Window.Export(
                    this.name_short, this.screen,
                    this.screen.current_view.get_fields());
            });
        },
        do_export: function(export_) {
            this.modified_save().then(() => {
                var ids, paths;
                if (export_.records == 'listed') {
                    ids = this.screen.listed_records.map(r => r.id);
                    paths = this.screen.listed_paths;
                } else {
                    ids = this.screen.selected_records.map(r => r.id);
                    paths = this.screen.selected_paths;
                }
                var fields = export_['export_fields.'].map(
                    field => field.name);
                this.screen.model.execute(
                    'export_data', [ids, fields, export_.header],
                    this.screen.context)
                    .then(function(data) {
                        var unparse_obj = {
                            'data': data,
                        };
                        unparse_obj.data = data.map((row, i) => {
                            var indent = (
                                paths && paths[i] ? paths[i].length -1 : 0);
                            return Sao.Window.Export.format_row(row, indent);
                        });
                        var delimiter = ',';
                        if (navigator.platform &&
                            navigator.platform.slice(0, 3) == 'Win') {
                            delimiter = ';';
                        }
                        var csv = Papa.unparse(unparse_obj, {
                            quoteChar: '"',
                            delimiter: delimiter,
                        });
                        if (navigator.platform &&
                            navigator.platform.slice(0, 3) == 'Win') {
                            csv = Sao.BOM_UTF8 + csv;
                        }
                        Sao.common.download_file(
                            csv, export_.name + '.csv',
                            {'type': 'text/csv;charset=utf-8'});
                    });
            });
        },
        import: function(){
            if (!Sao.common.MODELACCESS.get(this.screen.model_name).create) {
                return;
            }
            new Sao.Window.Import(this.name_short, this.screen);
        },
        get_url: function() {
            return this.screen.get_url(this.name);
        },
        get current_view_type() {
            return this.screen.current_view.view_type;
        },
    });

    Sao.Tab.Board = Sao.class_(Sao.Tab, {
        class_: 'tab-board',
        init: function(attributes) {
            var UIView;
            Sao.Tab.Board._super.init.call(this, attributes);
            this.model = attributes.model;
            this.view_id = (attributes.view_ids.length > 0 ?
                    attributes.view_ids[0] : null);
            this.context = attributes.context;
            var name = attributes.name;
            if (!name) {
                name = Sao.common.MODELNAME.get(this.model);
            }
            this.dialogs = [];
            this.board = null;
            UIView = new Sao.Model('ir.ui.view');
            this.view_prm = UIView.execute(
                'view_get', [this.view_id], this.context);
            this.view_prm.done(view => {
                view = jQuery(jQuery.parseXML(view.arch));
                this.board = new Sao.View.Board(view, this.context);
                this.board.actions_prms.done(() => {
                    var i, len, action;
                    for (i = 0, len = this.board.actions.length; i < len; i++) {
                        action = this.board.actions[i];
                        action.screen.windows.push(this);
                    }
                    this.board.reload();
                });
                this.content.append(this.board.el);
            });
            this.create_tabcontent();
            this.set_name(name);
        },
        compare: function(attributes) {
            if (!attributes) {
                return false;
            }
            var compare = Sao.common.compare;
            return ((this.model === attributes.model) &&
                (compare(
                    this.attributes.view_ids || [], attributes.view_ids || [])) &&
                (JSON.stringify(this.context) === JSON.stringify(attributes.context))
            );
        },
        reload: function() {
            this.board.reload();
        },
        record_message: function() {
            for (const action of this.board.actions) {
                action.update_domain(this.board.actions);
            }
        },
        refresh_resources: function() {
        },
        update_resources: function() {
        },
    });

    Sao.Tab.Wizard = Sao.class_(Sao.Tab, {
        class_: 'tab-wizard',
        init: function(wizard) {
            Sao.Tab.Wizard._super.init.call(this);
            this.wizard = wizard;
            wizard.tab = this;
            this.create_tabcontent();
            this.set_name(wizard.name);
            this.content.append(wizard.form);
        },
        create_toolbar: function() {
            return jQuery('<span/>');
        },
        _close_allowed: function() {
            var wizard = this.wizard;
            if ((wizard.state !== wizard.end_state) &&
                (wizard.end_state in wizard.states)) {
                wizard.response(
                    wizard.states[wizard.end_state].attributes);
            }
            var dfd = jQuery.Deferred();
            if (wizard.state === wizard.end_state) {
                dfd.resolve();
            } else {
                dfd.reject();
            }
            return dfd.promise();
        }
    });
}());
