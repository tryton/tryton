/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    var SaoTest = {
        'login': 'admin',
        'password': 'admin',
        'admin_password': 'admin',
        'language': 'en_US',
        'dbname': 'test_' + new Date().getTime()
    };

    QUnit.test('JSON', function() {
        var tests = {
            'array': [1, 2, 3],
            'object': {
                'foo': true,
                'bar': false
            },
            'datetime': new Date(2012, 11, 29, 19, 59, 10),
            'date': new Date(2012, 11, 29),
            'decimal': new Sao.Decimal(1.1),
            'null': null
        };
        for (var name in tests) {
            var test = tests[name];
            var result = Sao.rpc.convertJSONObject(jQuery.parseJSON(
                    JSON.stringify(Sao.rpc.prepareObject(test))));
            var ok_;
            if (name == 'null') {
                ok_ = test == result;
            } else {
                ok_ = test.toString() == result.toString();
            }
            QUnit.ok(ok_, 'JSON ' + name);
        }
    });

    QUnit.test('PYSON Decoder', function() {
        var decoder = new Sao.PYSON.Decoder();
        QUnit.strictEqual(decoder.decode('null'), null, "decode('null')");
    });

    QUnit.test('PYSON.Eval', function() {
        var value;
        value = new Sao.PYSON.Eval('test').pyson();
        QUnit.strictEqual(value.__class__, 'Eval', "Eval('test').pyson()");
        QUnit.strictEqual(value.v, 'test', "Eval('test').pyson()");
        QUnit.strictEqual(value.d, '', "Eval('test').pyson()");
        value = new Sao.PYSON.Eval('test', 'foo').pyson();
        QUnit.strictEqual(value.__class__, 'Eval',
            "Eval('test', 'foo').pyson()");
        QUnit.strictEqual(value.v, 'test', "Eval('test', 'foo').pyson()");
        QUnit.strictEqual(value.d, 'foo', "Eval('test', 'foo').pyson()");

        QUnit.ok(Sao.common.compare(new Sao.PYSON.Eval('test', 'foo').types(),
                [typeof 'foo']), "Eval('test', 'foo').types()");
        QUnit.ok(Sao.common.compare(new Sao.PYSON.Eval('test', 1).types(),
                [typeof 1]), "Eval('test', 1).types()");

        var eval_;
        eval_ = new Sao.PYSON.Encoder().encode(new Sao.PYSON.Eval('test', 0));
        QUnit.strictEqual(new Sao.PYSON.Decoder({test: 1}).decode(eval_), 1,
            "decode(Eval('test', 0))");
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), 0,
            "decode(Eval('test', 0))");
    });

    QUnit.test('PYSON Not', function() {
        var value = new Sao.PYSON.Not(true).pyson();
        QUnit.strictEqual(value.__class__, 'Not', 'Not(true).pyson()');
        QUnit.strictEqual(value.v, true, 'Not(true).pyson()');

        QUnit.throws(function() {
            new Sao.PYSON.Not('foo');
        }, 'value must be boolean', "Not('foo')");

        QUnit.ok(Sao.common.compare(new Sao.PYSON.Not(true).types(),
                ['boolean']), 'Not(true).types()');

        var eval_;
        eval_ = new Sao.PYSON.Encoder().encode(new Sao.PYSON.Not(true));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
            'decode(Not(true))');
        eval_ = new Sao.PYSON.Encoder().encode(new Sao.PYSON.Not(false));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
            'decode(Not(false))');
    });

    QUnit.test('PYSON Bool', function() {
        var value = new Sao.PYSON.Bool('test').pyson();
        QUnit.strictEqual(value.__class__, 'Bool', "Bool('test').pyson()");
        QUnit.strictEqual(value.v, 'test', "Bool('test').pyson()");

        QUnit.ok(Sao.common.compare(new Sao.PYSON.Bool('test').types(),
                ['boolean']), "Bool('test').types()");

        var eval_;
        eval_ = new Sao.PYSON.Encoder().encode(new Sao.PYSON.Bool(true));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
            'decode(Bool(true))');

        eval_ = new Sao.PYSON.Encoder().encode(new Sao.PYSON.Bool(false));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
            'decode(Bool(false))');

        eval_ = new Sao.PYSON.Encoder().encode(new Sao.PYSON.Bool('test'));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
            "decode(Bool('test'))");

        eval_ = new Sao.PYSON.Encoder().encode(new Sao.PYSON.Bool(''));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
            "decode(Bool(''))");

        eval_ = new Sao.PYSON.Encoder().encode(new Sao.PYSON.Bool(1));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
            'decode(Bool(1))');

        eval_ = new Sao.PYSON.Encoder().encode(new Sao.PYSON.Bool(0));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
            'decode(Bool(0))');

        eval_ = new Sao.PYSON.Encoder().encode(new Sao.PYSON.Bool(['test']));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
            "decode(Bool(['test']))");

        eval_ = new Sao.PYSON.Encoder().encode(new Sao.PYSON.Bool([]));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
            'decode(Bool([]))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Bool({foo: 'bar'}));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
            "decode(Bool({foo: 'bar'}))");

        eval_ = new Sao.PYSON.Encoder().encode(new Sao.PYSON.Bool({}));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
            'decode(Bool({}))');
    });

    QUnit.test('PYSON And', function() {
        var value = new Sao.PYSON.And([true, false]).pyson();
        QUnit.strictEqual(value.__class__, 'And', 'And([true, false]).pyson()');
        QUnit.ok(Sao.common.compare(value.s, [true, false]),
            'And([true, false]).pyson()');

        QUnit.throws(function() {
            new Sao.PYSON.And(['test', false]);
        }, 'statement must be boolean', "And(['test', false])");
        QUnit.throws(function() {
            new Sao.PYSON.And([true, 'test']);
        }, 'statement must be boolean', "And([true, 'test'])");
        QUnit.throws(function() {
            new Sao.PYSON.And([true, false, 'test']);
        }, 'statement must be boolean', "And([true, false, 'test'])");
        QUnit.throws(function() {
            new Sao.PYSON.And([true]);
        }, 'must have at least 2 statements', 'And([true])');
        QUnit.throws(function() {
            new Sao.PYSON.And([]);
        }, 'must have at least 2 statements', 'And([])');
        QUnit.throws(function() {
            new Sao.PYSON.And();
        }, 'must have at least 2 statements', 'And([])');

        QUnit.ok(Sao.common.compare(new Sao.PYSON.And([true, false]).types(),
                    ['boolean']), 'And([true, false]).types()');

        var eval_;
        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.And([true, true]));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
                'decode(And([true, true]))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.And([true, true, true]));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
                'decode(And([true, true, true]))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.And([true, false]));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
                'decode(And([true, false]))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.And([false, true]));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
                'decode(And([false, true]))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.And([false, false]));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
                'decode(And([false, false]))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.And([false, false, false]));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
                'decode(And([false, false, false]))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.And([true, false, false]));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
                'decode(And([true, false, false]))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.And([false, true, false]));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
                'decode(And([false, true, false]))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.And([false, false, true]));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
                'decode(And([false, false, true]))');
    });

    QUnit.test('PYSON Or', function() {
        var value = new Sao.PYSON.Or([true, false]).pyson();
        QUnit.strictEqual(value.__class__, 'Or', 'Or([true, false]).pyson()');
        QUnit.ok(Sao.common.compare(value.s, [true, false]),
            'Or([true, false]).pyson()');

        QUnit.throws(function() {
            new Sao.PYSON.Or(['test', false]);
        }, 'statement must be boolean', "Or(['test', false])");
        QUnit.throws(function() {
            new Sao.PYSON.Or([true, 'test']);
        }, 'statement must be boolean', "Or([true, 'test'])");
        QUnit.throws(function() {
            new Sao.PYSON.Or([true, false, 'test']);
        }, 'statement must be boolean', "Or([true, false, 'test'])");
        QUnit.throws(function() {
            new Sao.PYSON.Or([true]);
        }, 'must have at least 2 statements', 'Or([true])');
        QUnit.throws(function() {
            new Sao.PYSON.Or([]);
        }, 'must have at least 2 statements', 'Or([])');
        QUnit.throws(function() {
            new Sao.PYSON.Or();
        }, 'must have at least 2 statements', 'Or([])');

        QUnit.ok(Sao.common.compare(new Sao.PYSON.Or([true, false]).types(),
                    ['boolean']), 'Or([true, false]).types()');

        var eval_;
        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Or([true, true]));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
                'decode(Or([true, true]))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Or([true, true, true]));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
                'decode(Or([true, true, true]))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Or([true, false]));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
                'decode(Or([true, false]))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Or([false, true]));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
                'decode(Or([false, true]))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Or([false, false]));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
                'decode(Or([false, false]))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Or([false, false, false]));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
                'decode(Or([false, false, false]))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Or([true, false, false]));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
                'decode(Or([true, false, false]))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Or([false, true, false]));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
                'decode(Or([false, true, false]))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Or([false, false, true]));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
                'decode(Or([false, false, true]))');
    });

    QUnit.test('PYSON Equal', function() {
        var value = new Sao.PYSON.Equal('test', 'test').pyson();
        QUnit.strictEqual(value.__class__, 'Equal',
            "Equal('test', 'test').pyson()");
        QUnit.strictEqual(value.s1, 'test', "Equal('test', 'test').pyson()");
        QUnit.strictEqual(value.s2, 'test', "Equal('test', 'test').pyson()");

        QUnit.throws(function() {
            new Sao.PYSON.Equal('test', true);
        }, 'statements must have the same type');

        QUnit.ok(Sao.common.compare(new Sao.PYSON.Equal('test', 'test').types(),
                ['boolean']), "Equal('test', 'test').types()");

        var eval_;
        eval_ = new Sao.PYSON.Encoder().encode(
            new Sao.PYSON.Equal('test', 'test'));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
            "decode(Equal('test', 'test'))");

        eval_ = new Sao.PYSON.Encoder().encode(
            new Sao.PYSON.Equal('foo', 'bar'));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
            "decode(Equal('test', 'test'))");
    });

    QUnit.test('PYSON Greater', function() {
        var value = new Sao.PYSON.Greater(1, 0).pyson();
        QUnit.strictEqual(value.__class__, 'Greater', 'Greater(1, 0).pyson()');
        QUnit.strictEqual(value.s1, 1, 'Greater(1, 0).pyson()');
        QUnit.strictEqual(value.s2, 0, 'Greater(1, 0).pyson()');
        QUnit.strictEqual(value.e, false, 'Greater(1, 0).pyson()');

        QUnit.throws(function() {
            new Sao.PYSON.Greater('test', 0);
        }, 'statement must be an integer or a float');
        QUnit.throws(function() {
            new Sao.PYSON.Greater(1, 'test');
        }, 'statement must be an integer or a float');
        QUnit.throws(function() {
            new Sao.PYSON.Greater(1, 0, 'test');
        }, 'equal must be boolean');

        QUnit.ok(Sao.common.compare(new Sao.PYSON.Greater(1, 0).types(),
                ['boolean']), 'Greater(1, 0).types()');

        var eval_;
        eval_ = new Sao.PYSON.Encoder().encode(new Sao.PYSON.Greater(1, 0));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
                'decode(Greater(1, 0))');

        eval_ = new Sao.PYSON.Encoder().encode(new Sao.PYSON.Greater(0, 1));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
                'decode(Greater(0, 1))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Greater(1, 0, true));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
                'decode(Greater(1, 0, true))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Greater(0, 1, true));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
                'decode(Greater(0, 1, true))');

        eval_ = new Sao.PYSON.Encoder().encode(new Sao.PYSON.Greater(1, 1));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
                'decode(Greater(1, 1))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Greater(1, 1, true));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
                'decode(Greater(1, 1, true))');
    });

    QUnit.test('PYSON Less', function() {
        var value = new Sao.PYSON.Less(1, 0).pyson();
        QUnit.strictEqual(value.__class__, 'Less', 'Less(1, 0).pyson()');
        QUnit.strictEqual(value.s1, 1, 'Less(1, 0).pyson()');
        QUnit.strictEqual(value.s2, 0, 'Less(1, 0).pyson()');
        QUnit.strictEqual(value.e, false, 'Less(1, 0).pyson()');

        QUnit.throws(function() {
            new Sao.PYSON.Less('test', 0);
        }, 'statement must be an integer or a float');
        QUnit.throws(function() {
            new Sao.PYSON.Less(1, 'test');
        }, 'statement must be an integer or a float');
        QUnit.throws(function() {
            new Sao.PYSON.Less(1, 0, 'test');
        }, 'equal must be boolean');

        QUnit.ok(Sao.common.compare(new Sao.PYSON.Less(1, 0).types(),
                ['boolean']), 'Less(1, 0).types()');

        var eval_;
        eval_ = new Sao.PYSON.Encoder().encode(new Sao.PYSON.Less(1, 0));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
                'decode(Less(1, 0))');

        eval_ = new Sao.PYSON.Encoder().encode(new Sao.PYSON.Less(0, 1));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
                'decode(Less(0, 1))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Less(1, 0, true));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
                'decode(Less(1, 0, true))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Less(0, 1, true));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
                'decode(Less(0, 1, true))');

        eval_ = new Sao.PYSON.Encoder().encode(new Sao.PYSON.Less(1, 1));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
                'decode(Less(1, 1))');

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Less(1, 1, true));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
                'decode(Less(1, 1, true))');
    });

    QUnit.test('PYSON If', function() {
        var value = new Sao.PYSON.If(true, 'foo', 'bar').pyson();
        QUnit.strictEqual(value.__class__, 'If', "If(true, 'foo', 'bar')");
        QUnit.strictEqual(value.c, true, "If(true, 'foo', 'bar')");
        QUnit.strictEqual(value.t, 'foo', "If(true, 'foo', 'bar')");
        QUnit.strictEqual(value.e, 'bar', "If(true, 'foo', 'bar')");

        QUnit.throws(function() {
            new Sao.PYSON.If('test', 'foo', 'bar');
        }, 'condition must be boolean');
        QUnit.throws(function() {
            new Sao.PYSON.If(true, 'foo', false);
        }, 'then and else statements must be the same type');

        QUnit.ok(Sao.common.compare(
                new Sao.PYSON.If(true, 'foo', 'bar').types(),
                [typeof 'foo']), "If(true, 'foo', 'bar').types()");
        QUnit.ok(Sao.common.compare(
                new Sao.PYSON.If(true, false, true).types(),
                [typeof true]), 'If(true, false, true).types()');

        var eval_;
        eval_ = new Sao.PYSON.Encoder().encode(
            new Sao.PYSON.If(true, 'foo', 'bar'));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), 'foo',
                "decode(If(true, 'foo', 'bar'))");

        eval_ = new Sao.PYSON.Encoder().encode(
            new Sao.PYSON.If(false, 'foo', 'bar'));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), 'bar',
                "decode(If(false, 'foo', 'bar'))");
    });

    QUnit.test('PYSON Get', function() {
        var value = new Sao.PYSON.Get({foo: 'bar'}, 'foo', 'default').pyson();
        QUnit.strictEqual(value.__class__, 'Get',
            "Get({foo: 'bar'}, 'foo', 'default').pyson()");
        QUnit.strictEqual(value.v.foo, 'bar',
            "Get({foo: 'bar'}, 'foo', 'default').pyson()");
        QUnit.strictEqual(value.k, 'foo',
            "Get({foo: 'bar'}, 'foo', 'default').pyson()");
        QUnit.strictEqual(value.d, 'default',
            "Get({foo: 'bar'}, 'foo', 'default').pyson()");

        QUnit.throws(function() {
            new Sao.PYSON.Get('test', 'foo', 'default');
        }, 'obj must be a dict');
        QUnit.throws(function() {
            new Sao.PYSON.Get({}, 1, 'default');
        }, 'key must be a string');

        QUnit.ok(Sao.common.compare(
                new Sao.PYSON.Get({}, 'foo', 'default').types(),
                [typeof '']), "Get({}, 'foo', 'default').types()");
        QUnit.ok(Sao.common.compare(new Sao.PYSON.Get({}, 'foo', true).types(),
                [typeof true]), "Get({}, 'foo', true).types()");

        var eval_;
        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Get({foo: 'bar'}, 'foo', 'default'));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), 'bar',
                "decode(Get({foo: 'bar'}, 'foo', 'default'))");

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Get({foo: 'bar'}, 'test', 'default'));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), 'default',
                "decode(Get({foo: 'bar'}, 'test', 'default'))");

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Get({}, 'foo', 'default'));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), 'default',
                "decode(Get({}, 'foo', 'default'))");
    });

    QUnit.test('PYSON In', function() {
        var value = new Sao.PYSON.In('foo', {foo: 'bar'}).pyson();
        QUnit.strictEqual(value.__class__, 'In',
            "In('foo', {foo: 'bar'}).pyson()");
        QUnit.strictEqual(value.k, 'foo',
            "In('foo', {foo: 'bar'}).pyson()");
        QUnit.strictEqual(value.v.foo, 'bar',
            "In('foo', {foo: 'bar'}).pyson()");

        QUnit.throws(function() {
            new Sao.PYSON.In({}, {});
        }, 'key must be a string or a number');
        QUnit.throws(function() {
            new Sao.PYSON.In('test', 'foo');
        }, 'obj must be a dict or a list');

        QUnit.ok(Sao.common.compare(new Sao.PYSON.In('foo', {}).types(),
                ['boolean']), "In('foo', {}).types()");

        var eval_;
        eval_ = new Sao.PYSON.Encoder().encode(
            new Sao.PYSON.In('foo', {foo: 'bar'}));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
                "decode(In('foo', {foo: 'bar'}))");

        eval_ = new Sao.PYSON.Encoder().encode(
            new Sao.PYSON.In('1', {1: 'bar'}));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
                "decode(In('1', {1: 'bar'}))");

        eval_ = new Sao.PYSON.Encoder().encode(
            new Sao.PYSON.In('test', {foo: 'bar'}));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
                "decode(In('test', {foo: 'bar'}))");

        eval_ = new Sao.PYSON.Encoder().encode(
            new Sao.PYSON.In('foo', ['foo']));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
                "decode(In('foo', ['foo']))");

        eval_ = new Sao.PYSON.Encoder().encode(
            new Sao.PYSON.In(1, [1]));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), true,
                'decode(In(1, [1]))');

        eval_ = new Sao.PYSON.Encoder().encode(
            new Sao.PYSON.In('test', ['foo']));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
                "decode(In('test', ['foo']))");

        eval_ = new Sao.PYSON.Encoder().encode(
            new Sao.PYSON.In(1, [2]));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
                'decode(In(1, [2]))');

        eval_ = new Sao.PYSON.Encoder().encode(
            new Sao.PYSON.In('test', []));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_), false,
                "decode(In('test', []))");
    });

    QUnit.test('PYSON Date', function() {
        var value = new Sao.PYSON.Date(2010, 1, 12, -1, 12, -7).pyson();
        QUnit.strictEqual(value.__class__, 'Date',
            'Date(2010, 1, 12, -1, 12, -7).pyson()');
        QUnit.strictEqual(value.y, 2010,
            'Date(2010, 1, 12, -1, 12, -7).pyson()');
        QUnit.strictEqual(value.M, 1,
            'Date(2010, 1, 12, -1, 12, -7).pyson()');
        QUnit.strictEqual(value.d, 12,
            'Date(2010, 1, 12, -1, 12, -7).pyson()');
        QUnit.strictEqual(value.dy, -1,
            'Date(2010, 1, 12, -1, 12, -7).pyson()');
        QUnit.strictEqual(value.dM, 12,
            'Date(2010, 1, 12, -1, 12, -7).pyson()');
        QUnit.strictEqual(value.dd, -7,
            'Date(2010, 1, 12, -1, 12, -7).pyson()');

        QUnit.throws(function() {
            new Sao.PYSON.Date('test', 1, 12, -1, 12, -7);
        }, 'year must be an integer or None');
        QUnit.throws(function() {
            new Sao.PYSON.Date(2010, 'test', 12, -1, 12, -7);
        }, 'month must be an integer or None');
        QUnit.throws(function() {
            new Sao.PYSON.Date(2010, 1, 'test', -1, 12, -7);
        }, 'day must be an integer or None');
        QUnit.throws(function() {
            new Sao.PYSON.Date(2010, 1, 12, 'test', 12, -7);
        }, 'delta_years must be an integer or None');
        QUnit.throws(function() {
            new Sao.PYSON.Date(2010, 1, 12, -1, 'test', -7);
        }, 'delta_months must be an integer or None');
        QUnit.throws(function() {
            new Sao.PYSON.Date(2010, 1, 12, -1, 12, 'test');
        }, 'delta_days must be an integer or None');

        QUnit.ok(Sao.common.compare(
                    new Sao.PYSON.Date(2010, 1, 12, -1, 12, -7).types(),
                    ['object']), 'Date(2010, 1, 12, -1, 12, -7).types()');

        var eval_;
        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Date(2010, 1, 12));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_).valueOf(),
                new Date(2010, 1, 12).valueOf());

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Date(2010, 1, 12, -1));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_).valueOf(),
                new Date(2009, 1, 12).valueOf());

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Date(2010, 1, 12, 0, 12));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_).valueOf(),
                new Date(2011, 1, 12).valueOf());

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Date(2010, 1, 12, 0, 0, -7));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_).valueOf(),
                new Date(2010, 1, 5).valueOf());

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.Date(2010, 2, 22));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_).valueOf(),
                new Date(2010, 2, 22).valueOf());
    });

    QUnit.test('PYSON DateTime', function() {
        var value = new Sao.PYSON.DateTime(2010, 1, 12, 10, 30, 20, 0,
            -1, 12, -7, 2, 15, 30, 1).pyson();
        QUnit.strictEqual(value.__class__, 'DateTime',
            'Date(2010, 1, 12, 10, 30, 20, 0, -1, 12, -7, 2, 15, 30, 1)' +
            '.pyson()');
        QUnit.strictEqual(value.y, 2010,
            'Date(2010, 1, 12, 10, 30, 20, 0, -1, 12, -7, 2, 15, 30, 1)' +
            '.pyson()');
        QUnit.strictEqual(value.M, 1,
            'Date(2010, 1, 12, 10, 30, 20, 0, -1, 12, -7, 2, 15, 30, 1)' +
            '.pyson()');
        QUnit.strictEqual(value.d, 12,
            'Date(2010, 1, 12, 10, 30, 20, 0, -1, 12, -7, 2, 15, 30, 1)' +
            '.pyson()');
        QUnit.strictEqual(value.h, 10,
            'Date(2010, 1, 12, 10, 30, 20, 0, -1, 12, -7, 2, 15, 30, 1)' +
            '.pyson()');
        QUnit.strictEqual(value.m, 30,
            'Date(2010, 1, 12, 10, 30, 20, 0, -1, 12, -7, 2, 15, 30, 1)' +
            '.pyson()');
        QUnit.strictEqual(value.s, 20,
            'Date(2010, 1, 12, 10, 30, 20, 0, -1, 12, -7, 2, 15, 30, 1)' +
            '.pyson()');
        QUnit.strictEqual(value.ms, 0,
            'Date(2010, 1, 12, 10, 30, 20, 0, -1, 12, -7, 2, 15, 30, 1)' +
            '.pyson()');
        QUnit.strictEqual(value.dy, -1,
            'Date(2010, 1, 12, 10, 30, 20, 0, -1, 12, -7, 2, 15, 30, 1)' +
            '.pyson()');
        QUnit.strictEqual(value.dM, 12,
            'Date(2010, 1, 12, 10, 30, 20, 0, -1, 12, -7, 2, 15, 30, 1)' +
            '.pyson()');
        QUnit.strictEqual(value.dd, -7,
            'Date(2010, 1, 12, 10, 30, 20, 0, -1, 12, -7, 2, 15, 30, 1)' +
            '.pyson()');
        QUnit.strictEqual(value.dh, 2,
            'Date(2010, 1, 12, 10, 30, 20, 0, -1, 12, -7, 2, 15, 30, 1)' +
            '.pyson()');
        QUnit.strictEqual(value.dm, 15,
            'Date(2010, 1, 12, 10, 30, 20, 0, -1, 12, -7, 2, 15, 30, 1)' +
            '.pyson()');
        QUnit.strictEqual(value.ds, 30,
            'Date(2010, 1, 12, 10, 30, 20, 0, -1, 12, -7, 2, 15, 30, 1)' +
            '.pyson()');
        QUnit.strictEqual(value.dms, 1,
            'Date(2010, 1, 12, 10, 30, 20, 0, -1, 12, -7, 2, 15, 30, 1)' +
            '.pyson()');

        QUnit.throws(function() {
            new Sao.PYSON.DateTime('test', 1, 12, 10, 30, 20, 0,
                -1, 12, -7, 2, 15, 30, 1);
        }, 'year must be an integer or None');
        QUnit.throws(function() {
            new Sao.PYSON.DateTime(2010, 'test', 12, 10, 30, 20, 0,
                -1, 12, -7, 2, 15, 30, 1);
        }, 'month must be an integer or None');
        QUnit.throws(function() {
            new Sao.PYSON.DateTime(2010, 1, 'test', 10, 30, 20, 0,
                -1, 12, -7, 2, 15, 30, 1);
        }, 'day must be an integer or None');
        QUnit.throws(function() {
            new Sao.PYSON.DateTime(2010, 1, 12, 'test', 30, 20, 0,
                -1, 12, -7, 2, 15, 30, 1);
        }, 'hour must be an integer or None');
        QUnit.throws(function() {
            new Sao.PYSON.DateTime(2010, 1, 12, 10, 'test', 20, 0,
                -1, 12, -7, 2, 15, 30, 1);
        }, 'minute must be an integer or None');
        QUnit.throws(function() {
            new Sao.PYSON.DateTime(2010, 1, 12, 10, 30, 'test', 0,
                -1, 12, -7, 2, 15, 30, 1);
        }, 'second must be an integer or None');
        QUnit.throws(function() {
            new Sao.PYSON.DateTime(2010, 1, 12, 10, 30, 20, 'test',
                -1, 12, -7, 2, 15, 30, 1);
        }, 'microsecond must be an integer or None');
        QUnit.throws(function() {
            new Sao.PYSON.DateTime(2010, 1, 12, 10, 30, 20, 0,
                'test', 12, -7, 2, 15, 30, 1);
        }, 'delta_years must be an integer or None');
        QUnit.throws(function() {
            new Sao.PYSON.DateTime(2010, 1, 12, 10, 30, 20, 0,
                -1, 'test', -7, 2, 15, 30, 1);
        }, 'delta_months must be an integer or None');
        QUnit.throws(function() {
            new Sao.PYSON.DateTime(2010, 1, 12, 10, 30, 20, 0,
                -1, 12, 'test', 2, 15, 30, 1);
        }, 'delta_days must be an integer or None');
        QUnit.throws(function() {
            new Sao.PYSON.DateTime(2010, 1, 12, 10, 30, 20, 0,
                -1, 12, -7, 'test', 15, 30, 1);
        }, 'delta_hours must be an integer or None');
        QUnit.throws(function() {
            new Sao.PYSON.DateTime(2010, 1, 12, 10, 30, 20, 0,
                -1, 12, -7, 2, 'test', 30, 1);
        }, 'delta_minutes must be an integer or None');
        QUnit.throws(function() {
            new Sao.PYSON.DateTime(2010, 1, 12, 10, 30, 20, 0,
                -1, 12, -7, 2, 15, 'test', 1);
        }, 'delta_seconds must be an integer or None');
        QUnit.throws(function() {
            new Sao.PYSON.DateTime(2010, 1, 12, 10, 30, 20, 0,
                -1, 12, -7, 2, 15, 30, 'test');
        }, 'delta_microseconds must be an integer or None');

        QUnit.ok(Sao.common.compare(
                    new Sao.PYSON.DateTime(2010, 1, 12, 10, 30, 20, 0,
                        -1, 12, -7, 2, 15, 30, 1).types(),
                    ['object']), 'DateTime(2010, 1, 12, 10, 30, 20, 0, ' +
                        '-1, 12, -7, 2, 15, 30, 1).types()');

        var eval_;
        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.DateTime(2010, 1, 12, 10, 30, 20, 0));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_).valueOf(),
                new Date(2010, 1, 12, 10, 30, 20, 0).valueOf());

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.DateTime(2010, 1, 12, 10, 30, 20, 0, -1));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_).valueOf(),
                new Date(2009, 1, 12, 10, 30, 20, 0).valueOf());

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.DateTime(2010, 1, 12, 10, 30, 20, 0, 0, 12));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_).valueOf(),
                new Date(2011, 1, 12, 10, 30, 20, 0).valueOf());

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.DateTime(2010, 1, 12, 10, 30, 20, 0, 0, 0, -7));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_).valueOf(),
                new Date(2010, 1, 5, 10, 30, 20, 0).valueOf());

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.DateTime(2010, 1, 12, 10, 30, 20, 0,
                    0, 0, 0, 12));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_).valueOf(),
                new Date(2010, 1, 12, 22, 30, 20, 0).valueOf());

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.DateTime(2010, 1, 12, 10, 30, 20,
                    0, 0, 0, 0, 0, -30));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_).valueOf(),
                new Date(2010, 1, 12, 10, 0, 20, 0).valueOf());

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.DateTime(2010, 1, 12, 10, 30, 20,
                    0, 0, 0, 0, 0, 0, 30));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_).valueOf(),
                new Date(2010, 1, 12, 10, 30, 50, 0).valueOf());

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.DateTime(2010, 1, 12, 10, 30, 20,
                    0, 0, 0, 0, 0, 0, 0, 200));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_).valueOf(),
                new Date(2010, 1, 12, 10, 30, 20, 2).valueOf());

        eval_ = new Sao.PYSON.Encoder().encode(
                new Sao.PYSON.DateTime(2010, 2, 22, 10, 30, 20, 200));
        QUnit.strictEqual(new Sao.PYSON.Decoder().decode(eval_).valueOf(),
                new Date(2010, 2, 22, 10, 30, 20, 2).valueOf());
    });

    QUnit.test('CRUD', function() {
        var run_tests = function() {
            var User = new Sao.Model('res.user');
            prm = User.execute('fields_get', [], {}).pipe(
                function(descriptions) {
                    User.add_fields(descriptions);
                });
            var user = null;
            prm.pipe(function() {
                user = new Sao.Record(User);
                QUnit.ok(user.id < 0, 'Unsaved');
                user.model.fields.name.set_client(user, 'Test');
                user.model.fields.login.set_client(user, 'test');
            });
            prm = prm.pipe(function() {
                return user.default_get();
            });
            prm = prm.pipe(function() {
                return user.save();
            });
            prm = prm.pipe(function() {
                QUnit.ok(user.id >= 0, 'Saved');
                QUnit.ok(jQuery.isEmptyObject(user._values), 'No values');
                QUnit.ok(jQuery.isEmptyObject(user._loaded), 'No field loaded');
                return user.load('name');
            });
            prm = prm.pipe(function() {
                QUnit.ok(user.field_get_client('name') == 'Test',
                    'Check field_get_client');
            });
            prm = prm.pipe(function() {
                return User.find([['id', '=', user.id]], 0, null, null, {});
            });
            prm = prm.pipe(function(users) {
                QUnit.ok(users.length == 1, 'Found 1');
                QUnit.ok(users[0].id == user.id, 'Found right one');
                return users;
            });
            prm = prm.pipe(function(users) {
                User.delete_(users, {});
                prm = User.find([['login', '=', 'test']], 0, null, null, {});
                prm.done(function(users) {
                    QUnit.ok(users.length == 1, 'Deleted record not found');
                });
                return prm;
            });
            prm = prm.pipe(function() {
                return User.find([], 0, null, null, {});
            });
            prm = prm.pipe(function(users) {
                QUnit.ok(users.length >= 1, 'Found more then 1');
                return users[0].load('login').pipe(function() {
                    return users;
                });
            });
            prm = prm.pipe(function(users) {
                QUnit.ok(users[0].field_get_client('login'),
                    'Check first field_get_client');
                QUnit.ok(users[1].field_get_client('login'),
                    'Check second field_get_client');
            });
            prm.always(QUnit.start);
        };

        QUnit.stop();
        QUnit.expect(11);
        var prm = Sao.rpc({
            'method': 'common.db.create',
            'params': [SaoTest.dbname, SaoTest.password,
            SaoTest.language, SaoTest.admin_password]
        });
        prm.done(function() {
            var session = new Sao.Session(SaoTest.dbname, SaoTest.login);
            Sao.Session.current_session = session;
            var login_prm = session.do_login(SaoTest.login,
                SaoTest.password);
            login_prm.done(run_tests);
        });
    });

    Sao.Session.renew_credentials = function(session, parent_dfd) {
        session.do_login(SaoTest.login, SaoTest.password, parent_dfd);
    };
}());
