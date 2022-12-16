#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gettext
import tryton.rpc as rpc
from tryton.gui.window.view_form.screen import Screen
import tryton.gui.window.view_form.widget_search as widget_search
from tryton.config import TRYTON_ICON
import tryton.common as common
from tryton.gui.window.win_form import WinForm

_ = gettext.gettext


class WinSearch(object):

    def __init__(self, model, sel_multi=True, ids=None, context=None,
            domain=None, parent=None, views_preload=None):
        if views_preload is None:
            views_preload = {}
        self.domain = domain or []
        self.context = context or {}
        self.sel_multi = sel_multi
        self.parent = parent

        self.win = gtk.Dialog(_('Search'), self.parent,
                gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT)
        self.win.set_icon(TRYTON_ICON)
        self.win.set_has_separator(True)
        self.win.set_default_response(gtk.RESPONSE_APPLY)

        self.accel_group = gtk.AccelGroup()
        self.win.add_accel_group(self.accel_group)

        self.but_find = self.win.add_button(gtk.STOCK_FIND, gtk.RESPONSE_APPLY)
        self.but_new = self.win.add_button(gtk.STOCK_NEW, gtk.RESPONSE_ACCEPT)
        self.but_cancel = self.win.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        self.but_ok = self.win.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
        self.but_ok.add_accelerator('clicked', self.accel_group,
                gtk.keysyms.Return, gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)

        hbox = gtk.HBox()
        hbox.show()
        self.win.vbox.pack_start(hbox, expand=False, fill=True)
        self.win.vbox.pack_start(gtk.HSeparator(), expand=False, fill=True)
        scrollwindow = gtk.ScrolledWindow()
        scrollwindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.win.vbox.pack_start(scrollwindow, expand=True, fill=True)

        self.screen = Screen(model, self.win, domain=domain,
                view_type=['tree'], context=context,
                views_preload=views_preload, row_activate=self.sig_activate)
        self.view = self.screen.current_view
        self.view.unset_editable()
        sel = self.view.widget_tree.get_selection()

        if not sel_multi:
            sel.set_mode(gtk.SELECTION_SINGLE)
        else:
            sel.set_mode(gtk.SELECTION_MULTIPLE)
        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_NONE)
        viewport.add(self.screen.widget)
        self.screen.widget.show()
        viewport.show()
        scrollwindow.add(viewport)
        scrollwindow.show()
        self.view.widget_tree.connect('button_press_event', self.sig_button)

        self.model_name = model

        if ids:
            self.screen.load(ids)

        self.win.set_size_request(700, 500)

    def sig_activate(self, *args):
        self.view.widget_tree.emit_stop_by_name('row_activated')
        if not self.sel_multi:
            self.win.response(gtk.RESPONSE_OK)
        return False

    def sig_button(self, view, event):
        if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            self.win.response(gtk.RESPONSE_OK)
        return False

    def destroy(self):
        self.parent.present()
        self.screen.destroy()
        self.win.destroy()

    def run(self):
        end = False
        while not end:
            button = self.win.run()
            if button == gtk.RESPONSE_OK:
                res = self.screen.sel_ids_get()
                end = True
            elif button == gtk.RESPONSE_APPLY:
                end = not self.screen.search_filter()
                if end:
                    res = self.screen.sel_ids_get()
            elif button == gtk.RESPONSE_ACCEPT:
                res = None
                screen = Screen(self.model_name, self.win, domain=self.domain,
                        context=self.context, view_type=['form'])
                win = WinForm(screen, self.win, new=True)
                while win.run():
                    if screen.save_current():
                        res = [screen.current_record.id]
                        break
                    else:
                        screen.display()
                win.destroy()
                end = True
            else:
                res = None
                end = True
        self.destroy()
        return res
