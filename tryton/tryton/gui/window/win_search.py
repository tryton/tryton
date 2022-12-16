# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gettext
import tryton.common as common
from tryton.gui.window.view_form.screen import Screen
from tryton.config import TRYTON_ICON
from tryton.gui.window.win_form import WinForm
from tryton.gui.window.nomodal import NoModal

_ = gettext.gettext


class WinSearch(NoModal):

    def __init__(self, model, callback, sel_multi=True, context=None,
            domain=None, view_ids=None, views_preload=None, new=True,
            title=''):
        NoModal.__init__(self)
        if views_preload is None:
            views_preload = {}
        self.domain = domain or []
        self.context = context or {}
        self.sel_multi = sel_multi
        self.callback = callback
        self.title = title

        self.win = gtk.Dialog(_('Search'), self.parent,
            gtk.DIALOG_DESTROY_WITH_PARENT)
        self.win.set_icon(TRYTON_ICON)
        self.win.set_default_response(gtk.RESPONSE_APPLY)
        self.win.connect('response', self.response)

        self.accel_group = gtk.AccelGroup()
        self.win.add_accel_group(self.accel_group)

        self.but_cancel = self.win.add_button(gtk.STOCK_CANCEL,
            gtk.RESPONSE_CANCEL)
        self.but_find = self.win.add_button(gtk.STOCK_FIND, gtk.RESPONSE_APPLY)
        if new and common.MODELACCESS[model]['create']:
            self.but_new = self.win.add_button(gtk.STOCK_NEW,
                gtk.RESPONSE_ACCEPT)
            self.but_new.set_accel_path('<tryton>/Form/New', self.accel_group)

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

        self.screen = Screen(model, domain=domain, mode=['tree'],
            context=context, view_ids=view_ids, views_preload=views_preload,
            row_activate=self.sig_activate)
        self.view = self.screen.current_view
        self.view.unset_editable()
        # Prevent to set tree_state
        self.screen.tree_states_done.add(id(self.view))
        sel = self.view.treeview.get_selection()
        self.win.set_title(_('Search %s') % self.title)

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

        self.model_name = model

        self.win.set_default_size(700, 500)

        self.register()
        sensible_allocation = self.sensible_widget.get_allocation()
        self.win.set_default_size(int(sensible_allocation.width * 0.9),
            int(sensible_allocation.height * 0.9))

    def sig_activate(self, *args):
        self.view.treeview.emit_stop_by_name('row_activated')
        self.win.response(gtk.RESPONSE_OK)
        return True

    def destroy(self):
        self.screen.destroy()
        self.win.destroy()
        NoModal.destroy(self)

    def show(self):
        self.win.show()
        common.center_window(self.win, self.parent, self.sensible_widget)

    def hide(self):
        self.win.hide()

    def response(self, win, response_id):
        res = None
        if response_id == gtk.RESPONSE_OK:
            res = [r.id for r in self.screen.selected_records]
        elif response_id == gtk.RESPONSE_APPLY:
            self.screen.search_filter(self.screen.screen_container.get_text())
            return
        elif response_id == gtk.RESPONSE_ACCEPT:
            screen = Screen(self.model_name, domain=self.domain,
                context=self.context, mode=['form'])

            def callback(result):
                if result and screen.save_current():
                    record = screen.current_record
                    res = [(record.id, record.value.get('rec_name', ''))]
                    self.callback(res)
                else:
                    self.callback(None)
            self.destroy()
            WinForm(screen, callback, new=True, title=self.title)
            return
        if res:
            group = self.screen.group
            res = [(id_, group.get(id_).value.get('rec_name', ''))
                for id_ in res]
        self.callback(res)
        self.destroy()
