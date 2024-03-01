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
            this.login_service = null;
            this.user_id = null;
            this.session = null;
            this.cache = new Cache();
            this.prm = jQuery.when();  // renew promise
            this.database = database;
            this.login = login;
            this.restore();
            this.context = {};
            this.restore_context();
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
            var device_cookies = JSON.parse(
                localStorage.getItem('sao_device_cookies'));
            var device_cookie = null;
            if (device_cookies && device_cookies[this.database]) {
                device_cookie = device_cookies[this.database][this.login];
            }
            var func = function(parameters) {
                parameters.device_cookie = device_cookie;
                return {
                    'method': 'common.db.login',
                    'params': [login, parameters, Sao.i18n.getlang()]
                };
            };
            new Sao.Login(func, this).run().then(result => {
                this.login = login;
                this.user_id = result[0];
                this.session = result[1];
                this.store();
                this.renew_device_cookie();
                dfd.resolve();
            }, () => {
                this.user_id = null;
                this.session = null;
                this.store();
                dfd.reject();
            });
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
        do_reset_password: function() {
            if (!this.login) {
                return jQuery.when();
            }
            const args = {
                'id': 0,
                'method': 'common.db.reset_password',
                'params': [this.login, Sao.i18n.getlang()],
            };
            return jQuery.ajax({
                'contentType': 'application/json',
                'data': JSON.stringify(args),
                'dataType': 'json',
                'url': '/' + this.database + '/',
                'type': 'post',
            });
        },
        reload_context: function() {
            var args = {
                'method': 'model.res.user.get_preferences',
                'params': [true, this.context]
            };
            this.reset_context();
            var prm = Sao.rpc(args, this);
            return prm.then(context => {
                context = Object.fromEntries(Object.entries(context).filter(
                    ([k, v]) => (k != 'locale') && !k.endsWith('.rec_name')));
                jQuery.extend(this.context, context);
                this.store_context();
            });
        },
        reset_context: function() {
            this.context = {
                client: Sao.Bus.id,
            };
        },
        restore_context: function() {
            this.reset_context();
            var context = sessionStorage.getItem('sao_context_' + this.database);
            if (context !== null) {
                jQuery.extend(
                    this.context, Sao.rpc.convertJSONObject(JSON.parse(context)));
            }
        },
        store_context: function() {
            var context = jQuery.extend({}, this.context);
            delete context.client;
            context = JSON.stringify(Sao.rpc.prepareObject(context));
            sessionStorage.setItem('sao_context_' + this.database, context);
        },
        restore: function() {
            if (this.database && !this.session) {
                var session_data = localStorage.getItem(
                    'sao_session_' + this.database);
                if (session_data !== null) {
                    session_data = JSON.parse(session_data);
                    if (!this.login || this.login == session_data.login) {
                        this.login_service = session_data.login_service;
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
        renew_device_cookie: function() {
            var device_cookie;
            var device_cookies = JSON.parse(
                localStorage.getItem('sao_device_cookies'));
            if (!device_cookies || !(this.database in device_cookies)) {
                device_cookie = null;
            } else {
                device_cookie = device_cookies[this.database][this.login];
            }
            var renew_prm = Sao.rpc({
                method: 'model.res.user.device.renew',
                params: [device_cookie, {}],
            }, this);
            renew_prm.done(result => {
                device_cookies = JSON.parse(
                    localStorage.getItem('sao_device_cookies'));
                if (!device_cookies) {
                    device_cookies = {};
                }
                if (!(this.database in device_cookies)) {
                    device_cookies[this.database] = {};
                }
                device_cookies[this.database][this.login] = result;
                localStorage.setItem(
                    'sao_device_cookies', JSON.stringify(device_cookies));
            });
            renew_prm.fail(() => {
                Sao.Logger.error("Cannot renew device cookie");
            });
        }
    });

    Sao.Session.server_version = function() {
        var timeoutID = Sao.common.processing.show();
        return jQuery.ajax({
            'contentType': 'application/json',
            'data': JSON.stringify({
                'id': 0,
                'method': 'common.server.version',
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

    Sao.Session.login_dialog = function() {
        var dialog = new Sao.Dialog(
            Sao.i18n.gettext("Login"), 'login-dialog', 'md', true,
            Sao.__version__);
        dialog.database_select = jQuery('<select/>', {
            'class': 'form-control',
            'id': 'database',
            'name': 'database',
        }).hide();
        dialog.database_input = jQuery('<input/>', {
            'class': 'form-control',
            'id': 'database',
            'name': 'database',
        }).hide();
        dialog.login_input = jQuery('<input/>', {
            'class': 'form-control',
            'id': 'login',
            'name': 'login',
        });
        dialog.button = jQuery('<button/>', {
            'class': 'btn btn-primary btn-block',
            'type': 'submit',
            'title': Sao.i18n.gettext("Login"),
        }).text(' ' + Sao.i18n.gettext("Login"));
        dialog.body.append(jQuery('<div/>', {
            'class': 'form-group'
        }).append(jQuery('<label/>', {
            'class': 'control-label',
            'for': 'database'
        }).text(Sao.i18n.gettext('Database')))
        .append(dialog.database_select)
        .append(dialog.database_input))
        .append(jQuery('<div/>', {
            'class': 'panel panel-default',
        })
        .append(jQuery('<div/>', {
            'class': 'panel-body',
        })
        .append(jQuery('<div/>', {
            'class': 'form-group'
        }).append(jQuery('<label/>', {
            'class': 'control-label',
            'for': 'login'
        }).text(Sao.i18n.gettext('User name')))
        .append(dialog.login_input)
        )
        .append(dialog.button)));
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

        var disable_form = function(disabled=true) {
            dialog.body.find('input,select,button').prop('disabled', disabled);
        };

        var login = function() {
            var login = dialog.login_input.val();
            var database = database || dialog.database_select.val() ||
                dialog.database_input.val();
            dialog.modal.find('.has-error').removeClass('has-error');
            if (!(login && database)) {
                empty_field().closest('.form-group').addClass('has-error');
                return;
            }
            dialog.button.focus();
            disable_form();
            session.database = database;
            session.login = login;
            session.restore();
            (session.session ? jQuery.when() : session.do_login())
                .then(function() {
                    dialog.modal.modal('hide');
                    dfd.resolve(session);
                    dialog.modal.remove();
                    if (database_url() != database) {
                        window.location = '#' + database;
                    }
                }, function() {
                    disable_form(false);
                    empty_field().closest('.form-group').addClass('has-error');
                    empty_field().first().focus();
                });
        };

        var login_service = function(evt) {
            var database = database || dialog.database_select.val() ||
                dialog.database_input.val();
            dialog.modal.find('.has-error').removeClass('has-error');
            if (!database) {
                dialog.database_select
                    .closest('.form-group').addClass('has-error');
                return;
            }
            disable_form();
            var host = window.location.protocol + '//' + window.location.host;
            var next = new URL(host + '/');
            next.searchParams.append('login_service', evt.data);
            var url = new URL(host + '/' + database + evt.data);
            url.searchParams.append('next', next.href);
            var service_window = window.open(url.href, '_blank', 'popup=1');
            const timer = window.setInterval(() => {
                if (service_window.closed) {
                    window.clearInterval(timer);
                    session.database = database;
                    session.restore();
                    if (session.session) {
                        dfd.resolve(session);
                        dialog.modal.remove();
                        if (database_url() != database) {
                            window.location = '#' + database;
                        }
                    } else {
                        disable_form(false);
                        empty_field().first().focus();
                    }
                }
            }, 500);
        };

        dialog.modal.modal({
            backdrop: false,
            keyboard: false
        });
        dialog.modal.find('form').unbind().submit(function(e) {
            e.preventDefault();
            login();
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
                for (const database of databases) {
                    el.append(jQuery('<option/>', {
                        'value': database,
                        'text': database
                    }));
                }
            }
            el.prop('readonly', databases.length == 1);
            el.show();
            el.val(database || '');
        }, function() {
            dialog.database_input.show();
        });

        jQuery.when(Sao.Authentication.services()).then(function(services) {
            if (services.length) {
                var panel_body = jQuery('<div/>', {
                    'class': 'panel-body',
                }).append(jQuery('<p/>')
                    .text(Sao.i18n.gettext("Login with")));
                dialog.body.append(jQuery('<div/>', {
                    'class': 'panel panel-default',
                }).append(panel_body));
                for (const [name, url] of services) {
                    panel_body.append(jQuery('<button/>', {
                        'class': 'btn btn-block btn-default',
                        'type': 'button',
                    }).text(name).click(url, login_service));
                }
            }
        });
        return dfd.promise();
    };

    Sao.Session.renew = function(session) {
        if (session.prm.state() == 'pending') {
            return session.prm;
        }
        var dfd = jQuery.Deferred();
        session.session = null;
        session.prm = dfd.promise();
        if (!session.login_service) {
            session.do_login().then(dfd.resolve, function() {
                Sao.logout();
                dfd.reject();
            });
        } else {
            session.unstore();
            var host = window.location.protocol + '//' + window.location.host;
            var next = new URL(host + '/');
            next.searchParams.append('login_service', session.login_service);
            next.searchParams.append('renew', session.user_id);
            var url = new URL(host + '/' + session.database + session.login_service);
            url.searchParams.append('next', next.href);
            var service_window = window.open(url.href, '_blank', 'popup=1');
            const timer = window.setInterval(() => {
                if (service_window.closed) {
                    window.clearInterval(timer);
                    session.restore();
                    if (session.session) {
                        dfd.resolve();
                    } else {
                        Sao.logout();
                        dfd.reject();
                    }
                }
            }, 500);
        }
        dfd.done(function() {
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
        run: function(parameters={}) {
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
                        Sao.common.message.run(
                            Sao.i18n.gettext("Not found."),
                            'tryton-error').always(dfd.reject);
                    } else if (data.error[0] != 'LoginException') {
                        Sao.common.error.run(data.error[0], data.error[1])
                            .always(dfd.reject);
                    } else {
                        var args = data.error[1];
                        var name = args[0];
                        var message = args[1];
                        var type = args[2];
                        this['get_' + type](message, name).then(value => {
                            parameters[name] = value;
                            return this.run(parameters).then(
                                    dfd.resolve, dfd.reject);
                        }, dfd.reject);
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
                } else if (query.status == 404) {
                    Sao.common.message.run(
                        Sao.i18n.gettext("Not found."),
                        'tryton-error').always(dfd.reject);
                } else {
                    Sao.common.error.run(status_, error).always(dfd.reject);
                }
            };
            ajax_prm.done(ajax_success.bind(this));
            ajax_prm.fail(ajax_error.bind(this));
            return dfd.promise();
        },
        get_char: function(message, name) {
            return Sao.common.ask.run(message, name);
        },
        get_password: function(message, name) {
            const session = this.session;
            const AskPasswordDialog = Sao.class_(Sao.common.AskDialog, {
                build_dialog: function(question, name, visibility, prm) {
                    const dialog = AskPasswordDialog._super.build_dialog.call(
                        this, question, name, visibility, prm);
                    jQuery('<button/>', {
                        'class': 'btn btn-link btn-sm pull-left',
                        'type': 'button',
                        'title': Sao.i18n.gettext(
                            "Send you an email to reset your password."),
                    }).text("Reset forgotten password").click(() => {
                        session.do_reset_password().then(() => {
                            return Sao.common.message.run(Sao.i18n.gettext(
                                "A request to reset your password has been sent.\n" +
                                "Please check your mailbox."));
                        }).then(() => {
                            dialog.modal.find('input,select')
                                .filter(':visible').first().focus();
                        });
                    }).prependTo(dialog.footer);
                    dialog.modal.find('.modal-dialog').removeClass('modal-sm');
                    return dialog;
                },
            });
            var ask;
            if (name == 'password') {
                ask = new AskPasswordDialog();
            } else {
                ask = Sao.common.ask;
            }
            return ask.run(message, name, false);
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
            Sao.Logger.info("(cached)", prefix, key);
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

    Sao.Authentication = {};

    Sao.Authentication.services = function() {
        var timeoutID = Sao.common.processing.show();
        return jQuery.ajax({
            'contentType': 'application/json',
            'data': JSON.stringify({
                'id': 0,
                'method': 'common.authentication.services',
                'params': []
            }),
            'dataType': 'json',
            'url': '/',
            'type': 'post',
            'complete': [function() {
                Sao.common.processing.hide(timeoutID);
            }]
        }).then(function(data) {
            Sao.Authentication.services = function() {
                return data.result;
            };
            return data.result;
        });
    };
}());
