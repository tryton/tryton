#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gettext
import tryton.rpc as rpc
from tryton.gui.window.view_form.screen import Screen
import tryton.gui.window.view_form.widget_search as widget_search
from tryton.config import TRYTON_ICON
import tryton.common as common

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
                gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                (gtk.STOCK_FIND, gtk.RESPONSE_APPLY,
                gtk.STOCK_NEW, gtk.RESPONSE_ACCEPT,
                gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_OK, gtk.RESPONSE_OK))
        self.win.set_icon(TRYTON_ICON)
        self.win.set_has_separator(True)
        self.win.set_default_response(gtk.RESPONSE_APPLY)
        hbox = gtk.HBox()
        hbox.show()
        self.win.vbox.pack_start(hbox, expand=False, fill=True)
        self.win.vbox.pack_start(gtk.HSeparator(), expand=False, fill=True)
        scrollwindow = gtk.ScrolledWindow()
        scrollwindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.win.vbox.pack_start(scrollwindow, expand=True, fill=True)

        self.screen = Screen(model, self.win, view_type=['tree'],
                context=context, views_preload=views_preload)
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
        scrollwindow.add(viewport)
        scrollwindow.show_all()
        self.view.widget_tree.connect('row_activated', self.sig_activate)
        self.view.widget_tree.connect('button_press_event', self.sig_button)

        self.model_name = model

        if 'tree' in views_preload:
            view_form = views_preload['tree']
        else:
            ctx = self.context.copy()
            ctx.update(rpc.CONTEXT)
            try:
                args = ('model', self.model_name, 'fields_view_get',
                        False, 'tree', ctx)
                view_form = rpc.execute(*args)
            except Exception, exception:
                view_form = common.process_exception(exception, self.parent, *args)
        self.form = widget_search.Form(view_form['arch'], view_form['fields'],
                model, parent=self.win)

        self.title = _('Search: %s') % self.form.name
        self.title_results = _('Search: %s (%%d result(s))') % \
                self.form.name.replace('%', '%%')
        self.win.set_title(self.title)

        hbox.pack_start(self.form.widget)
        self.ids = ids
        if self.ids:
            self.reload()
        self.old_search = None
        self.old_offset = self.old_limit = None
        if self.ids:
            self.old_search = []
            self.old_limit = self.form.get_limit()
            self.old_offset = self.form.get_offset()

        self.view.widget.show_all()
        if self.form.focusable:
            self.form.focusable.grab_focus()

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

    def find(self, *args):
        limit = self.form.get_limit()
        offset = self.form.get_offset()
        if (self.old_search == self.form.value) \
                and (self.old_limit==limit) \
                and (self.old_offset==offset):
            self.win.response(gtk.RESPONSE_OK)
            return False
        self.old_offset = offset
        self.old_limit = limit
        value = self.form.value
        value += self.domain
        try:
            self.ids = rpc.execute('model', self.model_name, 'search', value,
                    offset, limit, None, rpc.CONTEXT)
        except Exception, exception:
            common.process_exception(exception, self.win)
            return False
        self.reload()
        self.old_search = self.form.value
        self.win.set_title(self.title_results % len(self.ids))
        return True

    def reload(self):
        self.screen.clear()
        self.screen.load(self.ids)
        sel = self.view.widget_tree.get_selection()

    def sel_ids_get(self):
        return self.screen.sel_ids_get()

    def destroy(self):
        self.parent.present()
        self.screen.destroy()
        self.win.destroy()

    def run(self):
        end = False
        while not end:
            button = self.win.run()
            if button == gtk.RESPONSE_OK:
                res = self.sel_ids_get()
                end = True
            elif button == gtk.RESPONSE_APPLY:
                end = not self.find()
                if end:
                    res = self.sel_ids_get()
            elif button == gtk.RESPONSE_ACCEPT:
                from tryton.gui.window.view_form.view.form_gtk.many2one \
                        import Dialog
                dia = Dialog(self.model_name, window=self.win,
                        domain=self.domain, context=self.context)
                res, value = dia.run()
                if res:
                    res = [value[0]]
                else:
                    res = None
                end = True
            else:
                res = None
                end = True
        self.destroy()
        return res
