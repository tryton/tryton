# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Board"
import gettext
from tryton.signal_event import SignalEvent
from tryton.gui import Main
from tryton.gui.window.view_board import ViewBoard
from tryton.common import RPCExecute, RPCException

from tabcontent import TabContent

_ = gettext.gettext


class Board(SignalEvent, TabContent):
    'Board'

    def __init__(self, model, name='', **attributes):
        super(Board, self).__init__()

        context = attributes.get('context')
        self.view_ids = attributes.get('view_ids')

        try:
            view, = RPCExecute('model', 'ir.ui.view', 'read',
                self.view_ids, ['arch'], context=context)
        except RPCException:
            raise

        self.board = ViewBoard(view['arch'], context=context)
        self.model = model
        self.dialogs = []
        if not name:
            self.name = self.board.name
        else:
            self.name = name

        self.create_tabcontent()

    def get_toolbars(self):
        return {}

    def widget_get(self):
        return self.board.widget_get()

    def sig_reload(self, test_modified=True):
        self.board.reload()
        return True

    def sig_close(self):
        return True

    def __eq__(self, value):
        if not value:
            return False
        if not isinstance(value, Board):
            return False
        return (self.model == value.model
            and self.view_ids == value.view_ids
            and self.board.context == value.board.context
            and self.name == value.name)

    def sig_win_close(self, widget):
        Main.get_main().sig_win_close(widget)

    def set_cursor(self):
        if not self.board.actions:
            return
        first_action = self.board.actions[0]
        first_action.screen.set_cursor()
