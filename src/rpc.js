/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.rpc = function(args, session) {
        var dfd = jQuery.Deferred();
        if (!session) {
            session = new Sao.Session();
        }

        var ajax_prm = jQuery.ajax({
            'contentType': 'application/json',
            'data': JSON.stringify(Sao.rpc.prepareObject({
                'method': args.method,
                'params': [session.user_id, session.session].concat(args.params)
            })),
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

    Sao.rpc.convertJSONObject = function(value, index, parent) {
       if (value instanceof Array) {
           for (var i = 0, length = value.length; i < length; i++) {
               Sao.rpc.convertJSONObject(value[i], i, value);
           }
       } else if ((typeof(value) != 'string') &&
           (typeof(value) != 'number')) {
           if (value && value.__class__) {
               switch (value.__class__) {
                   case 'datetime':
                       value = new Date(Date.UTC(value.year,
                               value.month - 1, value.day, value.hour,
                               value.minute, value.second));
                       break;
                   case 'date':
                       value = new Date(value.year,
                           value.month - 1, value.day);
                       break;
                   case 'time':
                       throw new Error('Time support not implemented');
                   case 'buffer':
                       throw new Error('Buffer support not implemented');
                   case 'Decimal':
                       value = new Sao.Decimal(value.decimal);
                       break;
               }
               if (parent) {
                   parent[index] = value;
               }
           } else {
               for (var p in value) {
                   Sao.rpc.convertJSONObject(value[p], p, value);
               }
           }
       }
       return parent || value;
    };

    Sao.rpc.prepareObject = function(value, index, parent) {
        if (value instanceof Array) {
            for (var i = 0, length = value.length; i < length; i++) {
                Sao.rpc.prepareObject(value[i], i, value);
            }
        } else if ((typeof(value) != 'string') && (typeof(value) != 'number')) {
            if (value instanceof Date) {
                if (value.getHours() || value.getMinutes() || value.getSeconds)
                {
                    value = {
                        '__class__': 'datetime',
                        'year': value.getUTCFullYear(),
                        'month': value.getUTCMonth() + 1,
                        'day': value.getUTCDate(),
                        'hour': value.getUTCHours(),
                        'minute': value.getUTCMinutes(),
                        'second': value.getUTCSeconds()
                    };
                } else {
                    value = {
                        '__class__': 'date',
                        'year': value.getFullYear(),
                        'month': value.getMonth() + 1,
                        'day': value.getDate()
                    };
                }
                if (parent) {
                    parent[index] = value;
                }
            } else if (value instanceof Sao.Decimal) {
                value = {
                    '__class__': 'Decimal',
                    'decimal': value.valueOf()
                };
                if (parent) {
                    parent[index] = value;
                }
            } else {
                for (var p in value) {
                    Sao.rpc.prepareObject(value[p], p, value);
                }
            }
        }
        return parent || value;
    };

    jQuery.ajaxSetup({
        converters: {
           'text json': function(json) {
               return Sao.rpc.convertJSONObject(jQuery.parseJSON(json));
           }
        }
    });
}());
