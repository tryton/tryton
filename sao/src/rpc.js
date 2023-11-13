/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.rpc = function(args, session=null, async=true, process_exception=true) {
        var dfd = jQuery.Deferred(),
            result;
        if (!session) {
            session = new Sao.Session();
        }
        var params = jQuery.extend([], args.params);
        params.push(jQuery.extend({}, session.context, params.pop()));

        if (session.cache && session.cache.cached(args.method)) {
            result = session.cache.get(
                args.method,
                JSON.stringify(Sao.rpc.prepareObject(params)));
            if (result !== undefined) {
                if (async) {
                    return jQuery.when(result);
                } else {
                    return result;
                }
            }
        }

        var timeoutID = Sao.common.processing.show();
        const id_ = Sao.rpc.id++;

        var ajax_success = function(data, status_, query) {
            if (data === null) {
                Sao.common.warning.run('',
                        Sao.i18n.gettext('Unable to reach the server.'))
                    .always(dfd.reject);
            } else if (data.id != id_) {
                Sao.common.warning.run('',
                    Sao.i18n.gettext(
                        `Invalid response id (${data.id}) expected ${id_}`))
                    .always(dfd.reject);
            } else if (data.error && !process_exception) {
                console.debug(`RPC error calling ${args}: ${data.error[0]}: ${data.error[1]}.`);
                dfd.reject(data.error);
            } else if (data.error && process_exception) {
                var name, msg, description;
                if (data.error[0] == 'UserWarning') {
                    name = data.error[1][0];
                    msg = data.error[1][1];
                    description = data.error[1][2];
                    Sao.common.userwarning.run(description, msg)
                        .then(function(result) {
                            if (!~['always', 'ok'].indexOf(result)) {
                                dfd.reject();
                                return;
                            }
                            Sao.rpc({
                                'method': 'model.res.user.warning.skip',
                                'params': [name, result == 'always', {}],
                            }, session).done(function() {
                                if (async) {
                                    Sao.rpc(args, session).then(
                                        dfd.resolve, dfd.reject);
                                } else {
                                    dfd.resolve();
                                }
                            });
                        }, dfd.reject);
                } else if (data.error[0] == 'UserError') {
                    msg = data.error[1][0];
                    description = data.error[1][1];
                    var domain = data.error[1][2];
                    if (!jQuery.isEmptyObject(domain)) {
                        var fields = domain[1];
                        domain = domain[0];
                        var domain_parser = new Sao.common.DomainParser(fields);
                        if (domain_parser.stringable(domain)) {
                            description += '\n' + domain_parser.string(domain);
                        }
                    }
                    Sao.common.warning.run(description, msg)
                        .always(dfd.reject);
                } else if (data.error[0] == 'ConcurrencyException') {
                    if (async &&
                        args.method.startsWith('model.') &&
                        (args.method.endsWith('.write') ||
                            args.method.endsWith('.delete')) &&
                        (args.params[0].length == 1)) {
                        var model = args.method.split('.').slice(1, -1).join('.');
                        Sao.common.concurrency.run(model, args.params[0][0],
                                args.params.slice(-1)[0])
                            .then(function() {
                                delete args.params.slice(-1)[0]._timestamp;
                                Sao.rpc(args, session).then(
                                    dfd.resolve, dfd.reject);
                            }, dfd.reject);
                    } else {
                        Sao.common.message.run('Concurrency Exception',
                                'tryton-warning').always(dfd.reject);
                    }
                } else {
                    Sao.common.error.run(data.error[0], data.error[1])
                        .always(dfd.reject);
                }
            } else {
                result = data.result;
                if (session.cache) {
                    var cache = query.getResponseHeader('X-Tryton-Cache');
                    if (cache) {
                        cache = parseInt(cache, 10);
                        session.cache.set(
                            args.method,
                            JSON.stringify(Sao.rpc.prepareObject(params)),
                            cache,
                            result);
                    }
                }
                dfd.resolve(result);
            }
        };

        var ajax_error = function(query, status_, error) {
            if (!process_exception) {
                console.debug(`RPC error calling ${args}: ${status_}: ${error}.`);
                dfd.reject();
                return;
            }
            if (query.status == 401) {
                //Try to relog
                Sao.Session.renew(session).then(function() {
                    if (async) {
                        Sao.rpc(args, session, async, process_exception)
                            .then(dfd.resolve, dfd.reject);
                    } else {
                        dfd.resolve();
                    }
                }, dfd.reject);
            } else {
                var err_msg = `[${query.status}] ${error}`;
                Sao.common.message.run(
                    Sao.i18n.gettext('Error: "%1". Try again later.', err_msg),
                    'tryton-error').always(dfd.reject);
            }
        };

        jQuery.ajax({
            'async': async,
            'headers': {
                'Authorization': 'Session ' + session.get_auth()
            },
            'contentType': 'application/json',
            'data': JSON.stringify(Sao.rpc.prepareObject({
                'id': id_,
                'method': args.method,
                'params': params
            })),
            'dataType': 'json',
            'url': '/' + (session.database || '') + '/',
            'type': 'post',
            'complete': [function() {
                Sao.common.processing.hide(timeoutID);
            }],
            'success': ajax_success,
            'error': ajax_error,
        });
        if (async) {
            return dfd.promise();
        } else if (result === undefined) {
            throw dfd;
        } else {
            return result;
        }
    };

    Sao.rpc.id = 0;

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
                               Math.ceil(value.microsecond / 1000), true);
                       break;
                   case 'date':
                       value = Sao.Date(value.year,
                           value.month - 1, value.day);
                       break;
                   case 'time':
                       value = Sao.Time(value.hour, value.minute,
                           value.second, Math.ceil(value.microsecond / 1000));
                       break;
                    case 'timedelta':
                       value = Sao.TimeDelta(null, value.seconds);
                       break;
                   case 'bytes':
                       value = Sao.common.atob(value);
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
            value = jQuery.extend([], value);
            for (var i = 0, length = value.length; i < length; i++) {
                Sao.rpc.prepareObject(value[i], i, value);
            }
        } else if ((typeof(value) != 'string') &&
                (typeof(value) != 'number') &&
                (typeof(value) != 'boolean') &&
                (value !== null) &&
                (value !== undefined)) {
            if (value.isDate){
                value = {
                    '__class__': 'date',
                    'year': value.year(),
                    'month': value.month() + 1,
                    'day': value.date()
                };
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
                    'decimal': value.toString()
                };
            } else if (value instanceof Uint8Array) {
                value = {
                    '__class__': 'bytes',
                    'base64': Sao.common.btoa(value),
                };
            } else {
                value = jQuery.extend({}, value);
                for (var p in value) {
                    Sao.rpc.prepareObject(value[p], p, value);
                }
            }
        }
        if (parent) {
            parent[index] = value;
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
