/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
var Sao = {};

(function() {
    'use strict';

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
        } else if (date === undefined) {
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
            datetime = new Date(year, month, day, hour, minute, second);
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
        jQuery('#user-menu').children().remove();
        jQuery('#menu').children().remove();
        session.do_logout();
        Sao.login();
    };

    Sao.preferences = function() {
        // TODO check modified
        jQuery('#tabs').children().remove();
        jQuery('#user-menu').children().remove();
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
        var user_menu = jQuery('#user-menu');
        user_menu.append(jQuery('<ul/>')
            .append(jQuery('<li/>')
                .append(jQuery('<a/>', {
                    'href': '#'
                }).append(preferences.status_bar)).append(
                jQuery('<ul/>').append(
                    jQuery('<li/>').append(
                        jQuery('<a/>', {
                            'href': '#'
                        }).click(Sao.preferences).append('Preferences')
                        ),
                    jQuery('<li/>').append(
                        jQuery('<a/>', {
                            'href': '#'
                        }).click(Sao.logout).append('Logout')
                        )))));
        user_menu.find('li')
            .css('float', 'left')
            .css('list-style', 'none');
        user_menu.find('li > a')
            .css('display', 'block')
            .css('white-space', 'nowrap');
        user_menu.find('li > ul')
            .css('position', 'absolute')
            .css('visibility', 'hidden');
        user_menu.find('li > ul > li')
            .css('float', 'none')
            .css('display', 'inline');
        var menu_timer = null;
        var menu_timeout = 500;
        var menu_item = null;
        var menu_open = function() {
            if (menu_timer) {
                window.clearTimeout(menu_timer);
                menu_timer = null;
            }
            menu_close();
            menu_item = jQuery(this).find('ul')
                .css('visibility', 'visible');
        };
        var menu_close = function() {
            if (menu_item) {
                menu_item.css('visibility', 'hidden');
            }
        };
        user_menu.find('li').bind('mouseover', menu_open);
        user_menu.find('li').bind('mouseout', function() {
            menu_timer = window.setTimeout(menu_close, menu_timeout);
        });
        document.onclick = menu_close;
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
                view.table.find('td:nth-child(1)').hide();
                // TODO remove when shortcuts is implemented
                view.table.find('td:nth-child(3)').hide();
                view.rows.forEach(set_select_row);
            };
            jQuery('#menu').append(
                form.screen.screen_container.content_box.detach());
        });
    };
}());
