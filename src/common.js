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
                    } else if (this.nowordchars.indexOf(nextchar) == -1) {
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
                    } else if ((this.nowordchars.indexOf(nextchar) == -1) ||
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
                var escaped;
                if ((typeof clause[0] == 'string') &&
                        ((clause[0] in this.fields) ||
                         (clause[0] == 'rec_name'))) {
                    var name = clause[0];
                    var operator = clause[1];
                    var value = clause[2];
                    if (!(name in this.fields)) {
                        escaped = value.replace('%%', '__');
                        if (escaped.startsWith('%') && escaped.endsWith('%')) {
                            value = value.slice(1, -1);
                        }
                        return this.quote(value);
                    }
                    var field = this.fields[name];
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
                             operator.contains('not'))) {
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
                    var formatted_value = this.format_value(field, value);
                    if ((this.OPERATORS.indexOf(operator) >= 0) &&
                            (['char', 'text', 'sha', 'selection']
                             .indexOf(field.type) >= 0) &&
                            (value === '')) {
                        formatted_value = '""';
                    }
                    return (this.quote(field.string) + ': ' +
                            operator + formatted_value);
                } else {
                    return '(' + this.string(clause) + ')';
                }
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
                    (this.OPERATORS.indexOf(cur + nex) >= 0)) {
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
                if (i == -1) {
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
                                (this.OPERATORS.indexOf(parts[i + 1]) >= 0)) {
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
                    if (operator.contains('like')) {
                        value = this.likify(value);
                    }
                    if (['integer', 'float', 'numeric', 'datetime', 'date',
                            'time'].indexOf(field.type) >= 0) {
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
                    result.push([field.name, operator, value]);
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
            if (['char', 'text', 'many2one', 'many2many', 'one2many']
                    .indexOf(field.type) >= 0) {
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
                // TODO datetime
                // TODO date
                // TODO time
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
        format_value: function(field, value) {
            var format_float = function() {
                if (!value && value !== 0 && value !== new Sao.Decimal(0)) {
                    return '';
                }
                var digit = parseInt((field.digits || [16, 2])[1], 10);
                if (isNaN(digit)) {
                    digit = 2;
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
                'reference': format_selection,
                // TODO datetime
                // TODO date
                // TODO time
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
}());
