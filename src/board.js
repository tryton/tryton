/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.View.BoardXMLViewParser = Sao.class_(Sao.View.FormXMLViewParser, {
        _parse_board: function(node, attributes) {
            var container = new Sao.View.Form.Container(
                Number(node.getAttribute('col') || 4));
            this.view.el.append(container.el);
            this.parse_child(node, container);
            if (this._containers.length > 0) {
                throw 'AssertionError';
            }
        },
        _parse_action: function(node, attributes) {
            var action;
            if (attributes.yexpand === undefined) {
                attributes.yexpand = true;
            }
            if (attributes.yfill === undefined) {
                attributes.yfill = true;
            }
            action = new Sao.View.Board.Action(attributes, this.view.context);
            this.view.actions.push(action);
            this.container.add(action, attributes);
        },
    });

    Sao.View.Board = Sao.class_(Object, {
        xml_parser: Sao.View.BoardXMLViewParser,
        init: function(xml, context) {
            var attributes, attribute, node, actions_prms;

            this.context = context;
            this.actions = [];
            this.state_widgets = [];
            this.el = jQuery('<div/>', {
                'class': 'board'
            });
            new this.xml_parser(this, null, {}).parse(xml.children()[0]);

            actions_prms = [];
            for (var i = 0, len = this.actions.length; i < len; i++) {
                actions_prms.push(this.actions[i].action_prm);
            }
            this.actions_prms = jQuery.when.apply(jQuery, actions_prms);
        },
        reload: function() {
            var i;
            for (i = 0; i < this.actions.length; i++) {
                this.actions[i].display();
            }
            for (i = 0; i < this.state_widgets.length; i++) {
                this.state_widgets[i].set_state(null);
            }
        }
    });

    Sao.View.Board.Action = Sao.class_(Object, {
        init: function(attributes, context) {
            if (context === undefined) {
                context = {};
            }

            var session = Sao.Session.current_session;
            this.name = attributes.name;

            this.el = jQuery('<div/>', {
                'class': 'board-action panel panel-default',
            });
            this.title = jQuery('<div/>', {
                'class': 'panel-heading',
            });
            this.el.append(this.title);
            this.body = jQuery('<div/>', {
                'class': 'panel-body',
            });
            this.el.append(this.body);

            var act_window = new Sao.Model('ir.action.act_window');
            this.action_prm = act_window.execute('get', [this.name], {});
            this.action_prm.done(function(action) {
                var params = {};
                this.action = action;
                params.view_ids = [];
                params.mode = null;
                if (!jQuery.isEmptyObject(action.views)) {
                    params.view_ids = [];
                    params.mode = [];
                    action.views.forEach(function(x) {
                        params.view_ids.push(x[0]);
                        params.mode.push(x[1]);
                    });
                } else if (!jQuery.isEmptyObject(action.view_id)) {
                    params.view_ids = [action.view_id[0]];
                }

                if (!('pyson_domain' in this.action)) {
                    this.action.pyson_domain = '[]';
                }
                var ctx = {};
                ctx = jQuery.extend(ctx, session.context);
                ctx._user = session.user_id;
                var decoder = new Sao.PYSON.Decoder(ctx);
                params.context = jQuery.extend(
                    {}, context,
                    decoder.decode(action.pyson_context || '{}'));
                ctx = jQuery.extend(ctx, params.context);

                ctx.context = ctx;
                decoder = new Sao.PYSON.Decoder(ctx);
                params.domain = decoder.decode(action.pyson_domain);
                params.order = decoder.decode(action.pyson_order);
                params.search_value = decoder.decode(
                    action.pyson_search_value || '[]');
                params.tab_domain = [];
                action.domains.forEach(function(element, index) {
                    params.tab_domain.push(
                        [element[0], decoder.decode(element[1]), element[2]]);
                });
                params.context_model = action.context_model;
                params.context_domain = action.context_domain;
                if (action.limit !== null) {
                    params.limit = action.limit;
                } else {
                    params.limit = Sao.config.limit;
                }

                this.context = ctx;
                this.domain = [];
                this.update_domain([]);

                params.row_activate = this.row_activate.bind(this);

                this.screen = new Sao.Screen(this.action.res_model,
                        params);

                if (attributes.string) {
                    this.title.text(attributes.string);
                } else {
                    this.title.text(this.action.name);
                }
                this.screen.switch_view().done(function() {
                    this.body.append(this.screen.screen_container.el);
                    this.screen.search_filter();
                }.bind(this));
            }.bind(this));
        },
        row_activate: function() {
            var record_ids, win;

            if (!this.screen.current_record) {
                return;
            }

            if (this.screen.current_view.view_type == 'tree' &&
                    (this.screen.current_view.attributes.keyword_open == 1)) {
                record_ids = this.screen.current_view.selected_records.map(
                        function(record) { return record.id; });
                Sao.Action.exec_keyword('tree_open', {
                    model: this.screen.model_name,
                    id: this.screen.current_record.id,
                    ids: record_ids
                }, jQuery.extend({}, this.screen.group._context), false);
            } else {
                win = new Sao.Window.Form(this.screen, function(result) {
                    if (result) {
                        this.screen.current_record.save();
                    } else {
                        this.screen.current_record.cancel();
                    }
                }.bind(this), {
                'title': this.title.text(),
                });
            }
        },
        set_value: function() {
        },
        display: function() {
            this.screen.search_filter(this.screen.screen_container.get_text());
        },
        get_active: function() {
            if (this.screen && this.screen.current_record) {
                return Sao.common.EvalEnvironment(this.screen.current_record);
            }
        },
        update_domain: function(actions) {
            var i, len;
            var active, domain_ctx, decoder, new_domain;

            domain_ctx = jQuery.extend({}, this.context);
            domain_ctx.context = domain_ctx;
            domain_ctx._user = Sao.Session.current_session.user_id;
            for (i = 0, len = actions.length; i < len; i++) {
                active = actions[i].get_active();
                if (active) {
                    domain_ctx[actions[i].name] = active;
                }
            }
            decoder = new Sao.PYSON.Decoder(domain_ctx);
            new_domain = decoder.decode(this.action.pyson_domain);
            if (Sao.common.compare(this.domain, new_domain)) {
                return;
            }
            this.domain.splice(0, this.domain.length);
            jQuery.extend(this.domain, new_domain);
            if (this.screen) {
                this.display();
            }
        }
    });
}());
