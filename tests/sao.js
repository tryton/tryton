/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
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
        'decimal': new Number(1.1)
    };
    for (var name in tests) {
        var test = tests[name];
        var result = Sao.rpc.convertJSONObject(jQuery.parseJSON(
                JSON.stringify(Sao.rpc.prepareObject(test))));
        QUnit.ok(test.toString() == result.toString(), 'JSON ' + name);
    }
});

QUnit.test('CRUD', function() {
    var run_tests = function() {
        var User = new Sao.Model('res.user');
        prm = User.execute('fields_get', [], {}).pipe(function(descriptions) {
            User.add_fields(descriptions);
        });
        var user = null;
        prm.pipe(function() {
            user = new Sao.Record(User);
            QUnit.ok(user.id < 0, 'Unsaved');
            user.model.fields['name'].set_client(user, 'Test');
            user.model.fields['login'].set_client(user, 'test');
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
            User.delete(users, {});
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
