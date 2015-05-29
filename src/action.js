/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.Action = {
        report_blob_url: undefined
    };

    Sao.Action.exec_action = function(action, data, context) {
        if (context === undefined) {
            context = {};
        }
        if (data === undefined) {
            data = {};
        } else {
            data = jQuery.extend({}, data);
        }
        data.action_id = action.id;
        var params = {};
        switch (action.type) {
            case 'ir.action.act_window':
                params.view_ids = false;
                params.view_mode = null;
                if (!jQuery.isEmptyObject(action.views)) {
                    params.view_ids = [];
                    params.view_mode = [];
                    action.views.forEach(function(x) {
                        params.view_ids.push(x[0]);
                        params.view_mode.push(x[1]);
                    });
                } else if (!jQuery.isEmptyObject(action.view_id)) {
                    params.view_ids = [action.view_id[0]];
                }

                if (action.pyson_domain === undefined) {
                    action.pyson_domain = '[]';
                }
                var ctx = {
                    active_model: data.model || null,
                    active_id: data.id || null,
                    active_ids: data.ids
                };
                var session = Sao.Session.current_session;
                ctx = jQuery.extend(ctx, session.context);
                var eval_ctx = jQuery.extend({}, ctx);
                eval_ctx._user = session.user_id;
                params.context = new Sao.PYSON.Decoder(eval_ctx).decode(
                        action.pyson_context || '{}');
                ctx = jQuery.extend(ctx, params.context);
                ctx = jQuery.extend(ctx, context);
                params.context = jQuery.extend(params.context, context);
                if (!('date_format' in params.context)) {
                    if (session.context.locale && session.context.locale.date) {
                        params.context.date_format = session.context.locale.date;
                    }
                }

                var domain_context = jQuery.extend({}, ctx);
                domain_context.context = ctx;
                domain_context._user = session.user_id;
                params.domain = new Sao.PYSON.Decoder(domain_context).decode(
                        action.pyson_domain);

                var search_context = jQuery.extend({}, ctx);
                search_context.context = ctx;
                search_context._user = session.user_id;
                params.search_value = new Sao.PYSON.Decoder(search_context)
                    .decode(action.pyson_search_value || '[]');

                var tab_domain_context = jQuery.extend({}, ctx);
                tab_domain_context.context = ctx;
                tab_domain_context._user = session.user_id;
                var decoder = new Sao.PYSON.Decoder(tab_domain_context);
                params.tab_domain = [];
                action.domains.forEach(function(element, index) {
                    params.tab_domain.push(
                        [element[0], decoder.decode(element[1])]);
                });
                params.name = false;
                if (action.window_name) {
                    params.name = action.name;
                }
                params.model = action.res_model || data.res_model;
                params.res_id = action.res_id || data.res_id;
                params.limit = action.limit;
                params.icon = action['icon.rec_name'] || '';
                Sao.Tab.create(params);
                return;
            case 'ir.action.wizard':
                params.action = action.wiz_name;
                params.data = data;
                params.name = action.name;
                params.context = context;
                params.window = action.window;
                Sao.Wizard.create(params);
                return;
            case 'ir.action.report':
                params.name = action.report_name;
                params.data = data;
                params.direct_print = action.direct_print;
                params.email_print = action.email_print;
                params.email = action.email;
                params.context = context;
                Sao.Action.exec_report(params);
                return;
            case 'ir.action.url':
                window.open(action.url, '_blank');
                return;
        }
    };

    Sao.Action.exec_keyword = function(keyword, data, context, warning,
            alwaysask)
    {
        if (warning === undefined) {
            warning = true;
        }
        if (alwaysask === undefined) {
            alwaysask = false;
        }
        var actions = [];
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
                keyact[action.name.replace(/_/g, '')] = action;
            }
            var prm = Sao.common.selection(
                    Sao.i18n.gettext('Select your action'),
                    keyact, alwaysask);
            return prm.then(function(action) {
                Sao.Action.exec_action(action, data, context);
            }, function() {
                if (jQuery.isEmptyObject(keyact) && warning) {
                    alert(Sao.i18n.gettext('No action defined!'));
                }
            });
        };
        return prm.pipe(exec_action);
    };

    Sao.Action.exec_report = function(attributes) {
        if (!attributes.context) {
            attributes.context = {};
        }
        if (!attributes.email) {
            attributes.email = {};
        }
        var data = jQuery.extend({}, attributes.data);
        var context = jQuery.extend({}, Sao.Session.current_session.context);
        jQuery.extend(context, attributes.context);
        context.direct_print = attributes.direct_print;
        context.email_print = attributes.email_print;
        context.email = attributes.email;

        var prm = Sao.rpc({
            'method': 'report.' + attributes.name + '.execute',
            'params': [data.ids || [], data, context]
        }, Sao.Session.current_session);
        prm.done(function(result) {
            var report_type = result[0];
            var data = result[1];
            var print = result[2];
            var name = result[3];

            // TODO direct print
            var blob = new Blob([data],
                {type: Sao.common.guess_mimetype(report_type)});
            var blob_url = window.URL.createObjectURL(blob);
            if (Sao.Action.report_blob_url) {
                window.URL.revokeObjectURL(Sao.Action.report_blob_url);
            }
            Sao.Action.report_blob_url = blob_url;
            window.open(blob_url);
        });
    };

    Sao.Action.execute = function(id, data, type, context) {
        if (!type) {
            Sao.rpc({
                'method': 'model.ir.action.read',
                'params': [[id], ['type'], context]
            }, Sao.Session.current_session).done(function(result) {
                Sao.Action.execute(id, data, result[0].type, context);
            });
        } else {
            Sao.rpc({
                'method': 'model.' + type + '.search_read',
                'params': [[['action', '=', id]], 0, 1, null, null, context]
            }, Sao.Session.current_session).done(function(result) {
                Sao.Action.exec_action(result[0], data, context);
            });
        }
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
