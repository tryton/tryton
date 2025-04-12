/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    class _Chat {
        constructor(record) {
            this.record = record;
            Sao.Bus.register(`chat:${this.record}`, this.notify.bind(this));
            this.el = this.__build();
        }

        unregister() {
            Sao.Bus.unregister(`chat:${this.record}`, this.notify);
        }

        send_message(message, internal) {
            return Sao.rpc({
                'method': 'model.ir.chat.channel.post',
                'params': [this.record, message, internal ? 'internal' : 'public', {}],
            }, Sao.Session.current_session)
        }

        get_messages() {
            return Sao.rpc({
                'method': 'model.ir.chat.channel.get',
                'params': [this.record, {}],
            }, Sao.Session.current_session);
        }

        notify(message) {
            this.refresh();
        }

        refresh() {
            let prm = this.get_messages();
            prm.done((posts) => {
                this._messages.empty();
                for (let post of posts) {
                    this._messages.append(this.create_message(post));
                }

                let messages = this._messages[this._messages.length - 1];
                messages.scrollTop = messages.scrollHeight;
            });
        }

        __build() {
            let el = jQuery('<div/>', {
                'class': 'chat',
            });

            this._messages = jQuery('<div/>', {
                'class': 'chat-messages',
            }).appendTo(jQuery('<div/>', {
                'class': 'chat-messages-outer',
            }).appendTo(el));

            let input = jQuery('<textarea/>', {
                'class': 'input-sm form-control',
                'placeholder': Sao.i18n.gettext("Enter a message"),
            });
            let submit = jQuery('<button/>', {
                'class': 'btn btn-block btn-default',
                'type': 'submit',
                'aria-label': Sao.i18n.gettext("Submit the message"),
                'title': Sao.i18n.gettext("Send"),
                'text': Sao.i18n.gettext("Send"),
            });
            let internal = jQuery('<input/>', {
                'type': 'checkbox',
            });
            jQuery('<hr/>').appendTo(el);
            let form = jQuery('<form/>')
                .append(jQuery('<div/>', {
                    'class': 'form-group',
                }).append(input))
                .append(jQuery('<div/>', {
                    'class': 'checkbox',
                }).append(jQuery('<label/>')
                    .append(internal)
                    .append(Sao.i18n.gettext("Make this an internal message"))))
                .append(submit)
                .appendTo(el);

            let send = (evt) => {
                evt.preventDefault();
                submit.prop('disabled', true);
                input.prop('disabled', true);
                this.send_message(
                    input.val(),
                    internal.prop('checked')
                ).done(() => {
                    input.val('');
                    submit.prop('disabled', false);
                    input.prop('disabled', false);
                    input.trigger('focus');
                    internal.prop('checked', false);
                    if (!Sao.Bus.listening) {
                        this.refresh();
                    }
                });
            };
            form.submit(send);
            input.keypress((evt) => {
                if ((evt.which == Sao.common.RETURN_KEYCODE) && evt.ctrlKey) {
                    evt.preventDefault();
                    form.submit();
                }
            });

            return el;
        }

        create_message(message) {
            let avatar_size = 32;
            let timestamp = Sao.common.format_datetime(
                Sao.common.date_format() + ' %X', message.timestamp);
            let avatar_url = '';
            if (message.avatar_url) {
                let url = new URL(message.avatar_url, window.location);
                url.searchParams.set('s', avatar_size);
                avatar_url = url.href;
            }
            return jQuery('<div/>', {
                'class': 'media chat-message',
            }).append(jQuery('<div/>', {
                'class': 'media-left',
            }).append(jQuery('<img/>', {
                'class': 'media-object img-circle chat-avatar',
                'src': avatar_url,
                'alt': message.author,
                'style': `width: ${avatar_size}px; height: ${avatar_size}px;`,
            }))).append(jQuery('<div/>', {
                'class': 'media-body well well-sm',
            }).append(jQuery('<h6/>', {
                'class': 'media-heading',
            }).text(message.author)
                .append(jQuery('<small/>', {
                    'class': 'text-muted pull-right',
                }).text(timestamp)))
            .append(jQuery('<div/>', {
                'class': `chat-content chat-content-${message.audience}`,
            }).text(message.content)));
        }
    }
    Sao.Chat = _Chat;

}());
