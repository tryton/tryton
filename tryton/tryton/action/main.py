#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import time
import datetime
import tryton.rpc as rpc
from tryton.wizard import Wizard
from tryton.common import message, error, selection, file_open, mailto
from tryton.gui.window import Window
from tryton.pyson import PYSONDecoder
import gettext
import tempfile
import base64
import os
import webbrowser
import tryton.common as common

_ = gettext.gettext

class Action(object):

    @staticmethod
    def exec_report(name, data, window, direct_print=False, email_print=False,
            email=None, context=None):
        if context is None:
            context = {}
        if email is None:
            email = {}
        datas = data.copy()
        ids = datas['ids']
        del datas['ids']
        ctx = rpc.CONTEXT.copy()
        ctx.update(context)
        if not ids:
            args = ('model', datas['model'], 'search', [], 0, None, None, ctx)
            try:
                ids = rpc.execute(*args)
            except Exception, exception:
                ids = common.process_exception(exception, window, *args)
                if not ids:
                    return False
            if ids == []:
                message(_('Nothing to print!'), window)
                return False
            datas['id'] = ids[0]
        args = ('report', name, 'execute', ids, datas, ctx)
        rpcprogress = common.RPCProgress('execute', args, window)
        try:
            res = rpcprogress.run()
        except Exception, exception:
            common.process_exception(exception, window)
            return False
        if not res:
            return False
        (type, data, print_p, name) = res
        if not print_p and direct_print:
            print_p = True
        dtemp = tempfile.mkdtemp(prefix='tryton_')
        fp_name = os.path.join(dtemp,
                name.replace(os.sep, '_').replace(os.altsep or os.sep, '_') \
                        + os.extsep + type)
        file_d = open(fp_name, 'wb')
        file_d.write(base64.decodestring(data))
        file_d.close()
        if email_print:
            mailto(to=email.get('to'), cc=email.get('cc'),
                    subject=email.get('subject'), body=email.get('body'),
                    attachment=fp_name)
        else:
            file_open(fp_name, type, window, print_p=print_p)
        return True

    @staticmethod
    def execute(act_id, datas, window, action_type=None, context=None):
        if context is None:
            context = {}
        ctx = rpc.CONTEXT.copy()
        ctx.update(context)
        if not action_type:
            res = False
            try:
                res = rpc.execute('model', 'ir.action', 'read', act_id,
                        ['type'], ctx)
            except Exception, exception:
                common.process_exception(exception, window)
                return
            if not res:
                raise Exception, 'ActionNotFound'
            action_type = res['type']
        try:
            res = rpc.execute('model', action_type, 'search_read',
                    [('action', '=', act_id)], 0, 1, None, None, ctx)
        except Exception, exception:
            common.process_exception(exception, window)
            return
        Action._exec_action(res, window, datas)

    @staticmethod
    def _exec_action(action, window, datas=None, context=None):
        if context is None:
            context = {}
        if datas is None:
            datas = {}
        if 'type' not in (action or {}):
            return

        if action['type'] == 'ir.action.act_window':
            for key in (
                    'res_id',
                    'res_model',
                    'view_type',
                    'limit',
                    'auto_refresh',
                    'search_value',
                    ):
                datas[key] = action.get(key, datas.get(key, None))

            view_ids = False
            datas['view_mode'] = None
            if action.get('views', []):
                view_ids = [x[0] for x in action['views']]
                datas['view_mode'] = [x[1] for x in action['views']]
            elif action.get('view_id', False):
                view_ids = [action['view_id'][0]]

            action.setdefault('pyson_domain', '[]')
            ctx = {
                'active_id': datas.get('id',False),
                'active_ids': datas.get('ids',[]),
            }
            ctx.update(rpc.CONTEXT)
            eval_ctx = ctx.copy()
            action_ctx = PYSONDecoder(eval_ctx).decode(
                    action.get('pyson_context') or '{}')
            ctx.update(action_ctx)
            ctx.update(context)

            domain_context = ctx.copy()
            domain_context['context'] = ctx
            domain = PYSONDecoder(domain_context).decode(action['pyson_domain'])

            if datas.get('domain', False):
                domain.append(datas['domain'])

            search_context = ctx.copy()
            search_context['context'] = ctx
            search_value = PYSONDecoder(search_context).decode(
                    action['pyson_search_value'] or '{}')

            name = False
            if action.get('window_name', True):
                name = action.get('name', False)

            Window.create(view_ids, datas['res_model'], datas['res_id'], domain,
                    action['view_type'], window, action_ctx,
                    datas['view_mode'], name=name,
                    limit=datas['limit'], auto_refresh=datas['auto_refresh'],
                    search_value=search_value)
        elif action['type'] == 'ir.action.wizard':
            if action.get('window', False):
                Window.create_wizard(action['wiz_name'], datas, window,
                    direct_print=action.get('direct_print', False),
                    email_print=action.get('email_print', False),
                    email=action.get('email'), name=action.get('name', False),
                    context=context)
            else:
                Wizard.execute(action['wiz_name'], datas, window,
                        direct_print=action.get('direct_print', False),
                        email_print=action.get('email_print', False),
                        email=action.get('email'), context=context)

        elif action['type'] == 'ir.action.report':
            Action.exec_report(action['report_name'], datas, window,
                    direct_print=action.get('direct_print', False),
                    email_print=action.get('email_print', False),
                    email=action.get('email'), context=context)

        elif action['type'] == 'ir.action.url':
            if action['url']:
                webbrowser.open(action['url'], new=2)

    @staticmethod
    def exec_keyword(keyword, window, data=None, context=None, warning=True,
            alwaysask=False):
        actions = []
        if 'id' in data:
            model_id = data.get('id', False)
            try:
                actions = rpc.execute('model', 'ir.action.keyword',
                        'get_keyword', keyword, (data['model'], model_id),
                        rpc.CONTEXT)
            except Exception, exception:
                common.process_exception(exception, window)
                return False

        keyact = {}
        for action in actions:
            keyact[action['name'].replace('_', '')] = action

        res = selection(_('Select your action'), keyact, window,
                alwaysask=alwaysask)
        if res:
            (name, action) = res
            Action._exec_action(action, window, data, context=context)
            return (name, action)
        elif not len(keyact) and warning:
            message(_('No action defined!'), window)
        return False
