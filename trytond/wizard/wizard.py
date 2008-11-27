#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Wizard"
from trytond.netsvc import Service
from trytond import pooler
import copy
from xml import dom
from trytond.osv import OSV
from trytond.config import CONFIG
import sys
from trytond.sql_db import IntegrityError
import traceback
import logging

MODULE_LIST = []
MODULE_CLASS_LIST = {}


class WizardService(Service):

    def __init__(self):
        self.object_name_pool = {}
        self.module_obj_list = {}
        Service.__init__(self, 'wizard_proxy')
        Service.join_group(self, 'web-service')
        Service.export_method(self, self.execute)

    def execute_cr(self, cursor, user, wizard_name, data, state='init',
            context=None):
        try:
            wizard = pooler.get_pool_wizard(cursor.dbname).get(wizard_name)
            if not wizard:
                raise Exception('Error',
                        'Wizard %s doesn\'t exist' % str(wizard_name))
            res = wizard.execute(cursor, user, data, state, context)
            return res
        except Exception, exception:
            if CONFIG['verbose'] or str(exception.args[0]) not in \
                    ('NotLogged', 'ConcurrencyException', 'UserError'):
                tb_s = reduce(lambda x, y: x+y,
                        traceback.format_exception(*sys.exc_info()))
                logging.getLogger("web-service").error(
                    'Exception in call: ' + tb_s)
            if isinstance(exception, IntegrityError):
                pool = pooler.get_pool(cursor.dbname)
                for key in pool._sql_errors.keys():
                    if key in exception[0]:
                        msg = pool._sql_errors[key]
                        cursor2 = pooler.get_db(cursor.dbname).cursor()
                        if context is None:
                            context = {}
                        try:
                            cursor2.execute('SELECT value ' \
                                    'FROM ir_translation ' \
                                    'WHERE lang=%s ' \
                                        'AND type=%s ' \
                                        'AND src=%s',
                                    (context.get('language', 'en_US'), 'error',
                                        msg))
                            if cursor2.rowcount:
                                res = cursor2.fetchone()[0]
                                if res:
                                    msg = res
                        finally:
                            cursor2.close()
                        raise Exception('UserError', 'Constraint Error',
                                msg)
            raise

    def execute(self, dbname, user, wizard_name, data, state='init',
            context=None):
        cursor = pooler.get_db(dbname).cursor()
        pool = pooler.get_pool_wizard(dbname)
        try:
            try:
                res = pool.execute_cr(cursor, user, wizard_name, data, state,
                        context)
                cursor.commit()
            except Exception:
                cursor.rollback()
                raise
        finally:
            cursor.close()
        return res

    def object_name_list(self):
        return self.object_name_pool.keys()

    def add(self, name, object_name_inst):
        """
        adds a new obj instance to the obj pool.
        if it already existed, the instance is replaced
        """
        if self.object_name_pool.has_key(name):
            del self.object_name_pool[name]
        self.object_name_pool[name] = object_name_inst

        module = str(object_name_inst.__class__)[6:]
        module = module[:len(module)-1]
        module = module.split('.')[0][2:]
        self.module_obj_list.setdefault(module, []).append(object_name_inst)

    def get(self, name):
        return self.object_name_pool.get(name, None)

    def instanciate(self, module, pool_obj):
        res = []
        class_list = MODULE_CLASS_LIST.get(module, [])
        for klass in class_list:
            res.append(klass.create_instance(self, module, pool_obj))
        return res


class Wizard(object):
    _name = ""
    states = {}

    def __new__(cls):
        for module in cls.__module__.split('.'):
            if module != 'trytond' and module != 'modules':
                break
        if not hasattr(cls, '_module'):
            cls._module = module
        MODULE_CLASS_LIST.setdefault(cls._module, []).append(cls)
        if module not in MODULE_LIST:
            MODULE_LIST.append(cls._module)
        return None

    def create_instance(cls, pool, module, pool_obj):
        """
        try to apply inheritancy at the instanciation level and
        put objs in the pool var
        """
        if pool.get(cls._name):
            parent_class = pool.get(cls._name).__class__
            cls = type(cls._name, (cls, parent_class), {})

        obj = object.__new__(cls)
        pool.add(obj._name, obj)
        obj.pool = pool_obj
        obj.__init__()
        return obj

    create_instance = classmethod(create_instance)

    def __init__(self):
        super(Wizard, self).__init__()
        self._error_messages = {}

    def auto_init(self, cursor, module_name):
        for state in self.states.keys():
            if self.states[state]['result']['type'] == 'form':
                for i, button in enumerate(
                        self.states[state]['result']['state']):
                    button_name = button[0]
                    button_value = button[1]
                    cursor.execute('SELECT id, name, src ' \
                            'FROM ir_translation ' \
                            'WHERE module = %s ' \
                                'AND lang = %s ' \
                                'AND type = %s ' \
                                'AND name = %s',
                            (module_name, 'en_US', 'wizard_button',
                                self._name + ',' + state + ',' + button_name))
                    res = cursor.dictfetchall()
                    if not res:
                        cursor.execute('INSERT INTO ir_translation ' \
                                '(name, lang, type, src, value, module, fuzzy) ' \
                                'VALUES (%s, %s, %s, %s, %s, %s, false)',
                                (self._name + ',' + state + ',' + button_name,
                                    'en_US', 'wizard_button', button_value,
                                    '', module_name))
                    elif res[0]['src'] != button_value:
                        cursor.execute('UPDATE ir_translation ' \
                                'SET src = %s, ' \
                                    'fuzzy = True '
                                'WHERE id = %s', (button_value, res[0]['id']))

        cursor.execute('SELECT id, src FROM ir_translation ' \
                'WHERE lang = %s ' \
                    'AND type = %s ' \
                    'AND name = %s',
                ('en_US', 'error', self._name))
        trans_error = {}
        for trans in cursor.dictfetchall():
            trans_error[trans['src']] = trans

        for error in self._error_messages.values():
            if error not in trans_error:
                cursor.execute('INSERT INTO ir_translation ' \
                        '(name, lang, type, src, value, module, fuzzy) ' \
                        'VALUES (%s, %s, %s, %s, %s, %s, false)',
                        (self._name, 'en_US', 'error', error, '', module_name))

    def raise_user_error(self, cursor, error, error_args=None,
            error_description='', error_description_args=None, context=None):
        translation_obj = self.pool.get('ir.translation')

        if context is None:
            context = {}

        error = self._error_messages.get(error, error)

        res = translation_obj._get_source(cursor, self._name, 'error',
                context.get('language', 'en_US'), error)
        if res:
            error = res

        if error_args:
            error = error % error_args

        if error_description:
            error_description = self._error_messages.get(error_description,
                    error_description)

            res = translation_obj._get_source(cursor, self._name, 'error',
                    context.get('language', 'en_US'), error_description)
            if res:
                error_description = res

            if error_description_args:
                error_description = error_description % error_description_args

            raise Exception('UserError', error, error_description)
        raise Exception('UserError', error)

    def execute(self, cursor, user, data, state='init', context=None):
        if context is None:
            context = {}
        res = {}
        translation_obj = self.pool.get('ir.translation')

        state_def = self.states[state]
        result_def = state_def.get('result', {})

        actions_res = {}
        # iterate through the list of actions defined for this state
        for action in state_def.get('actions', []):
            # execute them
            action_res = getattr(self, action)(cursor, user, data, context)
            assert isinstance(action_res, dict), \
                    'The return value of wizard actions ' \
                    'should be a dictionary'
            actions_res.update(action_res)

        res = copy.copy(result_def)
        if state_def.get('actions'):
            res['datas'] = actions_res

        lang = context.get('language', 'en_US')
        if result_def['type'] == 'action':
            res['action'] = getattr(self, result_def['action'])(cursor, user,
                    data, context)
        elif result_def['type'] == 'form':
            obj = self.pool.get(result_def['object'])

            view = obj.fields_view_get(cursor, user, view_type='form',
                    context=context, toolbar=False)
            fields = view['fields']
            arch = view['arch']

            button_list = copy.copy(result_def['state'])

            default_values = obj.default_get(cursor, user, fields.keys(),
                    context=context)
            for field in default_values.keys():
                fields[field]['value'] = default_values[field]

            # translate buttons
            for i, button  in enumerate(button_list):
                button_name = button[0]
                res_trans = translation_obj._get_source(cursor,
                        self._name + ',' + state + ',' + button_name,
                        'wizard_button', lang)
                if res_trans:
                    button = list(button)
                    button[1] = res_trans
                    button_list[i] = tuple(button)

            res['fields'] = fields
            res['arch'] = arch
            res['state'] = button_list
        elif result_def['type'] == 'choice':
            next_state = getattr(self, result_def['next_state'])(cursor, user,
                    data, context)
            if next_state == 'end':
                return {'type': 'state', 'state': 'end'}
            return self.execute(cursor, user, data, next_state, context)
        return res

class WizardOSV(OSV):
    """
    Object to use for wizard state
    """
    _protected = [
            'default_get',
            'fields_get',
            'fields_view_get',
            ]
    _auto = False

    def auto_init(self, cursor, module_name):
        self._field_create(cursor, module_name)

    def init(self, cursor):
        pass

    def browse(self, cursor, user, select, context=None):
        pass

    def export_data(self, cursor, user, ids, fields_name, context=None):
        pass

    def import_data(self, cursor, fields_names, datas, mode='init',
            current_module=None, noupdate=False, context=None):
        pass

    def read(self, cursor, ids, fields_names=None, context=None,
            load='_classic_read'):
        pass

    def delete(self, cursor, user, ids, context=None):
        pass

    def write(self, cursor, user, ids, vals, context=None):
        pass

    def create(self, cursor, user, vals, context=None):
        pass

    def search_count(self, cursor, user, args, context=None):
        pass

    def search(self, cursor, user, args, offset=0, limit=None, order=None,
            context=None, count=False, query_string=False):
        pass

    def name_get(self, cursor, user, ids, context=None):
        pass

    def name_search(self, cursor, user, name='', args=None, operator='ilike',
            context=None, limit=80):
        pass

    def copy(self, cursor, user, object_id, default=None, context=None):
        pass
