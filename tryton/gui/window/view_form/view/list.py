#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gobject
import gtk
import sys
try:
    import simplejson as json
except ImportError:
    import json
import locale
from interface import ParserView
from tryton.action import Action
from tryton.common import message
import gettext
from tryton.config import CONFIG
from tryton.common.cellrendererbutton import CellRendererButton
from tryton.common.cellrenderertoggle import CellRendererToggle
from tryton.common.cellrendererbinary import CellRendererBinary
from tryton.pyson import PYSONEncoder
from tryton.gui.window import Window
from tryton.common.popup_menu import populate
from tryton.common import RPCExecute, RPCException

_ = gettext.gettext


def path_convert_id2pos(model, id_path):
    "This function will transform a path of id into a path of position"
    group = model.group
    id_path = id_path[:]
    while id_path:
        current_id = id_path.pop(0)
        try:
            record = group.get(current_id)
            group = record.children_group(model.children_field,
                check_load=True)
        except (KeyError, AttributeError):
            return None
    return model.on_get_path(record)


class AdaptModelGroup(gtk.GenericTreeModel):

    def __init__(self, group, children_field=None):
        super(AdaptModelGroup, self).__init__()
        self.group = group
        self.last_sort = None
        self.sort_asc = True
        self.set_property('leak_references', False)
        self.children_field = children_field
        self.__removed = None  # XXX dirty hack to allow update of has_child

    def added(self, group, record):
        if (group is self.group
                and (record.group is self.group
                    or record.group.child_name == self.children_field)):
            path = self.on_get_path(record)
            iter_ = self.get_iter(path)
            self.row_inserted(path, iter_)
            if record.children_group(self.children_field):
                self.row_has_child_toggled(path, iter_)
            if (record.parent and
                    record.group is not self.group):
                path = self.on_get_path(record.parent)
                iter_ = self.get_iter(path)
                self.row_has_child_toggled(path, iter_)

    def cancel(self):
        pass

    def removed(self, group, record):
        if (group is self.group
                and (record.group is self.group
                    or record.group.child_name == self.children_field)):
            path = self.on_get_path(record)
            self.row_deleted(path)

    def append(self, model):
        self.group.add(model)

    def prepend(self, model):
        self.group.add(model, 0)

    def remove(self, iter_):
        record = self.get_value(iter_, 0)
        record.group.remove(record)
        self.invalidate_iters()

    def __move(self, record, path, offset=0):
        iter_ = self.get_iter(path)
        record_pos = self.get_value(iter_, 0)
        group = record_pos.group
        pos = group.index(record_pos) + offset
        if group is not record.group:
            prev_group = record.group
            record.group.remove(record, remove=True, force_remove=True)
            # Don't remove record from previous group
            # as the new parent will change the parent
            # This prevents concurrency conflict
            record.group.record_removed.remove(record)
            group.add(record)
            if not record.parent_name:
                record.modified_fields.setdefault(prev_group.parent_name)
                record.value[prev_group.parent_name] = False
            else:
                record.modified_fields.setdefault(record.parent_name)
        group.move(record, pos)

    def move_before(self, record, path):
        self.__move(record, path)

    def move_after(self, record, path):
        self.__move(record, path, 1)

    def move_into(self, record, path):
        iter_ = self.get_iter(path)
        parent = self.get_value(iter_, 0)
        group = parent.children_group(self.children_field, check_load=True)
        if group is not record.group:
            record.group.remove(record, remove=True, force_remove=True)
            # Don't remove record from previous group
            # as the new parent will change the parent
            # This prevents concurrency conflict
            record.group.record_removed.remove(record)
            group.add(record)
            record.modified_fields.setdefault(record.parent_name or 'id')
        group.move(record, 0)

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
            except KeyError:
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
        if not self.children_field:
            return gtk.TREE_MODEL_LIST_ONLY
        return 0

    def on_get_n_columns(self):
        # XXX
        return 1

    def on_get_column_type(self, index):
        # XXX
        return gobject.TYPE_PYOBJECT

    def on_get_path(self, iter_):
        if isinstance(iter_, tuple):
            return tuple(x[0] for x in iter_)
        else:
            path = []
            i = iter_
            while i:
                path.append(i.group.index(i))
                if i.group is self.group:
                    break
                i = i.parent
            path.reverse()
            return tuple(path)

    def on_get_tree_path(self, iter):
        return self.on_get_path(iter)

    def on_get_iter(self, path):
        group = self.group
        record = None
        for i in path:
            if group is None or i >= len(group):
                return None
            record = group[i]
            if not self.children_field:
                break
            group = record.children_group(self.children_field, check_load=True)
        return record

    def on_get_value(self, record, column):
        return record

    def on_iter_next(self, record):
        if record is None:
            return None
        return record.next.get(id(record.group))

    def on_iter_has_child(self, record):
        if record is None or not self.children_field:
            return False
        children = record.children_group(self.children_field)
        length = len(children)
        if self.__removed and self.__removed in children:
            length -= 1
        return bool(length)

    def on_iter_children(self, record):
        if record is None:
            return None
        if self.children_field:
            children = record.children_group(self.children_field)
            if children:
                return children[0]
        return None

    def on_iter_n_children(self, record):
        if record is None or not self.children_field:
            return len(self.group)
        return len(record.children_group(self.children_field))

    def on_iter_nth_child(self, record, nth):
        if record is None or not self.children_field:
            if nth < len(self.group):
                return self.group[nth]
            return None
        if nth < len(record.children_group(self.children_field)):
            return record.children_group(self.children_field)[nth]
        return None

    def on_iter_parent(self, record):
        if record is None:
            return None
        return record.parent


class ViewList(ParserView):

    def __init__(self, screen, widget, children=None, buttons=None,
            notebooks=None, cursor_widget=None, children_field=None):
        super(ViewList, self).__init__(screen, widget, children, buttons,
            notebooks, cursor_widget, children_field)
        self.store = None
        self.view_type = 'tree'

        vbox = gtk.VBox()
        scroll = gtk.ScrolledWindow()
        scroll.add(self.widget)
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_placement(gtk.CORNER_TOP_LEFT)
        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        viewport.add(scroll)
        self.widget_tree = self.widget

        vbox.pack_start(viewport, expand=True, fill=True)

        self.widget_tree.screen = screen

        self.widget = vbox
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

        self.display()

        self.widget_tree.connect('button-press-event', self.__button_press)
        self.widget_tree.connect_after('row-activated', self.__sig_switch)
        if hasattr(self.widget_tree, 'set_rubber_banding'):
            self.widget_tree.set_rubber_banding(True)
        selection = self.widget_tree.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)
        selection.connect('changed', self.__select_changed)

        dnd = False
        if self.children_field:
            children_field = self.widget_tree.cells.get(self.children_field)
            if children_field:
                parent_name = children_field.attrs.get('relation_field')
                dnd = parent_name in self.widget_tree.cells
        elif self.widget_tree.sequence:
            dnd = True
        # Disable DnD on mac until it is fully supported
        if sys.platform == 'darwin':
            dnd = False
        if screen.readonly:
            dnd = False
        if dnd:
            self.widget_tree.drag_source_set(
                gtk.gdk.BUTTON1_MASK | gtk.gdk.BUTTON3_MASK,
                [('MY_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0)],
                gtk.gdk.ACTION_MOVE)
            self.widget_tree.drag_dest_set(gtk.DEST_DEFAULT_ALL,
                [('MY_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0)],
                gtk.gdk.ACTION_MOVE)

            self.widget_tree.connect('drag-begin', self.drag_begin)
            self.widget_tree.connect('drag-motion', self.drag_motion)
            self.widget_tree.connect('drag-drop', self.drag_drop)
            self.widget_tree.connect("drag-data-get", self.drag_data_get)
            self.widget_tree.connect('drag-data-received',
                self.drag_data_received)
            self.widget_tree.connect('drag-data-delete', self.drag_data_delete)

        self.widget_tree.connect('key_press_event', self.on_keypress)
        if self.children_field:
            self.widget_tree.connect('test-expand-row', self.test_expand_row)
            self.widget_tree.set_expander_column(
                self.widget_tree.get_column(0))

    @property
    def modified(self):
        return False

    def get_fields(self):
        return [col.name for col in self.widget_tree.get_columns() if col.name]

    def on_keypress(self, widget, event):
        if (event.keyval == gtk.keysyms.c
                and event.state & gtk.gdk.CONTROL_MASK):
            self.on_copy()
            return False
        if event.keyval in (gtk.keysyms.Down, gtk.keysyms.Up):
            path, column = widget.get_cursor()
            if not path:
                return False
            model = widget.get_model()
            if event.keyval == gtk.keysyms.Down:
                test = True
                for i in xrange(len(path)):
                    iter_ = model.get_iter(path[0:i + 1])
                    if model.iter_next(iter_):
                        test = False
                if test:
                    iter_ = model.get_iter(path)
                    if (model.iter_has_child(iter_)
                            and widget.row_expanded(path)):
                        test = False
                return test
            elif event.keyval == gtk.keysyms.Up:
                if path == (0,):
                    return True
        if (event.keyval in (gtk.keysyms.Left, gtk.keysyms.Right)
                and self.children_field):
            selection = widget.get_selection()
            model, paths = selection.get_selected_rows()
            if event.keyval == gtk.keysyms.Left:
                if len(paths) == 1:
                    path, = paths
                    if not widget.row_expanded(path):
                        path = path[:-1]
                        if path:
                            selection.select_path(path)
                            widget.collapse_row(path)
                for path in paths:
                    widget.collapse_row(path)
            elif event.keyval == gtk.keysyms.Right:
                for path in paths:
                    widget.expand_row(path, False)

    def test_expand_row(self, widget, iter_, path):
        model = widget.get_model()
        iter_ = model.iter_children(iter_)
        if not iter_:
            return False
        fields = [col.name for col in self.widget_tree.get_columns()
                if col.name]
        while iter_:
            record = model.get_value(iter_, 0)
            if not record.get_loaded(fields):
                for field in fields:
                    record[field]
                    if record.exception:
                        return True
            iter_ = model.iter_next(iter_)
        return False

    def on_copy(self):
        for clipboard_type in (gtk.gdk.SELECTION_CLIPBOARD,
                gtk.gdk.SELECTION_PRIMARY):
            clipboard = self.widget_tree.get_clipboard(clipboard_type)
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
                    or sys.platform == 'darwin':
                data = []
                selection.selected_foreach(self.copy_foreach, data)
                clipboard.set_text('\n'.join(data))
            else:
                clipboard.set_with_data(targets, self.copy_get_func,
                        self.copy_clear_func, selection)

    def copy_foreach(self, treemodel, path, iter, data):
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

    def drag_begin(self, treeview, context):
        return True

    def drag_motion(self, treeview, context, x, y, time):
        try:
            treeview.set_drag_dest_row(*treeview.get_dest_row_at_pos(x, y))
        except TypeError:
            treeview.set_drag_dest_row(len(treeview.get_model()) - 1,
                gtk.TREE_VIEW_DROP_AFTER)
        if context.get_source_widget() == treeview:
            kind = gtk.gdk.ACTION_MOVE
        else:
            kind = gtk.gdk.ACTION_COPY
        context.drag_status(kind, time)
        return True

    def drag_drop(self, treeview, context, x, y, time):
        treeview.emit_stop_by_name('drag-drop')
        treeview.drag_get_data(context, context.targets[-1], time)
        return True

    def drag_data_get(self, treeview, context, selection, target_id,
            etime):
        treeview.emit_stop_by_name('drag-data-get')

        def _func_sel_get(store, path, iter_, data):
            value = store.get_value(iter_, 0)
            data.append(json.dumps(value.get_path(store.group)))
        data = []
        treeselection = treeview.get_selection()
        treeselection.selected_foreach(_func_sel_get, data)
        if not data:
            return
        data = str(data[0])
        selection.set(selection.target, 8, data)
        return True

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
        store = treeview.get_model()
        try:
            data = json.loads(selection.data)
        except ValueError:
            return
        record = store.group.get_by_path(data)
        record_path = store.on_get_path(record)
        drop_info = treeview.get_dest_row_at_pos(x, y)

        def check_recursion(from_, to):
            if not from_ or not to:
                return True
            if from_ == to:
                return False
            length = min(len(from_), len(to))
            if len(from_) < len(to) and from_[:length] == to[:length]:
                return False
            return True
        if drop_info:
            path, position = drop_info
            check_path = path
            if position in (gtk.TREE_VIEW_DROP_BEFORE,
                    gtk.TREE_VIEW_DROP_AFTER):
                check_path = path[:-1]
            if not check_recursion(record_path, check_path):
                return
            if position == gtk.TREE_VIEW_DROP_BEFORE:
                store.move_before(record, path)
            elif position == gtk.TREE_VIEW_DROP_AFTER:
                store.move_after(record, path)
            elif self.children_field:
                store.move_into(record, path)
        else:
            store.move_after(record, (len(store) - 1,))
        context.drop_finish(False, etime)
        if treeview.sequence:
            record.group.set_sequence(field=treeview.sequence)
        return True

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
            group = model.group
            record = group[path[0][0]]
            menu = gtk.Menu()
            menu.popup(None, None, None, event.button, event.time)

            def pop(menu, group, record):
                copy_item = gtk.ImageMenuItem('gtk-copy')
                copy_item.connect('activate', lambda x: self.on_copy())
                menu.append(copy_item)
                # Don't activate actions if parent is modified
                parent = record.parent if record else None
                while parent:
                    if parent.modified:
                        break
                    parent = parent.parent
                else:
                    populate(menu, group.model_name, record)
                for col in self.widget_tree.get_columns():
                    if not col.get_visible() or not col.name:
                        continue
                    field = group.fields[col.name]
                    model = None
                    if field.attrs['type'] == 'many2one':
                        model = field.attrs['relation']
                        record_id = field.get(record)
                    elif field.attrs['type'] == 'reference':
                        value = field.get(record)
                        if value:
                            model, record_id = value.split(',')
                            record_id = int(record_id)
                    if not model:
                        continue
                    label = field.attrs['string']
                    populate(menu, model, record_id, title=label)
                menu.show_all()
            # Delay filling of popup as it can take time
            gobject.idle_add(pop, menu, group, record)
        elif event.button == 2:
            event.button = 1
            event.state |= gtk.gdk.MOD1_MASK
            treeview.emit('button-press-event', event)
            return True
        return False

    def click_and_relate(self, action, value, path):
        data = {}
        context = {}
        act = action.copy()
        if not(value):
            message(_('You must select a record to use the relation!'))
            return False
        from tryton.gui.window.view_form.screen import Screen
        screen = Screen(self.screen.group.fields[
            path[1].name].attrs['relation'])
        screen.load([value])
        encoder = PYSONEncoder()
        act['domain'] = encoder.encode(screen.current_record.expr_eval(
            act.get('domain', []), check_load=False))
        act['context'] = encoder.encode(screen.current_record.expr_eval(
            act.get('context', {}), check_load=False))
        data['model'] = self.screen.model_name
        data['id'] = value
        data['ids'] = [value]
        return Action._exec_action(act, data, context)

    def click_and_action(self, atype, value, path):
        return Action.exec_keyword(atype, {
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
        return 'ViewList (%d)' % id(self)

    def __getitem__(self, name):
        return None

    def save_width_height(self):
        if not CONFIG['client.save_width_height']:
            return
        fields = {}
        last_col = None
        for col in self.widget_tree.get_columns():
            if col.get_visible():
                last_col = col
            if not hasattr(col, 'name') or not hasattr(col, 'width'):
                continue
            if (col.get_width() != col.width and col.get_visible()
                    and not col.get_expand()):
                fields[col.name] = col.get_width()
        #Don't set width for last visible columns
        #as it depends of the screen size
        if last_col and last_col.name in fields:
            del fields[last_col.name]

        if fields and any(fields.itervalues()):
            try:
                RPCExecute('model', 'ir.ui.view_tree_width', 'set_width',
                    self.screen.model_name, fields)
            except RPCException:
                pass

    def destroy(self):
        self.save_width_height()
        self.widget_tree.destroy()
        self.screen = None
        self.widget_tree = None
        self.widget = None

    def __sig_switch(self, treeview, path, column):
        if column._type == 'button':
            return
        allow_similar = False
        event = gtk.get_current_event()
        if (event.state & gtk.gdk.MOD1_MASK
                or event.state & gtk.gdk.SHIFT_MASK):
            allow_similar = True
        with Window(allow_similar=allow_similar):
            if not self.screen.row_activate() and self.children_field:
                if treeview.row_expanded(path):
                    treeview.collapse_row(path)
                else:
                    treeview.expand_row(path, False)

    def __select_changed(self, tree_sel):
        previous_record = self.screen.current_record
        if previous_record and previous_record not in previous_record.group:
            previous_record = None

        if tree_sel.get_mode() == gtk.SELECTION_SINGLE:
            model, iter_ = tree_sel.get_selected()
            if model and iter_:
                record = model.get_value(iter_, 0)
                self.screen.current_record = record
            else:
                self.screen.current_record = None

        elif tree_sel.get_mode() == gtk.SELECTION_MULTIPLE:
            model, paths = tree_sel.get_selected_rows()
            if model and paths:
                iter_ = model.get_iter(paths[0])
                record = model.get_value(iter_, 0)
                self.screen.current_record = record
            else:
                self.screen.current_record = None

        if hasattr(self.widget_tree, 'editable') \
                and self.widget_tree.editable \
                and not self.screen.parent \
                and previous_record != self.screen.current_record:
            if previous_record:
                def go_previous():
                    self.screen.current_record = previous_record
                    self.set_cursor()

                def save():
                    if not previous_record.destroyed:
                        if not previous_record.save():
                            go_previous()

                if not previous_record.validate(self.get_fields()):
                    go_previous()
                    return True
                # Delay the save to let GTK process the current event
                gobject.idle_add(save)
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
            self.store = AdaptModelGroup(self.screen.group,
                    self.children_field)
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
            value = 0
            value_selected = 0
            loaded = True
            child_fieldname = self.children[child][0]
            for record in self.screen.group:
                if not record.get_loaded([child_fieldname]):
                    loaded = False
                    break
                field_value = record.fields_get()[child_fieldname].get(record,
                    check_load=False)
                if field_value is not None:
                    value += field_value
                    if record.id in ids or not ids:
                        value_selected += field_value

            if loaded:
                label_str = locale.format(
                    '%.' + str(self.children[child][3]) + 'f', value_selected,
                    True)
                label_str += ' / '
                label_str += locale.format(
                    '%.' + str(self.children[child][3]) + 'f', value, True)
            else:
                label_str = '-'
            self.children[child][2].set_text(label_str)

    def set_cursor(self, new=False, reset_view=True):
        self.widget_tree.grab_focus()
        if self.screen.current_record:
            path = self.store.on_get_path(self.screen.current_record)
            if self.store.get_flags() & gtk.TREE_MODEL_LIST_ONLY:
                path = (path[0],)
            focus_column = None
            for column in self.widget_tree.get_columns():
                renderers = column.get_cell_renderers()
                if not renderers:
                    continue
                renderer = renderers[0]
                if isinstance(renderer, CellRendererToggle):
                    editable = renderer.get_property('activatable')
                elif isinstance(renderer,
                        (gtk.CellRendererProgress, CellRendererButton,
                            gtk.CellRendererPixbuf, CellRendererBinary)):
                    editable = False
                else:
                    editable = renderer.get_property('editable')
                if column.get_visible() and editable:
                    focus_column = column
                    break
            if path[:-1]:
                self.widget_tree.expand_to_path(path[:-1])
            self.widget_tree.scroll_to_cell(path, focus_column,
                use_align=False)
            self.widget_tree.set_cursor(path, focus_column, new)

    def sel_ids_get(self):
        def _func_sel_get(store, path, iter, ids):
            record = store.on_get_iter(path)
            if record and record.id >= 0:
                ids.append(record.id)
        ids = []
        sel = self.widget_tree.get_selection()
        if sel:
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
                        (gtk.CellRendererProgress, CellRendererButton,
                            gtk.CellRendererPixbuf)):
                    pass
                else:
                    renderer.set_property('editable', False)

    def get_expanded_paths(self, starting_path=None, starting_id_path=None):
        # Use id instead of position
        # because the position may change between load
        if not starting_path:
            starting_path = []
        if not starting_id_path:
            starting_id_path = []
        id_paths = []
        record = self.store.on_get_iter(starting_path)
        for path_idx in range(self.store.on_iter_n_children(record)):
            path = starting_path + [path_idx]
            expanded = self.widget_tree.row_expanded(tuple(path))
            if expanded:
                expanded_record = self.store.on_get_iter(path)
                id_path = starting_id_path + [expanded_record.id]
                id_paths.append(id_path)
                child_id_paths = self.get_expanded_paths(path, id_path)
                id_paths += child_id_paths
        return id_paths

    def expand_nodes(self, nodes):
        for node in nodes:
            expand_path = path_convert_id2pos(self.store, node)
            if expand_path:
                self.widget_tree.expand_to_path(expand_path)
