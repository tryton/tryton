#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.tools import safe_eval
from trytond.transaction import Transaction


class EnvCall(object):

    def __init__(self, obj, method, obj_id):
        self.obj = obj
        self.method = method
        self.obj_id = obj_id

    def __call__(self, *args, **kargs):
        return getattr(self.obj, self.method)(self.obj_id, *args, **kargs)


class Env(dict):

    def __init__(self, model, obj_id):
        super(Env, self).__init__()
        self.model = model
        self.obj_id = obj_id
        self.obj = Pool(Transaction().cursor.dbname).get(model)
        self.browse = self.obj.browse(obj_id)
        self.columns = self.obj._columns.keys() + \
                self.obj._inherit_fields.keys()

    def __getitem__(self, key):
        if key == 'context':
            return Transaction().context
        elif key in self.columns:
            res = self.browse[key]
            return res
        elif key in dir(self.obj):
            return EnvCall(self.obj, key, self.obj_id)
        else:
            return super(Env, self).__getitem__(key)

def eval_expr(model, obj_id, action):
    res = False
    env = Env(model, obj_id)
    for line in action.split('\n'):
        if line == 'True':
            res = True
        elif line =='False':
            res = False
        else:
            res = safe_eval(line, env)
    return res

def execute(model, obj_id, activity):
    '''
    Execute

    :param model: the model name
    :param obj_id: the record id
    :param activity: a BrowseRecord of workflow.activity
    '''
    return eval_expr(model, obj_id, activity.action)

def check(model, obj_id, transition, signal):
    '''
    Check

    :param model: the model name
    :param obj_id: the record id
    :param transition: a BrowseRecord of workflow.transition
    '''
    if transition.signal:
        if signal != transition.signal:
            return False

    if transition.group and Transaction().user != 0:
        user_obj = Pool(Transaction().cursor.dbname).get('res.user')
        user_groups = user_obj.get_groups()
        if transition.group.id not in user_groups:
            return False
    return eval_expr(model, obj_id, transition.condition)
