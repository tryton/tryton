# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk

import tryton.common as common


class NoModal(object):

    def __init__(self):
        self.parent = common.get_toplevel_window()
        self.sensible_widget = common.get_sensible_widget(self.parent)
        self.page = None
        self.parent_focus = []
        focus = self.parent.get_focus()
        while focus:
            self.parent_focus.append(focus)
            focus = focus.get_parent()

    def register(self):
        from tryton.gui.main import Main
        main = Main.get_main()
        self.page = main.get_page()
        if not self.page:
            self.page = main
        self.page.dialogs.append(self)
        self.sensible_widget.props.sensitive = False

    def destroy(self):
        self.page.dialogs.remove(self)
        # Test if the parent is not already destroyed
        if self.parent not in gtk.window_list_toplevels():
            return
        self.parent.present()
        self.sensible_widget.props.sensitive = True
        for focus in self.parent_focus:
            if focus and focus.is_ancestor(self.parent):
                focus.grab_focus()
                break
