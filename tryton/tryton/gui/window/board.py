#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Board"
import gtk
import pango
from tryton.signal_event import SignalEvent
import tryton.rpc as rpc
from tryton.gui.window.view_board import ViewBoard
import tryton.common as common


class Board(SignalEvent):
    'Board'

    def __init__(self, model, window, view_id, context=None, name=False,
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
        self.model = model

        self.widget = gtk.VBox()

        title = gtk.Label()
        title.set_use_markup(True)
        title.modify_font(pango.FontDescription("14"))
        title.set_label('<b>' + self.name + '</b>')
        title.set_padding(20, 4)
        title.set_alignment(0.0, 0.5)
        title.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#000000"))
        title.show()

        hbox = gtk.HBox()
        hbox.pack_start(title, expand=True, fill=True)
        hbox.show()

        frame = gtk.Frame()
        frame.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        frame.add(hbox)
        frame.show()

        eb = gtk.EventBox()
        eb.add(frame)
        eb.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#ffffff"))
        eb.show()

        self.widget.pack_start(eb, expand=False, fill=True, padding=3)

        self.toolbar_box = gtk.HBox()
        self.widget.pack_start(self.toolbar_box, False, True)

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
