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
            var timeoutID = Sao.common.processing.show();
            var args = {
                'method': 'common.db.login',
                'params': [login, password]
            };
            var ajax_prm = jQuery.ajax({
                'contentType': 'application/json',
                'data': JSON.stringify(args),
                'dataType': 'json',
                'url': '/' + this.database,
                'type': 'post',
                'complete': [function() {
                    Sao.common.processing.hide(timeoutID);
                }]
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
        dialog.password_input = jQuery('<input/>', {
            'class': 'form-control',
            'type': 'password',
            'id': 'login-password',
            'placeholder': Sao.i18n.gettext('Password')
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
        ).append(jQuery('<div/>', {
            'class': 'form-group'
        }).append(jQuery('<label/>', {
            'class': 'control-label',
            'for': 'login-password'
        }).append(Sao.i18n.gettext('Password')))
        .append(dialog.password_input));
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
            var password = dialog.password_input.val();
            var database = database || dialog.database_select.val() ||
                dialog.database_input.val();
            dialog.modal.find('.has-error').removeClass('has-error');
            if (!(login && password && database)) {
                empty_field().closest('.form-group').addClass('has-error');
                return;
            }
            dialog.button.focus();
            dialog.button.prop('disabled', true);
            var session = new Sao.Session(database, login);
            session.do_login(login, password)
                .then(function() {
                    dfd.resolve(session);
                    dialog.modal.remove();
                }, function() {
                    dialog.button.prop('disabled', false);
                    dialog.password_input.val('');
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
            if (jQuery.isEmptyObject(databases)) {
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
            el.show();
            el.val(database || '');
            empty_field().first().focus();
        });
        return dfd.promise();
    };

    Sao.Session.password_dialog = function() {
        var dialog = new Sao.Dialog(Sao.i18n.gettext('Password'), 'lg');
        dialog.password_input = jQuery('<input/>', {
            'class': 'form-control',
            'type': 'password',
            'id': 'password-password',
            'placeholder': Sao.i18n.gettext('Password')
        });
        dialog.body.append(jQuery('<div/>', {
            'class': 'form-group'
        }).append(jQuery('<label/>', {
            'for': 'password-password'
        }).append(Sao.i18n.gettext('Password')))
        .append(dialog.password_input));
        dialog.button = jQuery('<button/>', {
            'class': 'btn btn-primary',
            'type': 'submit'
        }).append(Sao.i18n.gettext('OK')).appendTo(dialog.footer);
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
            dialog.button.focus();
            dialog.button.prop('disabled', true);
            session.do_login(session.login, password)
                .then(function() {
                    dfd.resolve();
                    dialog.modal.remove();
                }, function() {
                    dialog.button.prop('disabled', false);
                    dialog.password_input.val('').focus();
                });
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
        var timeoutID = Sao.common.processing.show();
        return jQuery.ajax({
            'contentType': 'application/json',
            'data': JSON.stringify({
                'method': 'common.db.list',
                'params': [null, null]
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
