/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.Session = Sao.class_(Object, {
        init: function(database, login) {
            this.user_id = null;
            this.session = null;
            this.database = database;
            this.login = login;
            this.context = {};
            if (!Sao.Session.current_session) {
                Sao.Session.current_session = this;
            }
        },
        do_login: function(login, password) {
            var dfd = jQuery.Deferred();
            var args = {
                'method': 'common.db.login',
                'params': [login, password]
            };
            var ajax_prm = jQuery.ajax({
                'contentType': 'application/json',
                'data': JSON.stringify(args),
                'dataType': 'json',
                'url': '/' + this.database,
                'type': 'post'
            });

            var ajax_success = function(data) {
                if (data === null) {
                    Sao.common.warning.run('', 'Unable to reach the server.');
                    dfd.reject();
                } else if (data.error) {
                    Sao.common.error.run(data.error[0], data.error[1]);
                    dfd.reject();
                } else {
                    if (!data.result) {
                        this.user_id = null;
                        this.session = null;
                        dfd.reject();
                    } else {
                        this.user_id = data.result[0];
                        this.session = data.result[1];
                        dfd.resolve();
                    }
                }
            };
            ajax_prm.success(ajax_success.bind(this));
            ajax_prm.error(dfd.reject);
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
            var prm = Sao.rpc(args, this);
            this.database = null;
            this.login = null;
            this.user_id = null;
            this.session = null;
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

    Sao.Session.get_credentials = function() {
        var dfd = jQuery.Deferred();
        var database = window.location.hash.replace(
                /^(#(!|))/, '') || null;
        var database_select = jQuery('#login-database');
        var login_input = jQuery('#login-login');
        var password_input = jQuery('#login-password');
        var login_modal = jQuery('#login');

        var ok_func = function() {
            var login = login_input.val();
            var password = password_input.val();
            // clear the password as the input will stay in the DOM
            password_input.val('');
            var database = database || database_select.val();
            if (!(login && password)) {
                return;
            }
            var session = new Sao.Session(database, login);
            session.do_login(login, password)
                .then(function() {
                    dfd.resolve(session);
                }, function() {
                    login_modal.modal('show');
                });
            login_modal.modal('hide');
        };

        login_modal.modal({
            backdrop: false,
            keyboard: false
        });
        login_modal.on('shown.bs.modal', function() {
            if (database) {
                if (!login_input.val()) {
                    login_input.focus();
                } else {
                    password_input.focus();
                }
            } else {
                database_select.focus();
            }
        });
        login_modal.find('form').unbind().submit(function(e) {
            ok_func();
            e.preventDefault();
        });

        jQuery.when(Sao.DB.list()).then(function(databases) {
            databases.forEach(function(database) {
                database_select.append(jQuery('<option/>', {
                    'value': database,
                    'text': database
                }));
            });
            if (database) {
                database_select.val(database);
            }
            login_modal.modal('show');
        });
        return dfd.promise();
    };

    Sao.Session.renew = function(session) {
        var dfd = jQuery.Deferred();
        var password_modal = jQuery('#password');
        var password_input = jQuery('#password-password');
        if (!session.login) {
            return dfd.reject();
        }

        var ok_func = function() {
            var password = password_input.val();
            // clear the password as the input will stay in the DOM
            password_input.val('');
            session.do_login(session.login, password)
                .then(function() {
                    dfd.resolve();
                }, function() {
                    password_modal.modal('show');
                });
            password_modal.modal('hide');
        };

        password_modal.modal({
            backdrop: false,
            keyboard: false
        });
        password_modal.on('shown.bs.modal', function() {
            password_input.focus();
        });
        password_modal.find('form').unbind().submit(function(e) {
            ok_func();
            e.preventDefault();
        });
        password_modal.modal('show');
        return dfd.promise();
    };

    Sao.Session.current_session = null;

    Sao.DB = {};

    Sao.DB.list = function() {
        var args = {
            'method': 'common.db.list',
            'params': []
        };
        return Sao.rpc(args);
    };
}());
