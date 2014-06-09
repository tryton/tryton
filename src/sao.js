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
        var previous_day = date.getDate();
        var previous_hour = date.getHours();
        date.setHours(0);
        // Setting hours could change the day due to local timezone
        if (previous_day != date.getDate()) {
            date.setDate(previous_day);
            date.setHours(previous_hour);
        }
        date.setMinutes(0);
        date.setSeconds(0);
        date.setMilliseconds(0);
        return date;
    };

    Sao.DateTime = function(year, month, day, hour, minute, second,
            millisecond) {
        var datetime;
        if (year === undefined) {
            datetime = new Date();
            datetime.setMilliseconds(0);
        } else if (month === undefined) {
            datetime = new Date(year);
        } else {
            datetime = new Date(year, month, day,
                    hour || 0, minute || 0, second || 0, millisecond || 0);
        }
        datetime.isDateTime = true;
        return datetime;
    };

    Sao.Time = Sao.class_(Object, {
        init: function(hour, minute, second, millisecond) {
            this.date = new Date(0, 0, 0, hour, minute, second,
                millisecond || 0);
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
        getMilliseconds: function() {
            return this.date.getMilliseconds();
        },
        setMilliseconds: function(millisecond) {
            this.date.setMilliseconds(millisecond);
        },
        valueOf: function() {
            return this.date.valueOf();
        }
    });

    Sao.config = {};
    Sao.config.limit = 1000;
    Sao.config.display_size = 20;
    Sao.config.roundup = {};
    Sao.config.roundup.url = 'http://bugs.tryton.org/roundup/';

    Sao.get_preferences = function() {
        var session = Sao.Session.current_session;
        return Sao.rpc({
            'method': 'model.res.user.get_preferences',
            'params': [false, {}]
        }, session).then(function(preferences) {
            var deferreds = [];
            // TODO view_search
            deferreds.push(Sao.common.MODELACCESS.load_models());
            deferreds.push(Sao.common.ICONFACTORY.load_icons());
            deferreds.push(Sao.common.MODELHISTORY.load_history());
            return jQuery.when.apply(jQuery, deferreds).then(function() {
                (preferences.actions || []).forEach(function(action_id) {
                    Sao.Action.execute(action_id, {}, null, {});
                });
                var title = 'Tryton';
                if (!jQuery.isEmptyObject(preferences.status_bar)) {
                    title += ' - ' + preferences.status_bar;
                }
                document.title = title;
                // TODO language
                return jQuery.when(preferences);
            });
        });
    };

    Sao.login = function() {
        var dfd = jQuery.Deferred();
        Sao.Session.get_credentials(dfd);
        dfd.then(function(session) {
            Sao.Session.current_session = session;
            session.reload_context();
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
            jQuery('#menu').children().remove();
            document.title = 'Tryton';
            session.do_logout();
            Sao.login();
        });
    };

    Sao.preferences = function() {
        Sao.Tab.tabs.close(true).done(function() {
            jQuery('#user-preferences').children().remove();
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

    Sao.user_menu = function(preferences) {
        jQuery('#user-preferences').children().remove();
        jQuery('#user-logout').children().remove();
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
        var action_ctx = decoder.decode(action.pyson_context || '{}');
        var domain = decoder.decode(action.pyson_domain);
        var form = new Sao.Tab.Form(action.res_model, {
            'mode': ['tree'],
            'view_ids': view_ids,
            'domain': domain,
            'context': action_ctx,
            'selection_mode': Sao.common.SELECTION_NONE
        });
        Sao.Tab.tabs.splice(Sao.Tab.tabs.indexOf(form), 1);
        form.view_prm.done(function() {
            Sao.main_menu_screen = form.screen;
            var view = form.screen.current_view;
            view.table.find('th').hide();
            jQuery('#menu').children().remove();
            jQuery('#menu').append(
                form.screen.screen_container.content_box.detach());
        });
    };
    Sao.main_menu_screen = null;

}());
