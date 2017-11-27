/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
var Sao = {};

(function() {
    'use strict';

    // Browser compatibility: polyfill
    if (!('contains' in String.prototype)) {
        String.prototype.contains = function(str, startIndex) {
            return -1 !== String.prototype.indexOf.call(this, str, startIndex);
        };
    }
    if (!String.prototype.startsWith) {
        Object.defineProperty(String.prototype, 'startsWith', {
            enumerable: false,
            configurable: false,
            writable: false,
            value: function(searchString, position) {
                position = position || 0;
                return this.indexOf(searchString, position) === position;
            }
        });
    }
    if (!String.prototype.endsWith) {
        Object.defineProperty(String.prototype, 'endsWith', {
            enumerable: false,
            configurable: false,
            writable: false,
            value: function(searchString, position) {
                position = position || this.length;
                position = position - searchString.length;
                var lastIndex = this.lastIndexOf(searchString);
                return lastIndex !== -1 && lastIndex === position;
            }
        });
    }
    if (!Array.prototype.some) {
        Array.prototype.some = function(fun /*, thisp */) {
            if (this === null) {
                throw new TypeError();
            }
            var thisp, i,
                t = Object(this),
                len = t.length >>> 0;
            if (typeof fun !== 'function') {
                throw new TypeError();
            }
            thisp = arguments[1];
            for (i = 0; i < len; i++) {
                if (i in t && fun.call(thisp, t[i], i, t)) {
                    return true;
                }
            }
            return false;
        };
    }

    // Ensure RichText doesn't use style with css
    try {
        document.execCommand('styleWithCSS', false, false);
    } catch (e) {
    }
    try {
        document.execCommand('useCSS', false, true);
    } catch (e) {
    }

    // Add .uniqueId to jQuery
    jQuery.fn.extend({
        uniqueId: (function() {
            var uuid = 0;
            return function() {
                return this.each(function() {
                    if (!this.id) {
                        this.id = "ui-id-" + (++uuid);
                    }
                });
            };
        })()
    });

    window.onbeforeunload = function(e) {
        if (Sao.main_menu_screen) {
            Sao.main_menu_screen.save_tree_state(true);
        }
        if (Sao.Tab.tabs.length) {
            var dialog = Sao.i18n.gettext("Are your sure to leave?");
            e.returnValue = dialog;
            return dialog;
        }
    };

    Sao.class_ = function(Parent, props) {
        var ClassConstructor = function() {
            if (!(this instanceof ClassConstructor))
                throw new Error('Constructor function requires new operator');
            this.Class = ClassConstructor;
            if (this.init) {
                this.init.apply(this, arguments);
            }
        };

        // Plug prototype chain
        ClassConstructor.prototype = Object.create(Parent.prototype);
        ClassConstructor._super = Parent.prototype;
        if (props) {
            for (var name in props) {
                ClassConstructor.prototype[name] = props[name];
            }
        }
        return ClassConstructor;
    };

    Sao.Decimal = Number;

    Sao.Date = function(year, month, day) {
        var date = moment();
        date.year(year);
        date.month(month);
        date.date(day);
        date.set({hour: 0, minute: 0, second: 0, millisecond: 0});
        date.isDate = true;
        return date;
    };

    Sao.Date.min = moment(new Date(-100000000 * 86400000));
    Sao.Date.min.set({hour: 0, minute: 0, second: 0, millisecond: 0});
    Sao.Date.min.isDate = true;
    Sao.Date.max = moment(new Date(100000000 * 86400000));
    Sao.Date.max.set({hour: 0, minute: 0, second: 0, millisecond: 0});
    Sao.Date.max.isDate = true;

    Sao.DateTime = function(year, month, day, hour, minute, second,
            millisecond, utc) {
        var datetime;
        if (month === undefined) {
            datetime = moment(year);
            year = undefined;
        }
        else {
            datetime = moment();
        }
        if (utc) {
            datetime.utc();
        }
        datetime.year(year);
        datetime.month(month);
        datetime.date(day);
        if (month !== undefined) {
            datetime.hour(hour || 0);
            datetime.minute(minute || 0);
            datetime.second(second || 0);
            datetime.milliseconds(millisecond || 0);
        }
        datetime.isDateTime = true;
        datetime.local();
        return datetime;
    };

    Sao.DateTime.combine = function(date, time) {
        var datetime = date.clone();
        datetime.set({hour: time.hour(), minute: time.minute(),
            second: time.second(), millisecond: time.millisecond()});
        datetime.isDateTime = true;
        return datetime;
    };

    Sao.DateTime.min = moment(new Date(-100000000 * 86400000)).local();
    Sao.DateTime.min.isDateTime = true;
    Sao.DateTime.max = moment(new Date(100000000 * 86400000)).local();
    Sao.DateTime.max.isDateTime = true;

    Sao.Time = function(hour, minute, second, millisecond) {
        var time = moment({hour: hour, minute: minute, second: second,
           millisecond: millisecond || 0});
        time.isTime = true;
        return time;
    };

    Sao.TimeDelta = function(days, seconds,
            milliseconds, minutes, hours, weeks) {
        var timedelta = moment.duration({
            days: days,
            seconds: seconds,
            milliseconds: milliseconds,
            minutes: minutes,
            hours: hours,
            weeks: weeks
        });
        timedelta.isTimeDelta = true;
        return timedelta;
    };

    Sao.config = {};
    Sao.config.limit = 1000;
    Sao.config.display_size = 20;
    Sao.config.roundup = {};
    Sao.config.roundup.url = 'http://bugs.tryton.org/roundup/';
    Sao.config.title = 'Tryton';

    Sao.i18n = i18n();
    Sao.i18n.setlang = function(lang) {
        if (!lang) {
            lang = (navigator.language ||
                 navigator.browserLanguage ||
                 navigator.userLanguage ||
                 'en').replace('-', '_');
        }
        Sao.i18n.setLocale(lang);
        moment.locale(lang.slice(0, 2));
        return jQuery.getJSON('locale/' + lang + '.json', function(data) {
            if (!data[''].language) {
                data[''].language = lang;
            }
            if (!data['']['plural-forms']) {
                data['']['plural-forms'] = 'nplurals=2; plural=(n!=1);';
            }
            // gettext.js requires to dump untranslated keys
            for (var key in data) {
                if ('' === key) {
                    continue;
                }
                data[key] = 2 == data[key].length ? data[key][1] : data[key].slice(1);
            }
            Sao.i18n.loadJSON(data);
        });
    };
    Sao.i18n.getlang = function() {
        return Sao.i18n.getLocale();
    };
    Sao.i18n.setlang();

    Sao.get_preferences = function() {
        var session = Sao.Session.current_session;
        return session.reload_context().then(function() {
            return Sao.rpc({
                'method': 'model.res.user.get_preferences',
                'params': [false, {}]
            }, session).then(function(preferences) {
                var deferreds = [];
                deferreds.push(Sao.common.MODELACCESS.load_models());
                deferreds.push(Sao.common.ICONFACTORY.load_icons());
                deferreds.push(Sao.common.MODELHISTORY.load_history());
                deferreds.push(Sao.common.VIEW_SEARCH.load_searches());
                return jQuery.when.apply(jQuery, deferreds).then(function() {
                    (preferences.actions || []).forEach(function(action_id) {
                        Sao.Action.execute(action_id, {}, null, {});
                    });
                    Sao.set_title(preferences.status_bar);
                    var new_lang = preferences.language != Sao.i18n.getLocale();
                    var prm = jQuery.Deferred();
                    Sao.i18n.setlang(preferences.language).always(function() {
                        if (new_lang) {
                            Sao.user_menu(preferences);
                        }
                        prm.resolve(preferences);
                    });
                    return prm;
                });
            });
        });
    };

    Sao.set_title = function(value) {
        var title = [Sao.config.title];
        var session = Sao.Session.current_session;
        var login_info = '';
        if (session) {
            if (session.login) {
                login_info = session.login + '@' + document.location.host;
            }
            if (session.database) {
                login_info += '/' + session.database;
            }
            title = title.concat(login_info);
        } else {
            title = title.concat(document.location.host);
        }
        if (value) {
            title = title.concat(value);
        }
        document.title = title.join(' - ');
    };

    Sao.login = function() {
        Sao.Session.get_credentials()
            .then(function(session) {
                Sao.Session.current_session = session;
                return session.reload_context();
            }).then(Sao.get_preferences).then(function(preferences) {
                Sao.menu(preferences);
                Sao.user_menu(preferences);
            });
    };

    Sao.logout = function() {
        var session = Sao.Session.current_session;
        Sao.Tab.tabs.close(true).done(function() {
            jQuery('#user-preferences').children().remove();
            jQuery('#user-logout').children().remove();
            jQuery('#user-favorites').children().remove();
            jQuery('#menu').children().remove();
            session.do_logout().always(Sao.login);
            Sao.set_title();
        });
    };

    Sao.preferences = function() {
        Sao.Tab.tabs.close(true).done(function() {
            jQuery('#user-preferences').children().remove();
            jQuery('#user-favorites').children().remove();
            jQuery('#user-logout').children().remove();
            jQuery('#menu').children().remove();
            new Sao.Window.Preferences(function() {
                Sao.get_preferences().then(function(preferences) {
                    Sao.menu(preferences);
                    Sao.user_menu(preferences);
                });
            });
        });
    };
    Sao.favorites_menu = function() {
        var clear_menu = function() {
            if (menu) {
                menu.remove();
            }
        };
        jQuery(window).click(function() {
            clear_menu();
        });
        if (jQuery('#user-favorites').children('.dropdown-menu')
                .length !== 0 ) {
            clear_menu();
        } else {
            var name = Sao.main_menu_screen.model_name + '.favorite';
            var session = Sao.Session.current_session;
            var args = {
                'method': 'model.' + name + '.get',
            };
            var menu = jQuery('<ul/>', {
                'class': 'dropdown-menu',
                'aria-expanded': 'false'
            });
            jQuery('#user-favorites').append(menu);
            Sao.rpc(args, session).then(function(fav) {
                fav.forEach(function(menu_item) {
                    var a = jQuery('<a/>', {
                        'href': '#'
                    });
                    var id = menu_item[0];
                    var li = jQuery('<li/>', {
                        'role': 'presentation'
                    });
                    var icon = jQuery('<img/>', {
                        'class': 'favorite-icon'
                    });
                    a.append(icon);
                    li.append(a);
                    icon.attr('src',
                         Sao.common.ICONFACTORY.get_icon_url(menu_item[2]));
                    a.append(menu_item[1]);
                    a.click(function() {
                        clear_menu();
                        // ids is not defined to prevent to add suffix
                        Sao.Action.exec_keyword('tree_open', {
                            'model': Sao.main_menu_screen.model_name,
                            'id': id,
                        });
                    });
                    menu.append(li);
                });
                menu.append(jQuery('<li/>', {
                        'class': 'divider'
                }));
                jQuery('<li/>', {
                    'role': 'presentation'
                }).append(jQuery('<a/>', {
                        'href': '#'
                    }).click(function() {
                        clear_menu();
                        Sao.Tab.create({
                            'model': Sao.main_menu_screen.model_name +
                            '.favorite',
                            'mode': ['tree', 'form'],
                            'name': Sao.i18n.gettext('Manage favorites')
                        });
                    }).text(Sao.i18n.gettext('Manage favorites'))).appendTo(
                       menu);
            });
        }
    };

    Sao.user_menu = function(preferences) {
        jQuery('#user-preferences').children().remove();
        jQuery('#user-favorites').children().remove();
        jQuery('#user-logout').children().remove();
        jQuery('#user-preferences').append(jQuery('<a/>', {
            'href': '#'
        }).click(Sao.preferences).append(preferences.status_bar));
        jQuery('#user-logout').append(jQuery('<a/>', {
            'href': '#'
        }).click(Sao.logout).append(Sao.i18n.gettext('Logout')));
        jQuery('#user-favorites').append(jQuery('<a/>', {
            'href': '#',
            'data-toggle': 'dropdown'
        }).click(Sao.favorites_menu).append(Sao.i18n.gettext('Favorites')));
    };

    Sao.main_menu_row_activate = function() {
        var screen = Sao.main_menu_screen;
        // ids is not defined to prevent to add suffix
        return Sao.Action.exec_keyword('tree_open', {
            'model': screen.model_name,
            'id': screen.get_id(),
        }, jQuery.extend({}, screen.context), false);
    };

    Sao.menu = function(preferences) {
        var decoder = new Sao.PYSON.Decoder();
        var action = decoder.decode(preferences.pyson_menu);
        var view_ids = false;
        if (!jQuery.isEmptyObject(action.views)) {
            view_ids = action.views.map(function(view) {
                return view[0];
            });
        } else if (action.view_id) {
            view_ids = [action.view_id[0]];
        }
        decoder = new Sao.PYSON.Decoder(Sao.Session.current_session.context);
        var action_ctx = decoder.decode(action.pyson_context || '{}');
        var domain = decoder.decode(action.pyson_domain);
        var form = new Sao.Tab.Form(action.res_model, {
            'mode': ['tree'],
            'view_ids': view_ids,
            'domain': domain,
            'context': action_ctx,
            'selection_mode': Sao.common.SELECTION_NONE,
            'limit': null,
            'row_activate': Sao.main_menu_row_activate,
        });
        Sao.Tab.tabs.splice(Sao.Tab.tabs.indexOf(form), 1);
        form.view_prm.done(function() {
            Sao.main_menu_screen = form.screen;
            var view = form.screen.current_view;
            view.table.removeClass('table table-bordered table-striped');
            view.table.find('thead').hide();
            jQuery('#menu').children().remove();

            var gs = new Sao.GlobalSearch();
            jQuery('#menu').append(gs.el);
            jQuery('#menu').append(
                form.screen.screen_container.content_box.detach());
            form.screen.views[0].columns.push(
                new FavoriteColumn(form.screen.model.fields.favorite));
        });
    };
    Sao.main_menu_screen = null;

    var FavoriteColumn = Sao.class_(Object, {
        init: function(favorite) {
            this.field = favorite;
            this.header = jQuery('<th/>');
            this.attributes = jQuery.extend({}, this.field.description);
            this.attributes.name = this.field.name;

        },
        get_cell: function() {
            var cell = jQuery('<span/>', {
                'tabindex': 0
            });
            return cell;
        },
        render: function(record, cell) {
            if (!cell) {
                cell = this.get_cell();
            }
            record.load(this.field.name).done(function() {
                if (record._values.favorite !== null) {
                    var star = 'glyphicon glyphicon-star';
                    if (!record._values.favorite) {
                        star += '-empty';
                    }
                    cell.addClass(star);
                    cell.click({'record': record, 'button': cell},
                        this.favorite_click);
                    }
                }.bind(this));
            return cell;
        },
        favorite_click: function(e) {
            // Prevent activate the action of the row
            e.stopImmediatePropagation();
            var button = e.data.button;
            var method;
            if (button.hasClass('glyphicon-star-empty')) {
                button.removeClass('glyphicon-star-empty');
                button.addClass('glyphicon-star');
                method = 'set';
            } else {
                button.removeClass('glyphicon-star');
                button.addClass('glyphicon-star-empty');
                method = 'unset';
            }
            var name = Sao.main_menu_screen.model_name + '.favorite';
            var session = Sao.Session.current_session;
            var args = {
                'method': 'model.' + name + '.' + method,
                'params': [e.data.record.id, session.context]
            };
            Sao.rpc(args, session);
        }
    });

    Sao.Dialog = Sao.class_(Object, {
        init: function(title, class_, size) {
            size = size || 'sm';
            this.modal = jQuery('<div/>', {
                'class': class_ + ' modal fade',
                'role': 'dialog',
                'data-backdrop': 'static',
            });
            this.content = jQuery('<form/>', {
                'class': 'modal-content'
            }).appendTo(jQuery('<div/>', {
                'class': 'modal-dialog modal-' + size
            }).appendTo(this.modal));
            this.header = jQuery('<div/>', {
                'class': 'modal-header'
            }).appendTo(this.content);
            if (title) {
                this.add_title(title);
            }
            this.body = jQuery('<div/>', {
                'class': 'modal-body'
            }).appendTo(this.content);
            this.footer = jQuery('<div/>', {
                'class': 'modal-footer'
            }).appendTo(this.content);

            this.modal.on('shown.bs.modal', function() {
                var currently_focused = jQuery(document.activeElement);
                var has_focus = currently_focused.closest(this.el) > 0;
                if (!has_focus) {
                    jQuery(this).find(':input:visible:not([readonly]):first')
                        .focus();
                }
            });
        },
        add_title: function(title) {
            this.header.append(jQuery('<h4/>', {
                'class': 'modal-title'
            }).append(title));
        }
    });

    Sao.GlobalSearch = Sao.class_(Object, {
        init: function() {
            this.el = jQuery('<div/>', {
                'class': 'global-search-container'
            });
            this.search_entry = jQuery('<input>', {
                'id': 'global-search-entry',
                'class': 'form-control mousetrap',
                'placeholder': Sao.i18n.gettext('Search...')
            });
            this.el.append(this.search_entry);
            var completion = new Sao.common.InputCompletion(
                    this.search_entry,
                    this.update.bind(this),
                    this.match_selected.bind(this),
                    this.format.bind(this));
        },
        format: function(content) {
            var el = jQuery('<div/>');
            var img = jQuery('<img/>', {
                'class': 'global-search-icon'
            }).appendTo(el);
            Sao.common.ICONFACTORY.register_icon(content.icon).then(
                    function(icon_url) {
                        img.attr('src', icon_url);
                    });
            jQuery('<span/>', {
                'class': 'global-search-text'
            }).text(content.record_name).appendTo(el);
            return el;
        },
        update: function(text) {
            var ir_model = new Sao.Model('ir.model');
            return ir_model.execute('global_search',
                    [text, Sao.config.limit, Sao.main_menu_screen.model_name],
                    Sao.main_menu_screen.context).then(function(s_results) {
                var results = [];
                for (var i=0, len=s_results.length; i < len; i++) {
                    results.push({
                        'model': s_results[i][1],
                        'model_name': s_results[i][2],
                        'record_id': s_results[i][3],
                        'record_name': s_results[i][4],
                        'icon': s_results[i][5],
                    });
                }
                return results;
            }.bind(this));
        },
        match_selected: function(item) {
            if (item.model == Sao.main_menu_screen.model_name) {
                // ids is not defined to prevent to add suffix
                Sao.Action.exec_keyword('tree_open', {
                    'model': item.model,
                    'id': item.record_id,
                }, Sao.main_menu_screen.context);
            } else {
                var params = {
                    'model': item.model,
                    'res_id': item.record_id,
                    'mode': ['form', 'tree'],
                    'name': item.model_name
                };
                Sao.Tab.create(params);
            }
            this.search_entry.val('');
        }
    });

    function shortcuts_defs() {
        // Shortcuts available on Tab on this format:
        // {shortcut, label, id of tab button or callback method}
        return [
            {
                shortcut: 'ctrl+a',
                label: Sao.i18n.gettext('New'),
                id: 'new_',
            }, {
                shortcut: 'ctrl+s',
                label: Sao.i18n.gettext('Save'),
                id: 'save',
            }, {
                shortcut: 'ctrl+l',
                label: Sao.i18n.gettext('Switch'),
                id: 'switch_',
            }, {
                shortcut: 'ctrl+r',
                label: Sao.i18n.gettext('Reload/Undo'),
                id: 'reload',
            }, {
                shortcut: 'ctrl+shift+d',
                label: Sao.i18n.gettext('Duplicate'),
                id: 'copy',
            }, {
                shortcut: 'ctrl+d',
                label: Sao.i18n.gettext('Delete'),
                id: 'delete_',
            }, {
                shortcut: 'ctrl+up',
                label: Sao.i18n.gettext('Previous'),
                id: 'previous',
            }, {
                shortcut: 'ctrl+down',
                label: Sao.i18n.gettext('Next'),
                id: 'next',
            }, {
                shortcut: 'ctrl+f',
                label: Sao.i18n.gettext('Search'),
                id: 'search',
            }, {
                shortcut: 'ctrl+x',
                label: Sao.i18n.gettext('Close Tab'),
                id: 'close',
            }, {
                shortcut: 'ctrl+shift+t',
                label: Sao.i18n.gettext('Attachment'),
                id: 'attach',
            }, {
                shortcut: 'ctrl+shift+o',
                label: Sao.i18n.gettext('Note'),
                id: 'note',
            }, {
                shortcut: 'ctrl+e',
                label: Sao.i18n.gettext('Action'),
                id: 'action',
            }, {
                shortcut: 'ctrl+shift+r',
                label: Sao.i18n.gettext('Relate'),
                id: 'relate',
            }, {
                shortcut: 'ctrl+p',
                label: Sao.i18n.gettext('Print'),
                id: 'print',
            }, {
                shortcut: 'ctrl+left',
                label: Sao.i18n.gettext('Previous tab'),
                callback: function() {
                    Sao.Tab.previous_tab();
                },
            }, {
                shortcut: 'ctrl+right',
                label: Sao.i18n.gettext('Next tab'),
                callback: function() {
                    Sao.Tab.next_tab();
                },
            }, {
                shortcut: 'ctrl+k',
                label: Sao.i18n.gettext('Global search'),
                callback: function() {
                    jQuery('#global-search-entry').focus();
                },
            }, {
                shortcut: 'ctrl+h',
                label: Sao.i18n.gettext('Show this help'),
                callback: function() {
                    shortcuts_dialog();
                },
            },
        ];
    }

    jQuery(document).ready(function() {
        set_shortcuts();
    });

    function set_shortcuts() {
        if (typeof Mousetrap != 'undefined') {
            shortcuts_defs().forEach(function(definition) {
                Mousetrap.bind(definition.shortcut, function() {
                    if (definition.id){
                        var current_tab = Sao.Tab.tabs.get_current();
                        if (current_tab) {
                            var focused = $(':focus');
                            focused.blur();
                            current_tab.el.find('a[id="' + definition.id + '"]').click();
                            focused.focus();
                        }
                    } else if (definition.callback) {
                        jQuery.when().then(definition.callback);
                    }
                    return false;
                });
            });
        }
    }

    function shortcuts_dialog() {
        var dialog = new Sao.Dialog(Sao.i18n.gettext('Keyboard shortcuts'),
            'shortcut-dialog', 'm');
        jQuery('<button>', {
            'class': 'close',
            'data-dismiss': 'modal',
            'aria-label': Sao.i18n.gettext("Close"),
        }).append(jQuery('<span>', {
            'aria-hidden': true,
        }).append('&times;')).prependTo(dialog.header);
        var row = jQuery('<div/>', {
            'class': 'row'
        }).appendTo(dialog.body);
        var global_shortcuts_dl = jQuery('<dl/>', {
            'class': 'dl-horizontal col-md-6'
        }).append(jQuery('<h5/>')
                  .append(Sao.i18n.gettext('Global shortcuts')))
            .appendTo(row);
        var tab_shortcuts_dl = jQuery('<dl/>', {
            'class': 'dl-horizontal col-md-6'
        }).append(jQuery('<h5/>')
            .append(Sao.i18n.gettext('Tab shortcuts')))
        .appendTo(row);

        shortcuts_defs().forEach(function(definition) {
            var dt = jQuery('<dt/>').append(definition.label);
            var dd = jQuery('<dd/>').append(jQuery('<kbd>')
                .append(definition.shortcut));
            var dest_dl;
            if (definition.id) {
                dest_dl = tab_shortcuts_dl;
            } else {
                dest_dl = global_shortcuts_dl;
            }
            dt.appendTo(dest_dl);
            dd.appendTo(dest_dl);
        });
        dialog.modal.on('hidden.bs.modal', function() {
            jQuery(this).remove();
        });

        dialog.modal.modal('show');
        return false;
    }

    // Fix stacked modal
    jQuery(document)
        .on('show.bs.modal', '.modal', function(event) {
            jQuery(this).appendTo(jQuery('body'));
        })
    .on('shown.bs.modal', '.modal.in', function(event) {
        setModalsAndBackdropsOrder();
    })
    .on('hidden.bs.modal', '.modal', function(event) {
        setModalsAndBackdropsOrder();
    });

    function setModalsAndBackdropsOrder() {
        var modalZIndex = 1040;
        jQuery('.modal.in').each(function(index) {
            var $modal = jQuery(this);
            modalZIndex++;
            $modal.css('zIndex', modalZIndex);
            $modal.next('.modal-backdrop.in').addClass('hidden')
            .css('zIndex', modalZIndex - 1);
        });
        jQuery('.modal.in:visible:last').focus()
        .next('.modal-backdrop.in').removeClass('hidden');
    }
}());
