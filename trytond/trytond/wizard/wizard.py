#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import copy
from threading import Lock
from random import randint
from xmlrpclib import MAXINT
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.error import WarningErrorMixin
from trytond.url import URLMixin


class Wizard(WarningErrorMixin, URLMixin):
    _name = ""
    states = {}

    def __new__(cls):
        Pool.register(cls, type='wizard')

    def __init__(self):
        super(Wizard, self).__init__()
        self._rpc = {
            'create': True,
            'delete': True,
            'execute': True,
        }
        self._error_messages = {}
        self._lock = Lock()
        self._datas = {}

    def init(self, module_name):
        pool = Pool()
        translation_obj = pool.get('ir.translation')
        cursor = Transaction().cursor
        for state in self.states.keys():
            if self.states[state]['result']['type'] == 'form':
                for button in \
                        self.states[state]['result']['state']:
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
                    value_md5 = translation_obj.get_src_md5(button_value)
                    if not res:
                        cursor.execute('INSERT INTO ir_translation '
                            '(name, lang, type, src, src_md5, value, module, '
                                'fuzzy) '
                            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                            (self._name + ',' + state + ',' + button_name,
                                'en_US', 'wizard_button', button_value,
                                value_md5, '', module_name, False))
                    elif res[0]['src'] != button_value:
                        cursor.execute('UPDATE ir_translation '
                            'SET src = %s, src_md5 = %s '
                            'WHERE id = %s',
                            (button_value, value_md5, res[0]['id']))

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
                error_md5 = translation_obj.get_src_md5(error)
                cursor.execute('INSERT INTO ir_translation '
                    '(name, lang, type, src, src_md5,  value, module, fuzzy) '
                    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                    (self._name, 'en_US', 'error', error, error_md5, '',
                        module_name, False))

    def create(self):
        self._lock.acquire()
        wiz_id = 0
        while True:
            wiz_id = randint(0, MAXINT)
            if wiz_id not in self._datas:
                break
        self._datas[wiz_id] = {'user': Transaction().user, '_wiz_id': wiz_id}
        self._lock.release()
        return wiz_id

    def delete(self, wiz_id):
        if wiz_id not in self._datas:
            return
        if self._datas[wiz_id]['user'] != Transaction().user:
            raise Exception('AccessDenied')
        self._lock.acquire()
        del self._datas[wiz_id]
        self._lock.release()

    def execute(self, wiz_id, data, state='init'):
        pool = Pool()
        translation_obj = pool.get('ir.translation')
        res = {}

        if self._datas.get(wiz_id, {}).get('user') != Transaction().user:
            raise Exception('AccessDenied')
        self._datas[wiz_id].update(data)
        data = self._datas[wiz_id]

        state_def = self.states[state]
        result_def = state_def.get('result', {})

        actions_res = {}
        # iterate through the list of actions defined for this state
        for action in state_def.get('actions', []):
            # execute them
            action_res = getattr(self, action)(data)
            assert isinstance(action_res, dict), \
                    'The return value of wizard actions ' \
                    'should be a dictionary'
            actions_res.update(action_res)

        res = copy.copy(result_def)
        if state_def.get('actions'):
            res['datas'] = actions_res

        if result_def['type'] == 'action':
            res['action'] = getattr(self, result_def['action'])(data)
        elif result_def['type'] == 'form':
            obj = pool.get(result_def['object'])

            view = obj.fields_view_get(view_type='form')
            fields = view['fields']
            arch = view['arch']

            button_list = copy.copy(result_def['state'])

            default_values = obj.default_get(fields.keys())
            for field in default_values.keys():
                if '.' in field:
                    continue
                fields[field]['value'] = default_values[field]

            # translate buttons
            for i, button  in enumerate(button_list):
                button_name = button[0]
                res_trans = translation_obj._get_source(
                        self._name + ',' + state + ',' + button_name,
                        'wizard_button', Transaction().language)
                if res_trans:
                    button = list(button)
                    button[1] = res_trans
                    button_list[i] = tuple(button)

            res['fields'] = fields
            res['arch'] = arch
            res['state'] = button_list
        elif result_def['type'] == 'choice':
            next_state = getattr(self, result_def['next_state'])(data)
            if next_state == 'end':
                return {'type': 'state', 'state': 'end'}
            return self.execute(wiz_id, data, next_state)
        return res
