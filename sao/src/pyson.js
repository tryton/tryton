/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.PYSON = {};
    Sao.PYSON.eval = {
        True: true,
        False: false,
    };
    Sao.PYSON.toString = function(value) {
        if (value instanceof Sao.PYSON.PYSON) {
            return value.toString();
        } else if (value instanceof Array) {
            return '[' + value.map(Sao.PYSON.toString).join(', ') + ']';
        } else if (value instanceof Object) {
            return '{' + Object.keys(value).map(key => {
                return Sao.PYSON.toString(key) + ': ' +
                    Sao.PYSON.toString(value[key]);
            }).join(', ') + '}';
        } else {
            return JSON.stringify(value);
        }
    };

    Sao.PYSON.PYSON = class PYSON {
        constructor() {
            this._operator = null;
        }
        pyson() {
            throw 'NotImplementedError';
        }
        types() {
            throw 'NotImplementedError';
        }
        get(k, d='') {
            return new Sao.PYSON.Get(this, k, d);
        }
        in_(obj) {
            return new Sao.PYSON.In(this, obj);
        }
        contains(k) {
            return new Sao.PYSON.In(k, this);
        }
        toString() {
            const params = this.__string_params__();
            if (this._operator && (params[0] instanceof Sao.PYSON.PYSON)) {
                const args = params.slice(1).map(Sao.PYSON.toString);
                return `${params[0]}.${this._operator}(` + args.join(', ') + ')';
            } else {
                var klass = this.pyson().__class__;
                var args = params.map(Sao.PYSON.toString);
                return klass + '(' + args.join(', ') + ')';
            }
        }
        __string_params__() {
            throw 'NotImplementedError';
        }
    };

    Sao.PYSON.PYSON.eval_ = function(value, context) {
        throw 'NotImplementedError';
    };
    Sao.PYSON.PYSON.init_from_object = function(object) {
        throw 'NotImplementedError';
    };

    Sao.PYSON.Encoder = class Encoder{
        prepare(value, index, parent) {
            if (value !== null && value !== undefined) {
                if (value instanceof Array) {
                    value = jQuery.extend([], value);
                    for (var i = 0, length = value.length; i < length; i++) {
                        this.prepare(value[i], i, value);
                    }
                } else if (moment.isMoment(value)) {
                    if (value.isDate) {
                        value = new Sao.PYSON.Date(
                            value.year(),
                            value.month() + 1,
                            value.date()).pyson();
                    } else {
                        value = new Sao.PYSON.DateTime(
                            value.year(),
                            value.month() + 1,
                            value.date(),
                            value.hours(),
                            value.minutes(),
                            value.seconds(),
                            value.milliseconds() * 1000).pyson();
                    }
                } else if (moment.isDuration(value)) {
                    value = new Sao.PYSON.TimeDelta(
                        Math.round(value.asDays()),
                        value.seconds(),
                        value.milliseconds() * 1000).pyson();
                } else if (value instanceof Sao.Decimal) {
                    value = value.valueOf();
                } else if ((value instanceof Object) &&
                    !(value instanceof Sao.PYSON.PYSON)) {
                    value = jQuery.extend({}, value);
                    for (var p in value) {
                        this.prepare(value[p], p, value);
                    }
                }
            }
            if (parent) {
                parent[index] = value;
            }
            return parent || value;
        }

        encode(pyson) {
            pyson = this.prepare(pyson);
            return JSON.stringify(pyson, (k, v) => {
                if (v instanceof Sao.PYSON.PYSON) {
                    return this.prepare(v.pyson());
                } else if (v === null || v === undefined) {
                    return null;
                }
                return v;
            });
        }
    };

    Sao.PYSON.Decoder = class Decoder{
        constructor(context, noeval) {
            this.__context = context || {};
            this.noeval = noeval || false;
        }
        decode(str) {
            const reviver = (k, v) => {
                if (typeof v == 'object' && v !== null) {
                    var cls = Sao.PYSON[v.__class__];
                    if (cls) {
                        if (!this.noeval) {
                            return cls.eval_(v, this.__context);
                        } else {
                            var args = jQuery.extend({}, v);
                            delete args.__class__;
                            return Sao.PYSON[v.__class__].init_from_object(
                                args);
                        }
                    }
                }
                return v;
            };
            return JSON.parse(str, reviver);
        }
    };

    Sao.PYSON.eval.Eval = function(value, default_) {
        return new Sao.PYSON.Eval(value, default_);
    };
    Sao.PYSON.Eval = class Eval extends Sao.PYSON.PYSON {
        constructor(value, default_='') {
            super();
            this._value = value;
            this._default = default_;
        }
        pyson() {
            return {
                '__class__': 'Eval',
                'v': this._value,
                'd': this._default
            };
        }
        types() {
            if (this._default instanceof Sao.PYSON.PYSON) {
                return this._default.types();
            } else {
                return [typeof this._default];
            }
        }
        __string_params__() {
            const params = [this._value];
            if (this._default !== '') {
                params.push(this._default);
            }
            return params;
        }
        get basename() {
            var name = this._value;
            if (name.startsWith('_parent_')) {
                name = name.slice('_parent_'.length);
            }
            var idx = name.indexOf('.');
            if (idx >= 0) {
                name = name.substring(0, idx);
            }
            return name;
        }
        static create(...args) {
            return new Eval(...args);
        }
    };

    Sao.PYSON.Eval.eval_ = function(value, context) {
        var idx = value.v.indexOf('.');
        if ((idx >= 0) && !(value.v in context)) {
            return Sao.PYSON.Eval.eval_({
                'v': value.v.substring(idx + 1),
                'd': value.d,
            }, context[value.v.substring(0, idx)] || {});
        }
        if ((value.v in context) && (context[value.v] !== undefined)) {
            return context[value.v];
        } else {
            return value.d;
        }
    };
    Sao.PYSON.Eval.init_from_object = function(obj) {
        return new Sao.PYSON.Eval(obj.v, obj.d);
    };

    Sao.PYSON.eval.Not = function(value) {
        return new Sao.PYSON.Not(value);
    };
    Sao.PYSON.Not = class Not extends Sao.PYSON.PYSON {
        constructor(value) {
            super();
            if (value instanceof Sao.PYSON.PYSON) {
                if (jQuery(value.types()).not(['boolean', 'object']).length ||
                    jQuery(['boolean']).not(value.types()).length) {
                    value = new Sao.PYSON.Bool(value);
                    }
            } else if (typeof value != 'boolean') {
                value = new Sao.PYSON.Bool(value);
            }
            this._value = value;
        }
        pyson() {
            return {
                '__class__': 'Not',
                'v': this._value
                };
        }
        types() {
            return ['boolean'];
        }
        __string_params__() {
            return [this._value];
        }
    };

    Sao.PYSON.Not.eval_ = function(value, context) {
        return !Sao.PYSON.Bool.eval_(value, context);
    };
    Sao.PYSON.Not.init_from_object = function(obj) {
        return new Sao.PYSON.Not(obj.v);
    };

    Sao.PYSON.eval.Bool = function(value) {
        return new Sao.PYSON.Bool(value);
    };
    Sao.PYSON.Bool = class Bool extends Sao.PYSON.PYSON {
        constructor(value) {
            super();
            this._value = value;
        }
        pyson() {
            return {
                '__class__': 'Bool',
                'v': this._value
            };
        }
        types() {
            return ['boolean'];
        }
        __string_params__() {
            return [this._value];
        }
    };

    Sao.PYSON.Bool.eval_ = function(value, context) {
        if (moment.isMoment(value.v) && value.v.isTime) {
            return Boolean(value.v.hour() || value.v.minute() ||
                    value.v.second() || value.v.millisecond());
        } else if (moment.isDuration(value.v)) {
            return Boolean(value.v.valueOf());
        } else if (value.v instanceof Number) {
            return Boolean(value.v.valueOf());
        } else if (value.v instanceof Object) {
            return !jQuery.isEmptyObject(value.v);
        } else {
            return Boolean(value.v);
        }
    };
    Sao.PYSON.Bool.init_from_object = function(obj) {
        return new Sao.PYSON.Bool(obj.v);
    };


    Sao.PYSON.eval.And = function() {
        return new Sao.PYSON.And(...arguments);
    };
    Sao.PYSON.And = class And extends Sao.PYSON.PYSON {
        constructor() {
            var statements = jQuery.extend([], arguments);
            super();
            for (var i = 0, len = statements.length; i < len; i++) {
                var statement = statements[i];
                if (statement instanceof Sao.PYSON.PYSON) {
                    if (jQuery(statement.types()).not(['boolean']).length ||
                        jQuery(['boolean']).not(statement.types()).length) {
                        statements[i] = new Sao.PYSON.Bool(statement);
                        }
                } else if (typeof statement != 'boolean') {
                    statements[i] = new Sao.PYSON.Bool(statement);
                }
            }
            if (statements.length < 2) {
                throw 'must have at least 2 statements';
            }
            this._statements = statements;
        }
        pyson() {
            return {
                '__class__': 'And',
                's': this._statements
            };
        }
        types() {
            return ['boolean'];
        }
        __string_params__() {
            return this._statements;
        }
    };

    Sao.PYSON.And.eval_ = function(value, context) {
        var result = true;
        for (const statement of value.s) {
            result = result && statement;
        }
        return result;
    };
    Sao.PYSON.And.init_from_object = function(obj) {
        return new Sao.PYSON.And(...obj.s);
    };


    Sao.PYSON.eval.Or = function() {
        return new Sao.PYSON.Or(...arguments);
    };
    Sao.PYSON.Or = class Or extends Sao.PYSON.And {
        pyson() {
            var result = super.pyson();
            result.__class__ = 'Or';
            return result;
        }
    };

    Sao.PYSON.Or.eval_ = function(value, context) {
        var result = false;
        for (const statement of value.s) {
            result = result || statement;
        }
        return result;
    };
    Sao.PYSON.Or.init_from_object= function(obj) {
        return new Sao.PYSON.Or(...obj.s);
    };

    Sao.PYSON.eval.Equal = function(statement1, statement2) {
        return new Sao.PYSON.Equal(statement1, statement2);
    };
    Sao.PYSON.Equal = class Equal extends Sao.PYSON.PYSON {
        constructor(statement1, statement2) {
            super();
            var types1, types2;
            if (statement1 instanceof Sao.PYSON.PYSON) {
                types1 = statement1.types();
            } else {
                types1 = [typeof statement1];
            }
            if (statement2 instanceof Sao.PYSON.PYSON) {
                types2 = statement2.types();
            } else {
                types2 = [typeof statement2];
            }
            if (jQuery(types1).not(types2).length ||
                jQuery(types2).not(types1).length) {
                throw 'statements must have the same type';
                }
            this._statement1 = statement1;
            this._statement2 = statement2;
        }
        pyson() {
            return {
                '__class__': 'Equal',
                's1': this._statement1,
                's2': this._statement2
            };
        }
        types() {
            return ['boolean'];
        }
        __string_params__() {
            return [this._statement1, this._statement2];
        }
    };

    Sao.PYSON.Equal.eval_ = function(value, context) {
        if (value.s1 instanceof Array  && value.s2 instanceof Array) {
            return Sao.common.compare(value.s1, value.s2);
        } else if (moment.isMoment(value.s1) && moment.isMoment(value.s2)) {
            return ((value.s1.isDate == value.s2.isDate) &&
                (value.s1.isDateTime == value.s2.isDateTime) &&
                (value.s1.valueOf() == value.s2.valueOf()));
        } else if (moment.isDuration(value.s1) && moment.isDuration(value.s2)) {
            return value.s1.valueOf() == value.s2.value();
        } else {
            return value.s1 == value.s2;
        }
    };
    Sao.PYSON.Equal.init_from_object = function(obj) {
        return new Sao.PYSON.Equal(obj.s1, obj.s2);
    };

    Sao.PYSON.eval.Greater = function(statement1, statement2, equal) {
        return new Sao.PYSON.Greater(statement1, statement2, equal);
    };
    Sao.PYSON.Greater = class Greater extends Sao.PYSON.PYSON {
        constructor(statement1, statement2, equal=false) {
            super();
            var statements = [statement1, statement2];
            for (var i = 0; i < 2; i++) {
                var statement = statements[i];
                if (statement instanceof Sao.PYSON.PYSON) {
                    if ( (!(statement instanceof Sao.PYSON.DateTime ||
                        statement instanceof Sao.PYSON.Date ||
                        statement instanceof Sao.PYSON.TimeDelta)) &&
                        (jQuery(statement.types()).not(['number']).length) ) {
                        throw 'statement must be an integer, float, ' +
                            'date, datetime or timedelta';
                    }
                } else {
                    if (!~['number', 'object'].indexOf(typeof statement)) {
                        throw 'statement must be an integer, float, ' +
                            'date, datetime or timedelta';
                    }
                }
            }
            if (equal instanceof Sao.PYSON.PYSON) {
                if (jQuery(equal.types()).not(['boolean']).length ||
                    jQuery(['boolean']).not(equal.types()).length) {
                    equal = new Sao.PYSON.Bool(equal);
                    }
            } else if (typeof equal != 'boolean') {
                equal = new Sao.PYSON.Bool(equal);
            }
            this._statement1 = statement1;
            this._statement2 = statement2;
            this._equal = equal;
        }
        pyson() {
            return {
                '__class__': 'Greater',
                's1': this._statement1,
                's2': this._statement2,
                'e': this._equal
            };
        }
        types() {
            return ['boolean'];
        }
        __string_params__() {
            return [this._statement1, this._statement2, this._equal];
        }
    };

    Sao.PYSON.Greater._convert = function(value) {
        value = jQuery.extend({}, value);
        var values = [value.s1, value.s2];
        for (var i=0; i < 2; i++) {
            if (moment.isMoment(values[i])) {
                values[i] = values[i].valueOf();
            } else if (moment.isDuration(values[i])) {
                values[i] = values[i].valueOf();
            } else {
                values[i] = Number(values[i]);
            }
        }
        value.s1 = values[0];
        value.s2 = values[1];
        return value;
    };

    Sao.PYSON.Greater.eval_ = function(value, context) {
        if (value.s1 == null || value.s2 == null) {
            return false;
        }
        value = Sao.PYSON.Greater._convert(value);
        if (value.e) {
            return value.s1 >= value.s2;
        } else {
            return value.s1 > value.s2;
        }
    };
    Sao.PYSON.Greater.init_from_object = function(obj) {
        return new Sao.PYSON.Greater(obj.s1, obj.s2, obj.e);
    };

    Sao.PYSON.eval.Less = function(statement1, statement2, equal) {
        return new Sao.PYSON.Less(statement1, statement2, equal);
    };
    Sao.PYSON.Less = class Less extends Sao.PYSON.Greater {
        pyson() {
            var result = super.pyson();
            result.__class__ = 'Less';
            return result;
        }
    };

    Sao.PYSON.Less._convert = Sao.PYSON.Greater._convert;

    Sao.PYSON.Less.eval_ = function(value, context) {
        if (value.s1 == null || value.s2 == null) {
            return false;
        }
        value = Sao.PYSON.Less._convert(value);
        if (value.e) {
            return value.s1 <= value.s2;
        } else {
            return value.s1 < value.s2;
        }
    };
    Sao.PYSON.Less.init_from_object = function(obj) {
        return new Sao.PYSON.Less(obj.s1, obj.s2, obj.e);
    };

    Sao.PYSON.eval.If = function(condition, then_statement, else_statement) {
        return new Sao.PYSON.If(condition, then_statement, else_statement);
    };
    Sao.PYSON.If = class If extends Sao.PYSON.PYSON {
        constructor(condition, then_statement, else_statement=null) {
            super();
            if (condition instanceof Sao.PYSON.PYSON) {
                if (jQuery(condition.types()).not(['boolean']).length ||
                    jQuery(['boolean']).not(condition.types()).length) {
                    condition = new Sao.PYSON.Bool(condition);
                }
            } else if (typeof condition != 'boolean') {
                condition = new Sao.PYSON.Bool(condition);
            }
            this._condition = condition;
            this._then_statement = then_statement;
            this._else_statement = else_statement;
        }
        pyson() {
            return {
                '__class__': 'If',
                'c': this._condition,
                't': this._then_statement,
                'e': this._else_statement
            };
        }
        types() {
            var types;
            if (this._then_statement instanceof Sao.PYSON.PYSON) {
                types = this._then_statement.types();
            } else {
                types = [typeof this._then_statement];
            }
            if (this._else_statement instanceof Sao.PYSON.PYSON) {
                for (const type of this._else_statement.types()) {
                    if (!~types.indexOf(type)) {
                        types.push(type);
                    }
                }
            } else {
                const type = typeof this._else_statement;
                if (!~types.indexOf(type)) {
                    types.push(type);
                }
            }
            return types;
        }
        __string_params__() {
            return [this._condition, this._then_statement,
                this._else_statement];
        }
    };

    Sao.PYSON.If.eval_ = function(value, context) {
        if (value.c) {
            return value.t;
        } else {
            return value.e;
        }
    };
    Sao.PYSON.If.init_from_object = function(obj) {
        return new Sao.PYSON.If(obj.c, obj.t, obj.e);
    };

    Sao.PYSON.eval.Get = function(obj, key, default_) {
        return new Sao.PYSON.Get(obj, key, default_);
    };
    Sao.PYSON.Get = class Get extends Sao.PYSON.PYSON {
        constructor(obj, key, default_=null) {
            super();
            this._operator = 'get';
            if (obj instanceof Sao.PYSON.PYSON) {
                if (jQuery(obj.types()).not(['object']).length ||
                    jQuery(['object']).not(obj.types()).length) {
                    throw 'obj must be a dict';
                }
            } else {
                if (!(obj instanceof Object)) {
                    throw 'obj must be a dict';
                }
            }
            this._obj = obj;
            if (key instanceof Sao.PYSON.PYSON) {
                if (jQuery(key.types()).not(['string']).length ||
                    jQuery(['string']).not(key.types()).length) {
                    throw 'key must be a string';
                }
            } else {
                if (typeof key != 'string') {
                    throw 'key must be a string';
                }
            }
            this._key = key;
            this._default = default_;
        }
        pyson() {
            return {
                '__class__': 'Get',
                'v': this._obj,
                'k': this._key,
                'd': this._default
            };
        }
        types() {
            if (this._default instanceof Sao.PYSON.PYSON) {
                return this._default.types();
            } else {
                return [typeof this._default];
            }
        }
        __string_params__() {
            const params = [this._obj, this._key];
            if (this._default !== '') {
                params.push(this._default);
            }
            return params;
        }
    };

    Sao.PYSON.Get.eval_ = function(value, context) {
        if (value.k in value.v) {
            return value.v[value.k];
        } else {
            return value.d;
        }
    };
    Sao.PYSON.Get.init_from_object = function(obj) {
        return new Sao.PYSON.Get(obj.v, obj.k, obj.d);
    };

    Sao.PYSON.eval.In = function(key, obj) {
        return new Sao.PYSON.In(key, obj);
    };
    Sao.PYSON.In = class In extends Sao.PYSON.PYSON {
        constructor(key, obj) {
            super();
            this._operator = 'in_';
            if (key instanceof Sao.PYSON.PYSON) {
                if (jQuery(key.types()).not(['string', 'number']).length) {
                    throw 'key must be a string or a number';
                }
            } else {
                if (!~['string', 'number'].indexOf(typeof key)) {
                    throw 'key must be a string or a number';
                }
            }
            if (obj instanceof Sao.PYSON.PYSON) {
                if (jQuery(obj.types()).not(['object']).length ||
                    jQuery(['object']).not(obj.types()).length) {
                    throw 'obj must be a dict or a list';
                }
            } else {
                if (!(obj instanceof Object)) {
                    throw 'obj must be a dict or a list';
                }
            }
            this._key = key;
            this._obj = obj;
        }
        pyson() {
            return {'__class__': 'In',
                'k': this._key,
                'v': this._obj
            };
        }
        types() {
            return ['boolean'];
        }
        toString() {
            const params = this.__string_params__();
            if (params[1] instanceof Sao.PYSON.PYSON) {
                const args = params.slice().map(Sao.PYSON.toString);
                args.splice(1, 1);
                return `${params[1]}.contains(` + args.join(', ') + ')';
            } else {
                return super.toString();
            }
        }
        __string_params__() {
            return [this._key, this._obj];
        }
    };

    Sao.PYSON.In.eval_ = function(value, context) {
        if (value.v) {
            if (value.v.indexOf) {
                return Boolean(~value.v.indexOf(value.k));
            } else {
                return !!value.v[value.k];
            }
        } else {
            return false;
        }
    };
    Sao.PYSON.In.init_from_object = function(obj) {
        return new Sao.PYSON.In(obj.k, obj.v);
    };

    Sao.PYSON.eval.Date = function(year, month, day, delta_years, delta_months,
            delta_days) {
        return new Sao.PYSON.Date(year, month, day, delta_years, delta_months,
                delta_days);
    };
    Sao.PYSON.Date = class Date extends Sao.PYSON.PYSON {
        constructor(
            year=null, month=null, day=null,
            delta_years=0, delta_months=0, delta_days=0, start=null) {
            super();
            this._test(year, 'year');
            this._test(month, 'month');
            this._test(day, 'day');
            this._test(delta_years, 'delta_years');
            this._test(delta_days, 'delta_days');
            this._test(delta_months, 'delta_months');

            this._year = year;
            this._month = month;
            this._day = day;
            this._delta_years = delta_years;
            this._delta_months = delta_months;
            this._delta_days = delta_days;
            this._start = start;
        }
        pyson() {
            return {
                '__class__': 'Date',
                'y': this._year,
                'M': this._month,
                'd': this._day,
                'dy': this._delta_years,
                'dM': this._delta_months,
                'dd': this._delta_days,
                'start': this._start,
            };
        }
        types() {
            return ['object'];
        }
        _test(value, name) {
            if (value instanceof Sao.PYSON.PYSON) {
                if (jQuery(value.types()).not(
                        ['number', typeof null]).length) {
                    throw name + ' must be an integer or None';
                }
            } else {
                if ((typeof value != 'number') && (value !== null)) {
                    throw name + ' must be an integer or None';
                }
            }
        }
        __string_params__() {
            return [this._year, this._month, this._day, this._delta_years,
                this._delta_months, this._delta_days, this._start];
        }
    };

    Sao.PYSON.Date.eval_ = function(value, context) {
        var date = value.start;
        if (date && date.isDateTime) {
            date = Sao.Date(date.year(), date.month(), date.date());
        }
        if (!date || !date.isDate) {
            date = Sao.Date();
        }
        if (value.y) date.year(value.y);
        if (value.M) date.month(value.M - 1);
        if (value.d) date.date(value.d);
        if (value.dy) date.add(value.dy, 'y');
        if (value.dM) date.add(value.dM, 'M');
        if (value.dd) date.add(value.dd, 'd');
        return date;
    };
    Sao.PYSON.Date.init_from_object = function(obj) {
        return new Sao.PYSON.Date(
            obj.y, obj.M, obj.d, obj.dy, obj.dM, obj.dd, obj.start);
    };

    Sao.PYSON.eval.DateTime = function(year, month, day, hour, minute, second,
            microsecond, delta_years, delta_months, delta_days, delta_hours,
            delta_minutes, delta_seconds, delta_microseconds) {
        return new Sao.PYSON.DateTime(year, month, day, hour, minute, second,
            microsecond, delta_years, delta_months, delta_days, delta_hours,
            delta_minutes, delta_seconds, delta_microseconds);
    };
    Sao.PYSON.DateTime = class DateTime extends Sao.PYSON.Date {
        constructor(
            year=null, month=null, day=null,
            hour=null, minute=null, second=null, microsecond=null,
            delta_years=0, delta_months=0, delta_days=0, 
            delta_hours=0, delta_minutes=0, delta_seconds=0,
            delta_microseconds=0, start=null) {
            super(
                year, month, day, delta_years, delta_months, delta_days,
                start);
            this._test(hour, 'hour');
            this._test(minute, 'minute');
            this._test(second, 'second');
            this._test(microsecond, 'microsecond');
            this._test(delta_hours, 'delta_hours');
            this._test(delta_minutes, 'delta_minutes');
            this._test(delta_seconds, 'delta_seconds');
            this._test(delta_microseconds, 'delta_microseconds');

            this._hour = hour;
            this._minute = minute;
            this._second = second;
            this._microsecond = microsecond;
            this._delta_hours = delta_hours;
            this._delta_minutes = delta_minutes;
            this._delta_seconds = delta_seconds;
            this._delta_microseconds = delta_microseconds;
        }
        pyson() {
            var result = super.pyson();
            result.__class__ = 'DateTime';
            result.h = this._hour;
            result.m = this._minute;
            result.s = this._second;
            result.ms = this._microsecond;
            result.dh = this._delta_hours;
            result.dm = this._delta_minutes;
            result.ds = this._delta_seconds;
            result.dms = this._delta_microseconds;
            return result;
        }
        __string_params__() {
            var date_params = super.__string_params__();
            return [date_params[0], date_params[1], date_params[2],
                this._hour, this._minute, this._second, this._microsecond,
                date_params[3], date_params[4], date_params[5],
                this._delta_hours, this._delta_minutes, this._delta_seconds,
                this._delta_microseconds, date_params[6]];
        }
    };

    Sao.PYSON.DateTime.eval_ = function(value, context) {
        var date = value.start;
        if (date && date.isDate) {
            date = Sao.DateTime.combine(date, Sao.Time());
        }
        if (!date || !date.isDateTime) {
            date = Sao.DateTime();
            date.utc();
        }
        if (value.y) date.year(value.y);
        if (value.M) date.month(value.M - 1);
        if (value.d) date.date(value.d);
        if (value.h !== null) date.hour(value.h);
        if (value.m !== null) date.minute(value.m);
        if (value.s !== null) date.second(value.s);
        if (value.ms !== null) date.milliseconds(value.ms / 1000);
        if (value.dy) date.add(value.dy, 'y');
        if (value.dM) date.add(value.dM, 'M');
        if (value.dd) date.add(value.dd, 'd');
        if (value.dh) date.add(value.dh, 'h');
        if (value.dm) date.add(value.dm, 'm');
        if (value.ds) date.add(value.ds, 's');
        if (value.dms) date.add(value.dms / 1000, 'ms');
        return date;
    };
    Sao.PYSON.DateTime.init_from_object = function(obj) {
        return new Sao.PYSON.DateTime(obj.y, obj.M, obj.d, obj.h, obj.m, obj.s,
            obj.ms, obj.dy, obj.dM, obj.dd, obj.dh, obj.dm, obj.ds, obj.dms);
    };

    Sao.PYSON.eval.TimeDelta = function(days, seconds, microseconds) {
        return new Sao.PYSON.TimeDelta(days, seconds, microseconds);
    };
    Sao.PYSON.TimeDelta = class TimeDelta extends Sao.PYSON.PYSON {
        constructor(days=0, seconds=0, microseconds=0) {
            super();
            function test(value, name) {
                if (value instanceof Sao.PYSON.TimeDelta) {
                    if (jQuery(value.types()).not(['number']).length)
                    {
                        throw name + ' must be an integer';
                    }
                } else {
                    if (typeof value != 'number') {
                        throw name + ' must be an integer';
                    }
                }
                return value;
            }
            this._days = test(days, 'days');
            this._seconds = test(seconds, 'seconds');
            this._microseconds = test(microseconds, 'microseconds');
        }
        pyson() {
            return {
                '__class__': 'TimeDelta',
                'd': this._days,
                's': this._seconds,
                'm': this._microseconds,
            };
        }
        types() {
            return ['object'];
        }
        __string_params__() {
            return [this._days, this._seconds, this._microseconds];
        }
    };
    Sao.PYSON.TimeDelta.eval_ = function(value, context) {
        return Sao.TimeDelta(value.d, value.s, value.m / 1000);
    };
    Sao.PYSON.TimeDelta.init_from_object = function(obj) {
        return new Sao.PYSON.TimeDelta(obj.d, obj.s, obj.microseconds);
    };

    Sao.PYSON.eval.Len = function(value) {
        return new Sao.PYSON.Len(value);
    };
    Sao.PYSON.Len = class Len extends Sao.PYSON.PYSON {
        constructor(value) {
            super();
            if (value instanceof Sao.PYSON.PYSON) {
                if (jQuery(value.types()).not(['object', 'string']).length ||
                    jQuery(['object', 'string']).not(value.types()).length) {
                    throw 'value must be an object or a string';
                }
            } else {
                if ((typeof value != 'object') && (typeof value != 'string')) {
                    throw 'value must be an object or a string';
                }
            }
            this._value = value;
        }
        pyson() {
            return {
                '__class__': 'Len',
                'v': this._value
            };
        }
        types() {
            return ['integer'];
        }
        __string_params__() {
            return [this._value];
        }
    };

    Sao.PYSON.Len.eval_ = function(value, context) {
        if (typeof value.v == 'object') {
            return Object.keys(value.v).length;
        } else {
            return value.v.length;
        }
    };
    Sao.PYSON.Len.init_from_object = function(obj) {
        return new Sao.PYSON.Len(obj.v);
    };
}());
