# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import gettext

try:
    from http import HTTPStatus
except ImportError:
    from http import client as HTTPStatus

from gi.repository import Gtk

from tryton.common import (
    IconFactory, RPCException, play_sound, process_exception)
from tryton.common.underline import set_underline
from tryton.config import CONFIG, TRYTON_ICON
from tryton.exceptions import TrytonServerError
from tryton.gui import Main
from tryton.gui.window.nomodal import NoModal

_ = gettext.gettext


class CodeScanner(NoModal):

    def __init__(self, callback, loop=False):
        super().__init__()
        self.callback = callback
        self.loop = loop
        self.dialog = Gtk.MessageDialog(
            transient_for=self.parent, destroy_with_parent=True,
            text=_("Code Scanner"))
        Main().add_window(self.dialog)
        self.dialog.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.dialog.set_icon(TRYTON_ICON)
        self.dialog.connect('response', self.response)

        self.dialog.set_title(_("Code Scanner"))

        self.entry = Gtk.Entry()
        self.entry.set_activates_default(True)
        self.entry.set_placeholder_text(_("Code"))
        self.dialog.get_message_area().pack_start(
            self.entry, expand=False, fill=False, padding=9)

        button_close = self.dialog.add_button(
            set_underline(_("Close")), Gtk.ResponseType.CLOSE)
        button_close.set_image(IconFactory.get_image(
                'tryton-close', Gtk.IconSize.BUTTON))

        button_ok = self.dialog.add_button(
            set_underline(_("OK")), Gtk.ResponseType.OK)
        button_ok.set_image(IconFactory.get_image(
                'tryton-ok', Gtk.IconSize.BUTTON))
        self.dialog.set_default_response(Gtk.ResponseType.OK)

        self.dialog.show_all()
        self.register()
        self.entry.grab_focus()

    def _play(self, sound):
        if CONFIG['client.code_scanner_sound']:
            play_sound(sound)

    def response(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            code = self.entry.get_text()
            self.entry.set_text('')
            if code:
                while True:
                    try:
                        modified = self.callback(code)
                        self._play('success')
                        if not self.loop or not modified:
                            self.destroy()
                    except Exception as exception:
                        unauthorized = (
                            isinstance(exception, TrytonServerError)
                            and exception.faultCode == str(
                                int(HTTPStatus.UNAUTHORIZED)))
                        if not unauthorized:
                            self._play('danger')
                        try:
                            process_exception(exception)
                        except RPCException:
                            pass
                        if unauthorized:
                            continue
                        self.destroy()
                    return
        if not self.loop or response != Gtk.ResponseType.OK:
            self.destroy()

    def destroy(self):
        super().destroy()
        self.dialog.destroy()

    def show(self):
        self.dialog.show()

    def hide(self):
        self.dialog.hide()
