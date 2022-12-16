#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
from ..model import ModelView, ModelSQL, fields
from ..pyson import Eval, If
from ..transaction import Transaction
from ..pool import Pool
from ..rpc import RPC

__all__ = [
    'Request', 'RequestLink', 'RequestHistory', 'RequestReference',
    ]

_STATES = [
    ('draft', 'Draft'),
    ('waiting', 'Waiting'),
    ('chatting', 'Chatting'),
    ('closed', 'Closed'),
]

_PRIORITIES = [
    ('0', 'Low'),
    ('1', 'Normal'),
    ('2', 'High'),
]

_READONLY = If(Eval('state').in_(['waiting', 'closed']),
    True,
    If(Eval('state') == 'chatting',
        Eval('act_from') != Eval('_user'),
        False))
_DEPENDS = ['state', 'act_from']


class Request(ModelSQL, ModelView):
    "Request"
    __name__ = 'res.request'
    name = fields.Char('Subject', states={
            'readonly': _READONLY,
            }, required=True, depends=_DEPENDS)
    active = fields.Boolean('Active')
    priority = fields.Selection(_PRIORITIES, 'Priority', states={
            'readonly': _READONLY,
            }, required=True, order_field='priority', depends=_DEPENDS)
    act_from = fields.Many2One('res.user', 'From', required=True,
       readonly=True)
    act_to = fields.Many2One('res.user', 'To', required=True,
            domain=[('active', '=', True)],
            states={
                'readonly': _READONLY,
            }, depends=_DEPENDS)
    body = fields.Text('Body', states={
            'readonly': _READONLY,
            }, depends=_DEPENDS)
    date_sent = fields.DateTime('Date', readonly=True)
    trigger_date = fields.DateTime('Trigger Date', states={
            'readonly': _READONLY,
            }, depends=_DEPENDS)
    references = fields.One2Many('res.request.reference', 'request',
        'References', states={
            'readonly': If(Eval('state') == 'closed',
                True,
                Eval('act_from', 0) != Eval('_user', 0)),
            }, depends=['state', 'act_from'])
    number_references = fields.Function(fields.Integer('Number of References',
        on_change_with=['references']), 'on_change_with_number_references')
    state = fields.Selection(_STATES, 'State', required=True, readonly=True)
    history = fields.One2Many('res.request.history', 'request',
           'History', readonly=True)

    @classmethod
    def __setup__(cls):
        super(Request, cls).__setup__()
        cls.__rpc__.update({
                'request_get': RPC(),
                })
        cls._order.insert(0, ('priority', 'DESC'))
        cls._order.insert(1, ('trigger_date', 'DESC'))
        cls._order.insert(2, ('create_date', 'DESC'))
        cls._buttons.update({
                'send': {
                    'invisible': ~Eval('state').in_(['draft', 'chatting']),
                    'readonly': Eval('act_from') != Eval('_user'),
                    },
                'reply': {
                    'invisible': Eval('state') != 'waiting',
                    'readonly': Eval('act_to') != Eval('_user'),
                    },
                'close': {
                    'invisible': ~Eval('state').in_(['waiting', 'draft',
                            'chatting']),
                    },
                })

    @staticmethod
    def default_act_from():
        return int(Transaction().user)

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_priority():
        return '1'

    def on_change_with_number_references(self, name=None):
        return len(self.references or '')

    @classmethod
    @ModelView.button
    def send(cls, requests):
        pool = Pool()
        RequestHistory = pool.get('res.request.history')
        to_create = []
        for request in requests:
            values = {
                'request': request.id,
                'act_from': request.act_from.id,
                'act_to': request.act_to.id,
                'body': request.body,
                'state': request.state,
                'subject': request.name,
                'number_references': request.number_references,
                'priority': request.priority,
            }
            if values['body'] and len(values['body']) > 128:
                values['name'] = values['body'][:125] + '...'
            else:
                values['name'] = values['body'] or '/'
            to_create.append(values)
        if to_create:
            RequestHistory.create(to_create)
        cls.write(requests, {
            'state': 'waiting',
            'date_sent': datetime.datetime.now(),
            })

    @classmethod
    @ModelView.button
    def reply(cls, requests):
        user = Transaction().user
        for request in requests:
            cls.write([request], {
                'state': 'chatting',
                'act_from': user,
                'act_to': request.act_from.id,
                'trigger_date': None,
                'body': '',
                })

    @classmethod
    @ModelView.button
    def close(cls, requests):
        cls.write(requests, {'state': 'closed', 'active': False})

    @classmethod
    def request_get(cls):
        user = Transaction().user
        requests = cls.search([
            ('act_to', '=', user),
            ['OR',
                ('trigger_date', '<=', datetime.datetime.now()),
                ('trigger_date', '=', None),
            ],
            ('active', '=', True),
            ])
        requests2 = cls.search([
            ('act_from', '=', user),
            ('act_to', '!=', user),
            ('state', '!=', 'draft'),
            ('active', '=', True),
            ])
        return ([r.id for r in requests], [r.id for r in requests2])


class RequestLink(ModelSQL, ModelView):
    "Request link"
    __name__ = 'res.request.link'
    name = fields.Char('Name', required=True, translate=True)
    model = fields.Selection('models_get', 'Model', required=True)
    priority = fields.Integer('Priority', required=True)

    @classmethod
    def __setup__(cls):
        super(RequestLink, cls).__setup__()
        cls._order.insert(0, ('priority', 'ASC'))

    @staticmethod
    def default_priority():
        return 5

    @staticmethod
    def models_get():
        pool = Pool()
        Model = pool.get('ir.model')
        models = Model.search([])
        res = []
        for model in models:
            res.append((model.model, model.name))
        return res


class RequestHistory(ModelSQL, ModelView):
    "Request history"
    __name__ = 'res.request.history'
    name = fields.Char('Summary', required=True, readonly=True)
    request = fields.Many2One('res.request', 'Request', required=True,
       ondelete='CASCADE', select=True, readonly=True)
    act_from = fields.Many2One('res.user', 'From', required=True,
       readonly=True)
    act_to = fields.Many2One('res.user', 'To', required=True, readonly=True)
    body = fields.Text('Body', readonly=True)
    date_sent = fields.DateTime('Date sent', required=True, readonly=True)
    state = fields.Selection(_STATES, 'State', required=True, readonly=True)
    subject = fields.Char('Subject', required=True, readonly=True)
    number_references = fields.Integer('References', readonly=True)
    priority = fields.Selection(_PRIORITIES, 'Priority', required=True,
            readonly=True)

    @classmethod
    def __setup__(cls):
        super(RequestHistory, cls).__setup__()
        cls._order.insert(0, ('date_sent', 'DESC'))

    @staticmethod
    def default_name():
        return 'No Name'

    @staticmethod
    def default_act_from():
        return int(Transaction().user)

    @staticmethod
    def default_act_to():
        return int(Transaction().user)

    @staticmethod
    def default_date_sent():
        return datetime.datetime.now()

    @staticmethod
    def write(records, vals):
        pass


class RequestReference(ModelSQL, ModelView):
    "Request Reference"
    __name__ = 'res.request.reference'
    _rec_name = 'reference'

    request = fields.Many2One('res.request', 'Request', required=True,
            ondelete="CASCADE", select=True)
    reference = fields.Reference('Reference', selection='links_get',
            required=True)

    @staticmethod
    def links_get():
        pool = Pool()
        RequestLink = pool.get('res.request.link')
        request_links = RequestLink.search([])
        return [(x.model, x.name) for x in request_links]
