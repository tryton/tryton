#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"File actions"
import gtk
import gettext
from tryton.config import TRYTON_ICON, CONFIG
from tryton.common import safe_eval, get_toplevel_window

_ = gettext.gettext


class FileActions(object):
    "File actions window"

    def __init__(self):
        self.parent= get_toplevel_window()
        self.win = gtk.Dialog(_('File Actions'), self.parent,
                gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                    gtk.STOCK_OK, gtk.RESPONSE_OK))
        self.win.set_default_response(gtk.RESPONSE_OK)
        self.win.set_icon(TRYTON_ICON)
        self.win.set_has_separator(True)
        self.win.vbox.pack_start(gtk.Label(
            _('Edit Files Actions')), expand=False, fill=True)
        self.win.vbox.pack_start(gtk.HSeparator())
        self.treeview = gtk.TreeView()

        self.model = gtk.ListStore(str, str, str, str)
        self.treeview.set_model(self.model)

        for index, text in enumerate((_('File Type'), _('Open'), _('Print'))):
            renderer = gtk.CellRendererText()
            if index != 0:
                renderer.set_property('editable', True)
                renderer.connect('edited', self._sig_edited)
            column = gtk.TreeViewColumn(text, renderer, text=index + 1)
            column.set_resizable(True)
            self.treeview.append_column(column)

        i = 1
        if isinstance(CONFIG['client.actions'], basestring):
            CONFIG['client.actions'] = safe_eval(CONFIG['client.actions'])
        extensions = CONFIG['client.actions'].keys()
        extensions.sort()
        for extension in extensions:
            iter = self.model.append()
            self.model.set(iter, 0, extension,
                    1, _('%s file') % extension.upper(),
                    2, CONFIG['client.actions'][extension][0],
                    3, CONFIG['client.actions'][extension][1])

        scroll = gtk.ScrolledWindow()
        scroll.add(self.treeview)
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        viewport= gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        viewport.set_size_request(400, 200)
        viewport.add(scroll)
        self.win.vbox.pack_start(viewport, expand=True, fill=True)

        label = gtk.Label(_('Use "%s" as a placeholder for the file name'))
        label.set_alignment(0.0, 0.5)
        label.set_padding(0, 10)
        self.win.vbox.pack_start(label, expand=False, fill=True)
        self.win.show_all()

    def run(self):
        "Run the window"
        res = self.win.run()
        if res == gtk.RESPONSE_OK:
            config = {}
            for extension, _, cmd_open, cmd_print in self.model:
                config[extension] = {
                    0: cmd_open,
                    1: cmd_print,
                }
            CONFIG['client.actions'] = config
            CONFIG.save()
        self.parent.present()
        self.win.destroy()
        return res

    def _sig_edited(self, cell, path, new_text):
        iter = self.model.get_iter_from_string(path)
        (path, column) = self.treeview.get_cursor()
        column_id = self.treeview.get_columns().index(column)
        self.model.set(iter, column_id + 1, new_text)
