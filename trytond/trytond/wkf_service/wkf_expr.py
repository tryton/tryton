#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
from trytond import pooler


class EnvCall(object):

    def __init__(self, obj, cursor, user, method, obj_id, context=None):
        self.obj = obj
        self.cursor = cursor
        self.user = user
        self.method = method
        self.obj_id = obj_id
        self.context = context

    def __call__(self, *args, **kargs):
        kargs = kargs.copy()
        kargs['context'] = self.context
        return getattr(self.obj, self.method)(self.cursor, self.user,
                self.obj_id, *args, **kargs)


class Env(dict):

    def __init__(self, cursor, user, model, obj_id, context=None):
        super(Env, self).__init__()
        self.cursor = cursor
        self.user = user
        self.model = model
        self.obj_id = obj_id
        self.context = context
        self.obj = pooler.get_pool(cursor.dbname).get(model)
        self.browse = self.obj.browse(cursor, user, obj_id)
        self.columns = self.obj._columns.keys() + \
                self.obj._inherit_fields.keys()

    def __getitem__(self, key):
        if key == 'context':
            return self.context
        elif key in self.columns:
            res = self.browse[key]
            return res
        elif key in dir(self.obj):
            return EnvCall(self.obj, self.cursor, self.user, key, self.obj_id,
                    context=self.context)
        else:
            return super(Env, self).__getitem__(key)

def eval_expr(cursor, ident, action, context=None):
    res = False
    user = ident[0]
    model = ident[1]
    obj_id = ident[2]
    env = Env(cursor, user, model, obj_id, context=context)
    for line in action.split('\n'):
        if line == 'True':
            res = True
        elif line =='False':
            res = False
        else:
            res = eval(line, env)
    return res

def execute(cursor, ident, activity, context=None):
    return eval_expr(cursor, ident, activity['action'], context=context)

def check(cursor, ident, transition, signal, context=None):
    res = True
    if transition['signal']:
        res = (signal == transition['signal'])

    user = ident[0]
    if transition['group'] and user != 0:
        user_obj = pooler.get_pool(cursor.dbname).get('res.user')
        user_groups = user_obj.read(cursor, user, user, ['groups'],
                context=context)['groups']
        res = res and transition['group'] in user_groups
    res = res and eval_expr(cursor, ident, transition['condition'],
            context=context)
    return res
