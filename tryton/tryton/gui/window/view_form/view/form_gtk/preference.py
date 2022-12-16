# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
import gtk
import gettext
import tryton.common as common
from tryton.config import CONFIG, TRYTON_ICON
import tryton.rpc as rpc

_ = gettext.gettext


class WidgetFieldPreference(object):
    """
    Widget for field preferences.
    """
    def __init__(self, window, reset=False):
        self.parent = window
        self.dialog = gtk.Dialog(
                title=_("Field Preference"),
                parent=window,
                flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT
                | gtk.WIN_POS_CENTER_ON_PARENT)
        self.dialog.set_icon(TRYTON_ICON)
        self.dialog.add_button("gtk-cancel", gtk.RESPONSE_CANCEL)

        if not reset:
            button_ok = gtk.Button(_("Set"))
        else:
            button_ok = gtk.Button(_("Reset"))
        button_ok.set_flags(gtk.CAN_DEFAULT)
        button_ok.set_flags(gtk.HAS_DEFAULT)
        img_ok = gtk.Image()
        img_ok.set_from_stock("gtk-ok", gtk.ICON_SIZE_BUTTON)
        button_ok.set_image(img_ok)
        self.dialog.add_action_widget(button_ok, gtk.RESPONSE_OK)
        self.dialog.set_default_response(gtk.RESPONSE_OK)
        vbox = gtk.VBox()
        self.dialog.vbox.pack_start(vbox)
        table = gtk.Table(4, 2, False)
        table.set_border_width(4)
        table.set_row_spacings(4)
        table.set_col_spacings(4)
        vbox.pack_start(table, True, True, 0)

        label_field_name = gtk.Label(_("Field Name:"))
        label_field_name.set_justify(gtk.JUSTIFY_RIGHT)
        label_field_name.set_alignment(1, 0.5)
        table.attach(label_field_name, 0, 1, 0, 1)
        self.entry_field_name = gtk.Entry()
        self.entry_field_name.set_editable(False)
        style = self.entry_field_name.get_style()
        self.entry_field_name.modify_bg(gtk.STATE_NORMAL,
                style.bg[gtk.STATE_INSENSITIVE])
        self.entry_field_name.modify_base(gtk.STATE_NORMAL,
                style.base[gtk.STATE_INSENSITIVE])
        self.entry_field_name.modify_fg(gtk.STATE_NORMAL,
                style.fg[gtk.STATE_INSENSITIVE])
        table.attach(self.entry_field_name, 1, 2, 0, 1)
        label_default_value = gtk.Label(_("Default value:"))
        label_default_value.set_alignment(1, 0.5)
        table.attach(label_default_value, 0, 1, 1, 2)
        self.entry_default_value = gtk.Entry()
        self.entry_default_value.set_editable(False)
        self.entry_default_value.set_width_chars(32)
        style = self.entry_field_name.get_style()
        self.entry_default_value.modify_bg(gtk.STATE_NORMAL,
                style.bg[gtk.STATE_INSENSITIVE])
        self.entry_default_value.modify_base(gtk.STATE_NORMAL,
                style.base[gtk.STATE_INSENSITIVE])
        self.entry_default_value.modify_fg(gtk.STATE_NORMAL,
                style.fg[gtk.STATE_INSENSITIVE])
        table.attach(self.entry_default_value, 1, 2, 1, 2)

        frame_user = gtk.Frame()
        alignment_user = gtk.Alignment(0.5, 0.5, 1, 1)
        alignment_user.set_padding(0, 0, 12, 0)
        frame_user.add(alignment_user)
        label_user = gtk.Label(_("<b>Value applicable for:</b>"))
        label_user.set_use_markup(True)
        frame_user.set_label_widget(label_user)
        hbox_user = gtk.HBox(True, 0)
        alignment_user.add(hbox_user)
        hbox_user.set_border_width(6)
        self.radio_current_user = gtk.RadioButton(None, _("Current _User"))
        radio_all_user = gtk.RadioButton(self.radio_current_user,
                _("_All Users"))
        hbox_user.pack_start(self.radio_current_user, False, False, 0)
        hbox_user.pack_start(radio_all_user, False, False, 0)
        radio_all_user.set_active(True)
        table.attach(frame_user, 0, 2, 2, 3)

        frame_condition = gtk.Frame()
        alignment_condition = gtk.Alignment(0.5, 0.5, 1, 1)
        alignment_condition.set_padding(0, 0, 12, 0)
        frame_condition.add(alignment_condition)
        label_condition = gtk.Label(_("<b>Value applicable if:</b>"))
        label_condition.set_use_markup(True)
        frame_condition.set_label_widget(label_condition)
        self.vbox_condition = gtk.VBox(False, 0)
        alignment_condition.add(self.vbox_condition)
        table.attach(frame_condition, 0, 2, 3, 4)

        self.dialog.show_all()
        if reset:
            label_default_value.hide()
            self.entry_default_value.hide()

        radio_all_user.grab_focus()

    def run(self):
        while True:
            res = self.dialog.run()
            if res :
                self.parent.present()
                self.dialog.destroy()
                return res
