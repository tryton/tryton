# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext

from gi.repository import Gdk, Gio, GLib, GObject, Gtk

from tryton import common, rpc
from tryton.bus import Bus
from tryton.common import sur

_ = gettext.gettext


class MessageItem(GObject.GObject):

    def __init__(self, message):
        super().__init__()
        self.message = message


class MessageList(GObject.GObject, Gio.ListModel):

    def __init__(self):
        super().__init__()
        self._messages = []
        self._items = {}

    def do_get_item(self, position):
        if position >= len(self._messages):
            return None
        message = self._messages[position]
        if message['id'] not in self._items:
            self._items[message['id']] = MessageItem(message)
        return self._items[message['id']]

    def do_get_item_type(self):
        return MessageItem

    def do_get_n_items(self):
        return len(self._messages)

    def clear(self):
        self.emit('items-changed', 0, len(self._messages), 0)
        self._messages = []
        self._items = {}

    def append(self, message):
        self._messages.append(message)
        self.emit('items-changed', len(self._messages) - 1, 0, 1)


def _follower_self(follower):
    return (
        follower['type'] == 'user'
        and follower['key'] == rpc._LOGIN)


class Chat:

    def __init__(self, record):
        self.record = record
        Bus.register(f"chat:{self.record}", self.notify)
        self.widget = self.__build()

    def unregister(self):
        Bus.unregister(f"chat:{self.record}", self.notify)

    def send_message(self, message, internal):
        rpc.execute(
            'model', 'ir.chat.channel', 'post', self.record, message,
            'internal' if internal else 'public', rpc.CONTEXT)

    def get_messages(self):
        return rpc.execute(
            'model', 'ir.chat.channel', 'get', self.record, rpc.CONTEXT)

    def notify(self, message):
        self.refresh()

    def refresh(self):
        self._messages.clear()
        for post in self.get_messages():
            self._messages.append(post)
        self.widget.show_all()

        def scroll_to_bottom(*args):
            self._messages_sw.disconnect(signal_id)
            vadj = self._messages_sw.get_vadjustment()
            vadj.props.value = vadj.get_upper()
        signal_id = self._messages_sw.connect(
            'size-allocate', scroll_to_bottom)

    def __build(self):
        tooltips = common.Tooltips()

        widget = Gtk.VBox()
        widget.set_spacing(3)

        hbox = Gtk.HBox()
        widget.pack_start(hbox, expand=False, fill=True, padding=0)

        subscribe_entry = self.__build_follower_entry()
        hbox.pack_start(subscribe_entry, expand=True, fill=True, padding=0)

        subscribe_btn = Gtk.MenuButton()
        subscribe_btn.set_image(common.IconFactory.get_image(
                'tryton-notification', Gtk.IconSize.SMALL_TOOLBAR))
        tooltips.set_tip(subscribe_btn, _("Show followers"))
        subscribe_btn.set_relief(Gtk.ReliefStyle.NONE)
        hbox.pack_start(
            subscribe_btn, expand=False, fill=True, padding=0)

        def set_subscribe_state():
            if subscribed:
                img = 'tryton-notification-on'
            else:
                img = 'tryton-notification-off'
            subscribe_btn.set_image(common.IconFactory.get_image(
                    img, Gtk.IconSize.SMALL_TOOLBAR))

        subscribed = any(_follower_self(f) for f in self._get_followers())
        set_subscribe_state()

        followers_grid = Gtk.Grid()
        followers_grid.set_column_spacing(2)
        followers_grid.set_row_spacing(2)

        subscribe_popover = Gtk.Popover()
        subscribe_btn.set_popover(subscribe_popover)
        subscribe_popover.add(followers_grid)

        def unsubscribe(follower):
            def do_unsubscribe(btn):
                confirmation_text = _('Are you sure to unsubscribe "%(name)s"'
                    ' from this channel?') % follower
                if sur(confirmation_text):
                    if follower['type'] == 'user':
                        method = 'unsubscribe'
                    elif follower['type'] == 'email':
                        method = 'unsubscribe_email'
                    rpc.execute(
                        'model', 'ir.chat.channel', method,
                        self.record, follower['key'], rpc.CONTEXT)
                    subscribe_popover.popdown()
            return do_unsubscribe

        def fill_followers(btn):
            nonlocal subscribed
            for child in followers_grid.get_children():
                followers_grid.remove(child)

            followers = self._get_followers()
            subscribed = any(_follower_self(f) for f in self._get_followers())
            if subscribed:
                action_txt = _("Unsubscribe")
            else:
                action_txt = _("Subscribe")

            followers_grid.attach(
                (b := Gtk.Button(action_txt)), 0, 0, 5, 1)
            b.set_relief(Gtk.ReliefStyle.NONE)
            b.connect('clicked', toggle_subscribe)

            followers = filter(lambda f: not _follower_self(f), followers)
            for idx, follower in enumerate(followers, start=1):
                if follower['avatar_url']:
                    image = Gtk.Image()
                    pixbuf = common.IconFactory.get_pixbuf_url(
                        follower['avatar_url'], size=16, size_param='s',
                        callback=image.set_from_pixbuf)
                    image.set_from_pixbuf(pixbuf)
                    followers_grid.attach(image, 0, idx, 1, 1)
                followers_grid.attach(
                    Gtk.Label(follower['name'], halign=Gtk.Align.START),
                    1, idx, 3, 1)
                followers_grid.attach((b := Gtk.Button('×')), 4, idx, 1, 1)
                b.set_relief(Gtk.ReliefStyle.NONE)
                b.connect('clicked', unsubscribe(follower))

            subscribe_popover.show_all()

        def toggle_subscribe(button):
            nonlocal subscribed
            if subscribed:
                rpc.execute(
                    'model', 'ir.chat.channel', 'unsubscribe', self.record,
                    rpc.CONTEXT)
            else:
                rpc.execute(
                    'model', 'ir.chat.channel', 'subscribe', self.record,
                    rpc.CONTEXT)
            subscribed = not subscribed
            set_subscribe_state()
            if subscribed:
                action_txt = _("Unsubscribe")
            else:
                action_txt = _("Subscribe")
            button.set_label(action_txt)

        subscribe_btn.connect('clicked', fill_followers)

        def _submit(button):
            buffer = input_.get_buffer()
            self.send_message(
                buffer.get_text(
                    buffer.get_start_iter(), buffer.get_end_iter(), False),
                internal.get_active())
            buffer.set_text('')
            if not Bus.listening:
                self.refresh()

        def _keypress(entry, event):
            if (event.state & Gdk.ModifierType.CONTROL_MASK
                    and event.keyval == Gdk.KEY_Return):
                _submit(None)
                return True

        self._messages = MessageList()
        chat_messages = Gtk.ListBox.new()
        chat_messages.props.activate_on_single_click = False
        chat_messages.set_selection_mode(Gtk.SelectionMode.NONE)
        chat_messages.bind_model(self._messages, self.create_message)
        self._messages_sw = scrolledwindow = Gtk.ScrolledWindow()
        viewport = Gtk.Viewport()
        viewport.add(chat_messages)
        viewport.set_valign(Gtk.Align.END)
        scrolledwindow.set_shadow_type(Gtk.ShadowType.NONE)
        scrolledwindow.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolledwindow.add(viewport)
        widget.pack_start(scrolledwindow, True, True, 0)

        input_ = Gtk.TextView()
        input_.connect('key-press-event', _keypress)
        input_.set_size_request(-1, 100)
        widget.pack_start(input_, False, True, 0)

        internal = Gtk.CheckButton.new_with_mnemonic(
            _("Make this an _internal message"))
        widget.pack_start(internal, False, True, 0)

        submit = Gtk.Button.new_with_label(_("Send"))
        submit.connect('clicked', _submit)
        widget.pack_start(submit, False, False, 0)

        return widget

    def _get_followers(self):
        return rpc.execute(
            'model', 'ir.chat.channel', 'get_followers', self.record,
            rpc.CONTEXT)

    def _search_followers(self, text):
        followers = rpc.execute(
            'model', 'ir.chat.channel', 'search_followers',
            str(self.record), text, rpc.CONTEXT)
        return filter(lambda f: not _follower_self(f), followers)

    def _add_follower(self, follower):
        if follower['type'] == 'user':
            rpc.execute(
                'model', 'ir.chat.channel', 'subscribe',
                self.record, follower['key'], rpc.CONTEXT)
        elif follower['type'] == 'email':
            rpc.execute(
                'model', 'ir.chat.channel', 'subscribe_email',
                self.record, follower['key'], rpc.CONTEXT)

    def __build_follower_entry(self):
        tooltips = common.Tooltips()
        subscribe_entry = Gtk.Entry()
        subscribe_entry.set_placeholder_text(_("Add a follower"))
        tooltips.set_tip(
            subscribe_entry, _("Subscribe a follower to this channel"))

        def text_setter(layout, cell, store, iter_):
            cell.set_property('text', store[iter_][0]['name'])

        def pixbuf_setter(layout, cell, store, iter_):
            avatar_url = store[iter_][0]['avatar_url']
            if avatar_url:
                pixbuf = common.IconFactory.get_pixbuf_url(
                    avatar_url, size=16, size_param='s')
            else:
                pixbuf = None
            cell.set_property('pixbuf', pixbuf)

        model = Gtk.ListStore(GObject.TYPE_PYOBJECT)
        completion = Gtk.EntryCompletion()
        completion.set_match_func(lambda *a: True)
        completion.set_property('popup_set_width', True)
        completion.set_model(model)
        completion.pack_start(
            (pixbuf_rdr := Gtk.CellRendererPixbuf()), expand=False)
        completion.set_cell_data_func(pixbuf_rdr, pixbuf_setter)
        completion.pack_start(
            text_rdr := (Gtk.CellRendererText()), expand=True)
        completion.set_cell_data_func(text_rdr, text_setter)
        subscribe_entry.set_completion(completion)

        def update(entry, search_text):
            if search_text != entry.get_text():
                return

            if not search_text or not model:
                model.clear()
                model.search_text = search_text
                return

            if getattr(model, 'search_text', None) == search_text:
                return

            followers = self._search_followers(search_text)

            model.clear()
            for follower in followers:
                model.append([follower])

            model.search_text = search_text
            entry.emit('changed')

        def changed(entry):
            search_text = entry.get_text()
            GLib.timeout_add(300, update, entry, search_text)

        subscribe_entry.connect('changed', changed)

        def match_selected(completion, model, iter_):
            self._add_follower(model[iter_][0])
            subscribe_entry.set_text('')
            subscribe_entry.grab_focus()

        completion.connect('match-selected', match_selected)

        return subscribe_entry

    def create_message(self, item):
        tooltips = common.Tooltips()
        message = item.message

        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_margin_top(5)

        hbox = Gtk.HBox(spacing=10)
        row.add(hbox)

        timestamp = message['timestamp'].strftime('%x %X')

        if message.get('user'):
            if avatar_url := message.get('avatar_url'):
                image = Gtk.Image()
                pixbuf = common.IconFactory.get_pixbuf_url(
                    avatar_url, size=32, size_param='s',
                    callback=image.set_from_pixbuf)
                image.set_from_pixbuf(pixbuf)
                image.set_valign(Gtk.Align.START)
                hbox.pack_start(image, False, False, 0)

            bubble = Gtk.VBox()
            hbox.pack_end(bubble, True, True, 0)

            author = Gtk.Label(label=message['author'])
            author.set_xalign(0)
            author.get_style_context().add_class('dim')

            timestamp = Gtk.Label(label=timestamp)
            timestamp.set_xalign(1)
            timestamp.get_style_context().add_class('dim')

            meta = Gtk.HBox()
            meta.pack_start(author, True, True, 0)
            meta.pack_end(timestamp, False, False, 0)

            content = Gtk.Label(label=message['content'])
            content.set_xalign(0)
            content.set_line_wrap(True)
            content.set_selectable(True)
            content.get_style_context().add_class(
                f"chat-content-{message['audience']}")

            bubble.pack_start(meta, False, False, 0)
            bubble.pack_start(content, False, False, 0)
        else:
            content = Gtk.Label(label=message['content'])
            content.set_xalign(.5)
            content.set_line_wrap(True)
            content.set_selectable(True)
            content.get_style_context().add_class('dim')

            hbox.pack_start(content, True, True, 0)
            tooltips.set_tip(content, timestamp)

        return row
