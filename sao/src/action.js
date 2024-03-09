/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.Action = {
        report_blob_url: undefined
    };

    Sao.Action.exec_action = function(action, data, context) {
        if (!context) {
            context = {};
        } else {
            context = jQuery.extend({}, context);
        }
        var session = Sao.Session.current_session;
        if (data === undefined) {
            data = {};
        } else {
            data = jQuery.extend({}, data);
        }

        delete context.active_id;
        delete context.active_ids;
        delete context.active_model;

        function add_name_suffix(name, context){
            if (!data.model || !data.ids) {
                return jQuery.when(name);
            }
            var max_records = 5;
            var ids = data.ids.filter(function(id){
                return id >= 0;
            }).slice(0, max_records);
            if (!ids.length) {
                return jQuery.when(name);
            }
            return Sao.rpc({
                'method': 'model.' + data.model + '.read',
                'params': [ids, ['rec_name'], context]
            }, Sao.Session.current_session).then(function(result) {
                var name_suffix = result.map(function(record){
                    return record.rec_name;
                }).join(Sao.i18n.gettext(', '));

                if (data.ids.length > ids.length) {
                    name_suffix += Sao.i18n.gettext(',...');
                }
                if (name_suffix) {
                    return Sao.i18n.gettext('%1 (%2)', name, name_suffix);
                } else {
                    return name;
                }
            });
        }
        data.action_id = action.id;
        var params = {
            'icon': action['icon.rec_name'] || '',
        };
        var name_prm;
        switch (action.type) {
            case 'ir.action.act_window':
                if (!jQuery.isEmptyObject(action.views)) {
                    params.view_ids = [];
                    params.mode = [];
                    for (const view of action.views) {
                        params.view_ids.push(view[0]);
                        params.mode.push(view[1]);
                    }
                } else if (!jQuery.isEmptyObject(action.view_id)) {
                    params.view_ids = [action.view_id[0]];
                }

                if (action.pyson_domain === undefined) {
                    action.pyson_domain = '[]';
                }
                var ctx = {
                    active_model: data.model || null,
                    active_id: data.id || null,
                    active_ids: data.ids || [],
                };
                ctx = jQuery.extend(ctx, session.context);
                ctx._user = session.user_id;
                var decoder = new Sao.PYSON.Decoder(ctx);
                params.context = jQuery.extend(
                    {}, context,
                    decoder.decode( action.pyson_context || '{}'));
                ctx = jQuery.extend(ctx, params.context);

                ctx.context = ctx;
                decoder = new Sao.PYSON.Decoder(ctx);
                params.domain = decoder.decode(action.pyson_domain);
                params.order = decoder.decode(action.pyson_order);
                params.search_value = decoder.decode(
                    action.pyson_search_value || '[]');
                params.tab_domain = [];
                for (const element of action.domains) {
                    params.tab_domain.push(
                        [element[0], decoder.decode(element[1]), element[2]]);
                }
                name_prm = jQuery.when(action.name);
                params.model = action.res_model || data.res_model;
                params.res_id = action.res_id || data.res_id;
                params.context_model = action.context_model;
                params.context_domain = action.context_domain;
                if ((action.limit !== undefined) && (action.limit !== null)) {
                    params.limit = action.limit;
                }

                if (action.keyword) {
                    name_prm = add_name_suffix(action.name, params.context);
                }
                return name_prm.then(function(name) {
                    params.name = name;
                    return Sao.Tab.create(params);
                });
            case 'ir.action.wizard':
                params.action = action.wiz_name;
                params.data = data;
                params.context = context;
                params.window = action.window;
                name_prm = jQuery.when(action.name);
                if ((action.keyword || 'form_action') === 'form_action') {
                    name_prm = add_name_suffix(action.name, context);
                }
                return name_prm.then(function(name) {
                    params.name = name;
                    return Sao.Wizard.create(params);
                });
            case 'ir.action.report':
                params.name = action.report_name;
                params.data = data;
                params.direct_print = action.direct_print;
                params.context = context;
                return Sao.Action.exec_report(params);
            case 'ir.action.url':
                window.open(action.url, '_blank', 'noreferrer,noopener');
                return jQuery.when();
        }
    };

    Sao.Action.exec_keyword = function(
        keyword, data, context, warning=true, alwaysask=false) {
        var model_id = data.id;
        var args = {
            'method': 'model.' + 'ir.action.keyword.get_keyword',
            'params': [keyword, [data.model, model_id], {}]
        };
        var prm = Sao.rpc(args, Sao.Session.current_session);
        var exec_action = function(actions) {
            var keyact = {};
            for (var i in actions) {
                var action = actions[i];
                keyact[action.name.split(' / ').pop()] = action;
            }
            var prm = Sao.common.selection(
                    Sao.i18n.gettext('Select your action'),
                    keyact, alwaysask);
            return prm.then(function(action) {
                Sao.Action.exec_action(action, data, context);
            }, function() {
                if (jQuery.isEmptyObject(keyact) && warning) {
                    alert(Sao.i18n.gettext('No action defined.'));
                }
            });
        };
        return prm.pipe(exec_action);
    };

    Sao.Action.exec_report = function(attributes) {
        if (!attributes.context) {
            attributes.context = {};
        }
        var data = jQuery.extend({}, attributes.data);
        var context = jQuery.extend({}, Sao.Session.current_session.context);
        jQuery.extend(context, attributes.context);
        context.direct_print = attributes.direct_print;

        var prm = Sao.rpc({
            'method': 'report.' + attributes.name + '.execute',
            'params': [data.ids || [], data, context]
        }, Sao.Session.current_session);
        prm.done(function(result) {
            var report_type = result[0];
            var data = result[1];
            // TODO direct print
            var name = result[3];

            var file_name = name + '.' + report_type;
            Sao.common.download_file(data, file_name);
        });
    };

    Sao.Action.execute = function(action, data, context, keyword) {
        if (typeof action == 'number') {
            action = Sao.rpc({
                'method': 'model.ir.action.get_action_value',
                'params': [action, context],
            }, Sao.Session.current_session, false);
        }
        if (keyword) {
            var keywords = {
                'ir.action.report': 'form_report',
                'ir.action.wizard': 'form_action',
                'ir.action.act_window': 'form_relate'
            };
            if (!action.keyword) {
                action.keyword = keywords[action.type];
            }
        }
        return Sao.Action.exec_action(action, data, context);
    };

    Sao.Action.evaluate = function(action, atype, record) {
        action = jQuery.extend({}, action);
        var email = {};
        if ('pyson_email' in action) {
            email = record.expr_eval(action.pyson_email);
            if (jQuery.isEmptyObject(email)) {
                email = {};
            }
        }
        if (!('subject' in email)) {
            email.subject = action.name.replace(/_/g, '');
        }
        action.email = email;
        return action;
    };
}());
