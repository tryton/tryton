#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import parser
import gettext
from tryton.common.cellrendererbutton import CellRendererButton
from tryton.common.cellrenderertoggle import CellRendererToggle

_ = gettext.gettext


class EditableTreeView(gtk.TreeView):
    leaving_model_events = (gtk.keysyms.Up, gtk.keysyms.Down,
            gtk.keysyms.Return)
    leaving_events = leaving_model_events + (gtk.keysyms.Tab,
            gtk.keysyms.ISO_Left_Tab, gtk.keysyms.KP_Enter)

    def __init__(self, position):
        super(EditableTreeView, self).__init__()
        self.editable = position
        self.cells = {}

    def on_quit_cell(self, current_model, fieldname, value):
        modelfield = current_model[fieldname]
        if hasattr(modelfield, 'editabletree_entry'):
            del modelfield.editabletree_entry
        cell = self.cells[fieldname]

        # The value has not changed and is valid ... do nothing.
        if value == cell.get_textual_value(current_model) \
                and modelfield.validate(current_model):
            return

        try:
            real_value = cell.value_from_text(current_model, value)
            modelfield.set_client(current_model, real_value)
        except parser.UnsettableColumn:
            return

    def on_open_remote(self, current_model, fieldname, create, value):
        modelfield = current_model[fieldname]
        cell = self.cells[fieldname]
        if value != cell.get_textual_value(current_model) or not value:
            changed = True
        else:
            changed = False
        try:
            valid, value = cell.open_remote(current_model, create,
                    changed, value)
            if valid:
                modelfield.set_client(current_model, value)
        except NotImplementedError:
            pass
        return cell.get_textual_value(current_model)

    def on_create_line(self):
        model = self.get_model()
        if self.editable == 'top':
            method = model.prepend
        else:
            method = model.append
        ctx = self.screen.context.copy()
        if self.screen.current_model and self.screen.current_model.parent:
            ctx.update(self.screen.current_model.parent.expr_eval(
                self.screen.default_get))
        new_model = model.model_group.model_new(domain=self.screen.domain,
                context=ctx)
        res = method(new_model)
        return res

    def __next_column(self, col):
        cols = self.get_columns()
        current = cols.index(col)
        for i in range(len(cols)):
            idx = (current + i + 1) % len(cols)
            if not cols[idx].get_cell_renderers():
                continue
            renderer = cols[idx].get_cell_renderers()[0]
            if isinstance(renderer, CellRendererToggle):
                editable = renderer.get_property('activatable')
            elif isinstance(renderer,
                    (gtk.CellRendererProgress, CellRendererButton)):
                editable = False
            else:
                editable = renderer.get_property('editable')
            if cols[idx].get_visible() and editable:
                break
        return cols[idx]

    def __prev_column(self, col):
        cols = self.get_columns()
        current = cols.index(col)
        for i in range(len(cols)):
            idx = (current - (i + 1)) % len(cols)
            if not cols[idx].get_cell_renderers():
                continue
            renderer = cols[idx].get_cell_renderers()[0]
            if isinstance(renderer, CellRendererToggle):
                editable = renderer.get_property('activatable')
            elif isinstance(renderer,
                    (gtk.CellRendererProgress, CellRendererButton)):
                editable = False
            else:
                editable = renderer.get_property('editable')
            if cols[idx].get_visible() and editable:
                break
        return cols[idx]

    def set_cursor(self, path, focus_column=None, start_editing=False):
        self.grab_focus()
        if focus_column and (focus_column._type in ('boolean')):
            start_editing = False
        return super(EditableTreeView, self).set_cursor(path, focus_column,
                start_editing)

    def set_value(self):
        path, column = self.get_cursor()
        store = self.get_model()
        if not path or not column or not column.name:
            return True
        model = store.get_value(store.get_iter(path), 0)
        modelfield = model[column.name]
        if hasattr(modelfield, 'editabletree_entry'):
            entry = modelfield.editabletree_entry
            if isinstance(entry, gtk.Entry):
                txt = entry.get_text()
            else:
                txt = entry.get_active_text()
            self.on_quit_cell(model, column.name, txt)
        return True

    def on_keypressed(self, entry, event):
        path, column = self.get_cursor()
        store = self.get_model()
        model = store.get_value(store.get_iter(path), 0)

        leaving = False
        if event.keyval == gtk.keysyms.Right:
            if isinstance(entry, gtk.Entry):
                if entry.get_position() >= \
                        len(entry.get_text().decode('utf-8')) \
                        and not entry.get_selection_bounds():
                    leaving = True
            else:
                leaving = True
        elif event.keyval == gtk.keysyms.Left:
            if isinstance(entry, gtk.Entry):
                if entry.get_position() <= 0 \
                        and not entry.get_selection_bounds():
                    leaving = True
            else:
                leaving = True

        if event.keyval in self.leaving_events or leaving:
            if isinstance(entry, gtk.Entry):
                txt = entry.get_text()
            else:
                txt = entry.get_active_text()
            entry.disconnect(entry.editing_done_id)
            self.on_quit_cell(model, column.name, txt)
            entry.editing_done_id = entry.connect('editing_done',
                    self.on_editing_done)
        if event.keyval in self.leaving_model_events:
            if not model.validate():
                invalid_fields = model.invalid_fields
                col = None
                for col in self.get_columns():
                    if col.name in invalid_fields:
                        break
                self.set_cursor(path, col, True)
                if self.screen.form:
                    self.screen.form.message_info(
                            _('Warning; field "%s" is required!') % \
                                    invalid_fields[col.name])
                return True
            if self.screen.tree_saves:
                obj_id = model.save()
                if not obj_id:
                    return True
        if event.keyval in (gtk.keysyms.Tab, gtk.keysyms.KP_Enter) \
                or (event.keyval == gtk.keysyms.Right and leaving):
            new_col = self.__next_column(column)
            self.set_cursor(path, new_col, True)
        elif event.keyval == gtk.keysyms.ISO_Left_Tab \
                or (event.keyval == gtk.keysyms.Left and leaving):
            new_col = self.__prev_column(column)
            self.set_cursor(path, new_col, True)
        elif event.keyval == gtk.keysyms.Up:
            entry.disconnect(entry.editing_done_id)
            self._key_up(path, store, column)
            entry.editing_done_id = entry.connect('editing_done',
                    self.on_editing_done)
        elif event.keyval == gtk.keysyms.Down:
            entry.disconnect(entry.editing_done_id)
            self._key_down(path, store, column)
            entry.editing_done_id = entry.connect('editing_done',
                    self.on_editing_done)
        elif event.keyval in (gtk.keysyms.Return,):
            col = None
            for column in self.get_columns():
                renderer = column.get_cell_renderers()[0]
                if isinstance(renderer, CellRendererToggle):
                    editable = renderer.get_property('activatable')
                elif isinstance(renderer,
                        (gtk.CellRendererProgress, CellRendererButton)):
                    editable = False
                else:
                    editable = renderer.get_property('editable')
                if column.get_visible() and editable:
                    col = column
                    break
            entry.disconnect(entry.editing_done_id)
            if self.editable == 'top':
                new_path = self._key_up(path, store, col)
            else:
                new_path = self._key_down(path, store, column)
            entry.editing_done_id = entry.connect('editing_done',
                    self.on_editing_done)
        elif event.keyval == gtk.keysyms.Escape:
            if model.id < 0:
                store.remove(store.get_iter(path))
                self.screen.current_model = False
            if not path[0]:
                self.screen.current_model = False
            if path[0] == len(self.screen.models.models) \
                    and path[0]:
                path = (path[0] - 1,)
            self.screen.display()
            if len(self.screen.models.models):
                self.set_cursor(path, column, False)
        elif event.keyval in (gtk.keysyms.F3, gtk.keysyms.F2):
            if isinstance(entry, gtk.Entry):
                value = entry.get_text()
            else:
                value = entry.get_active_text()
            entry.disconnect(entry.editing_done_id)
            newval = self.on_open_remote(model, column.name,
                                create=(event.keyval==gtk.keysyms.F3),
                                value=value)
            if isinstance(entry, gtk.Entry):
                entry.set_text(newval)
            else:
                entry.set_active_text(newval)
            entry.editing_done_id = entry.connect('editing_done',
                    self.on_editing_done)
            self.set_cursor(path, column, True)
        else:
            modelfield = model[column.name]
            if isinstance(entry, gtk.Entry):
                entry.set_max_length(int(modelfield.attrs.get('size', 0)))
            # store in the model the entry widget to get the value in set_value
            modelfield.editabletree_entry = entry
            model.modified = True
            model.modified_fields.setdefault(column.name)
            return False

        return True

    def _key_down(self, path, store, column):
        if path[0] == len(store) - 1 and self.editable == 'bottom':
            self.on_create_line()
        new_path = (path[0] + 1) % len(store)
        self.set_cursor(new_path, column, True)
        self.scroll_to_cell(new_path)
        return new_path

    def _key_up(self, path, store, column):
        if path[0] == 0 and self.editable == 'top':
            self.on_create_line()
            new_path = 0
        else:
            new_path = (path[0] - 1) % len(store)
        self.set_cursor(new_path, column, True)
        self.scroll_to_cell(new_path)
        return new_path

    def on_editing_done(self, entry):
        path, column = self.get_cursor()
        if not path:
            return True
        store = self.get_model()
        model = store.get_value(store.get_iter(path), 0)
        if isinstance(entry, gtk.Entry):
            self.on_quit_cell(model, column.name, entry.get_text())
        elif isinstance(entry, gtk.ComboBoxEntry):
            self.on_quit_cell(model, column.name, entry.get_active_text())
