#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gettext
from tryton.common import message, TRYTON_ICON
import tryton.rpc as rpc
from interface import ParserView
from tryton.action import Action
from tryton.config import CONFIG

_ = gettext.gettext


class ViewWidget(object):

    def __init__(self, parent, widget, widget_name):
        self.view_form = parent
        self.widget = widget
        self.widget._view = self
        self.widget_name = widget_name

    def display(self, model):
        if not model:
            self.widget.display(model, False)
            return False
        modelfield = model.mgroup.mfields.get(self.widget_name, None)
        if modelfield:
            modelfield.state_set(model)
            self.widget.display(model, modelfield)
        elif isinstance(self.widget, Action):
            self.widget.display(model, False)

    def reset(self, model):
        modelfield = None
        if model:
            modelfield = model.mgroup.mfields.get(self.widget_name, None)
            if modelfield and 'valid' in modelfield.get_state_attrs(model):
                modelfield.get_state_attrs(model)['valid'] = True
        self.display(model)

    def set_value(self, model):
        if self.widget_name in model.mgroup.mfields:
            self.widget.set_value(model, model.mgroup.mfields[self.widget_name])

    def _get_model(self):
        return self.view_form.screen.current_model

    model = property(_get_model)

    def _get_modelfield(self):
        if self.model:
            return self.model.mgroup.mfields[self.widget_name]

    modelfield = property(_get_modelfield)


class ViewForm(ParserView):

    def __init__(self, window, screen, widget, children=None,
            buttons=None, toolbar=None, notebooks=None, cursor_widget=''):
        super(ViewForm, self).__init__(window, screen, widget, children,
                buttons, toolbar, notebooks, cursor_widget)
        self.view_type = 'form'
        self.model_add_new = False

        for button in self.buttons:
            button.form = self

        self.widgets = dict([(name, [ViewWidget(self, widget, name)
            for widget in widgets])
            for name, widgets in children.items()])

        vbox = gtk.VBox()
        vp = gtk.Viewport()
        vp.set_shadow_type(gtk.SHADOW_NONE)
        vp.add(self.widget)
        scroll = gtk.ScrolledWindow()
        scroll.add(vp)
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.viewport = gtk.Viewport()
        self.viewport.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        self.viewport.add(scroll)
        width, height = self.widget.size_request()
        self.widget = vbox
        self.widget.set_size_request(width, height)
        self.widget.pack_start(self.viewport, expand=True, fill=True)

        if toolbar and not CONFIG['client.modepda']:
            hbox = gtk.HBox(homogeneous=False)
            self.widget.pack_start(hbox, False, False)

            gtktoolbar = gtk.Toolbar()
            gtktoolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
            gtktoolbar.set_style(gtk.TOOLBAR_BOTH)
            hbox.pack_start(gtktoolbar, expand=True, fill=True)
            for icontype in ('print', 'action', 'relate'):
                if not toolbar[icontype]:
                    continue

                for tool in toolbar[icontype]:
                    iconstock = {
                        'print': 'tryton-print',
                        'action': 'tryton-executable',
                        'relate': 'tryton-go-jump',
                    }.get(icontype)

                    if hasattr(gtk, 'MenuToolButton') and icontype == 'print':
                        tbutton = gtk.MenuToolButton(iconstock)
                    else:
                        tbutton = gtk.ToolButton(iconstock)
                    tbutton.set_use_underline(True)
                    text = tool['name']
                    if '_' not in text:
                        text = '_' + text
                    tbutton.set_label(text)
                    gtktoolbar.insert(tbutton, -1)

                    tbutton.connect('clicked', self._sig_clicked, tool,
                            icontype)
                    if hasattr(gtk, 'MenuToolButton') and icontype == 'print':
                        menu = gtk.Menu()
                        for mtype, text in (('print', _('_Direct Print')),
                                ('email', _('_Email as Attachment'))):
                            menuitem = gtk.MenuItem(text)
                            tool = tool.copy()
                            if mtype == 'print':
                                tool['direct_print'] = True
                                tool['email_print'] = False
                            else:
                                tool['direct_print'] = False
                                tool['email_print'] = True
                            menuitem.connect('activate', self._sig_clicked,
                                    tool, icontype)
                            menu.add(menuitem)
                            menuitem.show()
                        tbutton.set_menu(menu)
            hbox.show_all()


    def _sig_clicked(self, widget, action, atype):
        return self._action(action, atype)

    def _action(self, action, atype):
        act = action.copy()
        if atype in ('print', 'action'):
            self.screen.save_current()
            obj_id = self.screen.current_model \
                    and self.screen.current_model.id
            if obj_id < 0:
                if atype in ('print'):
                    message(_('You must save this record ' \
                        'to be able to use the print button!'), self.window)
                if atype in ('action'):
                    message(_('You must save this record ' \
                        'to be able to use the action button!'), self.window)
                return False
            email = {}
            if 'email' in action:
                email = self.screen.current_model.expr_eval(action['email'])
                if not email:
                    email = {}
            email['subject'] = action['name'].replace('_', '')
            act['email'] = email
            self.screen.display()
        if atype == 'relate':
            obj_id = self.screen.current_model \
                    and self.screen.current_model.id
            if not obj_id:
                message(_('You must select a record ' \
                        'to be able to use the relate button !'), self.window)
                return False
            if 'domain' in act:
                act['domain'] = str(
                        self.screen.current_model.expr_eval(
                                act['domain'], check_load=False))
            if 'context' in act:
                act['context'] = str(
                        self.screen.current_model.expr_eval(
                            act['context'], check_load=False))
        data = {
            'model': self.screen.name,
            'id': obj_id,
            'ids': [obj_id],
        }
        value = Action._exec_action(act, self.window, data, {})
        if atype in ('print', 'action'):
            if self.screen:
                self.screen.reload(writen=True)
        return value

    def __getitem__(self, name):
        return self.widgets[name][0]

    def destroy(self):
        for widget_name in self.widgets.keys():
            for widget in self.widgets[widget_name]:
                widget.widget.destroy()
            del self.widgets[widget_name]
        self.widget.destroy()
        del self.widget
        del self.widgets
        del self.screen
        del self.buttons

    def cancel(self):
        for widgets in self.widgets.values():
            for widget in widgets:
                widget.widget.cancel()

    def set_value(self):
        model = self.screen.current_model
        if model:
            for widgets in self.widgets.values():
                for widget in widgets:
                    widget.set_value(model)

    def sel_ids_get(self):
        if self.screen.current_model:
            return [self.screen.current_model.id]
        return []

    def sel_models_get(self):
        if self.screen.current_model:
            return [self.screen.current_model]
        return []

    def reset(self):
        model = self.screen.current_model
        for name, widgets in self.widgets.items():
            for widget in widgets:
                widget.reset(model)

    def signal_record_changed(self, *args):
        for widgets in self.widgets.values():
            for widget in widgets:
                if hasattr(widget.widget, 'screen'):
                    for view in widget.widget.screen.views:
                        view.signal_record_changed(*args)

    def display(self):
        model = self.screen.current_model
        if model:
            # Force to set mfields in model
            for field in model.mgroup.fields:
                model[field].get(model, check_load=False)
        for widgets in self.widgets.values():
            for widget in widgets:
                widget.display(model)
        for button in self.buttons:
            button.state_set(model)
        return True

    def set_cursor(self, new=False, reset_view=True):
        if reset_view:
            for notebook in self.notebooks:
                notebook.set_current_page(0)
            if self.cursor_widget in self.widgets:
                self.widgets[self.cursor_widget][0].widget.grab_focus()
        model = self.screen.current_model
        position = 0
        for widgets in self.widgets:
            position += len(widgets)
        focus_widget = None
        if model:
            for widgets in self.widgets.values():
                for widget in widgets:
                    modelfield = model.mgroup.mfields.get(widget.widget_name, None)
                    if not modelfield:
                        continue
                    if not modelfield.get_state_attrs(model).get('valid', True):
                        if widget.widget.position > position:
                            continue
                        position = widget.widget.position
                        focus_widget = widget
        if focus_widget:
            for notebook in self.notebooks:
                for i in range(notebook.get_n_pages()):
                    child = notebook.get_nth_page(i)
                    if focus_widget.widget.widget.is_ancestor(child):
                        notebook.set_current_page(i)
            focus_widget.widget.grab_focus()
