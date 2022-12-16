#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gobject
import gtk
import tryton.rpc as rpc
import locale
from interface import ParserView
from tryton.action import Action
from tryton.common import message
import gettext
import tryton.common as common
from tryton.config import CONFIG
from tryton.common.cellrendererbutton import CellRendererButton
from tryton.common.cellrenderertoggle import CellRendererToggle
from tryton.pyson import PYSONEncoder
import os

_ = gettext.gettext


class AdaptModelGroup(gtk.GenericTreeModel):

    def __init__(self, group):
        super(AdaptModelGroup, self).__init__()
        self.group = group
        self.last_sort = None
        self.sort_asc = True
        self.set_property('leak_references', False)

    def added(self, modellist, position):
        if modellist is self.group:
            model = self.group[position]
            self.row_inserted(self.on_get_path(model),
                    self.get_iter(self.on_get_path(model)))

    def cancel(self):
        pass

    def removed(self, lst, position):
        self.row_deleted(position)
        self.invalidate_iters()

    def append(self, model):
        self.group.add(model)

    def prepend(self, model):
        self.group.add(model, 0)

    def remove(self, iter):
        idx = self.get_path(iter)[0]
        self.group.remove(self.group[idx])
        self.invalidate_iters()

    def move(self, path, position):
        idx = path[0]
        self.group.move(self.group[idx], position)

    def sort(self, ids):
        ids2pos = {}
        pos = 0
        new_order = []
        for record in self.group:
            ids2pos[record.id] = pos
            new_order.append(pos)
            pos += 1
        pos = 0
        for obj_id in ids:
            try:
                old_pos = ids2pos[obj_id]
                if old_pos != pos:
                    new_order[old_pos] = pos
                pos += 1
            except:
                continue
        self.group.sort(lambda x, y: \
                cmp(new_order[ids2pos[x.id]], new_order[ids2pos[y.id]]))
        prev = None
        for record in self.group:
            if prev:
                prev.next[id(self.group)] = record
            prev = record
        if prev:
            prev.next[id(self.group)] = None
        self.rows_reordered(None, None, new_order)

    def __len__(self):
        return len(self.group)

    def on_get_flags(self):
        return gtk.TREE_MODEL_LIST_ONLY

    def on_get_n_columns(self):
        return 1

    def on_get_column_type(self, index):
        return gobject.TYPE_PYOBJECT

    def on_get_path(self, iter):
        if iter in self.group:
            return self.group.index(iter)
        else:
            return 0

    def on_get_iter(self, path):
        if isinstance(path, tuple):
            path = path[0]
        if self.group is not None:
            if path < len(self.group):
                return self.group[path]
            else:
                return None
        else:
            return None

    def on_get_value(self, node, column):
        assert column == 0
        return node

    def on_iter_next(self, node):
        try:
            return node.next[id(self.group)]
        except IndexError:
            return None

    def on_iter_has_child(self, node):
        return False

    def on_iter_children(self, node):
        return None

    def on_iter_n_children(self, node):
        if node is None:
            return len(self.group)
        return 0

    def on_iter_nth_child(self, node, nth):
        if node is None and self.group is not None:
            return self.on_get_iter(0)
        return None

    def on_iter_parent(self, node):
        return None


class ViewList(ParserView):

    def __init__(self, window, screen, widget, children=None, buttons=None,
            toolbar=None, notebooks=None, cursor_widget=None):
        super(ViewList, self).__init__(window, screen, widget, children,
                buttons, toolbar, notebooks, cursor_widget)
        self.store = None
        self.view_type = 'tree'
        self.widget = gtk.VBox()
        self.widget_tree = widget
        scroll = gtk.ScrolledWindow()
        scroll.add(self.widget_tree)
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        viewport.add(scroll)
        self.widget.pack_start(viewport, expand=True, fill=True)
        self.widget_tree.screen = screen
        self.reload = False
        self.children = children

        if children:
            hbox = gtk.HBox()
            self.widget.pack_start(hbox, expand=False, fill=False, padding=2)
            keys = children.keys()
            keys.sort()
            for i in keys:
                hbox2 = gtk.HBox()
                hbox2.pack_start(children[i][1], expand=True, fill=False)
                hbox2.pack_start(children[i][2], expand=True, fill=False)
                hbox.pack_start(hbox2, expand=False, fill=False, padding=12)
            hbox.show_all()

        if toolbar and not CONFIG['client.modepda'] \
                and (toolbar['print'] or toolbar['action']):
            hbox = gtk.HBox()
            self.widget.pack_start(hbox, expand=False, fill=False)

            gtktoolbar = gtk.Toolbar()
            gtktoolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
            gtktoolbar.set_style(gtk.TOOLBAR_BOTH)
            hbox.pack_start(gtktoolbar, True, True)

            for icontype in ('print', 'action'):
                if not toolbar[icontype]:
                    continue

                for tool in toolbar[icontype]:
                    iconstock = {
                        'print': 'tryton-print',
                        'action': 'tryton-executable',
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
                            tool2 = tool.copy()
                            if mtype == 'print':
                                tool2['direct_print'] = True
                                tool2['email_print'] = False
                            else:
                                tool2['direct_print'] = False
                                tool2['email_print'] = True
                            menuitem.connect('activate', self._sig_clicked,
                                    tool2, icontype)
                            menu.add(menuitem)
                            menuitem.show()
                        tbutton.set_menu(menu)
            hbox.show_all()

        self.display()

        self.widget_tree.connect('button-press-event', self.__button_press)
        self.widget_tree.connect_after('row-activated', self.__sig_switch)
        if hasattr(self.widget_tree, 'set_rubber_banding'):
            self.widget_tree.set_rubber_banding(True)
        selection = self.widget_tree.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)
        selection.connect('changed', self.__select_changed)

        # Disable DnD on mac until it is fully supported
        if self.widget_tree.sequence \
                and not (os.name == 'mac' \
                    or (hasattr(os, 'uname') and os.uname()[0] == 'Darwin')):
            self.widget_tree.enable_model_drag_source(gtk.gdk.BUTTON1_MASK,
                    [('MY_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0),],
                    gtk.gdk.ACTION_MOVE)
            self.widget_tree.drag_source_set(gtk.gdk.BUTTON1_MASK | gtk.gdk.BUTTON3_MASK,
                    [('MY_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0),],
                    gtk.gdk.ACTION_MOVE)
            self.widget_tree.enable_model_drag_dest(
                    [('MY_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0),],
                    gtk.gdk.ACTION_MOVE)

            self.widget_tree.connect('drag-drop', self.drag_drop)
            self.widget_tree.connect("drag-data-get", self.drag_data_get)
            self.widget_tree.connect('drag-data-received', self.drag_data_received)
            self.widget_tree.connect('drag-data-delete', self.drag_data_delete)

        self.widget_tree.connect('key_press_event', self.on_keypress)

    def _sig_clicked(self, widget, action, atype):
        return self._action(action, atype)

    def _action(self, action, atype):
        act = action.copy()
        obj_ids = self.screen.sel_ids_get()
        obj_id = self.screen.id_get()
        if not obj_ids or not obj_id:
            message(_('No record selected!'), self.window)
            return False
        email = {}
        if action.get('email'):
            email = self.screen.current_record.expr_eval(action['email'])
            if not email:
                email = {}
        email['subject'] = action['name'].replace('_', '')
        act['email'] = email
        data = {
            'model': self.screen.model_name,
            'id': obj_id,
            'ids': obj_ids,
        }
        value = Action._exec_action(act, self.window, data, {})
        if self.screen:
            self.screen.reload(writen=True)
        return value


    def on_keypress(self, widget, event):
        if event.keyval == gtk.keysyms.c and event.state & gtk.gdk.CONTROL_MASK:
            self.on_copy()
            return False
        if event.keyval in (gtk.keysyms.Down, gtk.keysyms.Up):
            path, column = self.widget_tree.get_cursor()
            if not path:
                return False
            store = self.widget_tree.get_model()
            if event.keyval == gtk.keysyms.Down:
                if path[0] ==  len(store) - 1:
                    return True
            elif event.keyval == gtk.keysyms.Up:
                if path[0] == 0:
                    return True

    def on_copy(self):
        clipboard = self.widget_tree.get_clipboard(gtk.gdk.SELECTION_CLIPBOARD)
        targets = [
            ('STRING', 0, 0),
            ('TEXT', 0, 1),
            ('COMPOUND_TEXT', 0, 2),
            ('UTF8_STRING', 0, 3)
        ]
        selection = self.widget_tree.get_selection()
        # Set to clipboard directly if not too much selected rows
        # to speed up paste
        # Don't use set_with_data on mac see:
        # http://bugzilla.gnome.org/show_bug.cgi?id=508601
        if selection.count_selected_rows() < 100 \
                or os.name == 'mac' \
                or (hasattr(os, 'uname') and os.uname()[0] == 'Darwin'):
            data = []
            selection.selected_foreach(self.copy_foreach, data)
            clipboard.set_text('\n'.join(data))
        else:
            clipboard.set_with_data(targets, self.copy_get_func,
                    self.copy_clear_func, selection)

    def copy_foreach(self, treemodel, path,iter, data):
        record = treemodel.get_value(iter, 0)
        values = []
        for col in self.widget_tree.get_columns():
            if not col.get_visible() or not col.name:
                continue
            cell = self.widget_tree.cells[col.name]
            values.append('"' + str(cell.get_textual_value(record)) + '"')
        data.append('\t'.join(values))
        return

    def copy_get_func(self, clipboard, selectiondata, info, selection):
        data = []
        selection.selected_foreach(self.copy_foreach, data)
        clipboard.set_text('\n'.join(data))
        del data
        return

    def copy_clear_func(self, clipboard, selection):
        del selection
        return

    def drag_drop(self, treeview, context, x, y, time):
        treeview.emit_stop_by_name('drag-drop')
        treeview.drag_get_data(context, context.targets[-1], time)
        return True

    def drag_data_get(self, treeview, context, selection, target_id,
            etime):
        treeview.emit_stop_by_name('drag-data-get')
        def _func_sel_get(store, path, iter, data):
            data.append(path)
        data = []
        treeselection = treeview.get_selection()
        treeselection.selected_foreach(_func_sel_get, data)
        if not data:
            return
        data = str(data[0])
        selection.set(selection.target, 8, data)

    def drag_data_received(self, treeview, context, x, y, selection,
            info, etime):
        treeview.emit_stop_by_name('drag-data-received')
        if treeview.sequence:
            field = self.screen.group.fields[treeview.sequence]
            for record in self.screen.group:
                if field.get_state_attrs(
                        record).get('readonly', False):
                    return
        if not selection.data:
            return
        model = treeview.get_model()
        data = common.safe_eval(selection.data)
        drop_info = treeview.get_dest_row_at_pos(x, y)
        if drop_info:
            path, position = drop_info
            idx = path[0]
            if position in (gtk.TREE_VIEW_DROP_BEFORE,
                    gtk.TREE_VIEW_DROP_INTO_OR_BEFORE):
                model.move(data, idx)
            else:
                model.move(data, idx + 1)
        context.drop_finish(False, etime)
        if treeview.sequence:
            self.screen.group.set_sequence(field=treeview.sequence)

    def drag_data_delete(self, treeview, context):
        treeview.emit_stop_by_name('drag-data-delete')

    def __button_press(self, treeview, event):
        if event.button == 3:
            path = treeview.get_path_at_pos(int(event.x), int(event.y))
            selection = treeview.get_selection()
            if selection.get_mode() == gtk.SELECTION_SINGLE:
                model = selection.get_selected()[0]
            elif selection.get_mode() == gtk.SELECTION_MULTIPLE:
                model = selection.get_selected_rows()[0]
            if (not path) or not path[0]:
                return False
            record = model.group[path[0][0]]

            if hasattr(path[1], '_type') and path[1]._type == 'many2one':
                value = record[path[1].name].get(record)
                args = ('model', 'ir.action.keyword', 'get_keyword',
                        'form_relate', (self.screen.group.fields[
                            path[1].name].attrs['relation'], 0), rpc.CONTEXT)
                try:
                    relates = rpc.execute(*args)
                except Exception, exception:
                    relates = common.process_exception(exception, self.window,
                            *args)
                    if not relates:
                        return False
                menu_entries = []
                menu_entries.append((None, None, None))
                menu_entries.append((_('Actions'),
                    lambda x: self.click_and_action(
                        'form_action', value, path), 0))
                menu_entries.append((_('Reports'),
                    lambda x: self.click_and_action(
                        'form_print', value, path), 0))
                menu_entries.append((None, None, None))
                for relate in relates:
                    relate['string'] = relate['name']
                    fct = lambda action: lambda x: \
                            self.click_and_relate(action, value, path)
                    menu_entries.append(
                            ('... ' + relate['name'], fct(relate), 0))
                menu = gtk.Menu()
                for stock_id, callback, sensitivity in menu_entries:
                    if stock_id:
                        item = gtk.ImageMenuItem(stock_id)
                        if callback:
                            item.connect('activate', callback)
                        item.set_sensitive(bool(sensitivity or value))
                    else:
                        item = gtk.SeparatorMenuItem()
                    item.show()
                    menu.append(item)
                menu.popup(None, None, None, event.button, event.time)
        return False

    def click_and_relate(self, action, value, path):
        data = {}
        context = {}
        act = action.copy()
        if not(value):
            message(_('You must select a record to use the relation!'),
                    self.window)
            return False
        from tryton.gui.window.view_form.screen import Screen
        screen = Screen(self.screen.group.fields[
            path[1].name].attrs['relation'], self.window)
        screen.load([value])
        encoder = PYSONEncoder()
        act['domain'] = encoder.encode(screen.current_record.expr_eval(
            act.get('domain', []), check_load=False))
        act['context'] = encoder.encode(screen.current_record.expr_eval(
            act.get('context', {}), check_load=False))
        data['model'] = self.screen.model_name
        data['id'] = value
        data['ids'] = [value]
        return Action._exec_action(act, self.window, data, context)

    def click_and_action(self, atype, value, path):
        return Action.exec_keyword(atype, self.window, {
            'model': self.screen.group.fields[
                path[1].name].attrs['relation'],
            'id': value or False,
            'ids': [value],
            }, alwaysask=True)

    def group_list_changed(self, group, signal):
        if self.store is not None:
            if signal[0] == 'record-added':
                self.store.added(group, signal[1])
            elif signal[0] == 'record-removed':
                self.store.removed(group, signal[1])
        self.display()

    def cancel(self):
        pass

    def __str__(self):
        return 'ViewList (%s)' % self.screen.model_name

    def __getitem__(self, name):
        return None

    def destroy(self):
        if CONFIG['client.save_width_height']:
            fields = {}
            last_col = None
            for col in self.widget_tree.get_columns():
                if col.get_visible():
                    last_col = col
                if not hasattr(col, 'name') or not hasattr(col, 'width'):
                    continue
                if col.get_width() != col.width and col.get_visible():
                    fields[col.name] = col.get_width()
            #Don't set width for last visible columns
            #as it depends of the screen size
            if last_col and last_col.name in fields:
                del fields[last_col.name]

            if fields and any(fields.itervalues()):
                try:
                    rpc.execute('model', 'ir.ui.view_tree_width', 'set_width',
                            self.screen.model_name, fields, rpc.CONTEXT)
                except:
                    pass
        self.widget_tree.destroy()
        del self.screen
        del self.widget_tree
        del self.widget

    def __sig_switch(self, treeview, path, column):
        if column._type == 'button':
            return
        self.screen.row_activate()

    def __select_changed(self, tree_sel):
        previous_record = self.screen.current_record

        if tree_sel.get_mode() == gtk.SELECTION_SINGLE:
            model, iter = tree_sel.get_selected()
            if iter:
                path = model.get_path(iter)[0]
                self.screen.current_record = model.group[path]

        elif tree_sel.get_mode() == gtk.SELECTION_MULTIPLE:
            model, paths = tree_sel.get_selected_rows()
            if paths:
                self.screen.current_record = model.group[paths[0][0]]

        if hasattr(self.widget_tree, 'editable') \
                and self.widget_tree.editable \
                and not self.screen.parent \
                and previous_record != self.screen.current_record:
            if previous_record and \
                    not (previous_record.validate() and previous_record.save()):
                self.screen.current_record = previous_record
                self.set_cursor()
                return True
        self.update_children()


    def set_value(self):
        if hasattr(self.widget_tree, 'editable') \
                and self.widget_tree.editable:
            self.widget_tree.set_value()

    def reset(self):
        pass

    # self.widget.set_model(self.store) could be removed if the store
    # has not changed -> better ergonomy. To test
    def display(self):
        if self.reload \
                or (not self.widget_tree.get_model()) \
                    or self.screen.group != \
                        self.widget_tree.get_model().group:
            self.store = AdaptModelGroup(self.screen.group)
            self.widget_tree.set_model(self.store)
        self.reload = False
        if not self.screen.current_record:
            # Should find a simpler solution to do something like
            #self.widget.set_cursor(None,None,False)
            if self.store:
                self.widget_tree.set_model(self.store)
        self.widget_tree.queue_draw()
        if hasattr(self.widget_tree, 'editable') \
                and self.widget_tree.editable:
            self.set_state()
        self.update_children()

    def set_state(self):
        record = self.screen.current_record
        if record:
            for field in record.group.fields:
                field = record.group.fields.get(field, None)
                if field:
                    field.state_set(record)

    def update_children(self):
        ids = self.sel_ids_get()
        for child in self.children:
            value = 0.0
            value_selected = 0.0
            loaded = True
            for record in self.screen.group:
                if not record.loaded:
                    loaded = False
                    break
                if record.id in ids or not ids:
                    if not value_selected:
                        value_selected = record.fields_get()[self.children[child][0]]\
                                .get(record, check_load=False)
                    else:
                        value_selected += record.fields_get()[self.children[child][0]]\
                                .get(record, check_load=False)
                if not value:
                    value = record.fields_get()[self.children[child][0]]\
                            .get(record, check_load=False)
                else:
                    value += record.fields_get()[self.children[child][0]]\
                            .get(record, check_load=False)

            if loaded:
                label_str = locale.format('%.' + str(self.children[child][3]) + 'f',
                        value_selected, True)
                label_str += ' / '
                label_str += locale.format('%.' + str(self.children[child][3]) + 'f',
                        value, True)
            else:
                label_str = '-'
            self.children[child][2].set_text(label_str)

    def set_cursor(self, new=False, reset_view=True):
        self.widget_tree.grab_focus()
        if self.screen.current_record:
            path = self.store.on_get_path(self.screen.current_record)
            focus_column = None
            for column in self.widget_tree.get_columns():
                renderers = column.get_cell_renderers()
                if not renderers:
                    continue
                renderer = renderers[0]
                if isinstance(renderer, CellRendererToggle):
                    editable = renderer.get_property('activatable')
                elif isinstance(renderer,
                        (gtk.CellRendererProgress, CellRendererButton)):
                    editable = False
                else:
                    editable = renderer.get_property('editable')
                if column.get_visible() and editable:
                    focus_column = column
                    break
            self.widget_tree.scroll_to_cell(path, focus_column, use_align=False)
            self.widget_tree.set_cursor(path, focus_column, new)

    def sel_ids_get(self):
        def _func_sel_get(store, path, iter, ids):
            record = store.on_get_iter(path)
            if record and record.id > 0:
                ids.append(record.id)
        ids = []
        sel = self.widget_tree.get_selection()
        sel.selected_foreach(_func_sel_get, ids)
        return ids

    def selected_records(self):
        def _func_sel_get(store, path, iter, records):
            records.append(store.on_get_iter(path))
        records = []
        sel = self.widget_tree.get_selection()
        sel.selected_foreach(_func_sel_get, records)
        return records

    def unset_editable(self):
        self.widget_tree.editable = False
        for col in self.widget_tree.get_columns():
            for renderer in col.get_cell_renderers():
                if isinstance(renderer, CellRendererToggle):
                    renderer.set_property('activatable', False)
                elif isinstance(renderer,
                        (gtk.CellRendererProgress, CellRendererButton)):
                    pass
                else:
                    renderer.set_property('editable', False)
