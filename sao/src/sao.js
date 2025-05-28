/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */

/* eslint-disable no-redeclare */
var Sao = {};
/* eslint-enable no-redeclare */

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
    if (!String.prototype.padEnd) {
        String.prototype.padEnd = function padEnd(targetLength, padString) {
            targetLength = targetLength >> 0;
            padString = String(
                typeof padString !== 'undefined' ? padString : ' ');
            if (this.length > targetLength) {
                return String(this);
            } else {
                targetLength = targetLength - this.length;
                if (targetLength > padString.length) {
                    padString += padString.repeat(
                        targetLength / padString.length);
                }
                return String(this) + padString.slice(0, targetLength);
            }
        };
    }
    if (!String.prototype.padStart) {
        String.prototype.padStart = function padStart(targetLength, padString) {
            targetLength = targetLength >> 0;
            padString = String(
                typeof padString !== 'undefined' ? padString : ' ');
            if (this.length > targetLength) {
                return String(this);
            } else {
                targetLength = targetLength - this.length;
                if (targetLength > padString.length) {
                    padString += padString.repeat(
                        targetLength / padString.length);
                }
                return padString.slice(0, targetLength) + String(this);
            }
        };
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

    if (!Array.from) {
        Array.from = function (value) {
            // Implementation is not strictly equivalent but works for most
            // cases
            var result = [];
            value.forEach(function(e) {
                result.push(e);
            });
            return result;
        };
    }

    Sao.setdefault = function(object, key, value) {
        if (!object.hasOwnProperty(key)) {
            object[key] = value;
        }
        return object[key];
    };

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
                Object.defineProperty(ClassConstructor.prototype, name,
                    Object.getOwnPropertyDescriptor(props, name));
            }
        }

        // Method to create new instance with a list of arguments
        function F(args) {
            return ClassConstructor.apply(this, args);
        }
        F.prototype = ClassConstructor.prototype;
        ClassConstructor.new_ = function(args) {
            return new F(args);
        };
        return ClassConstructor;
    };

    Sao.Decimal = Number;

    var _moment_to_string = moment.prototype.toString;
    moment.prototype.toString = function() {
        if (this.isDate) {
            return this.format('YYYY-MM-DD');
        } else if (this.isDateTime) {
            if (this.milliseconds()) {
                return this.format('YYYY-MM-DD HH:mm:ss.SSSSSS');
            } else {
                return this.format('YYYY-MM-DD HH:mm:ss');
            }
        } else if (this.isTime) {
            if (this.milliseconds()) {
                return this.format('HH:mm:ss.SSSSSS');
            } else {
                return this.format('HH:mm:ss');
            }
        } else {
            return _moment_to_string.call(this);
        }
    };

    Sao.Date = function(year, month, day) {
        var date;
        if (month === undefined) {
            date = moment(year);
            year = undefined;
        }
        else {
            date = moment();
        }
        date.year(year);
        date.month(month);
        date.date(day);
        date.set({hour: 0, minute: 0, second: 0, millisecond: 0});
        date.isDate = true;
        return date;
    };

    // Add 1 day to the limit because setting time make it out of the range
    Sao.Date.min = moment(new Date((-100000000 + 1) * 86400000));
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
            if (hour === undefined) {
                hour = 0;
            }
            if (minute === undefined) {
                minute = 0;
            }
            if (second === undefined) {
                second = 0;
            }
            if (millisecond === undefined) {
                millisecond = 0;
            }
            datetime = moment();
        }
        if (utc) {
            datetime.utc();
        }
        datetime.year(year);
        datetime.month(month);
        datetime.date(day);
        if (month !== undefined) {
            datetime.hour(hour);
            datetime.minute(minute);
            datetime.second(second);
            datetime.milliseconds(millisecond);
        }
        datetime.isDateTime = true;
        datetime.local();
        datetime.todate = function() {
            return Sao.Date(this.year(), this.month(), this.date());
        };
        datetime.totime = function() {
            return Sao.Time(
                this.hour(), this.minute(), this.second(), this.millisecond());
        };
        return datetime;
    };

    Sao.DateTime.combine = function(date, time) {
        return Sao.DateTime(
            date.year(), date.month(), date.date(),
            time.hour(), time.minute(), time.second(), time.millisecond());
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
    Sao.config.bug_url = 'https://bugs.tryton.org/';
    Sao.config.title = 'Tryton';
    Sao.config.icon_colors = '#267f82,#3e4950,#e78e42'.split(',');
    Sao.config.calendar_colors = '#fff,#267f82'.split(',');
    Sao.config.graph_color = '#267f82';
    Sao.config.bus_timeout = 10 * 60 * 1000;

    Sao.i18n = i18n();
    Sao.i18n.setlang = function(lang) {
        if (!lang) {
            lang = (navigator.language ||
                 navigator.browserLanguage ||
                 navigator.userLanguage ||
                 'en').replace('-', '_');
        }
        jQuery('html').attr('lang', lang);
        Sao.i18n.setLocale(lang);
        moment.locale(lang.slice(0, 2));
        return jQuery.getJSON('locale/' + lang + '.json').then(function(data) {
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
        }, function() {
            if (~lang.indexOf('_')) {
                return Sao.i18n.setlang(lang.split('_').slice(0, -1).join('_'));
            }
        });
    };
    Sao.i18n.getlang = function() {
        return Sao.i18n.getLocale();
    };
    Sao.i18n.BC47 = function(lang) {
        return lang.replace('_', '-');
    };
    Sao.i18n.set_direction = function(direction) {
        Sao.i18n.rtl = (direction === 'rtl');
        jQuery('html').attr('dir', direction);
        jQuery('.row-offcanvas')
            .removeClass('row-offcanvas-left row-offcanvas-right')
            .addClass(Sao.i18n.rtl ? 'row-offcanvas-right' : 'row-offcanvas-left');
    };
    Sao.i18n.locale = {};

    Sao.BOM_UTF8 = '\uFEFF';

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
                    Sao.set_title();
                    var new_lang = preferences.language != Sao.i18n.getLocale();
                    var prm = jQuery.Deferred();
                    Sao.i18n.setlang(preferences.language).always(function() {
                        if (new_lang) {
                            Sao.user_menu(preferences);
                        }
                        prm.resolve(preferences);
                    });
                    Sao.i18n.set_direction(preferences.language_direction);
                    Sao.i18n.locale = preferences.locale;
                    Sao.common.MODELNAME.clear();
                    return prm;
                });
            });
        });
    };

    Sao.set_title = function(name) {
        var title = [name, Sao.config.title];
        document.title = title.filter(function(e) {return e;}).join(' - ');
        jQuery('#title').text(Sao.config.title);
    };

    Sao.set_url = function(path, name) {
        var session = Sao.Session.current_session;
        if (session) {
            var url = '#' + session.database;
            if (path) {
                url += '/' + path;
            }
            window.location = url;
        }
        Sao.set_title(name);
    };

    window.onhashchange = function() {
        var session = Sao.Session.current_session;
        if (!session) {
            return;
        }
        var url,
            database = '#' + session.database;
        if (window.location.hash == database) {
            url = '';
        } else if (window.location.hash.startsWith(database + '/')) {
            url = window.location.hash.substr(database.length + 1);
        } else {
            return;
        }
        var tab;
        if (!url) {
            tab = Sao.Tab.tabs.get_current();
            if (tab) {
                Sao.set_url(tab.get_url(), tab.name);
            }
        } else {
            url = decodeURIComponent(url);
            for (var i = 0; i < Sao.Tab.tabs.length; i++) {
                tab = Sao.Tab.tabs[i];
                if (decodeURIComponent(tab.get_url()) == url) {
                    tab.show();
                    return;
                }
            }
            Sao.open_url();
        }
    };

    Sao.open_url = function(url) {
        function loads(value) {
            return Sao.rpc.convertJSONObject(jQuery.parseJSON(value));
        }
        if (url === undefined) {
            url = window.location.hash.substr(1);
        }
        var i = url.indexOf(';');
        var path, params = {};
        if (i >= 0) {
            path = url.substring(0, i);
            url.substring(i + 1).split('&').forEach(function(part) {
                if (part) {
                    var item = part.split('=').map(decodeURIComponent);
                    params[item[0]] = item[1];
                }
            });
        } else {
            path = url;
        }
        path = path.split('/').slice(1);
        var type = path.shift();

        function open_model(path) {
            var attributes = {};
            attributes.model = path.shift();
            if (!attributes.model) {
                return;
            }
            try {
                attributes.view_ids = loads(params.views || '[]');
                if (params.limit !== undefined) {
                    attributes.limit = loads(params.limit || 'null');
                }
                attributes.name = loads(params.name || '""');
                attributes.search_value = loads(params.search_value || '[]');
                attributes.domain = loads(params.domain || '[]');
                attributes.context = loads(params.context || '{}');
                attributes.context_model = params.context_model;
                attributes.tab_domain = loads(params.tab_domain || '[]');
            } catch (e) {
                return;
            }
            var res_id = path.shift();
            if (res_id) {
                res_id = Number(res_id);
                if (isNaN(res_id)) {
                    return;
                }
                attributes.res_id = res_id;
                attributes.mode = ['form', 'tree'];
            }
            try {
                Sao.Tab.create(attributes);
            } catch (e) {
                // Prevent crashing the client
                return;
            }
        }
        function open_wizard(path) {
            var attributes = {};
            attributes.action = path[0];
            if (!attributes.action) {
                return;
            }
            try {
                attributes.data = loads(params.data || '{}');
                attributes.direct_print = loads(params.direct_print || 'false');
                attributes.name = loads(params.name || '""');
                attributes.window = loads(params.window || 'false');
                attributes.context = loads(params.context || '{}');
            } catch (e) {
                return;
            }
            try {
                Sao.Wizard.create(attributes);
            } catch (e) {
                // Prevent crashing the client
                return;
            }
        }
        function open_report(path) {
            var attributes = {};
            attributes.name = path[0];
            if (!attributes.name) {
                return;
            }
            try {
                attributes.data = loads(params.data || '{}');
                attributes.direct_print = loads(params.direct_print || 'false');
                attributes.context = loads(params.context || '{}');
            } catch (e) {
                return;
            }
            try {
                Sao.Action.exec_report(attributes);
            } catch (e) {
                // Prevent crashing the client
                return;
            }
        }
        function open_url() {
            var url;
            try {
                url = loads(params.url || 'false');
            } catch (e) {
                return;
            }
            if (url) {
                window.open(url, '_blank', 'noreferrer,noopener');
            }
        }

        switch (type) {
            case 'model':
                open_model(path);
                break;
            case 'wizard':
                open_wizard(path);
                break;
            case 'report':
                open_report(path);
                break;
            case 'url':
                open_url();
                break;
        }
    };

    Sao.login = function() {
        Sao.set_title();
        Sao.i18n.setlang().always(function() {
            Sao.Session.get_credentials()
                .then(function(session) {
                    Sao.Session.current_session = session;
                    return session.reload_context();
                }).then(Sao.get_preferences).then(function(preferences) {
                    Sao.menu(preferences);
                    Sao.user_menu(preferences);
                    Sao.open_url();
                    Sao.Bus.listen();
                });
        });
    };

    Sao.logout = function() {
        var session = Sao.Session.current_session;
        Sao.Tab.tabs.close(true).done(function() {
            jQuery('#user-preferences').empty();
            jQuery('#user-favorites').empty();
            jQuery('#global-search').empty();
            jQuery('#menu').empty();
            session.do_logout().always(Sao.login);
            Sao.set_title();
        });
    };

    Sao.preferences = function() {
        Sao.Tab.tabs.close(true).done(function() {
            jQuery('#user-preferences').empty();
            jQuery('#user-favorites').empty();
            jQuery('#menu').empty();
            new Sao.Window.Preferences(function() {
                Sao.Session.current_session.reset_context();
                Sao.get_preferences().then(function(preferences) {
                    Sao.menu(preferences);
                    Sao.user_menu(preferences);
                });
            });
        });
    };
    Sao.favorites_menu = function() {
        jQuery(window).click(function() {
            Sao.favorites_menu_clear();
        });
        if (!jQuery('#user-favorites').children('.dropdown-menu').length) {
            var name = Sao.main_menu_screen.model_name + '.favorite';
            var session = Sao.Session.current_session;
            var args = {
                'method': 'model.' + name + '.get',
            };
            var menu = jQuery('<ul/>', {
                'class': 'dropdown-menu',
                'aria-expanded': 'false',
                'aria-labelledby': 'user-favorites',
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
                    var icon = Sao.common.ICONFACTORY.get_icon_img(
                        menu_item[2], {'class': 'favorite-icon'});
                    a.append(icon);
                    li.append(a);
                    a.append(menu_item[1]);
                    a.click(function(evt) {
                        evt.preventDefault();
                        Sao.favorites_menu_clear();
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
                    }).click(function(evt) {
                        evt.preventDefault();
                        Sao.favorites_menu_clear();
                        Sao.Tab.create({
                            'model': Sao.main_menu_screen.model_name +
                            '.favorite',
                            'mode': ['tree', 'form'],
                            'name': Sao.i18n.gettext('Favorites')
                        });
                    }).text(Sao.i18n.gettext('Manage...'))).appendTo(
                       menu);
            });
        }
    };
    Sao.favorites_menu_clear = function() {
        jQuery('#user-favorites').children('.dropdown-menu').remove();
    };

    Sao.user_menu = function(preferences) {
        jQuery('#user-preferences').empty();
        jQuery('#user-favorites').empty();
        var user = jQuery('<a/>', {
            'href': '#',
            'title': preferences.status_bar,
        }).click(function(evt) {
            evt.preventDefault();
            Sao.preferences();
        }).text(preferences.status_bar);
        jQuery('#user-preferences').append(user);
        if (preferences.avatar_badge_url) {
            user.prepend(jQuery('<img/>', {
                'src': preferences.avatar_badge_url + '?s=15',
                'class': 'img-circle img-badge',
            }));
        }
        if (preferences.avatar_url) {
            user.prepend(jQuery('<img/>', {
                'src': preferences.avatar_url + '?s=30',
                'class': 'img-circle',
            }));
        }
        var title = Sao.i18n.gettext("Logout");
        jQuery('#user-logout > a')
            .attr('title', title)
            .attr('aria-label', title)
            .off()
            .click(Sao.logout)
            .find('span:not(.icon)').text(title);
    };

    Sao.main_menu_row_activate = function() {
        var screen = Sao.main_menu_screen;
        var id = screen.get_id();
        if (id) {
            // ids is not defined to prevent to add suffix
            Sao.Action.exec_keyword('tree_open', {
                'model': screen.model_name,
                'id': screen.get_id(),
            }, null, false);
        }
    };

    Sao.menu = function(preferences) {
        if (!preferences) {
            var session = Sao.Session.current_session;
            Sao.rpc({
                'method': 'model.res.user.get_preferences',
                'params': [false, {}],
            }, session).then(Sao.menu);
            return;
        }
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
        Sao.main_menu_screen = form.screen;
        Sao.main_menu_screen.switch_callback = null;
        Sao.Tab.tabs.splice(Sao.Tab.tabs.indexOf(form), 1);
        form.view_prm.done(function() {
            var view = form.screen.current_view;
            view.table.removeClass('table table-bordered table-striped');
            view.table.addClass('no-responsive');
            view.table.find('thead').hide();
            var gs = new Sao.GlobalSearch();
            jQuery('#global-search').empty();
            jQuery('#global-search').append(gs.el);
            jQuery('#menu').empty();
            jQuery('#menu').append(
                form.screen.screen_container.content_box.detach());
            var column = new FavoriteColumn(form.screen.model.fields.favorite);
            form.screen.views[0].table.find('> colgroup').append(column.col);
            form.screen.views[0].table.find('> thead > tr').append(column.header);
            form.screen.views[0].columns.push(column);
        });
    };
    Sao.main_menu_screen = null;

    var FavoriteColumn = Sao.class_(Object, {
        init: function(favorite) {
            this.field = favorite;
            this.col = jQuery('<col/>', {
                'class': 'favorite',
            });
            this.header = jQuery('<th/>');
            this.footers = [];
            this.attributes = jQuery.extend({}, this.field.description);
            this.attributes.name = this.field.name;

        },
        get_cell: function() {
            var cell = jQuery('<img/>', {
                'class': 'column-affix',
                'tabindex': 0,
            });
            return cell;
        },
        render: function(record, cell) {
            if (!cell) {
                cell = this.get_cell();
            }
            record.load(this.field.name).done(function() {
                if (record._values.favorite !== null) {
                    var icon = 'tryton-star';
                    if (!record._values.favorite) {
                        icon += '-border';
                    }
                    cell.data('star', Boolean(record._values.favorite));
                    Sao.common.ICONFACTORY.get_icon_url(icon)
                        .then(function(url) {
                            cell.attr('src', url);
                        });
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
            var method, icon;
            var star = button.data('star');
            if (!star) {
                icon = 'tryton-star';
                method = 'set';
            } else {
                icon = 'tryton-star-border';
                method = 'unset';
            }
            button.data('star', !star);
            Sao.common.ICONFACTORY.get_icon_url(icon)
                .then(function(url) {
                    button.attr('src', url);
                });
            var name = Sao.main_menu_screen.model_name + '.favorite';
            var session = Sao.Session.current_session;
            var args = {
                'method': 'model.' + name + '.' + method,
                'params': [e.data.record.id, session.context]
            };
            Sao.rpc(args, session);
            Sao.favorites_menu_clear();
        }
    });

    Sao.Dialog = Sao.class_(Object, {
        init: function(title, class_, size, keyboard) {
            size = size || 'sm';
            if (keyboard === undefined) {
                keyboard = true;
            }
            this.modal = jQuery('<div/>', {
                'class': class_ + ' modal fade',
                'role': 'dialog',
                'data-backdrop': 'static',
                'data-keyboard': keyboard,
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
                    jQuery(this).find(':input:visible' +
                        ':not([readonly]):not([tabindex^="-"]):first')
                        .focus();
                }
            });
        },
        add_title: function(title) {
            this.header.append(jQuery('<h4/>', {
                'class': 'modal-title',
                'title': title,
            }).text(Sao.common.ellipsize(title, 120)));
        }
    });

    Sao.GlobalSearch = Sao.class_(Object, {
        init: function() {
            this.el = jQuery('<div/>', {
                'class': 'global-search-container',
            });
            var group = jQuery('<div/>', {
                'class': 'input-group input-group-sm',
            }).appendTo(this.el);

            jQuery('<div/>', {
                'id': 'user-favorites',
                'class': 'input-group-btn',
            }).append(jQuery('<button/>', {
                'class': 'btn btn-default dropdown-toggle',
                'data-toggle': 'dropdown',
                'aria-haspopup': true,
                'aria-expanded': false,
                'title': Sao.i18n.gettext("Favorites"),
                'aria-label': Sao.i18n.gettext("Favorites"),
            }).click(Sao.favorites_menu).append(
                Sao.common.ICONFACTORY.get_icon_img('tryton-bookmarks')))
                .appendTo(group);

            this.search_entry = jQuery('<input>', {
                'id': 'global-search-entry',
                'class': 'form-control mousetrap',
                'placeholder': Sao.i18n.gettext('Action')
            }).appendTo(group);

            var completion = new Sao.common.InputCompletion(
                    this.el,
                    this.update.bind(this),
                    this.match_selected.bind(this),
                    this.format.bind(this));
            completion.input.keydown(function(evt) {
                if (evt.which == Sao.common.RETURN_KEYCODE) {
                    if (!completion.dropdown.hasClass('open')) {
                        evt.preventDefault();
                        completion.menu.dropdown('toggle');
                    }
                }
            });
        },
        format: function(content) {
            var el = jQuery('<div/>');
            Sao.common.ICONFACTORY.get_icon_img(
                content.icon, {'class': 'global_search-icon'})
                .appendTo(el);
            jQuery('<span/>', {
                'class': 'global-search-text'
            }).text(content.record_name).appendTo(el);
            return el;
        },
        update: function(text) {
            var ir_model = new Sao.Model('ir.model');
            if (!text) {
                return jQuery.when([]);
            }
            return ir_model.execute('global_search',
                    [text, Sao.config.limit, Sao.main_menu_screen.model_name],
                    Sao.main_menu_screen.context)
                .then(function(s_results) {
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
                });
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
                shortcut: 'alt+n',
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
                shortcut: 'alt+w',
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
                shortcut: 'ctrl+shift+e',
                label: Sao.i18n.gettext('E-Mail'),
                id: 'email',
            }, {
                shortcut: 'alt+shift+tab',
                label: Sao.i18n.gettext('Previous tab'),
                callback: function() {
                    if (!jQuery('body').children('.modal').length) {
                        Sao.Tab.previous_tab();
                    }
                },
            }, {
                shortcut: 'alt+tab',
                label: Sao.i18n.gettext('Next tab'),
                callback: function() {
                    if (!jQuery('body').children('.modal').length) {
                        Sao.Tab.next_tab();
                    }
                },
            }, {
                shortcut: 'ctrl+k',
                label: Sao.i18n.gettext('Global search'),
                callback: function() {
                    if (!jQuery('body').children('.modal').length) {
                        jQuery('#main_navbar:hidden').collapse('show');
                        jQuery('#global-search-entry').focus();
                    }
                },
            }, {
                shortcut: 'f1',
                label: Sao.i18n.gettext('Show this help'),
                callback: function() {
                    shortcuts_dialog();
                },
            },
        ];
    }

    jQuery(document).ready(function() {
        set_shortcuts();
        try {
            Notification.requestPermission();
        } catch (e) {
            (console.error || console.log).call(console, e, e.stack);
        }
        Sao.login();
    });

    function set_shortcuts() {
        if (typeof Mousetrap != 'undefined') {
            shortcuts_defs().forEach(function(definition) {
                Mousetrap.bind(definition.shortcut, function() {
                    if (definition.id){
                        var current_tab = Sao.Tab.tabs.get_current();
                        if (current_tab) {
                            var focused = jQuery(':focus');
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
            .text(Sao.i18n.gettext('Global shortcuts')))
            .appendTo(row);
        var tab_shortcuts_dl = jQuery('<dl/>', {
            'class': 'dl-horizontal col-md-6'
        }).append(jQuery('<h5/>')
            .text(Sao.i18n.gettext('Tab shortcuts')))
            .appendTo(row);

        shortcuts_defs().forEach(function(definition) {
            var dt = jQuery('<dt/>').text(definition.label);
            var dd = jQuery('<dd/>').append(jQuery('<kbd>')
                .text(definition.shortcut));
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

    Sao.Plugins = [];

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
        if (jQuery('.modal:visible').length) {
            jQuery(document.body).addClass('modal-open');
        }
    });

    // Fix Chrome bug: https://bugs.chromium.org/p/chromium/issues/detail?id=890248
    jQuery(document).on('keydown', 'textarea', function(event) {
        if (event.key === 'PageUp' || event.key === 'PageDown') {
            var cursorPosition = (
                event.key === 'PageUp' ? 0 : event.target.textLength);
            event.preventDefault();
            event.target.setSelectionRange(cursorPosition, cursorPosition);
        }
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
