/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.Session = Sao.class_(Object, {
        init: function(database, login) {
            this.user_id = null;
            this.session = null;
            this.prm = jQuery.when();  // renew promise
            this.database = database;
            this.login = login;
            this.context = {};
            if (!Sao.Session.current_session) {
                Sao.Session.current_session = this;
            }
        },
        get_auth: function() {
            return btoa(this.login + ':' + this.user_id + ':' + this.session);
        },
        do_login: function(login, parameters) {
            var dfd = jQuery.Deferred();
            var func = function(parameters) {
                return {
                    'method': 'common.db.login',
                    'params': [login, parameters, Sao.i18n.getlang()]
                };
            };
            new Sao.Login(func, this).run().then(function(result) {
                this.user_id = result[0];
                this.session = result[1];
                dfd.resolve();
            }.bind(this), function() {
                this.user_id = null;
                this.session = null;
                dfd.reject();
            });
            return dfd.promise();
        },
        do_logout: function() {
            if (!(this.user_id && this.session)) {
                return jQuery.when();
            }
            var args = {
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
            // Call with custom session to not send context
            var session = jQuery.extend({}, this);
            session.context = {};
            var prm = Sao.rpc(args, session);
            return prm.then(function(context) {
                this.context = context;
            }.bind(this));
        }
    });

    Sao.Session.login_dialog = function() {
        var dialog = new Sao.Dialog(Sao.i18n.gettext('Login'), 'lg');
        dialog.database_select = jQuery('<select/>', {
            'class': 'form-control',
            'id': 'login-database'
        }).hide();
        dialog.database_input = jQuery('<input/>', {
            'class': 'form-control',
            'id': 'login-database'
        }).hide();
        dialog.login_input = jQuery('<input/>', {
            'class': 'form-control',
            'id': 'login-login',
            'placeholder': Sao.i18n.gettext('Login')
        });
        dialog.body.append(jQuery('<div/>', {
            'class': 'form-group'
        }).append(jQuery('<label/>', {
            'class': 'control-label',
            'for': 'login-database'
        }).append(Sao.i18n.gettext('Database')))
        .append(dialog.database_select)
        .append(dialog.database_input)
        ).append(jQuery('<div/>', {
            'class': 'form-group'
        }).append(jQuery('<label/>', {
            'class': 'control-label',
            'for': 'login-login'
        }).append(Sao.i18n.gettext('Login')))
        .append(dialog.login_input)
        );
        dialog.button = jQuery('<button/>', {
            'class': 'btn btn-primary',
            'type': 'submit'
        }).append(Sao.i18n.gettext('Login')).appendTo(dialog.footer);
        return dialog;
    };

    Sao.Session.get_credentials = function() {
        var dfd = jQuery.Deferred();
        var database = window.location.hash.replace(
                /^(#(!|))/, '') || null;
        var dialog = Sao.Session.login_dialog();

        var empty_field = function() {
            return dialog.modal.find('input,select').filter(':visible')
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
            var session = new Sao.Session(database, login);
            session.do_login(login)
                .then(function() {
                    dfd.resolve(session);
                    dialog.modal.remove();
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

        jQuery.when(Sao.DB.list()).then(function(databases) {
            var el;
            databases = databases || [];
            if (databases.length <= 1 ) {
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
            empty_field().first().focus();
        });
        return dfd.promise();
    };

    Sao.Session.renew = function(session) {
        if (session.prm.state() == 'pending') {
            return session.prm;
        }
        var dfd = jQuery.Deferred();
        session.prm = dfd.promise();
        if (!session.login) {
            dfd.reject();
            return session.prm;
        }
        session.do_login(session.login).then(dfd.resolve, dfd.reject);
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
            var args = {
                'contentType': 'application/json',
                'data': JSON.stringify(this.func(parameters)),
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
                    if (data.error[0].startsWith('403')) {
                        return this.run({}).then(dfd.resolve, dfd.reject);
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
            ajax_prm.success(ajax_success.bind(this));
            ajax_prm.error(dfd.reject);
            return dfd.promise();
        },
        get_char: function(message) {
            return Sao.common.ask.run(message);
        },
        get_password: function(message) {
            return Sao.common.ask.run(message, false);
        },
    });

    Sao.DB = {};

    Sao.DB.list = function() {
        var timeoutID = Sao.common.processing.show();
        return jQuery.ajax({
            'contentType': 'application/json',
            'data': JSON.stringify({
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
