/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.common = {};

    Sao.common.BACKSPACE_KEYCODE = 8;
    Sao.common.TAB_KEYCODE = 9;
    Sao.common.RETURN_KEYCODE = 13;
    Sao.common.DELETE_KEYCODE = 46;
    Sao.common.F2_KEYCODE = 113;
    Sao.common.F3_KEYCODE = 114;

    Sao.common.compare = function(arr1, arr2) {
        if (arr1.length != arr2.length) {
            return false;
        }
        for (var i = 0; i < arr1.length; i++) {
            if (arr1[i] instanceof Array && arr2[i] instanceof Array) {
                if (!Sao.common.compare(arr1[i], arr2[i])) {
                    return false;
                }
            } else if (arr1[i] != arr2[i]) {
                return false;
            }
        }
        return true;
    };

    // Find the intersection of two arrays.
    // The arrays must be sorted.
    Sao.common.intersect = function(a, b) {
        var ai = 0, bi = 0;
        var result = [];
        while (ai < a.length && bi < b.length) {
            if (a[ai] < b[bi]) {
                ai++;
            } else if (a[ai] > b[bi]) {
                bi++;
            } else {
                result.push(a[ai]);
                ai++;
                bi++;
            }
        }
        return result;
    };

    Sao.common.selection = function(title, values, alwaysask) {
        if (alwaysask === undefined) {
            alwaysask = false;
        }
        var prm = jQuery.Deferred();
        if ((Object.keys(values).length == 1) && (!alwaysask)) {
            var key = Object.keys(values)[0];
            prm.resolve(values[key]);
            return prm;
        }
        // TODO
        return prm.fail();
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
            for (var key in parent_.model.fields) {
                var field = parent_.model.fields[key];
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

    Sao.common.selection_mixin = {};
    Sao.common.selection_mixin.init = function() {
        this.selection = null;
        this._last_domain = null;
        this._values2selection = {};
        this._domain_cache = {};
    };
    Sao.common.selection_mixin.init_selection = function(key, callback) {
        if (!key) {
            key = [];
            (this.attributes.selection_change_with || []).forEach(function(e) {
                key.push([e, null]);
            });
            key.sort();
        }
        var selection = jQuery.extend([], this.attributes.selection || []);
        var prepare_selection = function(selection) {
            if (this.attributes.sort === undefined || this.attributes.sort) {
                selection.sort(function(a, b) {
                    return a[1].localeCompare(b[1]);
                });
            }
            this.selection = jQuery.extend([], selection);
            if (callback) callback(this.selection);
        };
        if (!(selection instanceof Object) &&
                !(key in this._values2selection)) {
            var prm;
            if (key) {
                var params = {};
                key.forEach(function(e) {
                    params[e[0]] = e[1];
                });
                prm = this.model.execute(selection, [params], {});
            } else {
                prm = this.model.execute(selection, [], {});
            }
            prm.pipe(prepare_selection.bind(this));
            prm.pipe(this.set_selection.bind(this));
        } else {
            if (key in this._values2selection) {
                selection = this._values2selection.selection;
            }
            prepare_selection.call(this, selection);
        }
    };
    Sao.common.selection_mixin.update_selection = function(record, field,
            callback) {
        if (!field) {
            return;
        }
        if (!('relation' in this.attributes)) {
            var change_with = this.attributes.selection_change_with || [];
            var key = [];
            var args = record._get_on_change_args(change_with);
            for (var k in args) {
                key.push([k, args[k]]);
            }
            key.sort();
            Sao.common.selection_mixin.init_selection.call(this, key,
                    callback);
        } else {
            var domain = field.get_domain(record);
            var jdomain = JSON.stringify(domain);
            if (jdomain in this._domain_cache) {
                this.selection = this._domain_cache[jdomain];
                this._last_domain = domain;
            }
            if ((this._last_domain !== null) &&
                    Sao.common.compare(domain, this._last_domain)) {
                return;
            }
            var prm = Sao.rpc({
                'method': 'model.' + this.attributes.relation + '.search_read',
                'params': [domain, 0, null, null, ['rec_name'], {}]
            }, record.model.session);
            prm.done(function(result) {
                var selection = [];
                result.forEach(function(x) {
                    selection.push([x.id, x.rec_name]);
                });
                selection.push([null, '']);
                this._last_domain = domain;
                this._domain_cache[jdomain] = selection;
                this.selection = jQuery.extend([], selection);
                if (callback) {
                    callback(this.selection);
                }
            }.bind(this));
            prm.fail(function() {
                this._last_domain = null;
                this.selection = [];
                if (callback) {
                    callback(this.selection);
                }
            }.bind(this));
        }
    };

    Sao.common.Button = Sao.class_(Object, {
        init: function(attributes) {
            this.attributes = attributes;
            this.el = jQuery('<button/>').button({
                text: true,
                label: attributes.string || ''
            });
            // TODO icon
        },
        set_state: function(record) {
            var states;
            if (record) {
                states = record.expr_eval(this.attributes.states || {});
            } else {
                states = {};
            }
            if (states.invisible) {
                this.el.hide();
            } else {
                this.el.show();
            }
            this.el.prop('disabled', states.readonly);
            // TODO icon
            if (record) {
                var parent = record.group.parent;
                while (parent) {
                    if (parent.has_changed()) {
                        this.el.prop('disabled', false);
                        break;
                    }
                    parent = parent.group.parent;
                }
            }
        }
    });
}());
