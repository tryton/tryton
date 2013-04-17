/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.Action = {};

    Sao.Action.exec_action = function(action, data, context) {
        if (context === undefined) {
            context = {};
        }
        if (data === undefined) {
            data = {};
        } else {
            data = jQuery.extend({}, data);
        }
        switch (action.type) {
            case 'ir.action.act_window':
                var params = {};
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
                    active_model: data.res_model,
                    active_id: data.id || false,
                    active_ids: data.ids
                };
                var session = Sao.Session.current_session;
                ctx = jQuery.extend(ctx, session.context);
                var eval_ctx = jQuery.extend({}, ctx);
                eval_ctx._user = session.user_id;
                params.action_ctx = new Sao.PYSON.Decoder(eval_ctx).decode(
                        action.pyson_context || '{}');
                ctx = jQuery.extend(ctx, params.action_ctx);
                ctx = jQuery.extend(ctx, context);

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
                params.auto_refresh = action.auto_refresh;
                params.icon = action['icon.rec_name'] || '';
                Sao.Tab.create(params);
                return;
            case 'ir.action.wizard':
                return;
            case 'ir.action.report':
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
            // TODO translation
            var prm = Sao.common.selection('Select your action', keyact,
                    alwaysask);
            return prm.then(function(action) {
                Sao.Action.exec_action(action, data, context);
            }, function() {
                if (jQuery.isEmptyObject(keyact) && warning) {
                    // TODO translation
                    alert('No action defined!');
                }
            });
        };
        return prm.pipe(exec_action);
    };

    Sao.Action.evaluate = function(action, atype, record) {
        action = jQuery.extend({}, action);
        switch (atype) {
            case 'print':
            case 'action':
                // TODO
                break;
            case 'relate':
                // TODO
                break;
            default:
                throw new Error('Action type ' + atype + ' is not supported');
        }
        return action;
    };
}());
