/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.common = {};

    Sao.common.BACKSPACE_KEYCODE = 8;
    Sao.common.TAB_KEYCODE = 9;
    Sao.common.RETURN_KEYCODE = 13;
    Sao.common.UP_KEYCODE = 38;
    Sao.common.DOWN_KEYCODE = 40;
    Sao.common.DELETE_KEYCODE = 46;
    Sao.common.F2_KEYCODE = 113;
    Sao.common.F3_KEYCODE = 114;

    Sao.common.SELECTION_NONE = 1;
    Sao.common.SELECTION_SINGLE = 2;  // Not implemented yet
    Sao.common.SELECTION_MULTIPLE = 3;

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

    Sao.common.contains = function(array1, array2) {
        for (var i = 0; i < array1.length; i++) {
            if (Sao.common.compare(array1[i], array2)) {
                return true;
            }
        }
        return false;
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
        if (Sao.Session.current_session) {
            var context = Sao.Session.current_session.context;
            if (context.locale && context.locale.date) {
                return context.locale.date
                    .replace('%d', 'dd')
                    .replace('%j', 'oo')
                    .replace('%a', 'D')
                    .replace('%A', 'DD')
                    .replace('%m', 'mm')
                    .replace('%b', 'M')
                    .replace('%B', 'MM')
                    .replace('%y', 'y')
                    .replace('%Y', 'yy');
            }
        }
        return jQuery.datepicker.W3C;
    };

    Sao.common.format_time = function(format, date) {
        var pad = Sao.common.pad;
        return format.replace('%H', pad(date.getHours(), 2))
            .replace('%M', pad(date.getMinutes(), 2))
            .replace('%S', pad(date.getSeconds(), 2))
            .replace('%f', pad(date.getMilliseconds(), 3));
    };

    Sao.common.parse_time = function(format, value) {
        if (jQuery.isEmptyObject(value)) {
            return null;
        }
        var getNumber = function(pattern) {
            var i = format.indexOf(pattern);
            if (~i) {
                var number = parseInt(value.slice(i, i + pattern.length), 10);
                if (!isNaN(number)) {
                    return number;
                }
            }
            return 0;
        };
        return new Sao.Time(getNumber('%H'), getNumber('%M'), getNumber('%S'),
                getNumber('%f'));
    };

    Sao.common.format_datetime = function(date_format, time_format, date) {
        return (jQuery.datepicker.formatDate(date_format, date) + ' ' +
                Sao.common.format_time(time_format, date));
    };

    Sao.common.parse_datetime = function(date_format, time_format, value) {
        var date = Sao.DateTime(
                jQuery.datepicker.parseDate(date_format, value));
        var time_value = value.replace(jQuery.datepicker.formatDate(
                    date_format, date), '').trim();
        var time = Sao.common.parse_time(time_format, time_value);
        date.setHours(time.getHours());
        date.setMinutes(time.getMinutes());
        date.setSeconds(time.getSeconds());
        return date;
    };

    Sao.common.pad = function(number, length) {
        var str = '' + number;
        while (str.length < length) {
            str = '0' + str;
        }
        return str;
    };

    Sao.common.text_to_float_time = function(text, conversion, digit) {
        // TODO
        return text;
    };

    Sao.common.ModelAccess = Sao.class_(Object, {
        init: function() {
            this.batchnum = 100;
            this._access = {};
        },
        load_models: function(refresh) {
            var prm = jQuery.Deferred();
            if (!refresh) {
                this._access = {};
            }
            Sao.rpc({
                'method': 'model.ir.model.list_models',
                'params': [{}]
            }, Sao.Session.current_session).then(function(models) {
                var deferreds = [];
                var update_access = function(access) {
                    this._access = jQuery.extend(this._access, access);
                };
                for (var i = 0; i < models.length; i += this.batchnum) {
                    var to_load = models.slice(i, i + this.batchnum);
                    deferreds.push(Sao.rpc({
                        'method': 'model.ir.model.access.get_access',
                        'params': [to_load, {}]
                    }, Sao.Session.current_session)
                        .then(update_access.bind(this)));
                }
                jQuery.when.apply(jQuery, deferreds).then(
                    prm.resolve, prm.reject);
            }.bind(this));
            return prm;
        },
        get: function(model) {
            return this._access[model];
        }
    });
    Sao.common.MODELACCESS = new Sao.common.ModelAccess();

    Sao.common.ModelHistory = Sao.class_(Object, {
        init: function() {
            this._models = [];
        },
        load_history: function() {
            this._models = [];
            return Sao.rpc({
                'method': 'model.ir.model.list_history',
                'params': [{}]
            }, Sao.Session.current_session).then(function(models) {
                this._models = models;
            }.bind(this));
        },
        contains: function(model) {
            return ~this._models.indexOf(model);
        }
    });
    Sao.common.MODELHISTORY = new Sao.common.ModelHistory();

    Sao.common.humanize = function(size) {
        var sizes = ['bytes', 'KB', 'MB', 'GB', 'TB', 'PB'];
        for (var i =0, len = sizes.length; i < len; i++) {
            if (size < 1000) {
                return size.toPrecision(4) + ' ' + sizes[i];
            }
            size /= 1000;
        }
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
        if (parent_.group.parent)
            Object.defineProperty(environment, '_parent_' +
                    parent_.group.parent_name, {
                'enumerable': true,
                'get': function() {
                    return Sao.common.EvalEnvironment(parent_.group.parent,
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
        this.inactive_selection = [];
        this._last_domain = null;
        this._values2selection = {};
        this._domain_cache = {};
        if (this.nullable_widget === undefined) {
            this.nullable_widget = true;
        }
    };
    Sao.common.selection_mixin.init_selection = function(key, callback) {
        if (!key) {
            key = [];
            (this.attributes.selection_change_with || []).forEach(function(e) {
                key.push([e, null]);
            });
            key.sort();
        }
        var selection = this.attributes.selection || [];
        var prepare_selection = function(selection) {
            selection = jQuery.extend([], selection);
            if (this.attributes.sort === undefined || this.attributes.sort) {
                selection.sort(function(a, b) {
                    return a[1].localeCompare(b[1]);
                });
            }
            this.selection = jQuery.extend([], selection);
            if (callback) callback(this.selection);
        };
        if (!(selection instanceof Array) &&
                !(key in this._values2selection)) {
            var prm;
            if (this.attributes.selection_change_with) {
                var params = {};
                key.forEach(function(e) {
                    params[e[0]] = e[1];
                });
                prm = this.model.execute(selection, [params]);
            } else {
                prm = this.model.execute(selection, []);
            }
            prm.pipe(prepare_selection.bind(this));
        } else {
            if (key in this._values2selection) {
                selection = this._values2selection.selection;
            }
            prepare_selection.call(this, selection);
        }
        this.inactive_selection = [];
    };
    Sao.common.selection_mixin.update_selection = function(record, field,
            callback) {
        if (!field) {
            if (callback) {
                callback(this.selection);
            }
            return;
        }
        var domain = field.get_domain(record);
        if (field.description.type == 'reference') {
            // The domain on reference field is not only based on the selection
            // so the selection can not be filtered.
            domain = [];
        }
        if (!('relation' in this.attributes)) {
            var change_with = this.attributes.selection_change_with || [];
            var key = [];
            var args = record._get_on_change_args(change_with);
            delete args.id;
            for (var k in args) {
                key.push([k, args[k]]);
            }
            key.sort();
            Sao.common.selection_mixin.init_selection.call(this, key,
                    function() {
                        Sao.common.selection_mixin.filter_selection.call(this,
                            domain, record, field);
                        if (callback) {
                            callback(this.selection);
                        }
                    }.bind(this));
        } else {
            var jdomain = JSON.stringify(domain);
            if (jdomain in this._domain_cache) {
                this.selection = this._domain_cache[jdomain];
                this._last_domain = domain;
            }
            if ((this._last_domain !== null) &&
                    Sao.common.compare(domain, this._last_domain)) {
                if (callback) {
                    callback(this.selection);
                }
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
                if (this.nullable_widget) {
                    selection.push([null, '']);
                }
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
    Sao.common.selection_mixin.filter_selection = function(
            domain, record, field) {
        if (jQuery.isEmptyObject(domain)) {
            return;
        }
        var inversion = new Sao.common.DomainInversion();
        this.selection = this.selection.filter(function(value) {
            var context = {};
            context[this.field_name] = value[0];
            return inversion.eval_domain(domain, context);
        }.bind(this));
    };
    Sao.common.selection_mixin.get_inactive_selection = function(value) {
        if (!this.attributes.relation) {
            return jQuery.when([]);
        }
        for (var i = 0, len = this.inactive_selection.length; i < len; i++) {
            if (value == this.inactive_selection[i][0]) {
                return jQuery.when(this.inactive_selection[i]);
            }
        }
        var prm = Sao.rpc({
            'method': 'model.' + this.attributes.relation + '.read',
            'params': [[value], ['rec_name'], {}]
        }, Sao.Session.current_session);
        return prm.then(function(result) {
            this.inactive_selection.push([result[0].id, result[0].rec_name]);
            return [result[0].id, result[0].rec_name];
        }.bind(this));
    };

    Sao.common.Button = Sao.class_(Object, {
        init: function(attributes) {
            this.attributes = attributes;
            this.el = jQuery('<button/>').button({
                text: true,
                label: attributes.string || '',
                icons: {primary: 'ui-icon-custom', secondary: null}
            });
            this.set_icon(attributes.icon);
        },
        set_icon: function(icon_name) {
            if (!icon_name) {
                return;
            }
            var prm = Sao.common.ICONFACTORY.register_icon(icon_name);
            prm.done(function(url) {
                this.el.children('.ui-button-icon-primary').css(
                    'background-image', 'url("' + url + '")');
            }.bind(this));
        },
        set_state: function(record) {
            var states;
            if (record) {
                states = record.expr_eval(this.attributes.states || {});
                if (record.group.get_readonly() || record.readonly) {
                    states.readonly = true;
                }
            } else {
                states = {};
            }
            if (states.invisible) {
                this.el.hide();
            } else {
                this.el.show();
            }
            this.el.prop('disabled', states.readonly);
            this.set_icon(states.icon || this.attributes.icon);
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

    Sao.common.udlex = Sao.class_(Object, {
        init: function(instream) {

            var Stream = Sao.class_(Object, {
                init: function(stream) {
                    this.stream = stream.split('');
                    this.i = 0;
                },
                read: function(length) {
                    if (length === undefined) {
                        length = 1;
                    }
                    if (this.i >= this.stream.length) {
                        return null;
                    }
                    var value = this.stream
                        .slice(this.i, this.i + length).join();
                    this.i += length;
                    return value;
                }
            });
            this.instream = new Stream(instream);
            this.eof = null;
            this.commenters = '';
            this.nowordchars = [':', '>', '<', '=', '!', '"', ';', '(', ')'];
            this.whitespace = ' \t\r\n';
            this.whitespace_split = false;
            this.quotes = '"';
            this.escape = '\\';
            this.escapedquotes = '"';
            this.state = ' ';
            this.pushback = [];
            this.token = '';
        },
        get_token: function() {
            if (this.pushback.length > 0) {
                return this.pushback.shift();
            }
            var raw = this.read_token();
            return raw;
        },
        read_token: function() {
            var quoted = false;
            var escapedstate = ' ';
            while (true) {
                var nextchar = this.instream.read(1);
                if (this.state === null) {
                    this.token = '';  // past en of file
                    break;
                } else if (this.state == ' ') {
                    if (!nextchar) {
                        this.state = null;  // end of file
                        break;
                    } else if (this.whitespace.contains(nextchar)) {
                        if (this.token || quoted) {
                            break;  // emit current token
                        } else {
                            continue;
                        }
                    } else if (this.commenters.contains(nextchar)) {
                        // TODO readline
                    } else if (this.escape.contains(nextchar)) {
                        escapedstate = 'a';
                        this.state = nextchar;
                    } else if (!~this.nowordchars.indexOf(nextchar)) {
                        this.token = nextchar;
                        this.state = 'a';
                    } else if (this.quotes.contains(nextchar)) {
                        this.state = nextchar;
                    } else if (this.whitespace_split) {
                        this.token = nextchar;
                        this.state = 'a';
                    } else {
                        this.token = nextchar;
                        if (this.token || quoted) {
                            break;  // emit current token
                        } else {
                            continue;
                        }
                    }
                } else if (this.quotes.contains(this.state)) {
                    quoted = true;
                    if (!nextchar) {  // end of file
                        throw 'no closing quotation';
                    }
                    if (nextchar == this.state) {
                        this.state = 'a';
                    } else if (this.escape.contains(nextchar) &&
                        this.escapedquotes.contains(this.state)) {
                        escapedstate = this.state;
                        this.state = nextchar;
                    } else {
                        this.token = this.token + nextchar;
                    }
                } else if (this.escape.contains(this.state)) {
                    if (!nextchar) {  // end of file
                        throw 'no escaped character';
                    }
                    if (this.quotes.contains(escapedstate) &&
                        (nextchar != this.state) &&
                        (nextchar != escapedstate)) {
                        this.token = this.token + this.state;
                    }
                    this.token = this.token + nextchar;
                    this.state = escapedstate;
                } else if (this.state == 'a') {
                    if (!nextchar) {
                        this.state = null;  // end of file
                        break;
                    } else if (this.whitespace.contains(nextchar)) {
                        this.state = ' ';
                        if (this.token || quoted) {
                            break;  // emit current token
                        } else {
                            continue;
                        }
                    } else if (this.commenters.contains(nextchar)) {
                        // TODO
                    } else if (this.quotes.contains(nextchar)) {
                        this.state = nextchar;
                    } else if (this.escape.contains(nextchar)) {
                        escapedstate = 'a';
                        this.state = nextchar;
                    } else if ((!~this.nowordchars.indexOf(nextchar)) ||
                            this.quotes.contains(nextchar) ||
                            this.whitespace_split) {
                        this.token = this.token + nextchar;
                    } else {
                        this.pushback.unshift(nextchar);
                        this.state = ' ';
                        if (this.token) {
                            break;  // emit current token
                        } else {
                            continue;
                        }
                    }
                }
            }
            var result = this.token;
            this.token = '';
            if (!quoted && result === '') {
                result = null;
            }
            return result;
        },
        next: function() {
            var token = this.get_token();
            if (token == this.eof) {
                return null;
            }
            return token;
        }
    });

    Sao.common.DomainParser = Sao.class_(Object, {
        OPERATORS: ['!=', '<=', '>=', '=', '!', '<', '>'],
        init: function(fields) {
            this.fields = {};
            this.strings = {};
            for (var name in fields) {
                var field = fields[name];
                if (field.searchable || (field.searchable === undefined)) {
                    this.fields[name] = field;
                    this.strings[field.string.toLowerCase()] = field;
                }
            }
        },
        parse: function(input) {
            try {
                var lex = new Sao.common.udlex(input);
                var tokens = [];
                while (true) {
                    var token = lex.next();
                    if (token === null) {
                        break;
                    }
                    tokens.push(token);
                }
                tokens = this.group_operator(tokens);
                tokens = this.parenthesize(tokens);
                tokens = this.group(tokens);
                tokens = this.operatorize(tokens, 'or');
                tokens = this.operatorize(tokens, 'and');
                tokens = this.parse_clause(tokens);
                return this.simplify(tokens);
            } catch (e) {
                if (e == 'no closing quotation') {
                    return this.parse(input + '"');
                }
                throw e;
            }
        },
        string: function(domain) {

            var string = function(clause) {
                if (jQuery.isEmptyObject(clause)) {
                    return '';
                }
                if ((typeof clause[0] != 'string') ||
                        ~['AND', 'OR'].indexOf(clause[0])) {
                    return '(' + this.string(clause) + ')';
                }
                var escaped;
                var name = clause[0];
                var operator = clause[1];
                var value = clause[2];
                if (name.endsWith('.rec_name')) {
                    name = name.slice(0, -9);
                }
                if (!(name in this.fields)) {
                    escaped = value.replace('%%', '__');
                    if (escaped.startsWith('%') && escaped.endsWith('%')) {
                        value = value.slice(1, -1);
                    }
                    return this.quote(value);
                }
                var field = this.fields[name];
                var target = null;
                if (clause.length > 3) {
                    target = clause[3];
                }
                if (operator.contains('ilike')) {
                    escaped = value.replace('%%', '__');
                    if (escaped.startsWith('%') && escaped.endsWith('%')) {
                        value = value.slice(1, -1);
                    } else if (!escaped.contains('%')) {
                        if (operator == 'ilike') {
                            operator = '=';
                        } else {
                            operator = '!';
                        }
                        value = value.replace('%%', '%');
                    }
                }
                var def_operator = this.default_operator(field);
                if ((def_operator == operator.trim()) ||
                        (operator.contains(def_operator) &&
                         (operator.contains('not') ||
                          operator.contains('!')))) {
                    operator = operator.replace(def_operator, '')
                        .replace('not', '!').trim();
                }
                if (operator.endsWith('in')) {
                    if (operator == 'not in') {
                        operator = '!';
                    } else {
                        operator = '';
                    }
                }
                var formatted_value = this.format_value(field, value, target);
                if (~this.OPERATORS.indexOf(operator) &&
                        ~['char', 'text', 'selection']
                        .indexOf(field.type) &&
                        (value === '')) {
                    formatted_value = '""';
                }
                return (this.quote(field.string) + ': ' +
                        operator + formatted_value);
            };
            string = string.bind(this);

            if (jQuery.isEmptyObject(domain)) {
                return '';
            }
            var nary = ' ';
            if ((domain[0] == 'AND') || (domain[0] == 'OR')) {
                if (domain[0] == 'OR') {
                    nary = ' or ';
                }
                domain = domain.slice(1);
            }
            return domain.map(string).join(nary);
        },
        group_operator: function(tokens) {
            var cur = tokens[0];
            var nex = null;
            var result = [];
            tokens.slice(1).forEach(function(nex) {
                if ((nex == '=') && cur &&
                    ~this.OPERATORS.indexOf(cur + nex)) {
                    result.push(cur + nex);
                    cur = null;
                } else {
                    if (cur !== null) {
                        result.push(cur);
                    }
                    cur = nex;
                }
            }.bind(this));
            if (cur !== null) {
                result.push(cur);
            }
            return result;
        },
        parenthesize: function(tokens) {
            var result = [];
            var current = result;
            var parent = [];
            tokens.forEach(function(token, i) {
                if (current === undefined) {
                    return;
                }
                if (token == '(') {
                    parent.push(current);
                    current = current[current.push([]) - 1];
                } else if (token == ')') {
                    current = parent.pop();
                } else {
                    current.push(token);
                }
            });
            return result;
        },
        group: function(tokens) {
            var result = [];

            var _group = function(parts) {
                var result = [];
                var push_result = function(part) {
                    result.push([part]);
                };
                var i = parts.indexOf(':');
                if (!~i) {
                    parts.forEach(push_result);
                    return result;
                }
                var sub_group = function(name, lvalue) {
                    return function(part) {
                        if (!jQuery.isEmptyObject(name)) {
                            if (!jQuery.isEmptyObject(lvalue)) {
                                if (part[0] !== null) {
                                    lvalue.push(part[0]);
                                }
                                result.push(name.concat([lvalue]));
                            } else {
                                result.push(name.concat(part));
                            }
                            name.splice(0, name.length);
                        } else {
                            result.push(part);
                        }
                    };
                };
                for (var j = 0; j < i; j++) {
                    var name = parts.slice(j, i).join(' ');
                    if (name.toLowerCase() in this.strings) {
                        if (!jQuery.isEmptyObject(parts.slice(0, j))) {
                            parts.slice(0, j).forEach(push_result);
                        } else {
                            push_result(null);
                        }
                        name = [name];
                        if (((i + 1) < parts.length) &&
                                (~this.OPERATORS.indexOf(parts[i + 1]))) {
                            name = name.concat([parts[i + 1]]);
                            i += 1;
                        } else {
                            name = name.concat([null]);
                        }
                        var lvalue = [];
                        while ((i + 2) < parts.length) {
                            if (parts[i + 2] == ';') {
                                lvalue.push(parts[i + 1]);
                                i += 2;
                            } else {
                                break;
                            }
                        }
                        _group(parts.slice(i + 1)).forEach(
                                sub_group(name, lvalue));
                        if (!jQuery.isEmptyObject(name)) {
                            if (!jQuery.isEmptyObject(lvalue)) {
                                result.push(name.concat([lvalue]));
                            } else {
                                result.push(name.concat([null]));
                            }
                        }
                        break;
                    }
                }
                return result;
            };
            _group = _group.bind(this);

            var parts = [];
            tokens.forEach(function(token) {
                if (token instanceof Array) {
                    _group(parts).forEach(function(group) {
                        if (!Sao.common.compare(group, [null])) {
                            result.push(group);
                        }
                    });
                    parts = [];
                    result.push(this.group(token));
                } else {
                    parts.push(token);
                }
            }.bind(this));
            _group(parts).forEach(function(group) {
                if (!Sao.common.compare(group, [null])) {
                    result.push(group);
                }
            });
            return result;
        },
        operatorize: function(tokens, operator) {
            var result = [];
            operator = operator || 'or';
            tokens = jQuery.extend([], tokens);
            var test = function(value) {
                if (value instanceof Array) {
                    return Sao.common.compare(value, [operator]);
                } else {
                    return value == operator;
                }
            };
            var cur = tokens.shift();
            while (test(cur)) {
                cur = tokens.shift();
            }
            if (cur === undefined) {
                return result;
            }
            if (cur instanceof Array) {
                cur = this.operatorize(cur, operator);
            }
            var nex = null;
            while (!jQuery.isEmptyObject(tokens)) {
                nex = tokens.shift();
                if ((nex instanceof Array) && !test(nex)) {
                    nex = this.operatorize(nex, operator);
                }
                if (test(nex)) {
                    nex = tokens.shift();
                    while (test(nex)) {
                        nex = tokens.shift();
                    }
                    if (nex instanceof Array) {
                        nex = this.operatorize(nex, operator);
                    }
                    if (nex !== undefined) {
                        cur = [operator.toUpperCase(), cur, nex];
                    } else {
                        if (!test(cur)) {
                            result.push([operator.toUpperCase(), cur]);
                            cur = null;
                        }
                    }
                    nex = null;
                } else {
                    if (!test(cur)) {
                        result.push(cur);
                    }
                    cur = nex;
                }
            }
            if (jQuery.isEmptyObject(tokens)) {
                if ((nex !== null) && !test(nex)) {
                    result.push(nex);
                } else if ((cur !== null) && !test(nex)) {
                    result.push(cur);
                }
            }
            return result;
        },
        parse_clause: function(tokens) {
            var result = [];
            tokens.forEach(function(clause) {
                if ((clause == 'OR') || (clause == 'AND')) {
                    result.push(clause);
                } else if ((clause.length == 1) &&
                    !(clause[0] instanceof Array)) {
                    result.push(['rec_name', 'ilike', this.likify(clause[0])]);
                } else if ((clause.length == 3) &&
                    (clause[0].toLowerCase() in this.strings)) {
                    var name = clause[0];
                    var operator = clause[1];
                    var value = clause[2];
                    var field = this.strings[clause[0].toLowerCase()];

                    var target = null;
                    if (field.type == 'reference') {
                        var split = this.split_target_value(field, value);
                        target = split[0];
                        value = split[1];
                    }

                    if (operator === null) {
                        operator = this.default_operator(field);
                    }
                    if (value instanceof Array) {
                        if (operator == '!') {
                            operator = 'not in';
                        } else {
                            operator = 'in';
                        }
                    }
                    if (operator == '!') {
                        operator = this.negate_operator(
                                this.default_operator(field));
                    }
                    if (~['integer', 'float', 'numeric', 'datetime', 'date',
                            'time'].indexOf(field.type)) {
                        if (value && value.contains('..')) {
                            var values = value.split('..', 2);
                            var lvalue = this.convert_value(field, values[0]);
                            var rvalue = this.convert_value(field, values[1]);
                            result.push([
                                    [field.name, '>=', lvalue],
                                    [field.name, '<', rvalue]
                                    ]);
                            return;
                        }
                    }
                    if (value instanceof Array) {
                        value = value.map(function(v) {
                            return this.convert_value(field, v);
                        }.bind(this));
                    } else {
                        value = this.convert_value(field, value);
                    }
                    if (operator.contains('like')) {
                        value = this.likify(value);
                    }
                    if (target) {
                        result.push([field.name + '.rec_name', operator, value,
                                target]);
                    } else {
                        result.push([field.name, operator, value]);
                    }
                } else {
                    result.push(this.parse_clause(clause));
                }
            }.bind(this));
            return result;
        },
        likify: function(value) {
            if (!value) {
                return '%';
            }
            var escaped = value.replace('%%', '__');
            if (escaped.contains('%')) {
                return value;
            } else {
                return '%' + value + '%';
            }
        },
        quote: function(value) {
            if (typeof value != 'string') {
                return value;
            }
            var tests = [':', ' ', '(', ')'].concat(this.OPERATORS);
            for (var i = 0; i < tests.length; i++) {
                var test = tests[i];
                if (value.contains(test)) {
                    return '"' + value + '"';
                }
            }
            return value;
        },
        default_operator: function(field) {
            if (~['char', 'text', 'many2one', 'many2many', 'one2many',
                    'reference'].indexOf(field.type)) {
                return 'ilike';
            } else {
                return '=';
            }
        },
        negate_operator: function(operator) {
            switch (operator) {
                case 'ilike':
                    return 'not ilike';
                case '=':
                    return '!=';
                case 'in':
                    return 'not in';
            }
        },
        time_format: function(field) {
            return new Sao.PYSON.Decoder({}).decode(field.format);
        },
        split_target_value: function(field, value) {
            var target = null;
            if (typeof value == 'string') {
                for (var i = 0; i < field.selection.length; i++) {
                    var selection = field.selection[i];
                    var key = selection[0];
                    var text = selection[1];
                    if (value.toLowerCase().startsWith(
                                text.toLowerCase() + ',')) {
                        target = key;
                        value = value.slice(text.length + 1);
                        break;
                    }
                }
            }
            return [target, value];
        },
        convert_value: function(field, value) {
            var convert_selection = function() {
                if (typeof value == 'string') {
                    for (var i = 0; i < field.selection.length; i++) {
                        var selection = field.selection[i];
                        var key = selection[0];
                        var text = selection[1];
                        if (value.toLowerCase() == text.toLowerCase()) {
                            return key;
                        }
                    }
                }
                return value;
            };

            var converts = {
                'boolean': function() {
                    if (typeof value == 'string') {
                        return ['y', 'yes', 'true', 't', '1'].some(
                                function(test) {
                                    return test.toLowerCase().startsWith(
                                        value.toLowerCase());
                                });
                    } else {
                        return Boolean(value);
                    }
                },
                'float': function() {
                    var result = Number(value);
                    if (isNaN(result) || value === '' || value === null) {
                        return null;
                    } else {
                        return result;
                    }
                },
                'integer': function() {
                    var result = parseInt(value, 10);
                    if (isNaN(result)) {
                        return null;
                    } else {
                        return result;
                    }
                },
                'numeric': function() {
                    var result = new Sao.Decimal(value);
                    if (isNaN(result.valueOf()) ||
                            value === '' || value === null) {
                        return null;
                    } else {
                        return result;
                    }
                },
                'selection': convert_selection,
                'reference': convert_selection,
                'datetime': function() {
                    try {
                        return Sao.common.parse_datetime(
                                Sao.common.date_format(),
                                this.time_format(field),
                                value);
                    } catch (e1) {
                        try {
                            return Sao.DateTime(jQuery.datepicker.parseDate(
                                        Sao.common.date_format(),
                                        value));
                        } catch (e2) {
                            return null;
                        }
                    }
                }.bind(this),
                'date': function() {
                    try {
                        return Sao.Date(jQuery.datepicker.parseDate(
                                    Sao.common.date_format(),
                                    value));
                    } catch (e) {
                        return null;
                    }
                },
                'time': function() {
                    try {
                        return Sao.common.parse_time(this.time_format(field),
                                value);
                    } catch (e) {
                        return null;
                    }
                }.bind(this),
                'many2one': function() {
                    if (value === '') {
                        return null;
                    } else {
                        return value;
                    }
                }
            };
            var func = converts[field.type];
            if (func) {
                return func();
            } else {
                return value;
            }
        },
        format_value: function(field, value, target) {
            if (target === undefined) {
                target = null;
            }
            var format_float = function() {
                if (!value && value !== 0 && value !== new Sao.Decimal(0)) {
                    return '';
                }
                var digit = String(value).split('.')[1];
                if (digit) {
                    digit = digit.length;
                } else {
                    digit = 0;
                }
                return value.toFixed(digit);
            };
            var format_selection = function() {
                for (var i = 0; i < field.selection.length; i++) {
                    if (field.selection[i][0] == value) {
                        return field.selection[i][1];
                    }
                }
                return value || '';
            };

            var format_reference = function() {
                if (!target) {
                    return format_selection();
                }
                for (var i = 0; i < field.selection.length; i++) {
                    if (field.selection[i][0] == target) {
                        target = field.selection[i][1];
                        break;
                    }
                }
                return target + ',' + value;
            };

            var converts = {
                'boolean': function() {
                    if (value) {
                        return 'True';  // TODO translate
                    } else {
                        return 'False';
                    }
                },
                'integer': function() {
                    if (value || value === 0) {
                        return '' + parseInt(value, 10);
                    } else {
                        return '';
                    }
                },
                'float': format_float,
                'numeric': format_float,
                'selection': format_selection,
                'reference': format_reference,
                'datetime': function() {
                    if (!value) {
                        return '';
                    }
                    if (value.isDate ||
                            !(value.getHours() ||
                             value.getMinutes() ||
                             value.getSeconds())) {
                        return jQuery.datepicker.formatDate(
                                Sao.common.date_format(),
                                value);
                    }
                    return Sao.common.format_datetime(
                            Sao.common.date_format(),
                            this.time_format(field),
                            value);
                }.bind(this),
                'date': function() {
                    if (!value) {
                        return '';
                    }
                    return jQuery.datepicker.formatDate(
                            Sao.common.date_format(),
                            value);
                },
                'time': function() {
                    if (!value) {
                        return '';
                    }
                    return Sao.common.format_time(
                            this.time_format(field),
                            value);
                }.bind(this),
                'many2one': function() {
                    if (value === null) {
                        return '';
                    } else {
                        return value;
                    }
                }
            };
            if (value instanceof Array) {
                return value.map(function(v) {
                    return this.format_value(field, v);
                }.bind(this)).join(';');
            } else {
                var func = converts[field.type];
                if (func) {
                    return this.quote(func(value));
                } else if (value === null) {
                    return '';
                } else {
                    return this.quote(value);
                }
            }
        },
        simplify: function(value) {
            if (value instanceof Array) {
                if ((value.length == 1) && (value[0] instanceof Array) &&
                        ((value[0][0] == 'AND') || (value[0][0] == 'OR') ||
                         (value[0][0] instanceof Array))) {
                    return this.simplify(value[0]);
                } else if ((value.length == 2) &&
                        ((value[0] == 'AND') || (value[0] == 'OR')) &&
                        (value[1] instanceof Array)) {
                    return this.simplify(value[1]);
                } else if ((value.length == 3) &&
                        ((value[0] == 'AND') || (value[0] == 'OR')) &&
                        (value[1] instanceof Array) &&
                        (value[0] == value[1][0])) {
                    value = this.simplify(value[1]).concat([value[2]]);
                }
                return value.map(this.simplify.bind(this));
            }
            return value;
        }
    });

    Sao.common.DomainInversion = Sao.class_(Object, {
        and: function(a, b) {return a && b;},
        or: function(a, b) {return a || b;},
        OPERATORS: {
            '=': function(a, b) {
                if ((a instanceof Array) && (b instanceof Array)) {
                    return Sao.common.compare(a, b);
                } else {
                    return (a === b);
                }
            },
            '>': function(a, b) {return (a > b);},
            '<': function(a, b) {return (a < b);},
            '<=': function(a, b) {return (a <= b);},
            '>=': function(a, b) {return (a >= b);},
            '!=': function(a, b) {
                if ((a instanceof Array) && (b instanceof Array)) {
                    return !Sao.common.compare(a, b);
                } else {
                    return (a !== b);
                }
            },
            'in': function(a, b) {
                return Sao.common.DomainInversion.in_(a, b);
            },
            'not in': function(a, b) {
                return !Sao.common.DomainInversion.in_(a, b);
            },
            // Those operators are not supported (yet ?)
            'like': function() {return true;},
            'ilike': function() {return true;},
            'not like': function() {return true;},
            'not ilike': function() {return true;},
            'child_of': function() {return true;},
            'not child_of': function() {return true;}
        },
        locale_part: function(expression, field_name, locale_name) {
            if (locale_name === undefined) {
                locale_name = 'id';
            }
            if (expression === field_name) {
                return locale_name;
            }
            if (expression.contains('.')) {
                return expression.split('.').slice(1).join('.');
            }
            return expression;
        },
        is_leaf: function(expression) {
            return ((expression instanceof Array) &&
                (expression.length > 2) &&
                (expression[1] in this.OPERATORS));
        },
        eval_leaf: function(part, context, boolop) {
            if (boolop === undefined) {
                boolop = this.and;
            }
            var field = part[0];
            var operand = part[1];
            var value = part[2];
            if (field.contains('.')) {
                // In the case where the leaf concerns a m2o then having a
                // value in the evaluation context is deemed suffisant
                return Boolean(context[field.split('.')[0]]);
            }
            if ((operand == '=') &&
                    (context[field] === null || context[field] === undefined) &&
                    (boolop === this.and)) {
                // We should consider that other domain inversion will set a
                // correct value to this field
                return true;
            }
            var context_field = context[field];
            if ((context_field instanceof Date) && !context_field) {
                // TODO set value to min
            }
            if ((value instanceof Date) && !context_field) {
                // TODO set context_field to min
            }
            if ((typeof context_field == 'string') &&
                    (value instanceof Array) && value.length == 2) {
                value = value.join(',');
            } else if ((context_field instanceof Array) &&
                    (typeof value == 'string') && context_field.length == 2) {
                context_field = context_field.join(',');
            }
            if (~['=', '!='].indexOf(operand) &&
                    context_field instanceof Array &&
                    typeof value == 'number') {
                operand = {
                    '=': 'in',
                    '!=': 'not in'
                }[operand];
            }
            return this.OPERATORS[operand](context_field, value);
        },
        inverse_leaf: function(domain) {
            if (~['AND', 'OR'].indexOf(domain)) {
                return domain;
            } else if (this.is_leaf(domain)) {
                if (domain[1].contains('child_of')) {
                    if (domain.length == 3) {
                        return domain;
                    } else {
                        return [domain[3]].concat(domain.slice(1));
                    }
                }
                return domain;
            } else {
                return domain.map(this.inverse_leaf.bind(this));
            }
        },
        eval_domain: function(domain, context, boolop) {
            if (boolop === undefined) {
                boolop = this.and;
            }
            if (this.is_leaf(domain)) {
                return this.eval_leaf(domain, context, boolop);
            } else if (jQuery.isEmptyObject(domain) && boolop == this.and) {
                return true;
            } else if (jQuery.isEmptyObject(domain) && boolop == this.or) {
                return false;
            } else if (domain[0] == 'AND') {
                return this.eval_domain(domain.slice(1), context);
            } else if (domain[0] == 'OR') {
                return this.eval_domain(domain.slice(1), context, this.or);
            } else {
                return boolop(this.eval_domain(domain[0], context),
                        this.eval_domain(domain.slice(1), context, boolop));
            }
        },
        localize_domain: function(domain, field_name) {
            if (~['AND', 'OR', true, false].indexOf(domain)) {
                return domain;
            } else if (this.is_leaf(domain)) {
                if (domain[1].contains('child_of')) {
                    if (domain.length == 3) {
                        return domain;
                    } else {
                        return [domain[3]].concat(domain.slice(1, -1));
                    }
                }
                var local_name = 'id';
                if (typeof domain[2] == 'string') {
                    local_name = 'rec_name';
                }
                return [this.locale_part(domain[0], field_name, local_name)]
                    .concat(domain.slice(1));
            } else {
                return domain.map(function(e) {
                    return this.localize_domain(e, field_name);
                }.bind(this));
            }
        },
        simplify: function(domain) {
            if (this.is_leaf(domain)) {
                return domain;
            } else if (~['OR', 'AND'].indexOf(domain)) {
                return domain;
            } else if ((domain instanceof Array) && (domain.length == 1) &&
                    (~['OR', 'AND'].indexOf(domain[0]))) {
                return [];
            } else if ((domain instanceof Array) && (domain.length == 1) &&
                    (!this.is_leaf(domain[0]))) {
                return this.simplify(domain[0]);
            } else if ((domain instanceof Array) && (domain.length == 2) &&
                    ~['AND', 'OR'].indexOf(domain[0])) {
                return [this.simplify(domain[1])];
            } else {
                return domain.map(this.simplify.bind(this));
            }
        },
        merge: function(domain, domoperator) {
            if (jQuery.isEmptyObject(domain) ||
                    ~['AND', 'OR'].indexOf(domain)) {
                return [];
            }
            var domain_type = domain[0] == 'OR' ? 'OR' : 'AND';
            if (this.is_leaf(domain)) {
                return [domain];
            } else if (domoperator === undefined) {
                return [domain_type].concat([].concat.apply([],
                        domain.map(function(e) {
                            return this.merge(e, domain_type);
                        }.bind(this))));
            } else if (domain_type == domoperator) {
                return [].concat.apply([], domain.map(function(e) {
                    return this.merge(e, domain_type);
                }.bind(this)));
            } else {
                // without setting the domoperator
                return [this.merge(domain)];
            }
        },
        concat: function(domains, domoperator) {
            var result = [];
            if (domoperator) {
                result.push(domoperator);
            }
            domains.forEach(function append(domain) {
                if (!jQuery.isEmptyObject(domain)) {
                    result.push(domain);
                }
            });
            return this.simplify(this.merge(result));
        },
        parse: function(domain) {
            var And = Sao.common.DomainInversion.And;
            var Or = Sao.common.DomainInversion.Or;
            if (this.is_leaf(domain)) {
                return domain;
            } else if (jQuery.isEmptyObject(domain)) {
                return new And([]);
            } else if (domain[0] === 'OR') {
                return new Or(domain.slice(1));
            } else {
                var begin = 0;
                if (domain[0] === 'AND') {
                    begin = 1;
                }
                return new And(domain.slice(begin));
            }
        },
        domain_inversion: function(domain, symbol, context) {
            if (context === undefined) {
                context = {};
            }
            var expression = this.parse(domain);
            if (!~expression.variables.indexOf(symbol)) {
                return true;
            }
            return expression.inverse(symbol, context);
        }
    });
    Sao.common.DomainInversion.in_ = function(a, b) {
        if (a instanceof Array) {
            if (b instanceof Array) {
                for (var i = 0, len = a.length; i < len; i++) {
                    if (~b.indexOf(a[i])) {
                        return true;
                    }
                }
                return false;
            } else {
                return Boolean(~a.indexOf(b));
            }
        } else {
            return Boolean(~b.indexOf(a));
        }
    };
    Sao.common.DomainInversion.And = Sao.class_(Object, {
        init: function(expressions) {
            this.domain_inversion = new Sao.common.DomainInversion();
            this.branches = expressions.map(this.domain_inversion.parse.bind(
                    this.domain_inversion));
            this.variables = [];
            for (var i = 0, len = this.branches.length; i < len; i++) {
                var expression = this.branches[i];
                if (this.domain_inversion.is_leaf(expression)) {
                    this.variables.push(this.base(expression[0]));
                } else if (expression instanceof
                    Sao.common.DomainInversion.And) {
                    this.variables = this.variables.concat(
                        expression.variables);
                }
            }
        },
        base: function(expression) {
            if (!expression.contains('.')) {
                return expression;
            } else {
                return expression.split('.')[0];
            }
        },
        inverse: function(symbol, context) {
            var DomainInversion = Sao.common.DomainInversion;
            var result = [];
            for (var i = 0, len = this.branches.length; i < len; i++) {
                var part = this.branches[i];
                if (part instanceof DomainInversion.And) {
                    var part_inversion = part.inverse(symbol, context);
                    var evaluated = typeof part_inversion == 'boolean';
                    if (!evaluated) {
                        result.push(part_inversion);
                    } else if (part_inversion) {
                        continue;
                    } else {
                        return false;
                    }
                } else if (this.domain_inversion.is_leaf(part) &&
                        (this.base(part[0]) === symbol)) {
                    result.push(part);
                } else {
                    var field = part[0];
                    if ((!(field in context)) ||
                            ((field in context) &&
                             this.domain_inversion.eval_leaf(part, context,
                                 this.domain_inversion.and))) {
                        result.push(true);
                    } else {
                        return false;
                    }
                }
            }
            result = result.filter(function(e) {
                return e !== true;
            });
            if (jQuery.isEmptyObject(result)) {
                return true;
            } else {
                return this.domain_inversion.simplify(result);
            }
        }
    });
    Sao.common.DomainInversion.Or = Sao.class_(Sao.common.DomainInversion.And, {
        inverse: function(symbol, context) {
            var DomainInversion = Sao.common.DomainInversion;
            var result = [];
            if (!~this.variables.indexOf(symbol) &&
                !jQuery.isEmptyObject(this.variables.filter(function(e) {
                    return !(e in context);
                }))) {
                // In this case we don't know anything about this OR part, we
                // consider it to be True (because people will have the
                // constraint on this part later).
                return true;
            }
            for (var i = 0, len = this.branches.length; i < len; i++) {
                var part = this.branches[i];
                if (part instanceof DomainInversion.And) {
                    var part_inversion = part.inverse(symbol, context);
                    var evaluated = typeof part_inversion == 'boolean';
                    if (!~this.variables.indexOf(symbol)) {
                        if (evaluated && part_inversion) {
                            return true;
                        }
                        continue;
                    }
                    if (!evaluated) {
                        result.push(part_inversion);
                    } else if (part_inversion) {
                        return true;
                    } else {
                        continue;
                    }
                } else if (this.domain_inversion.is_leaf(part) &&
                        (this.base(part[0]) == symbol)) {
                    result.push(part);
                } else {
                    var field = part[0];
                    field = this.base(field);
                    if ((field in context) &&
                            this.domain_inversion.eval_leaf(part, context,
                                this.domain_inversion.or)) {
                        return true;
                    } else if ((field in context) &&
                            !this.domain_inversion.eval_leaf(part, context,
                                this.domain_inversion.or)) {
                        result.push(false);
                    }
                }
            }
            result = result.filter(function(e) {
                return e !== false;
            });
            if (jQuery.isEmptyObject(result)) {
                return false;
            } else {
                return this.domain_inversion.simplify(['OR'].concat(result));
            }
        }
    });

    Sao.common.guess_mimetype = function(filename) {
        if (/.*odt$/.test(filename)) {
            return 'application/vnd.oasis.opendocument.text';
        } else if (/.*ods$/.test(filename)) {
            return 'application/vnd.oasis.opendocument.spreadsheet';
        } else if (/.*pdf$/.test(filename)) {
            return 'application/pdf';
        } else if (/.*docx$/.test(filename)) {
            return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
        } else if (/.*doc/.test(filename)) {
            return 'application/msword';
        } else if (/.*xlsx$/.test(filename)) {
            return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
        } else if (/.*xls/.test(filename)) {
            return 'application/vnd.ms-excel';
        } else {
            return 'application/octet-binary';
        }
    };

    Sao.common.LOCAL_ICONS = [
        'tryton-attachment-hi',
        'tryton-attachment',
        'tryton-bookmark',
        'tryton-cancel',
        'tryton-clear',
        'tryton-close',
        'tryton-connect',
        'tryton-copy',
        'tryton-delete',
        'tryton-dialog-error',
        'tryton-dialog-information',
        'tryton-dialog-warning',
        'tryton-disconnect',
        'tryton-executable',
        'tryton-find-replace',
        'tryton-find',
        'tryton-folder-new',
        'tryton-fullscreen',
        'tryton-go-home',
        'tryton-go-jump',
        'tryton-go-next',
        'tryton-go-previous',
        'tryton-help',
        'tryton-icon',
        'tryton-list-add',
        'tryton-list-remove',
        'tryton-locale',
        'tryton-lock',
        'tryton-log-out',
        'tryton-mail-message-new',
        'tryton-mail-message',
        'tryton-new',
        'tryton-ok',
        'tryton-open',
        'tryton-preferences-system-session',
        'tryton-preferences-system',
        'tryton-preferences',
        'tryton-print-email',
        'tryton-print-open',
        'tryton-print',
        'tryton-refresh',
        'tryton-save-as',
        'tryton-save',
        'tryton-star',
        'tryton-start-here',
        'tryton-system-file-manager',
        'tryton-system',
        'tryton-text-background',
        'tryton-text-foreground',
        'tryton-text-markup',
        'tryton-undo',
        'tryton-unstar',
        'tryton-web-browser'
    ];

    Sao.common.IconFactory = Sao.class_(Object, {
        batchnum: 10,
        name2id: {},
        loaded_icons: {},
        tryton_icons: [],
        register_prm: jQuery.when(),
        load_icons: function(refresh) {
            refresh = refresh || false;
            if (!refresh) {
                for (var icon_name in this.load_icons) {
                    if (!this.load_icons.hasOwnProperty(icon_name)) {
                        continue;
                    }
                    window.URL.revokeObjectURL(this.load_icons[icon_name]);
                }
            }

            var icon_model = new Sao.Model('ir.ui.icon');
            return icon_model.execute('list_icons', [], {})
            .then(function(icons) {
                if (!refresh) {
                    this.name2id = {};
                    this.loaded_icons = {};
                }
                this.tryton_icons = [];

                var icon_id, icon_name;
                for (var i=0, len=icons.length; i < len; i++) {
                    icon_id = icons[i][0];
                    icon_name = icons[i][1];
                    if (refresh && (icon_name in this.loaded_icons)) {
                        continue;
                    }
                    this.tryton_icons.push([icon_id, icon_name]);
                    this.name2id[icon_name] = icon_id;
                }
            }.bind(this));
        },
        register_icon: function(icon_name) {
            if (!icon_name) {
                return jQuery.when('');
            } else if ((icon_name in this.loaded_icons) ||
                    ~Sao.common.LOCAL_ICONS.indexOf(icon_name)) {
                return jQuery.when(this.get_icon_url(icon_name));
            }
            if (this.register_prm.state() == 'pending') {
                var waiting_prm = jQuery.Deferred();
                this.register_prm.then(function() {
                    this.register_icon(icon_name).then(
                        waiting_prm.resolve, waiting_prm.reject);
                }.bind(this));
                return waiting_prm;
            }
            var loaded_prm;
            if (!(icon_name in this.name2id)) {
                loaded_prm = this.load_icons(true);
            } else {
                loaded_prm = jQuery.when();
            }

            var icon_model = new Sao.Model('ir.ui.icon');
            this.register_prm = loaded_prm.then(function () {
                var find_array = function(array) {
                    var idx, l;
                    for (idx=0, l=this.tryton_icons.length; idx < l; idx++) {
                        var icon = this.tryton_icons[idx];
                        if (Sao.common.compare(icon, array)) {
                            break;
                        }
                    }
                    return idx;
                }.bind(this);
                var idx = find_array([this.name2id[icon_name], icon_name]);
                var from = Math.round(idx - this.batchnum / 2);
                from = (from < 0) ? 0 : from;
                var to = Math.round(idx + this.batchnum / 2);
                var ids = [];
                this.tryton_icons.slice(from, to).forEach(function(e) {
                    ids.push(e[0]);
                });

                var read_prm = icon_model.execute('read',
                    [ids, ['name', 'icon']], {});
                return read_prm.then(function(icons) {
                    icons.forEach(function(icon) {
                        var blob = new Blob([icon.icon],
                            {type: 'image/svg+xml'});
                        var img_url = window.URL.createObjectURL(blob);
                        this.loaded_icons[icon.name] = img_url;

                        delete this.name2id[icon.name];
                        this.tryton_icons.splice(
                            find_array([icon.id, icon.name]), 1);
                    }.bind(this));
                    return this.get_icon_url(icon_name);
                }.bind(this));
            }.bind(this));
            return this.register_prm;
        },
        get_icon_url: function(icon_name) {
            if (icon_name in this.loaded_icons) {
                return this.loaded_icons[icon_name];
            }
            return "images/" + icon_name + ".svg";
        }
    });

    Sao.common.ICONFACTORY = new Sao.common.IconFactory();

    Sao.common.UniqueDialog = Sao.class_(Object, {
        init: function() {
            this.running = false;
        },
        build_dialog: function() {
        },
        run: function() {
            if (this.running) {
                return;
            }
            var args = Array.prototype.slice.call(arguments);
            var prm = jQuery.Deferred();
            args.push(prm);
            var dialog = this.build_dialog.apply(this, args);
            var class_ = dialog.dialog('option', 'dialogClass');
            dialog.dialog({
                'dialogClass': class_ + ' unique-dialog'
            });
            this.running = true;
            dialog.dialog('open');
            Sao.common.center_dialog(dialog);
            return prm;
        },
        close: function(dialog) {
            dialog.dialog('close');
            this.running = false;
        }
    });

    Sao.common.MessageDialog = Sao.class_(Sao.common.UniqueDialog, {
        class_: 'message-dialog',
        build_dialog: function(message, icon, prm) {
            var dialog = jQuery('<div/>');
            dialog.append(jQuery('<p/>')
                .text(message)
                .prepend(jQuery('<span/>', {
                    'class': 'dialog-icon'
                }).append(jQuery('<span/>', {
                    'class': 'ui-icon ' + icon
                }))));
            dialog.dialog({
                dialogClass: this.class_,
                modal: true,
                autoOpen: false,
                buttons: {
                    'OK': function() {
                        this.close(dialog);
                        prm.resolve('ok');
                    }.bind(this)
                }
            });
            return dialog;
        },
        run: function(message, icon) {
            Sao.common.MessageDialog._super.run.call(
                    this, message, icon || 'ui-icon-info');
        }
    });
    Sao.common.message = new Sao.common.MessageDialog();

    Sao.common.WarningDialog = Sao.class_(Sao.common.UniqueDialog, {
        class_: 'warning-dialog',
        build_dialog: function(message, title, prm) {
            var dialog = jQuery('<div/>');
            dialog.append(jQuery('<p/>')
                .text(message)
                .prepend(jQuery('<span/>', {
                    'class': 'dialog-icon'
                }).append(jQuery('<span/>', {
                    'class': 'ui-icon ui-icon-alert'
                }))));
            dialog.dialog({
                dialogClass: this.class_,
                modal: true,
                autoOpen: false,
                title: title,
                buttons: {
                    'Ok': function() {
                        this.close(dialog);
                        prm.resolve('ok');
                    }.bind(this)
                }

            });
            return dialog;
        }
    });
    Sao.common.warning = new Sao.common.WarningDialog();

    Sao.common.UserWarningDialog = Sao.class_(Sao.common.WarningDialog, {
        class_: 'user-warning-dialog',
        always: false,
        _set_always: function() {
            this.always = jQuery(this).prop('checked');
        },
        build_dialog: function(message, title, prm) {
            var dialog = Sao.common.UserWarningDialog._super.build_dialog.call(
                this, message, title, prm);
            dialog.append(jQuery('<div/>')
                .append(jQuery('<input/>', {
                    'type': 'checkbox'
                }).change(this._set_always.bind(this)))
                .append(jQuery('<span/>').text('Always ignore this warning.'))
                );
            dialog.append(jQuery('<p/>').text('Do you want to proceed?'));
            dialog.dialog({
                buttons: {
                    'No': function() {
                        this.close(dialog);
                        prm.reject();
                    }.bind(this),
                    'Yes': function() {
                        this.close(dialog);
                        if (this.always) {
                            prm.resolve('always');
                        }
                        prm.resolve('ok');
                    }.bind(this)
                }
            });
            return dialog;
        }
    });
    Sao.common.userwarning = new Sao.common.UserWarningDialog();

    Sao.common.ConfirmationDialog = Sao.class_(Sao.common.UniqueDialog, {
        class_: 'confirmation-dialog',
        build_dialog: function(message) {
            var dialog = jQuery('<div/>');
            dialog.append(jQuery('<p/>')
                .text(message)
                .prepend(jQuery('<span/>', {
                    'class': 'dialog-icon'
                }).append(jQuery('<span/>', {
                    'class': 'ui-icon ui-icon-info'
                }))));
            dialog.dialog({
                dialogClass: this.class_,
                model: true,
                autoOpen: false,
                title: 'Confirmation'
            });
            return dialog;
        }
    });

    Sao.common.SurDialog = Sao.class_(Sao.common.ConfirmationDialog, {
        build_dialog: function(message, prm) {
            var dialog = Sao.common.SurDialog._super.build_dialog.call(
                this, message);
            dialog.dialog({
                buttons: {
                    'Cancel': function() {
                        this.close(dialog);
                        prm.reject();
                    }.bind(this),
                    'Ok': function() {
                        this.close(dialog);
                        prm.resolve();
                    }.bind(this)
                }
            });
            return dialog;
        }
    });
    Sao.common.sur = new Sao.common.SurDialog();

    Sao.common.Sur3BDialog = Sao.class_(Sao.common.ConfirmationDialog, {
        build_dialog: function(message, prm) {
            var dialog = Sao.common.SurDialog._super.build_dialog.call(
                this, message);
            dialog.dialog({
                buttons: {
                    'Cancel': function() {
                        this.close(dialog);
                        prm.resolve('cancel');
                    }.bind(this),
                    'No': function() {
                        this.close(dialog);
                        prm.resolve('ko');
                    }.bind(this),
                    'Yes': function() {
                        this.close(dialog);
                        prm.resolve('ok');
                    }.bind(this)
                }
            });
            return dialog;
        }
    });
    Sao.common.sur_3b = new Sao.common.Sur3BDialog();

    Sao.common.AskDialog = Sao.class_(Sao.common.UniqueDialog, {
        class_: 'ask-dialog',
        run: function() {
            var args = Array.prototype.slice.call(arguments);
            if (args.length == 1) {
                args.push(true);
            }
            return Sao.common.AskDialog._super.run.apply(this, args);
        },
        build_dialog: function(question, visibility, prm) {
            var dialog = jQuery('<div/>');
            var entry = jQuery('<input/>', {
                'type': visibility ? 'input' : 'password'
            });
            dialog.append(jQuery('<p/>')
                .text(question)
                .prepend(jQuery('<span/>', {
                    'class': 'dialog-icon'
                }).append(jQuery('<span/>', {
                    'class': 'ui-icon ui-icon-info'
                })))
                .append(entry));
            dialog.dialog({
                dialogClass: this.class_,
                modal: true,
                autoOpen: false,
                buttons: {
                    'Cancel': function() {
                        this.close(dialog);
                        prm.reject();
                    }.bind(this),
                    'Ok': function() {
                        this.close(dialog);
                        prm.resolve(entry.val());
                    }.bind(this)
                }
            });
            return dialog;
        }
    });
    Sao.common.ask = new Sao.common.AskDialog();

    Sao.common.ConcurrencyDialog = Sao.class_(Sao.common.UniqueDialog, {
        class_: 'ask-dialog',
        build_dialog: function(model, record_id, context, prm) {
            var dialog = jQuery('<div/>');
            dialog.append(jQuery('<p/>').append(jQuery('<b/>')
                    .text('Write Concurrency Warning:'))
                .prepend(jQuery('<span/>', {
                    'class': 'dialog-icon'
                }).append(jQuery('<span/>', {
                    'class': 'ui-icon ui-icon-info'
                })))
                .append(jQuery('<p/>')
                    .text('This record has been modified ' +
                        'while you were editing it.'))
                .append(jQuery('<p/>').text('Choose:'))
                .append(jQuery('<ul/>')
                    .append(jQuery('<li/>')
                        .text('"Cancel" to cancel saving;'))
                    .append(jQuery('<li/>')
                        .text('"Compare" to see the modified version;'))
                    .append(jQuery('<li/>')
                        .text('"Write Anyway" to save your current version.')))
                );
            dialog.dialog({
                dialogClass: this.class_,
                modal: true,
                autoOpen: false,
                title: 'Concurrency Exception',
                buttons: {
                    'Cancel': function() {
                        this.close(dialog);
                        prm.reject();
                    }.bind(this),
                    'Compare': function() {
                        this.close(dialog);
                        Sao.Tab.create({
                            'model': model,
                            'res_id': record_id,
                            'domain': [['id', '=', record_id]],
                            'context': context,
                            'mode': ['form', 'tree']
                        });
                        prm.reject();
                    }.bind(this),
                    'Write Anyway': function() {
                        this.close(dialog);
                        prm.resolve();
                    }.bind(this)
                }
            });
            return dialog;
        }
    });
    Sao.common.concurrency = new Sao.common.ConcurrencyDialog();

    Sao.common.ErrorDialog = Sao.class_(Sao.common.UniqueDialog, {
        class_: 'error-dialog',
        build_dialog: function(title, details, prm) {
            var dialog = jQuery('<div/>');
            dialog.append(jQuery('<p/>')
                .text(title)
                .prepend(jQuery('<span/>', {
                    'class': 'dialog-icon'
                }).append(jQuery('<span/>', {
                    'class': 'ui-icon ui-icon-alert'
                })))
                .append(jQuery('<p/>')
                    .append(jQuery('<textarea/>')
                        .text(details)
                        .prop('disabled', true)))
                .append(jQuery('<p/>')
                    .append(jQuery('<a/>', {
                        href: Sao.config.roundup.url,
                        target: '_blank'
                    }).text('Report Bug'))));
            dialog.dialog({
                dialogClass: this.class_,
                modal: true,
                autoOpen: false,
                title: 'Application Error!',
                buttons: {
                    'Close': function() {
                        this.close(dialog);
                        prm.resolve();
                    }.bind(this)
                }
            });
            return dialog;
        }
    });
    Sao.common.error = new Sao.common.ErrorDialog();

    Sao.common.center_dialog = function(element){
        var search_visible = function(parents){
            var parent;
            for (var i=0; i < parents.length; i++){
                var el = jQuery(parents[i]);
                if (el != element && el.is(':visible')) {
                    parent = el;
                    break;
                }
            }
            return parent;
        };
        var parents = jQuery(element).parents().find('.ui-dialog ' +
            '.screen-container');
        var parent = search_visible(parents);
        if (!parent) {
            parents = jQuery(element).parents().find('.screen-container');
            parent = search_visible(parents);
            if (!parent) {
                parent = window;
            }
            parent = jQuery(parent);
        }
        jQuery(element).dialog('option', 'width', parent.width() * 0.8);
        jQuery(element).dialog('option', 'position',{
                my: 'center top',
                at: 'center top',
                of: parent
            });
   };
}());
