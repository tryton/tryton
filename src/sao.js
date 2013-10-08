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

    Sao.error = function(title, message) {
        alert(title + '\n' + (message || ''));
    };

    Sao.warning = function(title, message) {
        alert(title + '\n' + (message || ''));
    };

    Sao.class_ = function(Parent, props) {
        var ClassConstructor = function() {
            if (!(this instanceof ClassConstructor))
                throw new Error('Constructor function requires new operator');
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
        var date;
        if (year === undefined) {
            date = new Date();
        } else if (month === undefined) {
            date = new Date(year);
        } else {
            date = new Date(year, month, day);
        }
        date.isDate = true;
        date.setHours(0);
        date.setMinutes(0);
        date.setSeconds(0);
        date.setMilliseconds(0);
        return date;
    };

    Sao.DateTime = function(year, month, day, hour, minute, second) {
        var datetime;
        if (year === undefined) {
            datetime = new Date();
        } else if (month === undefined) {
            datetime = new Date(year);
        } else {
            datetime = new Date(year, month, day,
                    hour || 0, minute || 0, second || 0);
        }
        datetime.isDateTime = true;
        datetime.setMilliseconds(0);
        return datetime;
    };

    Sao.Time = Sao.class_(Object, {
        init: function(hour, minute, second) {
            this.date = new Date(0, 0, 0, hour, minute, second);
        },
        getHours: function() {
            return this.date.getHours();
        },
        setHours: function(hour) {
            this.date.setHours(hour);
        },
        getMinutes: function() {
            return this.date.getMinutes();
        },
        setMinutes: function(minute) {
            this.date.setMinutes(minute);
        },
        getSeconds: function() {
            return this.date.getSeconds();
        },
        setSeconds: function(second) {
            this.date.setSeconds(second);
        },
        valueOf: function() {
            return this.date.valueOf();
        }
    });

    Sao.config = {};
    Sao.config.limit = 1000;
    Sao.config.display_size = 20;

    Sao.login = function() {
        var dfd = jQuery.Deferred();
        Sao.Session.get_credentials(dfd);
        dfd.then(function(session) {
            Sao.Session.current_session = session;
            session.reload_context();
            return session;
        }).then(function(session) {
            Sao.rpc({
                'method': 'model.res.user.get_preferences',
                'params': [false, {}]
            }, session).then(function(preferences) {
                var deferreds = [];
                // TODO view_search
                deferreds.push(Sao.common.MODELACCESS.load_models());
                deferreds.push(Sao.common.ICONFACTORY.load_icons());
                jQuery.when.apply(jQuery, deferreds).then(function() {
                    Sao.menu(preferences);
                    Sao.user_menu(preferences);
                });
            });
        });
    };

    Sao.logout = function() {
        var session = Sao.Session.current_session;
        // TODO check modified
        jQuery('#tabs').children().remove();
        jQuery('#user-preferences').children().remove();
        jQuery('#user-logout').children().remove();
        jQuery('#menu').children().remove();
        session.do_logout();
        Sao.login();
    };

    Sao.preferences = function() {
        // TODO check modified
        jQuery('#tabs').children().remove();
        jQuery('#user-preferences').children().remove();
        jQuery('#user-logout').children().remove();
        jQuery('#menu').children().remove();
        new Sao.Window.Preferences(function() {
            var session = Sao.Session.current_session;
            session.reload_context().done(
                Sao.rpc({
                    'method': 'model.res.user.get_preferences',
                    'params': [false, {}]
                }, session).then(function(preferences) {
                    Sao.menu(preferences);
                    Sao.user_menu(preferences);
                }));
        });
    };

    Sao.user_menu = function(preferences) {
        jQuery('#user-preferences').append(jQuery('<a/>', {
            'href': '#'
        }).click(Sao.preferences).append(preferences.status_bar));
        jQuery('#user-logout').append(jQuery('<a/>', {
            'href': '#'
        }).click(Sao.logout).append('Logout'));
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
        var domain = decoder.decode(action.pyson_domain);
        var form = new Sao.Tab.Form(action.res_model, {
            'mode': ['tree'],
            'view_ids': view_ids,
            'domain': domain
        });
        form.view_prm.done(function() {
            var view = form.screen.current_view;
            view.table.find('th').hide();
            var display = view.display;
            var select_row = function(event_) {
                this.tree.select_changed(this.record);
                this.tree.switch_(this.path);
            };
            var set_select_row = function(row) {
                row.select_row = select_row;
                row.rows.forEach(set_select_row);
            };
            view.display = function() {
                display.call(this);
                view.table.children('tbody').children('tr'
                    ).children('td:nth-child(1)').hide();
                // TODO remove when shortcuts is implemented
                view.table.children('tbody').children('tr'
                    ).children('td:nth-child(3)').hide();
                view.rows.forEach(set_select_row);
            };
            jQuery('#menu').append(
                form.screen.screen_container.content_box.detach());
        });
    };
}());
