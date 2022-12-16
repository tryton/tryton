/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.Bus = {};

    // Bus Identifier
    Sao.Bus.id = Sao.common.uuid4();
    Sao.Bus.channels = ['client:' + Sao.Bus.id];

    Sao.Bus.listen = function(last_message, wait) {
        wait = wait || 1;
        var session = Sao.Session.current_session;
        if (!session) {
            return;
        }

        var prm = jQuery.ajax({
            headers: {
                Authorization: 'Session ' + session.get_auth(),
            },
            contentType: 'application/json',
            data: JSON.stringify({
                last_message: last_message,
                channels: Sao.Bus.channels
            }),
            dataType: 'json',
            url: '/' + session.database + '/bus',
            type: 'POST',
            timeout: Sao.config.bus_timeout,
        });

        prm.done(function(response) {
            if (Sao.Session.current_session != session) {
                return;
            }
            if (response.message) {
                last_message = response.message.message_id;
                Sao.Logger.info(
                    "poll channels %s with last message",
                    Sao.Bus.channels, last_message);
                Sao.Bus.handle(response.message);
            }
            Sao.Bus.listen(last_message, 1);
        });

        prm.fail(function(response, status, error) {
            if (Sao.Session.current_session != session) {
                return;
            }
            if (error === "timeout") {
                Sao.Bus.listen(last_message, 1);
            } else if (response.status == 501) {
                Sao.Logger.info("Bus not supported");
                return;
            } else {
                Sao.Logger.error(
                    "An exception occured while connection to the bus. " +
                    "Sleeping for %s seconds",
                    wait, error);
                window.setTimeout(
                    Sao.Bus.listen,
                    Math.min(wait * 1000, Sao.config.bus_timeout),
                    last_message, wait * 2);
            }
        });
    };

    Sao.Bus.handle = function(message) {
        var notify = function(message) {
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
        };

        switch (message.type) {
            case 'notification':
                notify(message);
                break;
        }
    };

}());
