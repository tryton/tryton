/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
'use strict';

Sao.rpc = function(args, session) {
    var dfd = jQuery.Deferred();
    if (!session) {
        session = new Sao.Session();
    }

    var ajax_prm = jQuery.ajax({
        'contentType': 'application/json',
        'data': JSON.stringify({
            'method': args.method,
            'params': [session.user_id, session.session].concat(args.params)
        }),
        'dataType': 'json',
        'url': '/' + (session.database || ''),
        'type': 'post'
    });

    var ajax_success = function(data) {
        if (data === null) {
            Sao.warning('Unable to reach the server');
            dfd.reject();
        } else if (data.error) {
            if (data.error[0] == 'UserWarning') {
            } else if (data.error[0] == 'UserError') {
                // TODO
            } else if (data.error[0] == 'ConcurrencyException') {
                // TODO
            } else if (data.error[0] == 'NotLogged') {
                //Try to relog
                var cred_prm = jQuery.Deferred();
                Sao.Session.renew_credentials(session, cred_prm);
                cred_prm.done(function() {
                    Sao.rpc(session, args, dfd);
                });
                cred_prm.fail(dfd.reject);
            } else {
                console.log('ERROR');
                Sao.error(data.error[0], data.error[1]);
            }
            dfd.reject();
        } else {
            dfd.resolve(data.result);
        }
    };

    var ajax_error = function() {
        console.log('ERROR');
        dfd.reject();
    };
    ajax_prm.success(ajax_success);
    ajax_prm.error(ajax_error);

    return dfd.promise();
};
