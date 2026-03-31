/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    function add_size(url, size=32) {
        if (url) {
            url = new URL(url, window.location);
            url.searchParams.set('s', size);
            return url.href;
        } else {
            return '';
        }
    }

    class _Chat {
        constructor(record) {
            this.notify = this.notify.bind(this);
            this.record = record;
            Sao.Bus.register(`chat:${this.record}`, this.notify);
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

        _get_followers() {
            return Sao.rpc({
                'method': 'model.ir.chat.channel.get_followers',
                'params': [this.record, {}],
            }, Sao.Session.current_session);
        }

        _search_followers(text) {
            if (!text) {
                return jQuery.when();
            }

            return Sao.rpc({
                'method': 'model.ir.chat.channel.search_followers',
                'params': [this.record, text, {}],
            }, Sao.Session.current_session).then(followers => {
                return followers.filter(e => {
                    return !((e.type == 'user') &&
                        (e.key == Sao.Session.current_session.login));
                });
            });
        }

        _add_follower(follower) {
            let method;
            switch (follower.type) {
                case 'user':
                    method = 'subscribe';
                    break;
                case 'email':
                    method = 'subscribe_email';
                    break;
            }
            Sao.rpc({
                'method': `model.ir.chat.channel.${method}`,
                'params': [this.record, follower.key, {}],
            }, Sao.Session.current_session);
        }

        _remove_follower(follower) {
            let method;
            switch (follower.type) {
                case 'user':
                    method = 'unsubscribe';
                    break;
                case 'email':
                    method = 'unsubscribe_email';
                    break;
            }
            Sao.rpc({
                'method': `model.ir.chat.channel.${method}`,
                'params': [this.record, follower.key, {}],
            }, Sao.Session.current_session);
        }

        __build() {
            let el = jQuery('<div/>', {
                'class': 'chat',
            });

            let toolbar = jQuery('<div/>', {
                'class': 'btn-toolbar',
                'role': 'toolbar',
            }).appendTo(el);
            let input_group = jQuery('<div/>', {
                'class': 'input-group',
                'role': 'group',
            }).appendTo(toolbar);
            this.subscribe_input = jQuery('<input/>', {
                'class': 'form-control input-sm',
                'placeholder': Sao.i18n.gettext("Add a follower"),
                'title': Sao.i18n.gettext("Subscribe a follower to this channel"),
            }).appendTo(input_group);

            let avatar_size = 32;

            let format = function(val) {
                return jQuery('<div/>', {
                    'title': val.key,
                })
                    .append(jQuery('<img/>', {
                        'src': add_size(val.avatar_url, avatar_size),
                        'class': 'img-circle',
                        'style': `width: ${avatar_size}px; height: ${avatar_size}px;`,
                    }))
                    .append(jQuery('<span/>', {
                    })
                        .text(val.name));
            };
            new Sao.common.InputCompletion(
                input_group, this._search_followers.bind(this),
                (follower) => {
                    this._add_follower(follower);
                    this.subscribe_input.val('');
                    this.subscribe_input.focus();
                }, format);

            let dropdown = jQuery('<div/>', {
                'class': 'btn-group dropdown',
                'role': 'group',
            }).appendTo(toolbar);
            let subscribe_btn = jQuery('<button/>', {
                'type': 'button',
                'class': 'btn btn-default pull-right dropdown-toggle',
                'data-toggle': 'dropdown',
                'aria-expanded': false,
                'aria-haspopup': true,
                'title': Sao.i18n.gettext("Show followers"),
            }).append(Sao.common.ICONFACTORY.get_icon_img(
                'tryton-notification'))
                .appendTo(dropdown);
            subscribe_btn.uniqueId();

            this._get_followers().then((followers) => {
                let subscribed = followers.some((e) => (
                    (e.type == 'user') &&
                    (e.key == Sao.Session.current_session.login)));
                set_subscribe_state(subscribed);
            });;

            let set_subscribe_state = (subscribed) => {
                let img;
                if (subscribed) {
                    img = 'tryton-notification-on';
                    subscribe_btn.addClass('active');
                } else {
                    img = 'tryton-notification-off';
                    subscribe_btn.removeClass('active');
                }
                subscribe_btn.html(Sao.common.ICONFACTORY.get_icon_img(img));
            }

            let menu = jQuery('<ul/>', {
                'class': 'dropdown-menu dropdown-menu-right',
                'role': 'menu',
                'aria-labelledby': subscribe_btn.id,
            }).appendTo(dropdown);

            dropdown.on('show.bs.dropdown', () => {
                menu.empty();

                let user_action;
                if (subscribe_btn.hasClass('active')) {
                    user_action = jQuery('<a/>', {
                        'href': '#',
                        'class': 'text-danger text-uppercase',
                    }).text(Sao.i18n.gettext("Unsubscribe"))
                        .click(() => {
                            Sao.rpc({
                                'method': 'model.ir.chat.channel.unsubscribe',
                                'params': [this.record, {}],
                            }, Sao.Session.current_session).then(() => {
                                set_subscribe_state(false);
                            });
                        });
                } else {
                    user_action = jQuery('<a/>', {
                        'href': '#',
                        'class': 'text-primary text-uppercase',
                    }).text(Sao.i18n.gettext("Subscribe"))
                        .click(() => {
                            Sao.rpc({
                                'method': 'model.ir.chat.channel.subscribe',
                                'params': [this.record, {}],
                            }, Sao.Session.current_session).then(() => {
                                set_subscribe_state(true);
                            });
                        });
                }
                jQuery('<li/>', {
                    'role': 'presentation',
                }).append(user_action).appendTo(menu);

                this._get_followers().then((followers) => {
                    followers = followers.filter(e => {
                        return !((e.type == 'user') &&
                            (e.key == Sao.Session.current_session.login));
                    });
                    if (followers.length) {
                        jQuery('<li/>', {
                            'class': 'divider',
                        }).appendTo(menu);
                    }
                    let add_follower = (follower) => {
                        jQuery('<li/>', {
                            'role': 'presentation',
                        })
                            .append(jQuery('<div/>', {
                            'title': follower.key,
                            })
                            .append(jQuery('<img/>', {
                                'class': 'img-circle chat-avatar',
                                'src': add_size(follower.avatar_url, avatar_size),
                                'style': `width: ${avatar_size}px; height: ${avatar_size}px;`,
                            }))
                            .append(jQuery('<span/>')
                                .text(follower.name))
                            .append(jQuery('<button/>', {
                                'class': 'btn btn-link',
                                'title': Sao.i18n.gettext("Unsubscribe"),
                                'type': 'button',
                            }).append("&times;").click((evt) => {
                                Sao.common.sur.run(
                                    Sao.i18n.gettext(
                                        'Are you sure to unsubscribe "%1" from this channel?',
                                        follower.name)
                                ).then(() => {
                                    this._remove_follower(follower);
                                });
                            }))
                        ).appendTo(menu);
                    };
                    followers.forEach(add_follower);
                });
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
            let timestamp = Sao.common.format_datetime(
                Sao.common.date_format() + ' %X', message.timestamp);
            if (message.user) {
                let avatar_size = 32;
                let avatar_url = add_size(message.avatar_url, avatar_size);

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
            } else {
                return jQuery('<div/>', {
                    'class': 'media chat-message system-message',
                }).append(jQuery('<div/>', {
                    'class': 'chat-content',
                    'title': timestamp,
                }).text(message.content));
            }
        }
    }
    Sao.Chat = _Chat;

}());
