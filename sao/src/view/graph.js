/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.View.Graph = Sao.class_(Sao.View, {
        init: function(screen, xml) {
            Sao.View.Graph._super.init.call(this, screen, xml);
            this.view_type = 'graph';
            this.el = jQuery('<div/>', {
                'class': 'graph'
            });
            this.widgets = {};
            this.widget = this.parse(xml.children()[0]);
            this.widgets.root = this.widget;
            this.el.append(this.widget.el);
        },
        parse: function(node) {
            var field, xfield = null, yfields = [], yattrs;
            var child, node_child;
            var i, len, j, c_len;

            var get_attributes = function(node) {
                var attributes = {}, attribute;
                for (var i = 0, len = node.attributes.length; i < len; i++) {
                    attribute = node.attributes[i];
                    attributes[attribute.name] = attribute.value;
                }
                return attributes;
            };

            for (i=0, len=node.children.length; i < len; i++) {
                child = node.children[i];
                switch (child.tagName) {
                    case 'x':
                        for (j=0, c_len=child.children.length; j < c_len; j++) {
                            xfield = get_attributes(child.children[j]);
                            field = this.screen.model.fields[xfield.name];
                            if (!(xfield.string || '')) {
                                xfield.string = field.description.string;
                            }
                        }
                        break;
                    case 'y':
                        for (j=0, c_len=child.children.length; j < c_len; j++) {
                            yattrs = get_attributes(child.children[j]);
                            if (!(yattrs.string || '') &&
                                    (yattrs.name != '#')) {
                                field = this.screen.model.fields[yattrs.name];
                                yattrs.string = field.description.string;
                            }
                            yfields.push(yattrs);
                        }
                        break;
                }
            }

            var Widget;
            switch (this.attributes.type) {
                case 'hbar':
                    Widget = Sao.View.Graph.HorizontalBar;
                    break;
                case 'line':
                    Widget = Sao.View.Graph.Line;
                    break;
                case 'pie':
                    Widget = Sao.View.Graph.Pie;
                    break;
                default:
                    Widget = Sao.View.Graph.VerticalBar;
            }
            return new Widget(this, xfield, yfields);
        },
        display: function() {
            return this.widget.display(this.screen.group);
        }
    });

    Sao.View.Graph.Chart = Sao.class_(Object, {
        _chart_type: undefined,

        init: function(view, xfield, yfields) {
            this.view = view;
            this.xfield = xfield;
            this.yfields = yfields;
            this.el = jQuery('<div/>');
            this.el.uniqueId();
        },
        update_data: function(group) {
            var data = {};
            var record, yfield, key;
            var i, len, j, y_len;

            this.ids = {};
            data.columns = [['labels']];
            data.names = {};
            var key2columns = {};
            var fields2load = [this.xfield.name];
            for (i = 0, len = this.yfields.length; i < len; i++) {
                yfield = this.yfields[i];
                data.columns.push([yfield.name]);
                data.names[yfield.name] = yfield.string;
                key2columns[yfield.key || yfield.name] = i + 1;
                fields2load.push(yfield.name);
            }

            var prms = [];
            var set_data = function(index) {
                return function () {
                    record = group[index];
                    var x = record.field_get_client(this.xfield.name);
                    data.columns[0][index + 1] = x;
                    this._add_id(x, record.id);

                    var column;
                    for (j = 0, y_len = this.yfields.length; j < y_len; j++) {
                        yfield = this.yfields[j];
                        key = yfield.key || yfield.name;
                        column = data.columns[key2columns[key]];
                        if (yfield.domain) {
                            var ctx = jQuery.extend({},
                                    Sao.session.current_session.context);
                            ctx.context = ctx;
                            ctx._user = Sao.session.current_session.user_id;
                            for (var field in group.model.fields) {
                                ctx[field] = record.field_get(field);
                            }
                            var decoder = new Sao.PYSON.Decoder(ctx);
                            if (!decoder.decode(yfield.domain)) {
                                column[index + 1] = 0;
                                continue;
                            }
                        }
                        if (yfield.name == '#') {
                            column[index + 1] = 1;
                        } else {
                            var value = record.field_get(yfield.name);
                            if (value && value.isTimeDelta) {
                                value = value.asSeconds();
                            }
                            column[index + 1] = value || 0;
                        }
                    }
                }.bind(this);
            }.bind(this);
            var load_field = function(record) {
                return function(fname) {
                    prms.push(record.load(fname));
                };
            };

            var r_prms = [];
            for (i = 0, len = group.length; i < len; i++) {
                record = group[i];
                fields2load.forEach(load_field(group[i]));

                for (j = 0, y_len = data.columns.length; j < y_len; j++) {
                    data.columns[j].push(undefined);
                }
                r_prms.push(
                        jQuery.when.apply(jQuery, prms).then(set_data(i)));
            }
            return jQuery.when.apply(jQuery, r_prms).then(function() {
                return data;
            });
        },
        _add_id: function(key, id) {
            // c3 do not use the moment instance but its date repr when calling
            // onclick
            var id_x = (key.isDate || key.isDateTime) ? key._d : key;
            if (!(id_x in this.ids)) {
                this.ids[id_x] = [];
            }
            this.ids[id_x].push(id);
        },
        display: function(group) {
            var update_prm = this.update_data(group);
            update_prm.done(function(data) {
                c3.generate(this._c3_config(data));
            }.bind(this));
            return update_prm;
        },
        _c3_config: function(data) {
            var c3_config = {};

            c3_config.bindto = '#' + this.el.attr('id');
            c3_config.data = data;
            c3_config.data.type = this._chart_type;
            c3_config.data.x = 'labels';
            c3_config.data.onclick = this.action.bind(this);

            var i, len;
            var found, labels;
            for (i = 0, len = data.columns.length; i < len; i++) {
                labels = data.columns[i];
                if (labels[0] == 'labels') {
                    found = true;
                    break;
                }
            }
            if (found && (labels.length > 1) &&
                    (labels[1] && (labels[1].isDateTime || labels[1].isDate)))
            {
                var format_func, date_format, time_format;
                date_format = this.view.screen.context.date_format || '%x';
                time_format = '%X';
                if (labels[1].isDateTime) {
                    format_func = function(dt) {
                        return Sao.common.format_datetime(date_format,
                                time_format, moment(dt));
                    };
                } else {
                    format_func = function(dt) {
                        return Sao.common.format_date(date_format, moment(dt));
                    };
                }
                c3_config.axis = {
                    x: {
                        type: 'timeseries',
                        tick: {
                            format: format_func,
                        }
                    }
                };
            }
            else {
                c3_config.axis = {
                    x: {
                        type: 'category',
                    }
                };
            }
            return c3_config;
        },
        action: function(data, element) {
            var ids = this.ids[this._action_key(data)];
            var ctx = jQuery.extend({}, this.view.screen.context);
            delete ctx.active_ids;
            delete ctx.active_id;
            Sao.Action.exec_keyword('graph_open', {
                model: this.view.screen.model_name,
                id: ids[0],
                ids: ids
            }, ctx, false);
        },
        _action_key: function(data) {
            return data.x;
        }
    });

    Sao.View.Graph.VerticalBar = Sao.class_(Sao.View.Graph.Chart, {
        _chart_type: 'bar'
    });

    Sao.View.Graph.HorizontalBar = Sao.class_(Sao.View.Graph.Chart, {
        _chart_type: 'bar',
        _c3_config: function(data) {
            var config = Sao.View.Graph.HorizontalBar._super._c3_config
                .call(this, data);
            config.axis.rotated = true;
        }
    });

    Sao.View.Graph.Line = Sao.class_(Sao.View.Graph.Chart, {
        _chart_type: 'line'
    });

    Sao.View.Graph.Pie = Sao.class_(Sao.View.Graph.Chart, {
        _chart_type: 'pie',
        _c3_config: function(data) {
            var config = Sao.View.Graph.Pie._super._c3_config.call(this, data);
            var pie_columns = [], pie_names = {};
            var i, len;
            var labels, values;

            for (i = 0, len = data.columns.length; i < len; i++) {
                if (data.columns[i][0] == 'labels') {
                    labels = data.columns[i].slice(1);
                } else {
                    values = data.columns[i].slice(1);
                }
            }

            // Pie chart do not support axis definition.
            delete config.axis;
            delete config.data.x;
            var format_func, date_format, datetime_format;
            if ((labels.length > 0) &&
                    (labels[0].isDateTime || labels[0].isDate)) {
                date_format = this.view.screen.context.date_format || '%x';
                datetime_format = date_format + ' %X';
                if (labels[1].isDateTime) {
                    format_func = function(dt) {
                        return Sao.common.format_datetime(datetime_format, dt);
                    };
                } else {
                    format_func = function(dt) {
                        return Sao.common.format_date(date_format, dt);
                    };
                }
            }
            var label;
            for (i = 0, len = labels.length; i < len; i++) {
                label = labels[i];
                if (format_func) {
                    label = format_func(label);
                }
                pie_columns.push([i, values[i]]);
                pie_names[i] = label;
            }

            config.data.columns = pie_columns;
            config.data.names = pie_names;
            return config;
        },
        _add_id: function(key, id) {
            var id_x = key;
            if (key.isDateTime || key.isDate) {
                var date_format = this.view.screen.context.date_format || '%x';
                var datetime_format = date_format + ' %X';
                if (key.isDateTime) {
                    id_x = Sao.common.format_datetime(datetime_format, key);
                } else {
                    id_x = Sao.common.format_date(date_format, key);
                }
            }
            if (!(id_x in this.ids)) {
                this.ids[id_x] = [];
            }
            this.ids[id_x].push(id);
        },
        _action_key: function(data) {
            return data.id;
        }
    });

}());
