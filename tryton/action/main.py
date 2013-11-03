#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import time
import datetime
import tryton.rpc as rpc
from tryton.common import message, error, selection, file_open, mailto
from tryton.gui.window import Window
from tryton.pyson import PYSONDecoder
from tryton.exceptions import TrytonServerError
import gettext
import tempfile
import os
import webbrowser
import tryton.common as common

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
        ids = data['ids']
        del data['ids']
        ctx = rpc.CONTEXT.copy()
        ctx.update(context)
        ctx['direct_print'] = direct_print
        ctx['email_print'] = email_print
        ctx['email'] = email
        if not ids:
            args = ('model', data['model'], 'search', [], 0, None, None, ctx)
            try:
                ids = rpc.execute(*args)
            except TrytonServerError, exception:
                ids = common.process_exception(exception, *args)
                if not ids:
                    return False
            if ids == []:
                message(_('Nothing to print!'))
                return False
            data['id'] = ids[0]
        args = ('report', name, 'execute', ids, data, ctx)
        rpcprogress = common.RPCProgress('execute', args)
        try:
            res = rpcprogress.run()
        except TrytonServerError, exception:
            common.process_exception(exception)
            return False
        if not res:
            return False
        (type, data, print_p, name) = res
        if not print_p and direct_print:
            print_p = True
        dtemp = tempfile.mkdtemp(prefix='tryton_')
        fp_name = os.path.join(dtemp,
                name.replace(os.sep, '_').replace(os.altsep or os.sep, '_') \
            + os.extsep
            + type.replace(os.sep, '_').replace(os.altsep or os.sep, '_'))
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
        if context is None:
            context = {}
        ctx = rpc.CONTEXT.copy()
        ctx.update(context)
        if not action_type:
            res = False
            try:
                res = rpc.execute('model', 'ir.action', 'read', act_id,
                        ['type'], ctx)
            except TrytonServerError, exception:
                common.process_exception(exception)
                return
            if not res:
                raise Exception, 'ActionNotFound'
            action_type = res['type']
        try:
            res = rpc.execute('model', action_type, 'search_read',
                    [('action', '=', act_id)], 0, 1, None, None, ctx)
        except TrytonServerError, exception:
            common.process_exception(exception)
            return
        Action._exec_action(res, data)

    @staticmethod
    def _exec_action(action, data=None, context=None):
        if context is None:
            context = {}
        if data is None:
            data = {}
        else:
            data = data.copy()
        if 'type' not in (action or {}):
            return

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
                'active_id': data.get('id', False),
                'active_ids': data.get('ids', []),
            }
            ctx.update(rpc.CONTEXT)
            eval_ctx = ctx.copy()
            eval_ctx['_user'] = rpc._USER
            action_ctx = PYSONDecoder(eval_ctx).decode(
                    action.get('pyson_context') or '{}')
            ctx.update(action_ctx)
            ctx.update(context)

            domain_context = ctx.copy()
            domain_context['context'] = ctx
            domain_context['_user'] = rpc._USER
            domain = PYSONDecoder(domain_context).decode(action['pyson_domain'])

            search_context = ctx.copy()
            search_context['context'] = ctx
            search_context['_user'] = rpc._USER
            search_value = PYSONDecoder(search_context).decode(
                    action['pyson_search_value'] or '[]')

            name = False
            if action.get('window_name', True):
                name = action.get('name', False)

            res_model = action.get('res_model', data.get('res_model'))
            res_id = action.get('res_id', data.get('res_id'))

            Window.create(view_ids, res_model, res_id, domain,
                    action_ctx, view_mode, name=name,
                    limit=action.get('limit'),
                    auto_refresh=action.get('auto_refresh'),
                    search_value=search_value,
                    icon=(action.get('icon.rec_name') or ''))
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
        if 'id' in data:
            model_id = data.get('id', False)
            try:
                actions = rpc.execute('model', 'ir.action.keyword',
                        'get_keyword', keyword, (data['model'], model_id),
                        rpc.CONTEXT)
            except TrytonServerError, exception:
                common.process_exception(exception)
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
