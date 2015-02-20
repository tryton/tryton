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

        var timeoutID = Sao.common.processing.show();
        var ajax_prm = jQuery.ajax({
            'contentType': 'application/json',
            'data': JSON.stringify(Sao.rpc.prepareObject({
                'method': args.method,
                'params': [session.user_id, session.session].concat(params)
            })),
            'dataType': 'json',
            'url': '/' + (session.database || ''),
            'type': 'post',
            'complete': [function() {
                Sao.common.processing.hide(timeoutID);
            }]
        });

        var ajax_success = function(data) {
            if (data === null) {
                Sao.common.warning.run('', 'Unable to reach the server');
                dfd.reject();
            } else if (data.error) {
                var name, msg, description;
                if (data.error[0] == 'UserWarning') {
                    name = data.error[1];
                    msg = data.error[2];
                    description = data.error[3];
                    Sao.common.userwarning.run(description, msg)
                        .done(function(result) {
                            if (!~['always', 'ok'].indexOf(result)) {
                                dfd.reject();
                                return;
                            }
                            Sao.rpc({
                                'method': 'model.res.user.warning.create',
                                'params': [[{
                                    'user': session.user_id,
                                    'name': name,
                                    'always': result == 'always'
                                }], {}]
                            }, session).done(function() {
                                Sao.rpc(args, session).then(
                                    dfd.resolve, dfd.reject);
                            });
                        });
                    return;
                } else if (data.error[0] == 'UserError') {
                    msg = data.error[1];
                    description = data.error[2];
                    Sao.common.warning.run(description, msg)
                        .always(dfd.reject);
                    return;
                } else if (data.error[0] == 'ConcurrencyException') {
                    if (args.method.startsWith('model.') &&
                            (args.method.endsWith('.write') ||
                             args.method.endsWith('.delete'))) {
                        var model = args.method.split('.').slice(1, -1).join('.');
                        Sao.common.concurrency.run( model, args.params[1][0],
                                args.params[-1])
                            .then(function() {
                                delete args.params[-1]._timestamp;
                                Sao.rpc(args, session).then(
                                    dfd.resolve, dfd.reject);
                            }, dfd.reject);
                        return;
                    } else {
                        Sao.common.message.run('Concurrency Exception',
                                'glyphicon-alert').always(dfd.reject);
                        return;
                    }
                } else if (data.error[0] == 'NotLogged') {
                    //Try to relog
                    Sao.Session.renew(session).then(function() {
                        Sao.rpc(args, session).then(dfd.resolve, dfd.reject);
                    }, dfd.reject);
                    return;
                } else {
                    Sao.common.error.run(data.error[0], data.error[1]);
                }
                dfd.reject();
            } else {
                dfd.resolve(data.result);
            }
        };

        var ajax_error = function(query, status_, error) {
            Sao.common.error.run(status_, error);
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
                       value = Sao.DateTime(value.year,
                               value.month - 1, value.day, value.hour,
                               value.minute, value.second,
                               value.microsecond / 1000, true);
                       break;
                   case 'date':
                       value = Sao.Date(value.year,
                           value.month - 1, value.day);
                       break;
                   case 'time':
                       value = Sao.Time(value.hour, value.minute,
                               value.second, value.microsecond / 1000);
                       break;
                    case 'timedelta':
                       value = Sao.TimeDelta(null, value.seconds);
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
                (typeof(value) != 'number') &&
                (value !== null) &&
                (value !== undefined)) {
            if (value.isDate){
                value = {
                    '__class__': 'date',
                    'year': value.year(),
                    'month': value.month() + 1,
                    'day': value.date()
                };

                if (parent) {
                    parent[index] = value;
                }
            } else if (value.isDateTime) {
                value = value.clone();
                value = {
                    '__class__': 'datetime',
                    'year': value.utc().year(),
                    'month': value.utc().month() + 1,
                    'day': value.utc().date(),
                    'hour': value.utc().hour(),
                    'minute': value.utc().minute(),
                    'second': value.utc().second(),
                    'microsecond': value.utc().millisecond() * 1000
                };
                if (parent) {
                    parent[index] = value;
                }
            } else if (value.isTime) {
                value = {
                    '__class__': 'time',
                    'hour': value.hour(),
                    'minute': value.minute(),
                    'second': value.second(),
                    'microsecond': value.millisecond() * 1000
                };
            } else if (value.isTimeDelta) {
                value = {
                    '__class__': 'timedelta',
                    'seconds': value.asSeconds()
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
