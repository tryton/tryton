/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    // https://developer.mozilla.org/en-US/docs/Web/API/WindowOrWorkerGlobalScope/btoa#Unicode_strings
    function utoa(str) {
        return window.btoa(unescape(encodeURIComponent(str)));
    }

    Sao.Session = Sao.class_(Object, {
        init: function(database, login) {
            this.user_id = null;
            this.session = null;
            this.cache = new Cache();
            this.prm = jQuery.when();  // renew promise
            this.database = database;
            this.login = login;
            this.restore();
            this.context = {
                client: Sao.Bus.id,
            };
            if (!Sao.Session.current_session) {
                Sao.Session.current_session = this;
            }
        },
        get_auth: function() {
            return utoa(this.login + ':' + this.user_id + ':' + this.session);
        },
        do_login: function(parameters) {
            var dfd = jQuery.Deferred();
            var login = this.login;
            var func = function(parameters) {
                return {
                    'method': 'common.db.login',
                    'params': [login, parameters, Sao.i18n.getlang()]
                };
            };
            new Sao.Login(func, this).run().then(function(result) {
                this.login = login;
                this.user_id = result[0];
                this.session = result[1];
                this.store();
                dfd.resolve();
            }.bind(this), function() {
                this.user_id = null;
                this.session = null;
                this.store();
                dfd.reject();
            }.bind(this));
            return dfd.promise();
        },
        do_logout: function() {
            if (!(this.user_id && this.session)) {
                return jQuery.when();
            }
            var args = {
                'id': 0,
                'method': 'common.db.logout',
                'params': []
            };
            var prm = jQuery.ajax({
                'headers': {
                    'Authorization': 'Session ' + this.get_auth()
                },
                'contentType': 'application/json',
                'data': JSON.stringify(args),
                'dataType': 'json',
                'url': '/' + this.database + '/',
                'type': 'post',
            });
            this.unstore();
            this.database = null;
            this.login = null;
            this.user_id = null;
            this.session = null;
            if (Sao.Session.current_session === this) {
                Sao.Session.current_session = null;
            }
            return prm;
        },
        reload_context: function() {
            var args = {
                'method': 'model.res.user.get_preferences',
                'params': [true, {}]
            };
            this.context = {
                client: Sao.Bus.id,
            };
            var prm = Sao.rpc(args, this);
            return prm.then(function(context) {
                jQuery.extend(this.context, context);
            }.bind(this));
        },
        restore: function() {
            if (this.database && !this.session) {
                var session_data = localStorage.getItem(
                    'sao_session_' + this.database);
                if (session_data !== null) {
                    session_data = JSON.parse(session_data);
                    if (!this.login || this.login == session_data.login) {
                        this.login = session_data.login;
                        this.user_id = session_data.user_id;
                        this.session = session_data.session;
                    }
                }
            }
        },
        store: function() {
            var session = {
                'login': this.login,
                'user_id': this.user_id,
                'session': this.session,
            };
            session = JSON.stringify(session);
            localStorage.setItem('sao_session_' + this.database, session);
        },
        unstore: function() {
            localStorage.removeItem('sao_session_' + this.database);
        },
    });

    Sao.Session.login_dialog = function() {
        var dialog = new Sao.Dialog(Sao.i18n.gettext('Login'), 'lg');
        dialog.database_select = jQuery('<select/>', {
            'class': 'form-control',
            'id': 'database'
        }).hide();
        dialog.database_input = jQuery('<input/>', {
            'class': 'form-control',
            'id': 'database'
        }).hide();
        dialog.login_input = jQuery('<input/>', {
            'class': 'form-control',
            'id': 'login',
            'placeholder': Sao.i18n.gettext('User name')
        });
        dialog.body.append(jQuery('<div/>', {
            'class': 'form-group'
        }).append(jQuery('<label/>', {
            'class': 'control-label',
            'for': 'database'
        }).text(Sao.i18n.gettext('Database')))
        .append(dialog.database_select)
        .append(dialog.database_input)
        ).append(jQuery('<div/>', {
            'class': 'form-group'
        }).append(jQuery('<label/>', {
            'class': 'control-label',
            'for': 'login'
        }).text(Sao.i18n.gettext('User name')))
        .append(dialog.login_input)
        );
        dialog.button = jQuery('<button/>', {
            'class': 'btn btn-primary',
            'type': 'submit'
        }).text(' ' + Sao.i18n.gettext("Login")).appendTo(dialog.footer);
        return dialog;
    };

    Sao.Session.get_credentials = function() {
        var database_url = function() {
            return window.location.hash.replace(
                /^(#(!|))/, '').split('/', 1)[0] || null;
        };
        var dfd = jQuery.Deferred();
        var database = database_url();

        var session = new Sao.Session(database, null);
        if (session.session) {
            dfd.resolve(session);
            return dfd;
        }
        var dialog = Sao.Session.login_dialog();

        var empty_field = function() {
            return dialog.modal.find('input,select').filter(':visible:not([readonly])')
                .filter(function() {
                    return !jQuery(this).val();
                });
        };

        var ok_func = function() {
            var login = dialog.login_input.val();
            var database = database || dialog.database_select.val() ||
                dialog.database_input.val();
            dialog.modal.find('.has-error').removeClass('has-error');
            if (!(login && database)) {
                empty_field().closest('.form-group').addClass('has-error');
                return;
            }
            dialog.button.focus();
            dialog.button.prop('disabled', true);
            dialog.modal.modal('hide');
            session.database = database;
            session.login = login;
            session.restore();
            (session.session ? jQuery.when() : session.do_login())
                .then(function() {
                    dfd.resolve(session);
                    dialog.modal.remove();
                    if (database_url() != database) {
                        window.location = '#' + database;
                    }
                }, function() {
                    dialog.button.prop('disabled', false);
                    dialog.modal.modal('show');
                    empty_field().closest('.form-group').addClass('has-error');
                    empty_field().first().focus();
                });
        };

        dialog.modal.modal({
            backdrop: false,
            keyboard: false
        });
        dialog.modal.find('form').unbind().submit(function(e) {
            ok_func();
            e.preventDefault();
        });
        dialog.modal.on('shown.bs.modal', function() {
            empty_field().first().focus();
        });

        jQuery.when(Sao.DB.list()).then(function(databases) {
            var el;
            databases = databases || [];
            if (databases.length == 1 ) {
                database = databases[0];
                el = dialog.database_input;
            } else {
                el = dialog.database_select;
                databases.forEach(function(database) {
                    el.append(jQuery('<option/>', {
                        'value': database,
                        'text': database
                    }));
                });
            }
            el.prop('readonly', databases.length == 1);
            el.show();
            el.val(database || '');
        }, function() {
            dialog.database_input.show();
        });
        return dfd.promise();
    };

    Sao.Session.renew = function(session) {
        if (session.prm.state() == 'pending') {
            return session.prm;
        }
        var dfd = jQuery.Deferred();
        session.prm = dfd.promise();
        session.do_login().then(dfd.resolve, function() {
            Sao.logout();
            dfd.reject();
        }).done(function () {
            Sao.Bus.listen();
        });
        return session.prm;
    };

    Sao.Session.current_session = null;

    Sao.Login = Sao.class_(Object, {
        init: function(func, session) {
            this.func = func;
            this.session = session || Sao.Session.current_session;
        },
        run: function(parameters) {
            if (parameters === undefined) {
                parameters = {};
            }
            var dfd = jQuery.Deferred();
            var timeoutID = Sao.common.processing.show();
            var data = this.func(parameters);
            data.id = 0;
            var args = {
                'contentType': 'application/json',
                'data': JSON.stringify(data),
                'dataType': 'json',
                'url': '/' + this.session.database + '/',
                'type': 'post',
                'complete': [function() {
                    Sao.common.processing.hide(timeoutID);
                }]
            };
            if (this.session.user_id && this.session.session) {
                args.headers = {
                    'Authorization': 'Session ' + this.session.get_auth()
                };
            }
            var ajax_prm = jQuery.ajax(args);

            var ajax_success = function(data) {
                if (data === null) {
                    Sao.common.warning.run('',
                           Sao.i18n.gettext('Unable to reach the server.'));
                    dfd.reject();
                } else if (data.error) {
                    if (data.error[0].startsWith('401')) {
                        return this.run({}).then(dfd.resolve, dfd.reject);
                    } else if (data.error[0].startsWith('429')) {
                        Sao.common.message.run(
                            Sao.i18n.gettext('Too many requests. Try again later.'),
                            'tryton-error').always(dfd.resolve);
                    } else if (data.error[0].startsWith('404')) {
                        dfd.reject();
                    } else if (data.error[0] != 'LoginException') {
                        Sao.common.error.run(data.error[0], data.error[1]);
                        dfd.reject();
                    } else {
                        var args = data.error[1];
                        var name = args[0];
                        var message = args[1];
                        var type = args[2];
                        this['get_' + type](message).then(function(value) {
                            parameters[name] = value;
                            return this.run(parameters).then(
                                    dfd.resolve, dfd.reject);
                        }.bind(this), dfd.reject);
                    }
                } else {
                    dfd.resolve(data.result);
                }
            };
            var ajax_error = function(query, status_, error) {
                if (query.status == 401) {
                    // Retry
                    this.run({}).then(dfd.resolve, dfd.reject);
                } else if (query.status == 429) {
                    Sao.common.message.run(
                        Sao.i18n.gettext('Too many requests. Try again later.'),
                        'tryton-error').always(dfd.resolve);
                } else {
                    Sao.common.error.run(status_, error);
                    dfd.reject();
                }
            };
            ajax_prm.done(ajax_success.bind(this));
            ajax_prm.fail(ajax_error.bind(this));
            return dfd.promise();
        },
        get_char: function(message) {
            return Sao.common.ask.run(message);
        },
        get_password: function(message) {
            return Sao.common.ask.run(message, false);
        },
    });

    var Cache = Sao.class_(Object, {
        init: function() {
            this.store = {};
        },
        cached: function(prefix) {
            return prefix in this.store;
        },
        set: function(prefix, key, expire, value) {
            expire = new Date(new Date().getTime() + expire * 1000);
            Sao.setdefault(this.store, prefix, {})[key] = {
                'expire': expire,
                'value': JSON.stringify(Sao.rpc.prepareObject(value)),
            };
        },
        get: function(prefix, key) {
            var now = new Date();
            var data = Sao.setdefault(this.store, prefix, {})[key];
            if (!data) {
                return undefined;
            }
            if (data.expire < now) {
                delete this.store[prefix][key];
                return undefined;
            }
            return Sao.rpc.convertJSONObject(jQuery.parseJSON(data.value));
        },
        clear: function(prefix) {
            if (prefix) {
                this.store[prefix] = {};
            } else {
                this.store = {};
            }
        },
    });

    Sao.DB = {};

    Sao.DB.list = function() {
        var timeoutID = Sao.common.processing.show();
        return jQuery.ajax({
            'contentType': 'application/json',
            'data': JSON.stringify({
                'id': 0,
                'method': 'common.db.list',
                'params': []
            }),
            'dataType': 'json',
            'url': '/',
            'type': 'post',
            'complete': [function() {
                Sao.common.processing.hide(timeoutID);
            }]
        }).then(function(data) {
            return data.result;
        });
    };
}());
