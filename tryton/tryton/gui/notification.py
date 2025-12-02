# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import gettext

from gi.repository import Gtk, Pango

import tryton.common as common
import tryton.rpc as rpc
from tryton.action import Action
from tryton.config import CONFIG
from tryton.gui.window import Window

_ = gettext.gettext


class NotificationMenu:

    def __init__(self, app):
        self.app = app
        self.button = Gtk.MenuButton()
        img = common.IconFactory.get_image(
            'tryton-notification', Gtk.IconSize.BUTTON)
        self.button.set_image(img)
        self.menu = Gtk.Menu()
        self.menu.connect('show', self.fill)
        self.button.set_popup(self.menu)

    def fill(self, menu):
        for child in menu.get_children():
            menu.remove(child)

        notifications = rpc.execute(
            'model', 'res.notification', 'get', rpc.CONTEXT)

        for notification in notifications:
            item = Gtk.MenuItem()

            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            hbox.set_margin_top(4)
            hbox.set_margin_bottom(4)
            hbox.set_margin_start(6)
            hbox.set_margin_end(6)

            img = common.IconFactory.get_image(
                notification['icon'] or 'tryton-notification',
                Gtk.IconSize.MENU)
            hbox.pack_start(img, False, False, 0)

            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

            label = Gtk.Label(notification['label'])
            label.set_xalign(0)
            vbox.pack_start(label, False, False, 0)

            description = Gtk.Label(notification['description'])
            description.set_xalign(0)
            description.get_style_context().add_class("dim-label")
            description.set_max_width_chars(30)
            description.set_line_wrap(True)
            description.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            description.set_ellipsize(Pango.EllipsizeMode.END)
            description.set_lines(2)
            vbox.pack_start(description, False, False, 0)

            hbox.pack_start(vbox, True, True, 0)
            item.add(hbox)

            item.connect('activate', self.open, notification)

            if notification['unread']:
                style = item.get_style_context()
                style.add_class('unread-notification')

            menu.append(item)

        if notifications:
            menu.append(Gtk.SeparatorMenuItem())

            def open_all_notifications(item):
                params = {
                    'domain': [['user', '=', rpc._USER]],
                    }
                Window.create('res.notification', **params)

            all_notifications = Gtk.MenuItem(label=_("All Notifications..."))
            all_notifications.connect('activate', open_all_notifications)
            menu.append(all_notifications)

        menu.show_all()
        self._update(0)

    def open(self, menuitem, notification):
        if notification.get('model') and notification.get('records'):
            params = {
                'domain': [['id', 'in', notification['records']]],
                }
            if len(notification['records']) == 1:
                params['res_id'] = notification['records'][0]
                params['mode'] = ['form', 'tree']
            Window.create(notification['model'], **params)
        if notification.get('action'):
            Action.execute(notification['action'])
        if notification['unread']:
            rpc.execute(
                'model', 'res.notification', 'mark_read',
                [notification['id']], rpc.CONTEXT)

    def _update(self, count):
        img = common.IconFactory.get_image(
            'tryton-notification', Gtk.IconSize.BUTTON,
            badge=2 if count else None)
        self.button.set_image(img)

    def notify(self, message):
        if message['type'] == 'user-notification':
            self._update(message['count'])
            for msg in message['content']:
                self.app.show_notification(CONFIG['client.title'], msg)

    def count(self):
        count = rpc.execute(
            'model', 'res.notification', 'get_count', rpc.CONTEXT)
        self._update(count)
