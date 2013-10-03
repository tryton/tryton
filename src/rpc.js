/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.rpc = function(args, session) {
        var dfd = jQuery.Deferred();
        if (!session) {
            session = new Sao.Session();
        }
        var params = jQuery.extend([], args.params);
        params.push(jQuery.extend({}, session.context, params.pop()));

        var ajax_prm = jQuery.ajax({
            'contentType': 'application/json',
            'data': JSON.stringify(Sao.rpc.prepareObject({
                'method': args.method,
                'params': [session.user_id, session.session].concat(params)
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
                    Sao.Session.renew(session).then(function() {
                        Sao.rpc(args, session).then(dfd.resolve, dfd.reject);
                    }, dfd.reject);
                    return;
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
           (typeof(value) != 'number') && (value !== null)) {
           if (value && value.__class__) {
               switch (value.__class__) {
                   case 'datetime':
                       value = Sao.DateTime(Date.UTC(value.year,
                               value.month - 1, value.day, value.hour,
                               value.minute, value.second));
                       break;
                   case 'date':
                       value = Sao.Date(value.year,
                           value.month - 1, value.day);
                       break;
                   case 'time':
                       value = new Sao.Time(value.hour, value.minute,
                               value.second);
                       break;
                   case 'buffer':
                       // javascript's atob does not understand linefeed
                       // characters
                       var byte_string = atob(value.base64.replace(/\s/g, ''));
                       // javascript decodes base64 string as a "DOMString", we
                       // need to convert it to an array of bytes
                       var array_buffer = new ArrayBuffer(byte_string.length);
                       var uint_array = new Uint8Array(array_buffer);
                       for (var j=0; j < byte_string.length; j++) {
                           uint_array[j] = byte_string.charCodeAt(j);
                       }
                       value = uint_array;
                       break;
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
        } else if ((typeof(value) != 'string') &&
                (typeof(value) != 'number') && (value !== null)) {
            if (value instanceof Date) {
                if (value.isDate){
                    value = {
                        '__class__': 'date',
                        'year': value.getFullYear(),
                        'month': value.getMonth() + 1,
                        'day': value.getDate()
                    };
                } else {
                    value = {
                        '__class__': 'datetime',
                        'year': value.getUTCFullYear(),
                        'month': value.getUTCMonth() + 1,
                        'day': value.getUTCDate(),
                        'hour': value.getUTCHours(),
                        'minute': value.getUTCMinutes(),
                        'second': value.getUTCSeconds()
                    };
                }
                if (parent) {
                    parent[index] = value;
                }
            } else if (value instanceof Sao.Time) {
                value = {
                    '__class__': 'time',
                    'hour': value.getHours(),
                    'minute': value.getMinutes(),
                    'second': value.getSeconds()
                };
            } else if (value instanceof Sao.Decimal) {
                value = {
                    '__class__': 'Decimal',
                    'decimal': value.valueOf()
                };
                if (parent) {
                    parent[index] = value;
                }
            } else if (value instanceof Uint8Array) {
                value = {
                    '__class__': 'buffer',
                    'base64': btoa(String.fromCharCode.apply(null, value))
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
