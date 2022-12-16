#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import tryton.rpc as rpc
from preference import *


class Window(object):

    @staticmethod
    def create(view_ids, model, res_id=False, domain=None, window=None,
            context=None, mode=None, name=False, limit=None,
            auto_refresh=False, search_value=None, icon=None):
        from tryton.gui import Main
        if context is None:
            context = {}

        if model:
            from form import Form
            win = Form(model, window, res_id, domain, mode=mode,
                    view_ids=(view_ids or []), context=context, name=name,
                    limit=limit, auto_refresh=auto_refresh,
                    search_value=search_value)
        else:
            from board import Board
            win = Board(model, window, view_ids and view_ids[0] or None,
                    context=context, name=name, auto_refresh=auto_refresh)
        win.icon = icon
        Main.get_main().win_add(win)

    @staticmethod
    def create_wizard(action, datas, parent, state='init', direct_print=False,
            email_print=False, email=None, name=False, context=None,
            icon=None):
        from tryton.gui import Main
        from wizard import Wizard
        win = Wizard(parent, name=name)
        win.icon = icon
        Main.get_main().win_add(win)
        win.run(action, datas, state=state, direct_print=direct_print,
                email_print=email_print, email=email, context=context)
