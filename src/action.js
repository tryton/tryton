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
                // TODO context, domain, search, tab_domain
                params.name = false;
                if (action.window_name) {
                    params.name = action.name;
                }
                params.model = action.res_model || data.res_model;
                params.res_id = action.res_id || data.res_id;
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
            prm.done(function(action) {
                Sao.Action.exec_action(action, data, context);
            });
            prm.fail(function() {
                if (jQuery.isEmptyObject(keyact) && warning) {
                    // TODO translation
                    alert('No action defined!');
                }
            });
            return prm;
        };
        return prm.pipe(exec_action);
    };
}());
