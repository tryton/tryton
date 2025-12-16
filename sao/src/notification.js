/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */

(function() {
    'use strict';

    class _NotificationMenu {
        constructor() {
            this.notify = this.notify.bind(this);
            this.el = jQuery('<ul/>', {
                'class': 'notification-menu dropdown-menu',
                'role': 'menu',
            });
            this.el.on('show.bs.dropdown', () => {
                this.fill();
                this.indicator.hide();
            });
            this.indicator = jQuery('<span/>', {
                'class': 'notification-badge',
            });
            let indicator_observer = new MutationObserver(() => {
                let indicators = jQuery('.notification-badge').not(this.indicator);
                indicators.text(this.indicator.text())
                indicators.toggle(this.indicator.css('display') !== 'none');
            });
            indicator_observer.observe(
                this.indicator.get(0), {
                    characterData: true,
                    attributes: true,
                    attributeFilter: ['style'],
                });
            this.indicator.hide();
        }

        fill() {
            let Notification = new Sao.Model('res.notification');
            Notification.execute('get', []).done((notifications) => {
                this.el.empty();
                for (let notification of notifications) {
                    let notification_item = jQuery('<div/>', {
                    }).append(jQuery('<span/>', {
                        'class': 'notification-label',
                        'text': notification.label,
                        'title': notification.label,
                    })).append(jQuery('<span/>', {
                        'class': 'notification-description',
                        'text': notification.description,
                        'title': notification.description,
                    }));
                    let link = jQuery('<a/>', {
                        'role': 'menuitem',
                        'href': '#',
                    }).click((evt) => {
                        evt.preventDefault();
                        this.open(notification)
                    }).append(notification_item);
                    let li = jQuery('<li/>', {
                        'class': 'notification-item',
                        'role': 'presentation',
                    });
                    let img = jQuery('<img/>', {
                        'class': 'icon',
                    });
                    link.prepend(img);
                    Sao.common.ICONFACTORY.get_icon_url(
                        notification.icon || 'tryton-notification')
                        .then(url => {
                            img.attr('src', url);
                            // Append only when the url is known to prevent
                            // layout shifts
                            li.append(link);
                        });
                    if (notification.unread) {
                        li.addClass('notification-unread');
                    }
                    this.el.append(li)
                }
                this.el.append(
                    jQuery('<li/>', {
                        'role': 'presentation',
                        'class': 'notification-item notification-action',
                    }).append(jQuery('<a/>', {
                        'role': 'menuitem',
                        'href': '#',
                        'title': Sao.i18n.gettext("All Notifications..."),
                    }).append(jQuery('<span/>', {
                        'class': 'caret',
                    })).click((evt) => {
                        evt.preventDefault();
                        let params = {
                            context: jQuery.extend({}, Sao.Session.current_session.context),
                            domain: [['user', '=', Sao.Session.current_session.user_id]],
                        };
                        params.model = 'res.notification';
                        Sao.Tab.create(params).done(() => {
                            this.indicator.hide();
                        });
                    }))
                );
                if (notifications.length > 0) {
                    this.el.append(
                        jQuery('<li/>', {
                            'role': 'separator',
                            'class': 'divider',
                        }));
                }
                let preferences_img = jQuery('<img/>', {
                    'class': 'icon',
                });
                let preferences = jQuery('<li/>', {
                    'class': 'notification-item',
                    'role': 'presentation',
                }).append(
                    jQuery('<a/>', {
                        'role': 'menuitem',
                        'href': '#',
                        'text': Sao.i18n.gettext("Preferences..."),
                    }).prepend(preferences_img
                    ).click((evt) => {
                        evt.preventDefault();
                        Sao.preferences();
                    }));
                Sao.common.ICONFACTORY.get_icon_url('tryton-launch')
                    .then(url => {
                        preferences_img.attr('src', url);
                    });
                this.el.append(preferences);
            });

        }

        open(notification) {
            let prms = [];
            if (notification.model && notification.records) {
                let params = {
                    context: jQuery.extend({}, Sao.Session.current_session.context),
                    domain: [['id', 'in', notification.records]],
                };
                if (notification.records.length == 1) {
                    params['res_id'] = notification.records[0];
                    params['mode'] = ['form', 'tree'];
                }
                params.model = notification.model;
                prms.push(Sao.Tab.create(params));
            }
            if (notification.action) {
                prms.push(Sao.Action.execute(notification.action));
            }
            jQuery.when.apply(jQuery, prms).done(() => {
                if (notification.unread) {
                    let Notification = new Sao.Model('res.notification');
                    Notification.execute('mark_read', [[notification.id]]);
                }
            });
        }

        _update(count) {
            if (count > 0) {
                if (count < 10) {
                    this.indicator.text(count);
                } else {
                    // Let's keep the text short
                    this.indicator.text('9+');
                }
                this.indicator.show();
            } else {
                this.indicator.hide();
            }
        }

        notify(message) {
            if (message.type == 'user-notification') {
                this._update(message.count);
                try {
                    if (Notification.permission == "granted") {
                        message.content.forEach((body) => {
                            new Notification(
                                Sao.config.title, {
                                    'body': body,
                                });
                        });
                    }
                } catch (e) {
                    Sao.Logger.error(e.message, e.stack);
                }
            }
        }

        count() {
            let Notification = new Sao.Model('res.notification');
            Notification.execute('get_count', [])
                .done((count) => {
                    this._update(count);
                });
        }
    }

    Sao.NotificationMenu = new _NotificationMenu();

}());
