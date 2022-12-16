#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

__all__ = ['Wizard', 'StateView', 'StateTransition', 'StateAction', 'Button']

try:
    import simplejson as json
except ImportError:
    import json
import copy

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.error import WarningErrorMixin
from trytond.url import URLMixin
from trytond.protocols.jsonrpc import object_hook, JSONEncoder
from trytond.model.fields import states_validate
from trytond.pyson import PYSONEncoder
from trytond.rpc import RPC


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
    name = None


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
        Model_ = Pool().get(self.model_name)
        ModelData = Pool().get('ir.model.data')
        module, fs_id = self.view.split('.')
        view_id = ModelData.get_id(module, fs_id)
        return Model_.fields_view_get(view_id=view_id, view_type='form')

    def get_defaults(self, wizard, state_name, fields):
        '''
        Returns defaults values for the fields
        '''
        Model_ = Pool().get(self.model_name)
        defaults = Model_.default_get(fields)
        default = getattr(wizard, 'default_%s' % state_name, None)
        if default:
            defaults.update(default(fields))
        return defaults

    def get_buttons(self, wizard, state_name):
        '''
        Returns button definitions translated
        '''
        Translation = Pool().get('ir.translation')

        def translation_key(button):
            return (','.join((wizard.__name__, state_name, button.state)),
                'wizard_button', Transaction().language, button.string)
        translation_keys = [translation_key(button) for button in self.buttons]
        translations = Translation.get_sources(translation_keys)
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
        ModelData = pool.get('ir.model.data')
        Action = pool.get('ir.action')
        module, fs_id = self.action_id.split('.')
        action_id = Action.get_action_id(
            ModelData.get_id(module, fs_id))
        action = Action(action_id)
        return Action.get_action_values(action.type, [action.id])[0]


class Wizard(WarningErrorMixin, URLMixin):
    __metaclass__ = PoolMeta
    start_state = 'start'
    end_state = 'end'

    @classmethod
    def __setup__(cls):
        cls.__rpc__ = {
            'create': RPC(readonly=False),
            'delete': RPC(readonly=False),
            'execute': RPC(readonly=False),
            }
        cls._error_messages = {}

        # Copy states
        for attr in dir(cls):
            if isinstance(getattr(cls, attr), State):
                setattr(cls, attr, copy.deepcopy(getattr(cls, attr)))

    @classmethod
    def __post_setup__(cls):
        # Set states
        cls.states = {}
        for attr in dir(cls):
            if attr.startswith('_'):
                continue
            if isinstance(getattr(cls, attr), State):
                cls.states[attr] = getattr(cls, attr)

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Translation = pool.get('ir.translation')
        cursor = Transaction().cursor
        for state_name, state in cls.states.iteritems():
            if isinstance(state, StateView):
                for button in state.buttons:
                    cursor.execute('SELECT id, name, src '
                        'FROM ir_translation '
                        'WHERE module = %s '
                            'AND lang = %s '
                            'AND type = %s '
                            'AND name = %s',
                        (module_name, 'en_US', 'wizard_button',
                            cls.__name__ + ',' + state_name + ',' +
                            button.state))
                    res = cursor.dictfetchall()
                    src_md5 = Translation.get_src_md5(button.string)
                    if not res:
                        cursor.execute('INSERT INTO ir_translation '
                            '(name, lang, type, src, src_md5, value, module, '
                                'fuzzy) '
                            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                            (cls.__name__ + ',' + state_name + ',' +
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
            ('en_US', 'error', cls.__name__))
        trans_error = {}
        for trans in cursor.dictfetchall():
            trans_error[trans['src']] = trans

        for error in cls._error_messages.values():
            if error not in trans_error:
                error_md5 = Translation.get_src_md5(error)
                cursor.execute('INSERT INTO ir_translation '
                    '(name, lang, type, src, src_md5,  value, module, fuzzy) '
                    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                    (cls.__name__, 'en_US', 'error', error, error_md5, '',
                        module_name, False))

    @classmethod
    def create(cls):
        "Create a session"
        Session = Pool().get('ir.session.wizard')
        return (Session.create([{}])[0].id, cls.start_state, cls.end_state)

    @classmethod
    def delete(cls, session_id):
        "Delete the session"
        Session = Pool().get('ir.session.wizard')
        Session.delete([Session(session_id)])

    @classmethod
    def execute(cls, session, data, state_name):
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
        wizard = cls(session)
        for key, values in data.iteritems():
            record = getattr(wizard, key)
            for field, value in values.iteritems():
                if field == 'id':
                    continue
                setattr(record, field, value)
        return wizard._execute(state_name)

    def _execute(self, state_name):
        if state_name == self.end_state:
            return {}

        state = self.states[state_name]
        result = {}

        if isinstance(state, StateView):
            view = state.get_view()
            defaults = state.get_defaults(self, state_name,
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
                    do_result = do(action)
                else:
                    do_result = action, {}
            transition = getattr(self, 'transition_%s' % state_name, None)
            if transition:
                result = self._execute(transition())
            if do_result:
                result.setdefault('actions', []).append(do_result)
        self._save()
        return result

    def __init__(self, session_id):
        pool = Pool()
        Session = pool.get('ir.session.wizard')
        self._session_id = session_id
        session = Session(session_id)
        data = json.loads(session.data.encode('utf-8'),
            object_hook=object_hook)
        for state_name, state in self.states.iteritems():
            if isinstance(state, StateView):
                Target = pool.get(state.model_name)
                data.setdefault(state_name, {})
                setattr(self, state_name, Target(**data[state_name]))

    def _save(self):
        "Save the session in database"
        Session = Pool().get('ir.session.wizard')
        data = {}
        for state_name, state in self.states.iteritems():
            if isinstance(state, StateView):
                data[state_name] = getattr(self, state_name)._default_values
        session = Session(self._session_id)
        data = json.dumps(data, cls=JSONEncoder)
        if data != session.data.encode('utf-8'):
            Session.write([session], {
                    'data': data,
                    })
