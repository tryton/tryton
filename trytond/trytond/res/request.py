#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import time
import datetime
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval, If
from trytond.transaction import Transaction
from trytond.pool import Pool

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
    _name = 'res.request'
    _description = __doc__
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
        on_change_with=['references']), 'get_number_references')
    state = fields.Selection(_STATES, 'State', required=True, readonly=True)
    history = fields.One2Many('res.request.history', 'request',
           'History', readonly=True)

    def default_act_from(self):
        return int(Transaction().user)

    def default_state(self):
        return 'draft'

    def default_active(self):
        return True

    def default_priority(self):
        return '1'

    def __init__(self):
        super(Request, self).__init__()
        self._rpc.update({
            'request_send': True,
            'request_reply': True,
            'request_close': True,
            'request_get': False,
        })
        self._order.insert(0, ('priority', 'DESC'))
        self._order.insert(1, ('trigger_date', 'DESC'))
        self._order.insert(2, ('create_date', 'DESC'))

    def on_change_with_number_references(self, vals):
        if vals.get('references'):
            return len(vals['references'])
        return 0

    def get_number_references(self, ids, name):
        res = {}
        for request in self.browse(ids):
            if request.references:
                res[request.id] = len(request.references)
            else:
                res[request.id] = 0
        return res

    def request_send(self, ids):
        pool = Pool()
        request_history_obj = pool.get('res.request.history')
        for request in self.browse(ids):
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
            request_history_obj.create(values)
        self.write(ids, {
            'state': 'waiting',
            'date_sent': datetime.datetime.now(),
            })
        return True

    def request_reply(self, ids):
        user = Transaction().user
        for request in self.browse(ids):
            self.write(request.id, {
                'state': 'chatting',
                'act_from': user,
                'act_to': request.act_from.id,
                'trigger_date': False,
                'body': '',
                })
        return True

    def request_close(self, ids):
        self.write(ids, {'state': 'closed', 'active': False})
        return True

    def request_get(self):
        user = Transaction().user
        ids = self.search([
            ('act_to', '=', user),
            ['OR',
                ('trigger_date', '<=', datetime.datetime.now()),
                ('trigger_date', '=', False),
            ],
            ('active', '=', True),
            ])
        ids2 = self.search([
            ('act_from', '=', user),
            ('act_to', '!=', user),
            ('state', '!=', 'draft'),
            ('active', '=', True),
            ])
        return (ids, ids2)

Request()


class RequestLink(ModelSQL, ModelView):
    "Request link"
    _name = 'res.request.link'
    _description = __doc__
    name = fields.Char('Name', required=True, translate=True)
    model = fields.Selection('models_get', 'Model', required=True)
    priority = fields.Integer('Priority')

    def __init__(self):
        super(RequestLink, self).__init__()
        self._order.insert(0, ('priority', 'ASC'))

    def default_priority(self):
        return 5

    def models_get(self):
        pool = Pool()
        model_obj = pool.get('ir.model')
        model_ids = model_obj.search([])
        res = []
        for model in model_obj.browse(model_ids):
            res.append((model.model, model.name))
        return res

RequestLink()


class RequestHistory(ModelSQL, ModelView):
    "Request history"
    _name = 'res.request.history'
    _description = __doc__
    name = fields.Char('Summary', required=True, readonly=True)
    request = fields.Many2One('res.request', 'Request', required=True,
       ondelete='CASCADE', select=1, readonly=True)
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

    def __init__(self):
        super(RequestHistory, self).__init__()
        self._order.insert(0, ('date_sent', 'DESC'))

    def default_name(self):
        return 'No Name'

    def default_act_from(self):
        return int(Transaction().user)

    def default_act_to(self):
        return int(Transaction().user)

    def default_date_sent(self):
        return datetime.datetime.now()

    def write(self, ids, vals):
        pass

RequestHistory()


class RequestReference(ModelSQL, ModelView):
    "Request Reference"
    _name = 'res.request.reference'
    _description = __doc__
    _rec_name = 'reference'

    request = fields.Many2One('res.request', 'Request', required=True,
            ondelete="CASCADE", select=1)
    reference = fields.Reference('Reference', selection='links_get',
            required=True)

    def links_get(self):
        pool = Pool()
        request_link_obj = pool.get('res.request.link')
        ids = request_link_obj.search([])
        request_links = request_link_obj.browse(ids)
        return [(x.model, x.name) for x in request_links]

RequestReference()
