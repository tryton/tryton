# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import gtk
import gettext

from tryton.common import get_toplevel_window, IconFactory
from tryton.common.underline import set_underline
from tryton.config import TRYTON_ICON
from tryton.gui import Main

_ = gettext.gettext


class Shortcuts(object):
    'Shortcuts window'

    def __init__(self):
        self.parent = get_toplevel_window()
        self.dialog = gtk.Dialog(_('Keyboard Shortcuts'), self.parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT
            | gtk.WIN_POS_CENTER_ON_PARENT | gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
        Main().add_window(self.dialog)
        ok_button = self.dialog.add_button(
            set_underline(_("OK")), gtk.RESPONSE_OK)
        ok_button.set_image(IconFactory.get_image(
                'tryton-ok', gtk.ICON_SIZE_BUTTON))
        ok_button.set_always_show_image(True)
        self.dialog.set_icon(TRYTON_ICON)
        self.dialog.set_default_response(gtk.RESPONSE_OK)
        notebook = gtk.Notebook()
        self.dialog.vbox.pack_start(notebook)

        shortcuts = [
            (_('Text Entries Shortcuts'),),
            ('<Ctrl> + X', _('Cut selected text')),
            ('<Ctrl> + C', _('Copy selected text')),
            ('<Ctrl> + V', _('Paste copied text')),
            ('<Tab>', _('Next widget')),
            ('<Shift> + <Tab>', _('Previous widget')),
            (_('Relation Entries Shortcuts'),),
            ('<F3>', _('Create new relation')),
            ('<F2>', _('Open/Search relation')),
            (_('List Entries Shortcuts'),),
            ('<F3>', _('Create new line')),
            ('<F2>', _('Open relation')),
            ('<Del>', _('Mark line for deletion')),
            ('<Ins>', _('Unmark line for deletion')),
            ]
        notebook.append_page(self._fill_table(shortcuts),
                gtk.Label(_('Edition Widgets')))

        shortcuts = [
            (_('Move Cursor'),),
            ('<Right>', _('Move to right')),
            ('<Left>', _('Move to left')),
            ('<Up>', _('Move up')),
            ('<Down>', _('Move down')),
            ('<Page Up>', _('Move up of one page')),
            ('<Page Down>', _('Move down of one page')),
            ('<Home>', _('Move to top')),
            ('<End>', _('Move to bottom')),
            ('<Backspace>', _('Move to parent')),
            (_('Selection'),),
            ('<Ctrl> + a', _('Select all')),
            ('<Ctrl> + /', _('Select all')),
            ('<Shift> + <Ctrl> + a', _('Unselect all')),
            ('<Shift> + <Ctrl> + /', _('Unselect all')),
            ('<Backspace>', _('Select parent')),
            ('<Space>', _('Select/Activate current row')),
            ('<Shift> + <Space>', _('Select/Activate current row')),
            ('<Return>', _('Select/Activate current row')),
            ('<Enter>', _('Select/Activate current row')),
            ('<Ctrl> + <Space>', _('Toggle selection')),
            (_('Expand/Collapse'),),
            ('+', _('Expand row')),
            ('-', _('Collapse row')),
            ('<Space>', _('Toggle row')),
            ('<Shift> + <Left>', _('Collapse all rows')),
            ('<Shift> + <Right>', _('Expand all rows')),
            ]
        notebook.append_page(self._fill_table(shortcuts),
                gtk.Label(_('Tree view')))

        self.dialog.show_all()

    def _fill_table(self, shortcuts):
        table = gtk.Table(len(shortcuts), 2)
        table.set_col_spacings(15)
        table.set_row_spacings(3)
        table.set_border_width(8)

        i = 0
        for shortcut in shortcuts:
            if len(shortcut) == 1:
                label = gtk.Label()
                if '\n' not in shortcut[0]:
                    label.set_markup('<b>' + shortcut[0] + '</b>')
                else:
                    label.set_text(shortcut[0])
                    label.set_alignment(0, 0.5)
                label.set_padding(2, 0)
                table.attach(label, 0, 2, i, i + 1,
                        yoptions=False, xoptions=gtk.FILL)
            elif len(shortcut) == 2:
                label = gtk.Label()
                label.set_text(shortcut[0])
                label.set_alignment(0, 0.5)
                table.attach(label, 0, 1, i, i + 1,
                        yoptions=False, xoptions=gtk.FILL)
                label = gtk.Label()
                label.set_text(shortcut[1])
                label.set_alignment(0, 0.5)
                table.attach(label, 1, 2, i, i + 1,
                        yoptions=False, xoptions=gtk.FILL)
            i += 1
        return table

    def run(self):
        'Run the window'
        self.dialog.run()
        self.parent.present()
        self.dialog.destroy()
