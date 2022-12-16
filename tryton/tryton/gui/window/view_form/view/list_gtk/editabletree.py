# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext
from itertools import islice, cycle, chain

from gi.repository import Gdk, GLib, Gtk

from tryton.common import MODELACCESS
from tryton.common.datetime_ import Date, Time

_ = gettext.gettext


def focusable_cells(column, editable=True):
    for cell in column.get_cells():
        if (not editable
                or (isinstance(cell, (
                            Gtk.CellRendererText,
                            Gtk.CellRendererCombo))
                    and cell.get_property('editable'))
                or (isinstance(cell, Gtk.CellRendererToggle)
                    and cell.get_property('activatable'))):
            yield cell


class TreeView(Gtk.TreeView):
    display_counter = 0

    def __init__(self, view):
        super(TreeView, self).__init__()
        self.view = view

    def next_column(
            self, path, column=None, cell=None, editable=True, _sign=1):
        if cell:
            cells = list(focusable_cells(column, editable))
            if len(cells) > 1:
                idx = cells.index(cell) + _sign
                if 0 <= idx < len(cells):
                    return (column, cells[idx])
        columns = self.get_columns()
        if column is None:
            column = columns[-1 if _sign > 0 else 0]
        model = self.get_model()
        record = model.get_value(model.get_iter(path), 0)
        if _sign < 0:
            columns.reverse()
        current_idx = columns.index(column) + 1
        for column in islice(cycle(columns), current_idx,
                len(columns) + current_idx):
            if not column.name:
                continue
            widget = self.view.get_column_widget(column)
            field = record[column.name]
            field.state_set(record, states=('readonly', 'invisible'))
            invisible = field.get_state_attrs(record).get('invisible', False)
            if not column.get_visible():
                invisible = True
            if editable:
                readonly = widget.attrs.get('readonly',
                    field.get_state_attrs(record).get('readonly', False))
            else:
                readonly = False
            if not (invisible or readonly):
                cells = list(focusable_cells(column, editable))
                if cells:
                    cell = cells[0 if _sign > 0 else -1]
                else:
                    continue
                return (column, cell)
        return (None, None)

    def prev_column(self, path, column=None, cell=None, editable=True):
        return self.next_column(
            path, column=column, cell=cell, editable=editable, _sign=-1)


class EditableTreeView(TreeView):
    leaving_record_events = (
        Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_Return)
    leaving_events = leaving_record_events + (
        Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab, Gdk.KEY_KP_Enter)

    def on_quit_cell(
            self, current_record, column, renderer, value, callback=None):
        field = current_record[column.name]
        widget = self.view.get_column_widget(column)

        # The value has not changed and is valid ... do nothing.
        if value == widget.get_textual_value(current_record) \
                and field.validate(current_record):
            if callback:
                callback()
            return
        if widget.renderer != renderer:
            for widget in chain(widget.prefixes, widget.suffixes):
                if widget.renderer == renderer:
                    break
            else:
                raise ValueError("Unknown renderer")
        widget.value_from_text(current_record, value, callback=callback)

    def on_open_remote(self, current_record, column, create, value,
            entry=None, callback=None):
        widget = self.view.get_column_widget(column)
        if value != widget.get_textual_value(current_record) or not value:
            changed = True
        else:
            changed = False
        try:
            widget.open_remote(current_record, create, changed, value,
                callback=callback)
        except NotImplementedError:
            pass

    def on_create_line(self):
        access = MODELACCESS[self.view.screen.model_name]
        model = self.get_model()
        limit = (self.view.screen.size_limit is not None
            and (len(model) >= self.view.screen.size_limit >= 0))
        if not access['create'] or limit:
            return
        if self.view.screen.new_position == 0:
            method = model.prepend
        else:
            method = model.append
        new_record = model.group.new()
        res = method(new_record)
        sequence = self.view.attributes.get('sequence')
        if sequence:
            model.group.set_sequence(field=sequence)
        return res

    def set_cursor(
            self, path, focus_column=None, cell=None, start_editing=False):
        self.grab_focus()
        if focus_column:
            widget = self.view.get_column_widget(focus_column)
            if isinstance(widget.renderer, Gtk.CellRendererToggle):
                start_editing = False
        self.scroll_to_cell(path, focus_column, use_align=False)
        if cell:
            self.set_cursor_on_cell(path, focus_column, cell, start_editing)
        else:
            super(EditableTreeView, self).set_cursor(
                path, focus_column, start_editing)

    def set_value(self):
        path, column = self.get_cursor()
        if not path or not column or not column.name:
            return True
        for renderer in column.get_cells():
            if renderer.props.editing:
                widget = self.view.get_column_widget(column)
                self.on_editing_done(widget.editable, renderer)
        return True

    def on_keypressed(self, entry, event, renderer):
        path = self.get_cursor()[0]
        column = self.get_column_from_renderer(renderer)
        model = self.get_model()
        record = model.get_value(model.get_iter(path), 0)
        self.display_counter += 1  # Force a display

        leaving = False
        if event.keyval == Gdk.KEY_Right:
            if isinstance(entry, Gtk.Entry):
                if entry.get_position() >= \
                        len(entry.get_text()) \
                        and not entry.get_selection_bounds():
                    leaving = True
            else:
                leaving = True
        elif event.keyval == Gdk.KEY_Left:
            if isinstance(entry, Gtk.Entry):
                if entry.get_position() <= 0 \
                        and not entry.get_selection_bounds():
                    leaving = True
            else:
                leaving = True

        if event.keyval in self.leaving_events or leaving:
            if isinstance(entry, (Date, Time)):
                entry.activate()
                txt = entry.props.value
            elif isinstance(entry, Gtk.Entry):
                txt = entry.get_text()
            elif isinstance(entry, Gtk.ComboBox):
                active = entry.get_active()
                if active < 0:
                    txt = None
                else:
                    model = entry.get_model()
                    index = entry.get_property('entry-text-column')
                    txt = model[active][index]
            else:
                return True
            keyval = event.keyval
            entry.handler_block(entry.editing_done_id)

            def callback():
                entry.handler_unblock(entry.editing_done_id)
                if (keyval in [Gdk.KEY_Tab, Gdk.KEY_KP_Enter]
                        or (keyval == Gdk.KEY_Right and leaving)):
                    GLib.idle_add(self.set_cursor, path,
                        *self.next_column(path, column, renderer), True)
                elif (keyval == Gdk.KEY_ISO_Left_Tab
                        or (keyval == Gdk.KEY_Left and leaving)):
                    GLib.idle_add(self.set_cursor, path,
                        *self.prev_column(path, column, renderer), True)
                elif keyval in self.leaving_record_events:
                    fields = list(self.view.widgets.keys())
                    if not record.validate(fields):
                        invalid_fields = record.invalid_fields
                        col = None
                        for col in self.get_columns():
                            if col.name in invalid_fields:
                                break
                        GLib.idle_add(self.set_cursor, path, col, None, True)
                        return
                    if ((
                                self.view.screen.pre_validate
                                and not record.pre_validate())
                            or (not self.view.screen.parent
                                and not record.save())):
                        GLib.idle_add(
                            self.set_cursor, path, column, None, True)
                        return
                    entry.handler_block(entry.editing_done_id)
                    if keyval == Gdk.KEY_Up:
                        self._key_up(path, model, column)
                    elif keyval == Gdk.KEY_Down:
                        self._key_down(path, model, column)
                    elif keyval == Gdk.KEY_Return:
                        if self.view.screen.new_position == 0:
                            new_path = self._key_up(path, model)
                        else:
                            new_path = self._key_down(path, model)
                        GLib.idle_add(self.set_cursor, new_path,
                            *self.next_column(new_path), True)
                    entry.handler_unblock(entry.editing_done_id)
                else:
                    GLib.idle_add(self.set_cursor, path, column, None, True)
            self.on_quit_cell(record, column, renderer, txt, callback=callback)
            return True
        elif event.keyval in [Gdk.KEY_F3, Gdk.KEY_F2]:
            if isinstance(entry, Gtk.Entry):
                value = entry.get_text()
            elif isinstance(entry, Gtk.ComboBox):
                active = entry.get_active()
                if active < 0:
                    value = None
                else:
                    model = entry.get_model()
                    index = entry.get_property('entry-text-column')
                    value = model[active][index]
            else:
                return True
            entry.handler_block(entry.editing_done_id)

            def callback():
                widget = self.view.get_column_widget(column)
                value = widget.get_textual_value(record)
                if isinstance(entry, Gtk.Entry):
                    entry.set_text(value)
                else:
                    entry.set_active_text(value)
                entry.handler_unblock(entry.editing_done_id)
            self.on_open_remote(record, column,
                create=(event.keyval == Gdk.KEY_F3), value=value,
                callback=callback)
        else:
            field = record[column.name]
            if isinstance(entry, Gtk.Entry):
                entry.set_max_length(int(field.attrs.get('size', 0)))
            record.modified_fields.setdefault(column.name)
            return False

        return True

    def _key_down(self, path, model, column=None):
        if path[0] == len(model) - 1 and self.view.screen.new_position == -1:
            self.on_create_line()
        new_path = Gtk.TreePath((path[0] + 1) % len(model))
        if not column:
            column, cell = self.next_column(new_path)
        self.set_cursor(new_path, column, start_editing=True)
        self.scroll_to_cell(new_path)
        return new_path

    def _key_up(self, path, model, column=None):
        if path[0] == 0 and self.view.screen.new_position == 0:
            self.on_create_line()
            new_path = Gtk.TreePath(0)
        else:
            new_path = Gtk.TreePath((path[0] - 1) % len(model))
        if not column:
            column, cell = self.next_column(new_path)
        self.set_cursor(new_path, column, start_editing=True)
        self.scroll_to_cell(new_path)
        return new_path

    def on_editing_done(self, entry, renderer):
        path = self.get_cursor()[0]
        if not path:
            return True
        column = self.get_column_from_renderer(renderer)
        model = self.get_model()
        record = model.get_value(model.get_iter(path), 0)
        if isinstance(entry, (Date, Time)):
            entry.activate()
            text = entry.props.value
        elif isinstance(entry, Gtk.ComboBox):
            model = entry.get_model()
            iter_ = entry.get_active_iter()
            if iter_:
                text = model.get_value(iter_, entry.props.entry_text_column)
            else:
                text = ''
        else:
            text = entry.get_text()
        self.on_quit_cell(record, column, renderer, text)

    def get_column_from_renderer(self, renderer):
        for column in self.get_columns():
            for cell in column.get_cells():
                if cell == renderer:
                    return column
