# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Board"
import gettext
import xml.dom.minidom

from tryton.signal_event import SignalEvent
from tryton.gui import Main
from tryton.gui.window.view_board import ViewBoard
from tryton.common import RPCExecute, RPCException, MODELNAME

from .tabcontent import TabContent

_ = gettext.gettext


class Board(SignalEvent, TabContent):
    'Board'

    def __init__(self, model, name='', **attributes):
        super(Board, self).__init__(**attributes)

        context = attributes.get('context')
        self.view_ids = attributes.get('view_ids')

        try:
            view, = RPCExecute('model', 'ir.ui.view', 'read',
                self.view_ids, ['arch'], context=context)
        except RPCException:
            raise

        xml_dom = xml.dom.minidom.parseString(view['arch'])
        root, = xml_dom.childNodes
        self.board = ViewBoard(root, context=context)
        self.model = model
        self.dialogs = []
        if not name:
            name = MODELNAME.get(model)
        self.name = name

        self.create_tabcontent()
        self.board.reload()

    def get_toolbars(self):
        return {}

    def widget_get(self):
        return self.board.widget_get()

    def sig_reload(self, test_modified=True):
        self.board.reload()
        return True

    def sig_close(self):
        return True

    def compare(self, model, attributes):
        if not attributes:
            return False
        return (self.model == model
            and self.attributes.get('view_ids') == attributes.get('view_ids')
            and self.attributes.get('context') == attributes.get('context'))

    def __hash__(self):
        return id(self)

    def sig_win_close(self, widget):
        Main().sig_win_close(widget)

    def set_cursor(self):
        if not self.board.actions:
            return
        first_action = self.board.actions[0]
        first_action.screen.set_cursor()
