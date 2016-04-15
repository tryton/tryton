/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.PYSON = {};

    Sao.PYSON.PYSON = Sao.class_(Object, {
        init: function() {
        },
        pyson: function() {
            throw 'NotImplementedError';
        },
        types: function() {
            throw 'NotImplementedError';
        }
    });

    Sao.PYSON.PYSON.eval_ = function(value, context) {
        throw 'NotImplementedError';
    };

    Sao.PYSON.Encoder = Sao.class_(Object, {
        encode: function(pyson) {
            return JSON.stringify(pyson, function(k, v) {
                if (v instanceof Sao.PYSON.PYSON) {
                    return v.pyson();
                } else if (v._isAMomentObject) {
                    if (v.isDate) {
                        return Sao.PYSON.Date(
                            v.getFullYear(),
                            v.getMonth(),
                            v.getDate()).pyson();
                    } else {
                        return Sao.PYSON.DateTime(
                            v.getFullYear(),
                            v.getMonth(),
                            v.getDate(),
                            v.getHours(),
                            v.getMinutes(),
                            v.getSeconds(),
                            v.getMilliseconds()).pyson();
                    }
                }
                return v;
            });
        }
    });

    Sao.PYSON.Decoder = Sao.class_(Object, {
        init: function(context) {
            this.__context = context || {};
        },
        decode: function(str) {
            var reviver = function(k, v) {
                if (typeof v == 'object' && v !== null) {
                    var cls = Sao.PYSON[v.__class__];
                    if (cls) {
                        return cls.eval_(v, this.__context);
                    }
                }
                return v;
            };
            return JSON.parse(str, reviver.bind(this));
        }
    });

    Sao.PYSON.Eval = Sao.class_(Sao.PYSON.PYSON, {
        init: function(value, default_) {
            if (default_ === undefined) {
                default_ = '';
            }
            Sao.PYSON.Eval._super.init.call(this);
            this._value = value;
            this._default = default_;
        },
        pyson: function() {
            return {
                '__class__': 'Eval',
                'v': this._value,
                'd': this._default
            };
        },
        types: function() {
            if (this._default instanceof Sao.PYSON.PYSON) {
                return this._default.types();
            } else {
                return [typeof this._default];
            }
        }
    });

    Sao.PYSON.Eval.eval_ = function(value, context) {
        if (value.v in context) {
            return context[value.v];
        } else {
            return value.d;
        }
    };

    Sao.PYSON.Not = Sao.class_(Sao.PYSON.PYSON, {
        init: function(value) {
            Sao.PYSON.Not._super.init.call(this);
            if (value instanceof Sao.PYSON.PYSON) {
                if (jQuery(value.types()).not(['boolean']).length ||
                    jQuery(['boolean']).not(value.types()).length) {
                    throw 'value must be boolean';
                    }
            } else {
                if (typeof value != 'boolean') {
                    throw 'value must be boolean';
                }
            }
            this._value = value;
        },
        pyson: function() {
            return {
                '__class__': 'Not',
                'v': this._value
                };
        },
        types: function() {
            return ['boolean'];
        }
    });

    Sao.PYSON.Not.eval_ = function(value, context) {
        return !value.v;
    };

    Sao.PYSON.Bool = Sao.class_(Sao.PYSON.PYSON, {
        init: function(value) {
            Sao.PYSON.Bool._super.init.call(this);
            this._value = value;
        },
        pyson: function() {
            return {
                '__class__': 'Bool',
                'v': this._value
                };
        },
        types: function() {
            return ['boolean'];
        }
    });

    Sao.PYSON.Bool.eval_ = function(value, context) {
        if (value.v instanceof Object) {
            return !jQuery.isEmptyObject(value.v);
        } else {
            return Boolean(value.v);
        }
    };


    Sao.PYSON.And = Sao.class_(Sao.PYSON.PYSON, {
        init: function(statements) {
            if (statements === undefined) {
                statements = [];
            }
            Sao.PYSON.And._super.init.call(this);
            for (var i = 0, len = statements.length; i < len; i++) {
                var statement = statements[i];
                if (statement instanceof Sao.PYSON.PYSON) {
                    if (jQuery(statement.types()).not(['boolean']).length ||
                        jQuery(['boolean']).not(statement.types()).length) {
                        throw 'statement must be boolean';
                        }
                } else {
                    if (typeof statement != 'boolean') {
                        throw 'statement must be boolean';
                    }
                }
            }
            if (statements.length < 2) {
                throw 'must have at least 2 statements';
            }
            this._statements = statements;
        },
        pyson: function() {
            return {
                '__class__': 'And',
                's': this._statements
            };
        },
        types: function() {
            return ['boolean'];
        }
    });

    Sao.PYSON.And.eval_ = function(value, context) {
        var result = true;
        for (var i = 0, len = value.s.length; i < len; i++) {
            var statement = value.s[i];
            result = result && statement;
        }
        return result;
    };


    Sao.PYSON.Or = Sao.class_(Sao.PYSON.And, {
        pyson: function() {
            var result = Sao.PYSON.Or._super.pyson.call(this);
            result.__class__ = 'Or';
            return result;
        }
    });

    Sao.PYSON.Or.eval_ = function(value, context) {
        var result = false;
        for (var i = 0, len = value.s.length; i < len; i++) {
            var statement = value.s[i];
            result = result || statement;
        }
        return result;
    };

    Sao.PYSON.Equal = Sao.class_(Sao.PYSON.PYSON, {
        init: function(statement1, statement2) {
            Sao.PYSON.Equal._super.init.call(this);
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
        },
        pyson: function() {
            return {
                '__class__': 'Equal',
                's1': this._statement1,
                's2': this._statement2
            };
        },
        types: function() {
            return ['boolean'];
        }
    });

    Sao.PYSON.Equal.eval_ = function(value, context) {
        if (value.s1 instanceof Array  && value.s2 instanceof Array) {
            return Sao.common.compare(value.s1, value.s2);
        } else {
            return value.s1 == value.s2;
        }
    };

    Sao.PYSON.Greater = Sao.class_(Sao.PYSON.PYSON, {
        init: function(statement1, statement2, equal) {
            Sao.PYSON.Greater._super.init.call(this);
            var statements = [statement1, statement2];
            for (var i = 0; i < 2; i++) {
                var statement = statements[i];
                if (statement instanceof Sao.PYSON.PYSON) {
                    if (jQuery(statement).not(['number']).length) {
                        throw 'statement must be an integer or a float';
                    }
                } else {
                    if (typeof statement != 'number') {
                        throw 'statement must be an integer or a float';
                    }
                }
            }
            if (equal === undefined) {
                equal = false;
            }
            if (equal instanceof Sao.PYSON.PYSON) {
                if (jQuery(equal.types()).not(['boolean']).length ||
                    jQuery(['boolean']).not(equal.types()).length) {
                    throw 'equal must be boolean';
                    }
            } else {
                if (typeof equal != 'boolean') {
                    throw 'equal must be boolean';
                }
            }
            this._statement1 = statement1;
            this._statement2 = statement2;
            this._equal = equal;
        },
        pyson: function() {
            return {
                '__class__': 'Greater',
                's1': this._statement1,
                's2': this._statement2,
                'e': this._equal
            };
        },
        types: function() {
            return ['boolean'];
        }
    });

    Sao.PYSON.Greater._convert = function(value) {
        value = jQuery.extend({}, value);
        value.s1 = Number(value.s1);
        value.s2 = Number(value.s2);
        return value;
    };

    Sao.PYSON.Greater.eval_ = function(value, context) {
        value = Sao.PYSON.Greater._convert(value);
        if (value.e) {
            return value.s1 >= value.s2;
        } else {
            return value.s1 > value.s2;
        }
    };

    Sao.PYSON.Less = Sao.class_(Sao.PYSON.Greater, {
        pyson: function() {
            var result = Sao.PYSON.Less._super.pyson.call(this);
            result.__class__ = 'Less';
            return result;
        }
    });

    Sao.PYSON.Less._convert = Sao.PYSON.Greater._convert;

    Sao.PYSON.Less.eval_ = function(value, context) {
        value = Sao.PYSON.Less._convert(value);
        if (value.e) {
            return value.s1 <= value.s2;
        } else {
            return value.s1 < value.s2;
        }
    };

    Sao.PYSON.If = Sao.class_(Sao.PYSON.PYSON, {
        init: function(condition, then_statement, else_statement) {
            Sao.PYSON.If._super.init.call(this);
            if (condition instanceof Sao.PYSON.PYSON) {
                if (jQuery(condition.types()).not(['boolean']).length ||
                    jQuery(['boolean']).not(condition.types()).length) {
                    throw 'condition must be boolean';
                }
            } else {
                if (typeof condition != 'boolean') {
                    throw 'condition must be boolean';
                }
            }
            var then_types, else_types;
            if (then_statement instanceof Sao.PYSON.PYSON) {
                then_types = then_statement.types();
            } else {
                then_types = [typeof then_statement];
            }
            if (else_statement === undefined) {
                else_statement = null;
            }
            if (else_statement instanceof Sao.PYSON.PYSON) {
                else_types = else_statement.types();
            } else {
                else_types = [typeof else_statement];
            }
            if (jQuery(then_types).not(else_types).length ||
                jQuery(else_types).not(then_types).length) {
                throw 'then and else statements must be the same type';
            }
            this._condition = condition;
            this._then_statement = then_statement;
            this._else_statement = else_statement;
        },
        pyson: function() {
            return {
                '__class__': 'If',
                'c': this._condition,
                't': this._then_statement,
                'e': this._else_statement
            };
        },
        types: function() {
            if (this._then_statement instanceof Sao.PYSON.PYSON) {
                return this._then_statement.types();
            } else {
                return [typeof this._then_statement];
            }
        }
    });

    Sao.PYSON.If.eval_ = function(value, context) {
        if (value.c) {
            return value.t;
        } else {
            return value.e;
        }
    };

    Sao.PYSON.Get = Sao.class_(Sao.PYSON.PYSON, {
        init: function(obj, key, default_) {
            Sao.PYSON.Get._super.init.call(this);
            if (default_ === undefined) {
                default_ = null;
            }
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
        },
        pyson: function() {
            return {
                '__class__': 'Get',
                'v': this._obj,
                'k': this._key,
                'd': this._default
            };
        },
        types: function() {
            if (this._default instanceof Sao.PYSON.PYSON) {
                return this._default.types();
            } else {
                return [typeof this._default];
            }
        }
    });

    Sao.PYSON.Get.eval_ = function(value, context) {
        if (value.k in value.v) {
            return value.v[value.k];
        } else {
            return value.d;
        }
    };

    Sao.PYSON.In = Sao.class_(Sao.PYSON.PYSON, {
        init: function(key, obj) {
            Sao.PYSON.In._super.init.call(this);
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
        },
        pyson: function() {
            return {'__class__': 'In',
                'k': this._key,
                'v': this._obj
            };
        },
        types: function() {
            return ['boolean'];
        }
    });

    Sao.PYSON.In.eval_ = function(value, context) {
        if (value.v.indexOf) {
            return Boolean(~value.v.indexOf(value.k));
        } else {
            return !!value.v[value.k];
        }
    };

    Sao.PYSON.Date = Sao.class_(Sao.PYSON.PYSON, {
        init: function(year, month, day, delta_years, delta_months, delta_days)
        {
            Sao.PYSON.Date._super.init.call(this);
            if (year === undefined) year = null;
            if (month === undefined) month = null;
            if (day === undefined) day = null;
            if (delta_years === undefined) delta_years = 0;
            if (delta_months === undefined) delta_months = 0;
            if (delta_days === undefined) delta_days = 0;

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
        },
        pyson: function() {
            return {
                '__class__': 'Date',
                'y': this._year,
                'M': this._month,
                'd': this._day,
                'dy': this._delta_years,
                'dM': this._delta_months,
                'dd': this._delta_days
            };
        },
        types: function() {
            return ['object'];
        },
        _test: function(value, name) {
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
    });

    Sao.PYSON.Date.eval_ = function(value, context) {
        var date = Sao.Date(value.y, value.M && value.M - 1, value.d);
        if (value.dy) date.add(value.dy, 'y');
        if (value.dM) date.add(value.dM, 'M');
        if (value.dd) date.add(value.dd, 'd');
        return date;
    };

    Sao.PYSON.DateTime = Sao.class_(Sao.PYSON.Date, {
        init: function(year, month, day, hour, minute, second, microsecond,
                  delta_years, delta_months, delta_days, delta_hours,
                  delta_minutes, delta_seconds, delta_microseconds) {
            Sao.PYSON.DateTime._super.init.call(this, year, month, day,
                delta_years, delta_months, delta_days);
            if (hour === undefined) hour = null;
            if (minute === undefined) minute = null;
            if (second === undefined) second = null;
            if (microsecond === undefined) microsecond = null;
            if (delta_hours === undefined) delta_hours = 0;
            if (delta_minutes === undefined) delta_minutes = 0;
            if (delta_seconds === undefined) delta_seconds = 0;
            if (delta_microseconds === undefined) delta_microseconds = 0;

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
        },
        pyson: function() {
            var result = Sao.PYSON.DateTime._super.pyson.call(this);
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
    });

    Sao.PYSON.DateTime.eval_ = function(value, context) {
        var date = Sao.DateTime(value.y, value.M && value.M - 1, value.d,
                value.h, value.m, value.s, value.ms && value.ms / 1000);
        if (value.dy) date.add(value.dy, 'y');
        if (value.dM) date.add(value.dM, 'M');
        if (value.dd) date.add(value.dd, 'd');
        if (value.dh) date.add(value.dh, 'h');
        if (value.dm) date.add(value.dm, 'm');
        if (value.ds) date.add(value.ds, 's');
        if (value.dms) date.add(value.dms / 1000, 'ms');
        return date;
    };

    Sao.PYSON.Len = Sao.class_(Sao.PYSON.PYSON, {
        init: function(value) {
            Sao.PYSON.Len._super.init.call(this);
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
        },
        pyson: function() {
            return {
                '__class__': 'Len',
                'v': this._value
            };
        },
        types: function() {
            return ['integer'];
        }
    });

    Sao.PYSON.Len.eval_ = function(value, context) {
        if (typeof value.v == 'object') {
            return Object.keys(value.v).length;
        } else {
            return value.v.length;
        }
    };
}());
