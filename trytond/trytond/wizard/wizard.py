#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

__all__ = ['Wizard', 'StateView', 'StateTransition', 'StateAction', 'Button',
    'Session']

try:
    import simplejson as json
except ImportError:
    import json

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.error import WarningErrorMixin
from trytond.url import URLMixin
from trytond.protocols.jsonrpc import object_hook, JSONEncoder
from trytond.model.fields import states_validate
from trytond.pyson import PYSONEncoder
from trytond.model.browse import BrowseRecordNull


class Button(object):
    '''
    Define a button on wizard.
    '''

    def __init__(self, string, state, icon='', default=False, states=None):
        self.string = string
        self.state = state
        self.icon = icon
        self.default = bool(default)
        self.__states = None
        self.states = states or {}

    @property
    def states(self):
        return self.__states

    @states.setter
    def states(self, value):
        states_validate(value)
        self.__states = value


class State(object):
    '''
    A State of a wizard.
    '''


class StateView(State):
    '''
    A view state of a wizard.
    '''

    def __init__(self, model_name, view, buttons):
        '''
        model_name is the name of the model
        view is the xml id of the view
        buttons is a list of Button
        '''
        self.model_name = model_name
        self.view = view
        self.buttons = buttons
        assert len(self.buttons) == len(set(b.state for b in self.buttons))
        assert len([b for b in self.buttons if b.default]) <= 1

    def get_view(self):
        '''
        Returns the view definition
        '''
        model_obj = Pool().get(self.model_name)
        model_data_obj = Pool().get('ir.model.data')
        module, fs_id = self.view.split('.')
        view_id = model_data_obj.get_id(module, fs_id)
        return model_obj.fields_view_get(view_id=view_id, view_type='form')

    def get_defaults(self, wizard, session, state_name, fields):
        '''
        Returns defaults values for the fields
        '''
        model_obj = Pool().get(self.model_name)
        defaults = model_obj.default_get(fields)
        default = getattr(wizard, 'default_%s' % state_name, None)
        if default:
            defaults.update(default(session, fields))
        return defaults

    def get_buttons(self, wizard, state_name):
        '''
        Returns button definitions translated
        '''
        translation_obj = Pool().get('ir.translation')

        def translation_key(button):
            return (','.join((wizard._name, state_name, button.state)),
                'wizard_button', Transaction().language, button.string)
        translation_keys = [translation_key(button) for button in self.buttons]
        translations = translation_obj.get_sources(translation_keys)
        encoder = PYSONEncoder()
        result = []
        for button in self.buttons:
            result.append({
                    'state': button.state,
                    'icon': button.icon,
                    'default': button.default,
                    'string': (translations.get(translation_key(button))
                        or button.string),
                    'states': encoder.encode(button.states),
                    })
        return result


class StateTransition(State):
    '''
    A transition state of a wizard.
    '''


class StateAction(StateTransition):
    '''
    An action state of a wizard.
    '''

    def __init__(self, action_id):
        '''
        action_id is a string containing ``module.xml_id``
        '''
        super(StateAction, self).__init__()
        self.action_id = action_id

    def get_action(self):
        "Returns action definition"
        pool = Pool()
        model_data_obj = pool.get('ir.model.data')
        action_obj = pool.get('ir.action')
        module, fs_id = self.action_id.split('.')
        action_id = action_obj.get_action_id(
            model_data_obj.get_id(module, fs_id))
        action = action_obj.browse(action_id)
        return action_obj.get_action_values(action.type, action.id)


class _SessionRecord(object):
    '''
    A record of a wizard form.
    '''
    # Declared in class to prevent:
    # 'maximum recursion depth exceeded in __subclasscheck__'
    _model = None
    _data = None
    __cache = None

    def __init__(self, model, data):
        self._model = model
        self._data = data
        self.__cache = {}
        self.dirty = False

    def __getattr__(self, name):
        if name in self.__cache:
            return self.__cache[name]
        field = self._model._columns[name]
        data = self._data.get(name, None)
        target_obj = None
        if hasattr(field, 'model_name'):
            target_obj = Pool().get(field.model_name)
        elif hasattr(field, 'get_target'):
            target_obj = field.get_target()
        if data:
            if target_obj:
                def instance(data):
                    if isinstance(data, dict):
                        return _SessionRecord(target_obj, data)
                    return target_obj.browse(data)
                if isinstance(data, list):
                    data = [instance(x) for x in data]
                else:
                    data = instance(data)
        elif target_obj and not isinstance(data, list):
            return BrowseRecordNull()
        self.__cache[name] = data
        return data

    def __setattr__(self, name, value):
        if (self._model is not None
                and (name in self._model._columns
                    or name in self._model._inherit_fields)):
            self.__cache.pop(name, None)
            self._data[name] = value
            self.dirty = True
        else:
            super(_SessionRecord, self).__setattr__(name, value)


class Session(object):
    '''
    A wizard session.
    '''

    def __init__(self, wizard, session_id):
        pool = Pool()
        session_obj = pool.get('ir.session.wizard')
        self._session = session_obj.browse(session_id)
        self.data = json.loads(self._session.data.encode('utf-8'),
            object_hook=object_hook)
        for state_name, state in wizard.states.iteritems():
            if isinstance(state, StateView):
                model = pool.get(state.model_name)
                self.data.setdefault(state_name, {})
                setattr(self, state_name,
                    _SessionRecord(model, self.data[state_name]))

    @property
    def dirty(self):
        return any(getattr(self, state_name).dirty
            for state_name in self.data)

    def save(self):
        "Save the session in database"
        session_obj = Pool().get('ir.session.wizard')
        if self.dirty:
            session_obj.write(self._session.id, {
                    'data': json.dumps(self.data, cls=JSONEncoder),
                    })


class Wizard(WarningErrorMixin, URLMixin):
    _name = ""
    start_state = 'start'
    end_state = 'end'

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

    @property
    def states(self):
        result = {}
        for attr in dir(self):
            if attr == 'states':
                continue
            if isinstance(getattr(self, attr), State):
                result[attr] = getattr(self, attr)
        return result

    def init(self, module_name):
        pool = Pool()
        translation_obj = pool.get('ir.translation')
        cursor = Transaction().cursor
        for state_name, state in self.states.iteritems():
            if isinstance(state, StateView):
                for button in state.buttons:
                    cursor.execute('SELECT id, name, src '
                        'FROM ir_translation '
                        'WHERE module = %s '
                            'AND lang = %s '
                            'AND type = %s '
                            'AND name = %s',
                        (module_name, 'en_US', 'wizard_button',
                            self._name + ',' + state_name + ',' +
                            button.state))
                    res = cursor.dictfetchall()
                    src_md5 = translation_obj.get_src_md5(button.string)
                    if not res:
                        cursor.execute('INSERT INTO ir_translation '
                            '(name, lang, type, src, src_md5, value, module, '
                                'fuzzy) '
                            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                            (self._name + ',' + state_name + ',' +
                                button.state,
                                'en_US', 'wizard_button', button.string,
                                src_md5, '', module_name, False))
                    elif res[0]['src'] != button.string:
                        cursor.execute('UPDATE ir_translation '
                            'SET src = %s, src_md5 = %s '
                            'WHERE id = %s',
                            (button.string, src_md5, res[0]['id']))

        cursor.execute('SELECT id, src FROM ir_translation '
            'WHERE lang = %s '
                'AND type = %s '
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
        "Create a session"
        session_obj = Pool().get('ir.session.wizard')
        return (session_obj.create({}), self.start_state, self.end_state)

    def delete(self, session_id):
        "Delete the session"
        session_obj = Pool().get('ir.session.wizard')
        session_obj.delete(session_id)

    def execute(self, session, data, state_name):
        '''
        Execute the wizard state.

        session is a Session or a Session id
        data is a dictionary with the session data to update
        state_name is the name of state to execute

        Returns a dictionary with:
            - ``actions``: a list of Action to execute
            - ``view``: a dictionary with:
                - ``fields_view``: a fields/view definition
                - ``defaults``: a dictionary with default values
                - ``buttons``: a list of buttons
        '''
        if state_name == self.end_state:
            return {}
        if isinstance(session, (int, long)):
            session = Session(self, session)
        for key, value in data.iteritems():
            prev_data = session.data[key].copy()
            session.data[key].update(value)
            if prev_data != session.data[key]:
                getattr(session, key).dirty = True

        state = self.states[state_name]
        result = {}

        if isinstance(state, StateView):
            view = state.get_view()
            defaults = state.get_defaults(self, session, state_name,
                view['fields'].keys())
            buttons = state.get_buttons(self, state_name)
            result['view'] = {
                'fields_view': view,
                'defaults': defaults,
                'buttons': buttons,
                'state': state_name,
                }
        elif isinstance(state, StateTransition):
            do_result = None
            if isinstance(state, StateAction):
                action = state.get_action()
                do = getattr(self, 'do_%s' % state_name, None)
                if do:
                    do_result = do(session, action)
                else:
                    do_result = action, {}
            transition = getattr(self, 'transition_%s' % state_name, None)
            if transition:
                result = self.execute(session, {}, transition(session))
            if do_result:
                result.setdefault('actions', []).append(do_result)
        session.save()
        return result
