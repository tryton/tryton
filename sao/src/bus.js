/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.Bus = {};

    // Bus Identifier
    Sao.Bus.id = Sao.common.uuid4();
    Sao.Bus.channel_actions = {};
    Sao.Bus.request = null;
    Sao.Bus.last_message = undefined;
    Sao.Bus.listening = false;

    Sao.Bus.listen = function(last_message, wait) {
        wait = wait || 1;
        last_message = last_message || Sao.Bus.last_message;
        var session = Sao.Session.current_session;
        if (!session || !session.bus_url_host) {
            return;
        }
        Sao.Bus.listening = true;

        let channels = Object.keys(Sao.Bus.channel_actions);
        let url = new URL(`${session.database}/bus`, session.bus_url_host);
        Sao.Bus.last_message = last_message;
        Sao.Bus.request = jQuery.ajax({
            headers: {
                Authorization: 'Session ' + session.get_auth(),
            },
            contentType: 'application/json',
            data: JSON.stringify({
                last_message: last_message,
                channels: channels,
            }),
            dataType: 'json',
            url: url,
            type: 'POST',
            timeout: Sao.config.bus_timeout,
        });

        Sao.Bus.request.done(function(response) {
            if (Sao.Session.current_session != session) {
                return;
            }
            if (response.message) {
                last_message = response.message.message_id;
                Sao.Logger.info(
                    "poll channels %s with last message",
                    Sao.Bus.channels, last_message);
                Sao.Bus.handle(response.channel, response.message);
            }
            Sao.Bus.listen(last_message, 1);
        });

        Sao.Bus.request.fail(function(response, status, error) {
            if (Sao.Session.current_session != session) {
                return;
            }
            if ((error == "abort") || (error === "timeout")) {
                Sao.Bus.listen(last_message, 1);
            } else if (response.status == 501) {
                Sao.Logger.info("Bus not supported");
                Sao.Bus.listening = false;
            } else {
                Sao.Logger.error(
                    "An exception occured while connection to the bus. " +
                    "Sleeping for %s seconds",
                    wait, error);
                Sao.Bus.listening = false;
                window.setTimeout(
                    Sao.Bus.listen,
                    Math.min(wait * 1000, Sao.config.bus_timeout),
                    last_message, wait * 2);
            }
        });
    };

    Sao.Bus.handle = function(channel, message) {
        let actions = Sao.Bus.channel_actions[channel] || [];
        for (let callback of actions) {
            callback(message);
        }
    };

    Sao.Bus.register = function(channel, func) {
        if (!Object.hasOwn(Sao.Bus.channel_actions, channel)) {
            Sao.Bus.channel_actions[channel] = [];
        }
        Sao.Bus.channel_actions[channel].push(func);

        if (Sao.Bus.request) {
            Sao.Bus.request.abort();
        }
    };

    Sao.Bus.unregister = function(channel, func) {
        if (Object.hasOwn(Sao.Bus.channel_actions, channel)) {
            let actions = Sao.Bus.channel_actions[channel];
            let func_idx = actions.indexOf(func);
            if (func_idx != -1) {
                actions.splice(func_idx, 1);
            }
        }

        if ((Sao.Bus.channel_actions[channel] || []).length == 0) {
            delete Sao.Bus.channel_actions[channel];
        }
    }

    let popup_notification = function(message) {
        if (message.type != 'notification') {
            return;
        }

        try {
            if (Notification.permission != "granted") {
                return;
            }
        } catch (e) {
            Sao.Logger.error(e.message, e.stack);
            return;
        }

        new Notification(message.title, {
            body: message.body || '',
        });
    }
    Sao.Bus.register(`client:${Sao.Bus.id}`, popup_notification);

}());
