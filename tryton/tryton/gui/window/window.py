#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import tryton.rpc as rpc
from preference import *


class Window(object):

    @staticmethod
    def create(view_ids, model, res_id=False, domain=None,
            view_type='form', window=None, context=None, mode=None, name=False,
            limit=None, auto_refresh=False, search_value=None):
        from tryton.gui import Main
        if context is None:
            context = {}

        if view_type == 'form':
            from form import Form
            win = Form(model, window, res_id, domain, view_type=mode,
                    view_ids = (view_ids or []), context=context, name=name,
                    limit=limit, auto_refresh=auto_refresh,
                    search_value=search_value)
            Main.get_main().win_add(win)
        elif view_type == 'tree':
            if model == 'ir.ui.menu':
                if Main.get_main().sig_reload_menu():
                    return
            from tree import Tree
            win = Tree(model, window, res_id, view_ids and view_ids[0] or None,
                    domain, context, name=name)
            Main.get_main().win_add(win)
        elif view_type == 'board':
            from board import Board
            win = Board(window, view_ids and view_ids[0] or None,
                    context=context, name=name, auto_refresh=auto_refresh)
            Main.get_main().win_add(win)
        else:
            import logging
            log = logging.getLogger('view')
            log.error('unknown view type: '+view_type)
            del log

    @staticmethod
    def create_wizard(action, datas, parent, state='init', direct_print=False,
            email_print=False, email=None, name=False, context=None):
        from tryton.gui import Main
        from wizard import Wizard
        win = Wizard(parent, name=name)
        Main.get_main().win_add(win)
        win.run(action, datas, state=state, direct_print=direct_print,
                email_print=email_print, email=email, context=context)
