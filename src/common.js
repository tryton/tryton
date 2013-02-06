/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.common = {};

    Sao.common.compare = function(arr1, arr2) {
        return (jQuery(arr1).not(arr2).length === 0 &&
                jQuery(arr2).not(arr1).length === 0);
    };

    Sao.common.selection = function(title, values, alwaysask) {
        if (alwaysask === undefined) {
            alwaysask = false;
        }
        if ((Object.keys(values).length == 1) && (!alwaysask)) {
            var prm = jQuery.Deferred();
            var key = Object.keys(values)[0];
            prm.resolve(values[key]);
            return prm;
        }
        // TODO
    };

    Sao.common.date_format = function() {
        // TODO
        // http://stackoverflow.com/questions/2678230/how-to-getting-browser-current-locale-preference-using-javascript
        return '%m/%d/%Y';
    };

    Sao.common.text_to_float_time = function(text, conversion, digit) {
        // TODO
        return text;
    };

    Sao.common.EvalEnvironment = function(parent_, eval_type) {
        if (eval_type === undefined)
            eval_type = 'eval';
        var environment;
        if (eval_type == 'eval') {
            environment = parent_.get_eval();
        } else {
            environment = {};
            for (var key in parent_.fields) {
                var field = parent_.fields[field];
                environment[key] = field.get_on_change_value(parent_);
            }
        }
        environment.id = parent_.id;
        if (parent_.parent)
            Object.defineProperty(environment, '_parent_' +
                    parent_.parent_name, {
                'enumerable': true,
                'get': function() {
                    return Sao.common.EvalEnvironment(parent_.parent,
                        eval_type);
                }
            });
        environment.get = function(item, default_) {
            if (this.hasOwnProperty(item))
                return this[item];
            return default_;
        };

        return environment;
    };
}());
