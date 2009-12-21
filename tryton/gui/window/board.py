#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Board"
import gtk
from tryton.signal_event import SignalEvent
import tryton.rpc as rpc
from tryton.gui.window.view_board import ViewBoard
import tryton.common as common


class Board(SignalEvent):
    'Board'

    def __init__(self, window, view_id, context=None, name=False,
            auto_refresh=False):
        super(Board, self).__init__()

        try:
            view = rpc.execute('model', 'ir.ui.view', 'read',
                    view_id, ['arch'], context)
        except Exception, exception:
            common.process_exception(exception, window)
            raise

        self.board = ViewBoard(view['arch'], window, context=context)

        if not name:
            self.name = self.board.name
        else:
            self.name = name
        self.model = ''

        self.widget = gtk.VBox()

        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_NONE)
        viewport.add(self.board.widget_get())
        viewport.show()
        self.scrolledwindow = gtk.ScrolledWindow()
        self.scrolledwindow.set_shadow_type(gtk.SHADOW_NONE)
        self.scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC,
                gtk.POLICY_AUTOMATIC)
        self.scrolledwindow.add(viewport)
        self.scrolledwindow.show()

        self.widget.pack_start(self.scrolledwindow)
        self.widget.show()

        self.handlers = {
            'but_reload': self.sig_reload,
            'but_close': self.sig_close,
        }

    def sig_reload(self, test_modified=True):
        self.board.reload()
        return True

    def sig_close(self):
        return True
