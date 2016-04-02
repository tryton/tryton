# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import tryton.rpc as rpc
from tryton.common import message, selection, file_open, mailto
from tryton.gui.window import Window
from tryton.pyson import PYSONDecoder
import gettext
import tempfile
import os
import webbrowser
from tryton.common import RPCProgress, RPCExecute, RPCException, slugify

_ = gettext.gettext


class Action(object):

    @staticmethod
    def exec_report(name, data, direct_print=False, email_print=False,
            email=None, context=None):
        if context is None:
            context = {}
        if email is None:
            email = {}
        data = data.copy()
        ctx = rpc.CONTEXT.copy()
        ctx.update(context)
        ctx['direct_print'] = direct_print
        ctx['email_print'] = email_print
        ctx['email'] = email
        args = ('report', name, 'execute', data.get('ids', []), data, ctx)
        try:
            res = RPCProgress('execute', args).run()
        except RPCException:
            return False
        if not res:
            return False
        (type, data, print_p, name) = res
        if not print_p and direct_print:
            print_p = True
        dtemp = tempfile.mkdtemp(prefix='tryton_')

        fp_name = os.path.join(dtemp,
            slugify(name) + os.extsep + slugify(type))
        with open(fp_name, 'wb') as file_d:
            file_d.write(data)
        if email_print:
            mailto(to=email.get('to'), cc=email.get('cc'),
                subject=email.get('subject'), body=email.get('body'),
                attachment=fp_name)
        else:
            file_open(fp_name, type, print_p=print_p)
        return True

    @staticmethod
    def execute(act_id, data, action_type=None, context=None):
        # Must be executed synchronously to avoid double execution
        # on double click.
        if not action_type:
            action, = RPCExecute('model', 'ir.action', 'read', [act_id],
                ['type'], context=context)
            action_type = action['type']
        action, = RPCExecute('model', action_type, 'search_read',
            [('action', '=', act_id)], 0, 1, None, None,
            context=context)
        Action._exec_action(action, data, context=context)

    @staticmethod
    def _exec_action(action, data=None, context=None):
        if context is None:
            context = {}
        else:
            context = context.copy()
        if 'date_format' not in context:
            context['date_format'] = rpc.CONTEXT.get(
                'locale', {}).get('date', '%x')
        if data is None:
            data = {}
        else:
            data = data.copy()
        if 'type' not in (action or {}):
            return

        data['action_id'] = action['id']
        if action['type'] == 'ir.action.act_window':
            view_ids = False
            view_mode = None
            if action.get('views', []):
                view_ids = [x[0] for x in action['views']]
                view_mode = [x[1] for x in action['views']]
            elif action.get('view_id', False):
                view_ids = [action['view_id'][0]]

            action.setdefault('pyson_domain', '[]')
            ctx = {
                'active_model': data.get('model'),
                'active_id': data.get('id'),
                'active_ids': data.get('ids', []),
            }
            ctx.update(rpc.CONTEXT)
            ctx['_user'] = rpc._USER
            decoder = PYSONDecoder(ctx)
            action_ctx = context.copy()
            action_ctx.update(
                decoder.decode(action.get('pyson_context') or '{}'))
            ctx.update(action_ctx)
            ctx.update(context)

            ctx['context'] = ctx
            decoder = PYSONDecoder(ctx)
            domain = decoder.decode(action['pyson_domain'])
            order = decoder.decode(action['pyson_order'])
            search_value = decoder.decode(action['pyson_search_value'] or '[]')
            tab_domain = [(n, decoder.decode(d)) for n, d in action['domains']]

            name = False
            if action.get('window_name', True):
                name = action.get('name', False)

            res_model = action.get('res_model', data.get('res_model'))
            res_id = action.get('res_id', data.get('res_id'))

            Window.create(view_ids, res_model, res_id, domain,
                    action_ctx, order, view_mode, name=name,
                    limit=action.get('limit'),
                    search_value=search_value,
                    icon=(action.get('icon.rec_name') or ''),
                    tab_domain=tab_domain,
                    context_model=action['context_model'])
        elif action['type'] == 'ir.action.wizard':
            Window.create_wizard(action['wiz_name'], data,
                direct_print=action.get('direct_print', False),
                email_print=action.get('email_print', False),
                email=action.get('email'), name=action.get('name', False),
                context=context, icon=(action.get('icon.rec_name') or ''),
                window=action.get('window', False))

        elif action['type'] == 'ir.action.report':
            Action.exec_report(action['report_name'], data,
                    direct_print=action.get('direct_print', False),
                    email_print=action.get('email_print', False),
                    email=action.get('email'), context=context)

        elif action['type'] == 'ir.action.url':
            if action['url']:
                webbrowser.open(action['url'], new=2)

    @staticmethod
    def exec_keyword(keyword, data=None, context=None, warning=True,
            alwaysask=False):
        actions = []
        model_id = data.get('id', False)
        try:
            actions = RPCExecute('model', 'ir.action.keyword',
                'get_keyword', keyword, (data['model'], model_id))
        except RPCException:
            return False

        keyact = {}
        for action in actions:
            keyact[action['name'].replace('_', '')] = action

        res = selection(_('Select your action'), keyact, alwaysask=alwaysask)
        if res:
            (name, action) = res
            Action._exec_action(action, data, context=context)
            return (name, action)
        elif not len(keyact) and warning:
            message(_('No action defined!'))
        return False

    @staticmethod
    def evaluate(action, atype, record):
        '''
        Evaluate the action with the record.
        '''
        action = action.copy()
        email = {}
        if 'pyson_email' in action:
            email = record.expr_eval(action['pyson_email'])
            if not email:
                email = {}
        if 'subject' not in email:
            email['subject'] = action['name'].replace('_', '')
        action['email'] = email
        return action
