/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.parse_cookie = function() {
        var cookie = {};
        var parts = document.cookie.split('; ');
        for (var i = 0, length = parts.length; i < length; i++) {
            var part = parts[i].split('=');
            if (part.length != 2) {
                continue;
            }
            cookie[part[0]] = part[1];
        }
        return cookie;
    };


    Sao.set_cookie = function(values) {
        for (var name in values) {
            if (!values.hasOwnProperty(name)) {
                continue;
            }
            var value = values[name];
            document.cookie = name + '=' + value;
        }
    };

    Sao.Session = Sao.class_(Object, {
       init: function(database, login) {
           this.user_id = null;
           this.session = null;
            if (!database && !login) {
                var cookie = Sao.parse_cookie();
                this.database = cookie.database;
                this.login = cookie.login;
            } else {
                this.database = database;
                this.login = login;
            }
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
                    console.log('ERROR');
                    Sao.error(data.error[0], data.error[1]);
                    dfd.reject();
                } else {
                    if (!data.result) {
                        this.user_id = null;
                        this.session = null;
                    } else {
                        this.user_id = data.result[0];
                        this.session = data.result[1];
                        Sao.set_cookie({
                            'login': this.login,
                            'database': this.database
                        });
                    }
                    dfd.resolve();
                }
            };
            ajax_prm.success(ajax_success.bind(this));
            ajax_prm.error(dfd.reject);
            return dfd.promise();
        },
        do_logout: function() {
            if (!(this.user_id && this.session)) {
                return;
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

    Sao.Session.get_credentials = function(parent_dfd) {
        var cookie = Sao.parse_cookie();
        var login = cookie.login;
        var database = window.location.hash.replace(
                /^(#(!|))/, '') || null;
        var database_select;
        var login_modal;

        var ok_func = function() {
            var login = jQuery('#login-login').val();
            var password = jQuery('#login-password').val();
            var database = database || database_select.val();
            if (!(login && password)) {
                return;
            }
            var session = new Sao.Session(database, login);
            var prm = session.do_login(login, password);
            prm.done(function() {
                parent_dfd.resolve(session);
            });
            login_modal.modal('hide');
        };

        var fill_database = function() {
            jQuery.when(Sao.DB.list()).then(function(databases) {
                databases.forEach(function(database) {
                    database_select.append(jQuery('<option/>', {
                        'value': database,
                        'text': database
                    }));
                });
            }).then(function() {
                database_select.val(cookie.database);
            });
        };

        login_modal = jQuery('#login');

        if (!database) {
            database_select = jQuery('#login-database');
            fill_database();
        }

        login_modal.modal({
            backdrop: false,
            keyboard: false
        });
        login_modal.modal('show');
        login_modal.on('show.bs.modal', function() {
            if (database) {
                jQuery('#login-login').focus();
            } else {
                jQuery('#login-database').focus();
            }
        });
        login_modal.find('form').submit(function(e) {
            ok_func();
            e.preventDefault();
        });
    };

    Sao.Session.renew = function(session) {
        var dfd = jQuery.Deferred();
        var password_modal;
        if (!session.login) {
            return dfd.reject();
        }

        var ok_func = function() {
            var password = jQuery('#password-password').val();
            session.do_login(session.login, password).done(function() {
                dfd.resolve();
            });
            password_modal.modal('hide');
        };

        password_modal = jQuery('#password');
        password_modal.modal({
            backdrop: false,
            keyboard: false
        });
        password_modal.modal('show');
        password_modal.on('show.bs.modal', function() {
            jQuery('#password-password').focus();
        });
        password_modal.find('form').submit(function(e) {
            ok_func();
            e.preventDefault();
        });
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
