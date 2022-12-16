# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

__all__ = ['Wizard',
    'StateView', 'StateTransition', 'StateAction', 'StateReport',
    'Button']

import json
import copy

from trytond.i18n import gettext
from trytond.pool import Pool, PoolBase
from trytond.transaction import Transaction
from trytond.url import URLMixin
from trytond.protocols.jsonrpc import JSONDecoder, JSONEncoder
from trytond.model import ModelSQL
from trytond.model.exceptions import AccessError
from trytond.model.fields import states_validate
from trytond.pyson import PYSONEncoder
from trytond.rpc import RPC
from trytond.tools import cached_property


class Button(object):
    '''
    Define a button on wizard.
    '''

    def __init__(self, string, state,
            icon='', default=False, states=None, validate=None):
        self.string = string
        self.state = state
        self.icon = icon
        self.default = bool(default)
        self.__states = None
        self.states = states or {}
        self.validate = validate

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

    def get_view(self, wizard, state_name):
        '''
        Returns the view definition
        '''
        Model_ = Pool().get(self.model_name)
        ModelData = Pool().get('ir.model.data')
        if self.view:
            module, fs_id = self.view.split('.')
            view_id = ModelData.get_id(module, fs_id)
        else:
            view_id = None
        return Model_.fields_view_get(view_id=view_id, view_type='form')

    def get_defaults(self, wizard, state_name, fields):
        '''
        Returns defaults values for the fields
        '''
        pool = Pool()
        Model_ = pool.get(self.model_name)
        defaults = Model_.default_get(fields)
        default = getattr(wizard, 'default_%s' % state_name, None)
        if default:
            defaults.update(default(fields))
            for field_name, value in list(defaults.items()):
                if '.' in field_name:
                    continue
                field = Model_._fields[field_name]
                field_rec_name = field_name + '.rec_name'
                if (value
                        and field._type == 'many2one'
                        and field_rec_name not in defaults):
                    Target = pool.get(field.model_name)
                    if 'rec_name' in Target._fields:
                        defaults[field_rec_name] = Target(value).rec_name
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
            validate = (button.validate
                if button.validate is not None
                else button.state != wizard.end_state)
            result.append({
                    'state': button.state,
                    'icon': button.icon,
                    'default': button.default,
                    'validate': validate,
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
        return action.get_action_value()


class StateReport(StateAction):
    'An report state of a wizard'

    def __init__(self, report_name):
        super(StateReport, self).__init__(None)
        self.report_name = report_name

    def get_action(self):
        'Return report definition'
        pool = Pool()
        ActionReport = pool.get('ir.action.report')
        action_reports = ActionReport.search([
                ('report_name', '=', self.report_name),
                ])
        assert action_reports, '%s not found' % self.report_name
        action_report = action_reports[0]
        action = action_report.action
        return action.get_action_value()


class Wizard(URLMixin, PoolBase):
    __no_slots__ = True  # To allow setting State
    start_state = 'start'
    end_state = 'end'

    @classmethod
    def __setup__(cls):
        super(Wizard, cls).__setup__()
        cls.__rpc__ = {
            'create': RPC(readonly=False),
            'delete': RPC(readonly=False),
            'execute': RPC(readonly=False, check_access=False),
            }

        # Copy states
        for attr in dir(cls):
            if isinstance(getattr(cls, attr), State):
                setattr(cls, attr, copy.deepcopy(getattr(cls, attr)))

    @classmethod
    def __post_setup__(cls):
        super(Wizard, cls).__post_setup__()
        # Set states
        cls.states = {}
        for attr in dir(cls):
            if attr.startswith('_'):
                continue
            if isinstance(getattr(cls, attr), State):
                cls.states[attr] = getattr(cls, attr)

    @classmethod
    def __register__(cls, module_name):
        super(Wizard, cls).__register__(module_name)
        pool = Pool()
        Translation = pool.get('ir.translation')
        Translation.register_wizard(cls, module_name)

    @classmethod
    def check_access(cls):
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        ActionWizard = pool.get('ir.action.wizard')
        User = pool.get('res.user')
        context = Transaction().context

        if Transaction().user == 0:
            return

        with Transaction().set_context(_check_access=True):
            model = context.get('active_model')
            if model:
                Model = pool.get(model)
            if model and model != 'ir.ui.menu':
                ModelAccess.check(model, 'read')
            models = ActionWizard.get_models(
                cls.__name__, action_id=context.get('action_id'))
            if model and models and model not in models:
                raise AccessError(gettext(
                        'ir.msg_access_wizard_model_error',
                        wizard=cls.__name__,
                        model=model))
            groups = set(User.get_groups())
            wizard_groups = ActionWizard.get_groups(cls.__name__,
                action_id=context.get('action_id'))
            if wizard_groups:
                if not groups & wizard_groups:
                    raise AccessError(gettext(
                            'ir.msg_access_wizard_error',
                            name=cls.__name__))
            elif model and model != 'ir.ui.menu':
                if (not callable(getattr(Model, 'table_query', None))
                        or Model.write.__func__ != ModelSQL.write.__func__):
                    ModelAccess.check(model, 'write')

            if model:
                ids = context.get('active_ids') or []
                id_ = context.get('active_id')
                if id_ not in ids and id_ is not None:
                    ids.append(id_)
                # Check read access
                Model.read(ids, ['id'])

    @classmethod
    def create(cls):
        "Create a session"
        Session = Pool().get('ir.session.wizard')
        cls.check_access()
        return (Session.create([{}])[0].id, cls.start_state, cls.end_state)

    @classmethod
    def delete(cls, session_id):
        "Delete the session"
        Session = Pool().get('ir.session.wizard')
        end = getattr(cls, cls.end_state, None)
        if end:
            wizard = cls(session_id)
            action = end(wizard)
        else:
            action = None
        Session.delete([Session(session_id)])
        return action

    @classmethod
    def execute(cls, session_id, data, state_name):
        '''
        Execute the wizard state.

        session_id is a Session id
        data is a dictionary with the session data to update
        state_name is the name of state to execute

        Returns a dictionary with:
            - ``actions``: a list of Action to execute
            - ``view``: a dictionary with:
                - ``fields_view``: a fields/view definition
                - ``defaults``: a dictionary with default values
                - ``buttons``: a list of buttons
        '''
        cls.check_access()
        wizard = cls(session_id)
        for key, values in data.items():
            record = getattr(wizard, key)
            for field, value in values.items():
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
            view = state.get_view(self, state_name)
            defaults = state.get_defaults(self, state_name,
                list(view['fields'].keys()))
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
        data = json.loads(session.data, object_hook=JSONDecoder())
        for state_name, state in self.states.items():
            if isinstance(state, StateView):
                Target = pool.get(state.model_name)
                data.setdefault(state_name, {})
                setattr(self, state_name, Target(**data[state_name]))

    def _save(self):
        "Save the session in database"
        Session = Pool().get('ir.session.wizard')
        data = {}
        for state_name, state in self.states.items():
            if isinstance(state, StateView):
                data[state_name] = getattr(self, state_name)._default_values
        session = Session(self._session_id)
        data = json.dumps(data, cls=JSONEncoder, separators=(',', ':'))
        if data != session.data.encode('utf-8'):
            Session.write([session], {
                    'data': data,
                    })

    @cached_property
    def model(self):
        pool = Pool()
        context = Transaction().context
        if context.get('active_model'):
            return pool.get(context['active_model'])

    @cached_property
    def record(self):
        context = Transaction().context
        if context.get('active_id') is not None:
            return self.model(context['active_id'])

    @cached_property
    def records(self):
        context = Transaction().context
        if context.get('active_ids'):
            return self.model.browse(context['active_ids'])
        return []
