#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.

import gtk
import gettext
from tryton.config import TRYTON_ICON

_ = gettext.gettext


class Shortcuts(object):
    'Shortcuts window'

    def __init__(self, parent):
        self.dialog = gtk.Dialog(_('Keyboard Shortcuts'), parent, gtk.DIALOG_MODAL
                | gtk.DIALOG_DESTROY_WITH_PARENT | gtk.WIN_POS_CENTER_ON_PARENT
                | gtk.gdk.WINDOW_TYPE_HINT_DIALOG,
                (gtk.STOCK_OK, gtk.RESPONSE_OK))
        self.parent = parent
        self.dialog.set_icon(TRYTON_ICON)
        self.dialog.set_has_separator(True)
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
                (_('Date/Datetime Entries Shortcuts'),),
                (_('''You can use special operators:
* + to increase the date
* - to decrease the date or clear
* = to set the date or the current date

Available variables are:
h for hours
d for days
w for weeks (only with +/-)
m for months
y for years

Examples:
"+21d" increase of 21 days the date
"=11m" set the date to the 11th month of the year
"-2w" decrease of 2 weeks the date'''),)
                ]
        notebook.append_page(self._fill_table(shortcuts),
                gtk.Label(_('Edition Widgets')))

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
            i +=1
        return table

    def run(self):
        'Run the window'
        self.dialog.run()
        self.parent.present()
        self.dialog.destroy()
