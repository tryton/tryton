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

    Sao.i18n = i18n();
    Sao.i18n.setlang = function(lang) {
        Sao.i18n.setLocale(lang);
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
    Sao.i18n.setlang(
            (navigator.language ||
             navigator.browserLanguge ||
             navigator.userLanguage ||
             'en_US').replace('-', '_'));

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
                    var title = 'Tryton';
                    if (!jQuery.isEmptyObject(preferences.status_bar)) {
                        title += ' - ' + preferences.status_bar;
                    }
                    document.title = title;
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
            jQuery('#menu').children().remove();
            document.title = 'Tryton';
            session.do_logout().always(Sao.login);
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
        }).click(Sao.logout).append(Sao.i18n.gettext('Logout')));
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
            view.table.find('thead').hide();
            jQuery('#menu').children().remove();

            var gs = new Sao.GlobalSearch();
            jQuery('#menu').append(gs.el);
            jQuery('#menu').append(
                form.screen.screen_container.content_box.detach());
        });
    };
    Sao.main_menu_screen = null;

    Sao.Dialog = Sao.class_(Object, {
        init: function(title, class_, size) {
            size = size || 'sm';
            this.modal = jQuery('<div/>', {
                'class': class_ + ' modal fade',
                'role': 'dialog'
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
                'class': 'form-control',
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
                Sao.Action.exec_keyword('tree_open', {
                    'model': item.model,
                    'id': item.record_id,
                    'ids': [item.record_id]
                }, Sao.main_menu_screen.context);
            } else {
                var params = {
                    'model': item.model,
                    'res_id': item.record_id,
                    'mode': ['form', 'tree']
                };
                Sao.Tab.create(params);
            }
            this.search_entry.val('');
        }
    });

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
