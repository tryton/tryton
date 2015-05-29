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
                    Sao.common.warning.run('',
                           Sao.i18n.gettext('Unable to reach the server.'));
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

    Sao.Session.login_dialog = function() {
        var dialog = new Sao.Dialog(Sao.i18n.gettext('Login'), 'lg');
        dialog.database_select = jQuery('<select/>', {
            'class': 'form-control',
            'id': 'login-database'
        });
        dialog.login_input = jQuery('<input/>', {
            'class': 'form-control',
            'id': 'login-login',
            'placeholder': Sao.i18n.gettext('Login')
        });
        dialog.password_input = jQuery('<input/>', {
            'class': 'form-control',
            'type': 'password',
            'id': 'login-password',
            'placeholder': Sao.i18n.gettext('Password')
        });
        dialog.body.append(jQuery('<div/>', {
            'class': 'form-group'
        }).append(jQuery('<label/>', {
            'for': 'login-database'
        }).append(Sao.i18n.gettext('Database')))
        .append(dialog.database_select)
        ).append(jQuery('<div/>', {
            'class': 'form-group'
        }).append(jQuery('<label/>', {
            'for': 'login-login'
        }).append(Sao.i18n.gettext('Login')))
        .append(dialog.login_input)
        ).append(jQuery('<div/>', {
            'class': 'form-group'
        }).append(jQuery('<label/>', {
            'for': 'login-password'
        }).append(Sao.i18n.gettext('Password')))
        .append(dialog.password_input));
        jQuery('<button/>', {
            'class': 'btn btn-primary',
            'type': 'submit'
        }).append(Sao.i18n.gettext('Login')).appendTo(dialog.footer);
        dialog.modal.on('hidden.bs.modal', function(event) {
            jQuery(this).remove();
        });
        return dialog;
    };

    Sao.Session.get_credentials = function() {
        var dfd = jQuery.Deferred();
        var database = window.location.hash.replace(
                /^(#(!|))/, '') || null;
        var dialog = Sao.Session.login_dialog();

        var ok_func = function() {
            var login = dialog.login_input.val();
            var password = dialog.password_input.val();
            // clear the password as the input will stay in the DOM
            dialog.password_input.val('');
            var database = database || dialog.database_select.val();
            if (!(login && password)) {
                return;
            }
            var session = new Sao.Session(database, login);
            session.do_login(login, password)
                .then(function() {
                    dfd.resolve(session);
                }, function() {
                    dialog.modal.modal('show');
                });
            dialog.modal.modal('hide');
        };

        dialog.modal.modal({
            backdrop: false,
            keyboard: false
        });
        dialog.modal.on('shown.bs.modal', function() {
            if (database) {
                if (!dialog.login_input.val()) {
                    dialog.login_input.focus();
                } else {
                    dialog.password_input.focus();
                }
            } else {
                dialog.database_select.focus();
            }
        });
        dialog.modal.find('form').unbind().submit(function(e) {
            ok_func();
            e.preventDefault();
        });

        jQuery.when(Sao.DB.list()).then(function(databases) {
            databases.forEach(function(database) {
                dialog.database_select.append(jQuery('<option/>', {
                    'value': database,
                    'text': database
                }));
            });
            if (database) {
                dialog.database_select.val(database);
            }
            dialog.modal.modal('show');
        });
        return dfd.promise();
    };

    Sao.Session.password_dialog = function() {
        var dialog = new Sao.Dialog(Sao.i18n.gettext('Password'), 'lg');
        dialog.password_input = jQuery('<input/>', {
            'class': 'form-control',
            'tye': 'password',
            'id': 'password-password',
            'placeholder': Sao.i18n.gettext('Password')
        });
        dialog.body.append(jQuery('<div/>', {
            'class': 'form-group'
        }).append(jQuery('<label/>', {
            'for': 'password-password'
        }).append(Sao.i18n.gettext('Password')))
        .append(dialog.password_input));
        jQuery('<button/>', {
            'class': 'btn btn-primary',
            'type': 'submit'
        }).append(Sao.i18n.gettext('OK')).appendTo(dialog.footer);
        dialog.modal.on('hidden.bs.modal', function(event) {
            jQuery(this).remove();
        });
        return dialog;
    };

    Sao.Session.renew = function(session) {
        var dfd = jQuery.Deferred();
        var dialog = Sao.Session.password_dialog();
        if (!session.login) {
            return dfd.reject();
        }

        var ok_func = function() {
            var password = dialog.password_input.val();
            // clear the password as the input will stay in the DOM
            dialog.password_input.val('');
            session.do_login(session.login, password)
                .then(function() {
                    dfd.resolve();
                }, function() {
                    dialog.modal.modal('show');
                });
            dialog.modal.modal('hide');
        };

        dialog.modal.modal({
            backdrop: false,
            keyboard: false
        });
        dialog.modal.on('shown.bs.modal', function() {
            dialog.password_input.focus();
        });
        dialog.modal.find('form').unbind().submit(function(e) {
            ok_func();
            e.preventDefault();
        });
        dialog.modal.modal('show');
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
