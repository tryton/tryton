#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gettext
from tryton.common import message, TRYTON_ICON
import tryton.rpc as rpc
import tryton.common as common
from interface import ParserView
from tryton.action import Action
from tryton.config import CONFIG
from tryton.pyson import PYSONEncoder

_ = gettext.gettext


class ViewForm(ParserView):

    def __init__(self, window, screen, widget, children=None,
            buttons=None, toolbar=None, notebooks=None, cursor_widget='',
            children_field=None):
        super(ViewForm, self).__init__(window, screen, widget, children,
                buttons, toolbar, notebooks, cursor_widget, children_field)
        self.view_type = 'form'

        for button in self.buttons:
            button.form = self

        self.widgets = children
        for widgets in self.widgets.itervalues():
            for widget in widgets:
                widget.view = self

        vbox = gtk.VBox()
        vp = gtk.Viewport()
        vp.set_shadow_type(gtk.SHADOW_NONE)
        vp.add(self.widget)
        scroll = gtk.ScrolledWindow()
        scroll.add(vp)
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_placement(gtk.CORNER_TOP_LEFT)
        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        viewport.add(scroll)
        if isinstance(self.screen.window, gtk.Dialog):
            width, height = self.widget.size_request()
            if self.screen.window:
                parent = self.screen.window.get_transient_for()
                if parent:
                    parent_width, parent_height = parent.get_size()
                    width = min(parent_width - 40, width)
                    height = min(parent_height - 80, height)
            vbox.set_size_request(width or -1, height or -1)
        vbox.pack_start(viewport, expand=True, fill=True)

        self.widget = vbox

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
                    if not tool['icon.rec_name']:
                        iconstock = {
                            'print': 'tryton-print',
                            'action': 'tryton-executable',
                            'relate': 'tryton-go-jump',
                        }.get(icontype)
                    else:
                        iconstock = tool['icon.rec_name']
                    common.ICONFACTORY.register_icon(iconstock)

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
            obj_id = self.screen.current_record \
                    and self.screen.current_record.id
            if obj_id < 0:
                if atype in ('print'):
                    message(_('You must save this record ' \
                        'to be able to use the print button!'), self.window)
                if atype in ('action'):
                    message(_('You must save this record ' \
                        'to be able to use the action button!'), self.window)
                return False
            email = {}
            if 'pyson_email' in action:
                email = self.screen.current_record.expr_eval(
                    action['pyson_email'])
                if not email:
                    email = {}
            email['subject'] = action['name'].replace('_', '')
            act['email'] = email
            self.screen.display()
        if atype == 'relate':
            obj_id = self.screen.current_record \
                    and self.screen.current_record.id
            if not obj_id:
                message(_('You must select a record ' \
                        'to be able to use the relate button !'), self.window)
                return False
            if obj_id < 0:
                message(_('You must save this record '
                    'to be able to use the relate button!'), self.window)
                return False
            encoder = PYSONEncoder()
            if 'pyson_domain' in act:
                act['pyson_domain'] = encoder.encode(
                        self.screen.current_record.expr_eval(
                                act['pyson_domain'], check_load=False))
            if 'pyson_context' in act:
                act['pyson_context'] = encoder.encode(
                        self.screen.current_record.expr_eval(
                            act['pyson_context'], check_load=False))
        data = {
            'model': self.screen.model_name,
            'id': obj_id,
            'ids': [obj_id],
        }
        value = Action._exec_action(act, self.window, data, {})
        if atype in ('print', 'action'):
            if self.screen:
                self.screen.reload(written=True)
        return value

    def __getitem__(self, name):
        return self.widgets[name][0]

    def destroy(self):
        for widget_name in self.widgets.keys():
            for widget in self.widgets[widget_name]:
                widget.destroy()
            del self.widgets[widget_name]
        self.widget.destroy()
        del self.widget
        del self.widgets
        del self.screen
        del self.buttons

    def cancel(self):
        for widgets in self.widgets.itervalues():
            for widget in widgets:
                widget.cancel()

    def set_value(self):
        record = self.screen.current_record
        if record:
            for name, widgets in self.widgets.iteritems():
                if name in record.group.fields:
                    field = record.group.fields[name]
                    for widget in widgets:
                        widget.set_value(record, field)

    def sel_ids_get(self):
        if self.screen.current_record:
            return [self.screen.current_record.id]
        return []

    def selected_records(self):
        if self.screen.current_record:
            return [self.screen.current_record]
        return []

    def reset(self):
        record = self.screen.current_record
        if record:
            for name, widgets in self.widgets.iteritems():
                field = record.group.fields.get(name)
                if field and 'valid' in field.get_state_attrs(record):
                    for widget in widgets:
                        field.get_state_attrs(record)['valid'] = True
                        widget.display(record, field)

    def signal_record_changed(self, *args):
        for widgets in self.widgets.itervalues():
            for widget in widgets:
                if hasattr(widget, 'screen'):
                    for view in widget.screen.views:
                        view.signal_record_changed(*args)

    def display(self):
        record = self.screen.current_record
        if record:
            # Force to set fields in record
            # Get first the lazy one to reduce number of requests
            fields = [(name, field.attrs.get('loading', 'eager'))
                    for name, field in record.group.fields.iteritems()]
            fields.sort(lambda x, y: cmp(y[1], x[1]))
            for field, _ in fields:
                record[field].get(record, check_load=False)
        for name, widgets in self.widgets.iteritems():
            field = None
            if record:
                field = record.group.fields.get(name)
            if field:
                field.state_set(record)
            for widget in widgets:
                widget.display(record, field)
        for button in self.buttons:
            button.state_set(record)
        return True

    def set_cursor(self, new=False, reset_view=True):
        if reset_view:
            for notebook in self.notebooks:
                notebook.set_current_page(0)
            if self.cursor_widget in self.widgets:
                self.widgets[self.cursor_widget][0].grab_focus()
        record = self.screen.current_record
        position = reduce(lambda x, y: x + len(y), self.widgets, 0)
        focus_widget = None
        if record:
            for name, widgets in self.widgets.iteritems():
                for widget in widgets:
                    field = record.group.fields.get(name)
                    if not field:
                        continue
                    if not field.get_state_attrs(record).get('valid', True):
                        if widget.position > position:
                            continue
                        position = widget.position
                        focus_widget = widget
        if focus_widget:
            for notebook in self.notebooks:
                for i in range(notebook.get_n_pages()):
                    child = notebook.get_nth_page(i)
                    if focus_widget.widget.is_ancestor(child):
                        notebook.set_current_page(i)
            focus_widget.grab_focus()
