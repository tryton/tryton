/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.Session = Sao.class_(Object, {
        init: function(database, login) {
            this.database = database;
            this.login = login;
            this.user_id = null;
            this.session = null;
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
                    Sao.warning('Unable to reach the server');
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
            var prm = Sao.rpc(args, this);
            return prm.then(function(context) {
                this.context = context;
            }.bind(this));
        }
    });

    Sao.Session.get_credentials = function(parent_dfd) {
        var login;  // TODO use cookie
        var database = window.location.hash.replace(
                /^(#(!|))/, '') || null;
        var database_div, database_select;
        var login_div, login_input, password_input;

        var ok_func = function() {
            var login_val = login_input.val();
            var password_val = password_input.val();
            var database_val = (database ||
                    database_select.val());
            if (!(login_val && password_val)) {
                return;
            }
            var session = new Sao.Session(database_val,
                    login_val);
            var prm = session.do_login(login_val, password_val);
            prm.done(function() {
                parent_dfd.resolve(session);
            });
            login_div.dialog('close');
        };

        var keydown = function(ev) {
            if (ev.which === 13)
                ok_func();
        };

        var fill_database = function() {
            jQuery.when(Sao.DB.list()).then(function(databases) {
                databases.forEach(function(database) {
                    database_select.append(jQuery('<option/>', {
                        'value': database,
                        'text': database
                    }));
                });
            });
        };

        login_div = jQuery('<div/>', {
            'class': 'login'
        });
        if (!database) {
            login_div.append(jQuery('<label/>', {
                'text': 'Database:' // TODO translation
            }));
            database_select = jQuery('<select/>');
            login_div.append(database_select);
            fill_database();
            login_div.append(jQuery('<br/>'));
        }

        login_div.append(jQuery('<label/>', {
            'text': 'Login:' // TODO translation
        }));
        login_input = jQuery('<input/>', {
            'type': 'input',
                    'id': 'login',
                    'val': login
        });
        login_input.keydown(keydown);
        login_div.append(login_input);
        login_div.append(jQuery('<br/>'));

        login_div.append(jQuery('<label/>', {
            'text': 'Password:'
        }));
        password_input = jQuery('<input/>', {
            'type': 'password',
                       'id': 'password'
        });
        password_input.keydown(keydown);
        login_div.append(password_input);
        login_div.append(jQuery('<br/>'));

        login_div.dialog({
            'title': 'Login', // TODO translation
            'modal': true,
            'buttons': {
                'Cancel': function() {
                    jQuery(this).dialog('close');
                },
            'OK': ok_func
            },
            'open': function() {
                if (login) {
                    password_input.focus();
                } else {
                    login_input.focus();
                }
            }
        });

    };

    Sao.Session.renew = function(session) {
        var dfd = jQuery.Deferred();
        var login_div, password_input;

        var ok_func = function() {
            var password_val = password_input.val();
            session.do_login(session.login, password_val).done(function() {
                dfd.resolve();
            });
            login_div.dialog('close');
        };
        var keydown = function(ev) {
            if (ev.which === 13)
                ok_func();
        };

        login_div = jQuery('<div/>', {
            'class': 'login'
        });
        login_div.append(jQuery('<label/>', {
            'text': 'Password:'
        }));
        password_input = jQuery('<input/>', {
            'type': 'password',
                       'id': 'password'
        });
        password_input.keydown(keydown);
        login_div.append(password_input);
        login_div.append(jQuery('<br/>'));

        login_div.dialog({
            'title': 'Login', // TODO translation
            'modal': true,
            'buttons': {
                'Cancel': function() {
                    jQuery(this).dialog('close');
                },
            'OK': ok_func
            },
            'open': function() {
                password_input.focus();
            }
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
