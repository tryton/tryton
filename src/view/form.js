/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.View.Form = Sao.class_(Sao.View, {
        editable: true,
        init: function(screen, xml) {
            Sao.View.Form._super.init.call(this, screen, xml);
            this.view_type = 'form';
            this.el = jQuery('<div/>', {
                'class': 'form'
            });
            this.widgets = {};
            this.widget_id = 0;
            this.state_widgets = [];
            this.containers = [];
            this.notebooks = [];
            var root = xml.children()[0];
            var container = this.parse(screen.model, root);
            this.el.append(container.el);
        },
        _parse_node: function(model, child, container, attributes, labels) {
            var widget;
            switch (child.tagName) {
                case 'image':
                    this._parse_image(
                            model, child, container, attributes);
                    break;
                case 'separator':
                    this._parse_separator(
                            model, child, container, attributes);
                    break;
                case 'label':
                    widget = this._parse_label(
                            model, child, container, attributes);
                    if (attributes.name && widget) {
                        labels[attributes.name] = widget;
                    }
                    break;
                case 'newline':
                    container.add_row();
                    break;
                case 'button':
                    this._parse_button(child, container, attributes);
                    break;
                case 'notebook':
                    this._parse_notebook(
                            model, child, container, attributes);
                    break;
                case 'page':
                    this._parse_page(model, child, container, attributes);
                    break;
                case 'field':
                    widget = this._parse_field(
                            model, child, container, attributes);
                    if ((attributes.name in labels) &&
                            widget &&
                            widget.labelled) {
                        var label = labels[attributes.name];
                        label.el.uniqueId();
                        widget.labelled.uniqueId();
                        widget.labelled.attr(
                                'aria-labelledby', label.el.attr('id'));
                        label.el.attr('for', widget.labelled.attr('id'));
                    }
                    break;
                case 'group':
                    this._parse_group(model, child, container, attributes);
                    break;
                case 'hpaned':
                    this._parse_paned(model, child, container, attributes,
                            'horizontal');
                    break;
                case 'vpaned':
                    this._parse_paned(model, child, container, attributes,
                            'vertical');
                    break;
                case 'child':
                    this._parse_child(model, child, container, attributes);
                    break;
            }
        },
        parse: function(model, node, container) {
            if (container === undefined) {
                container = new Sao.View.Form.Container(
                    Number(node.getAttribute('col') || 4));
                this.containers.push(container);
            }
            var labels = {};
            var _parse = function(index, child) {
                var attributes = {};
                for (var i = 0, len = child.attributes.length; i < len; i++) {
                    var attribute = child.attributes[i];
                    attributes[attribute.name] = attribute.value;
                }
                ['readonly', 'invisible'].forEach(function(name) {
                    if (attributes[name]) {
                        attributes[name] = attributes[name] == 1;
                    }
                });
                ['yexpand', 'yfill', 'xexpand', 'xfill', 'colspan'].forEach(
                        function(name) {
                            if (attributes[name]) {
                                attributes[name] = Number(attributes[name]);
                            }
                        });
                this._parse_node(model, child, container, attributes, labels);
            };
            jQuery(node).children().each(_parse.bind(this));
            return container;
        },
        _parse_image: function(model, node, container, attributes) {
            var image = new Sao.View.Form.Image_(attributes);
            this.state_widgets.push(image);
            container.add(attributes, image);
        },
        _parse_separator: function(model, node, container, attributes) {
            var name = attributes.name;
            var text = attributes.string;
            if (name in model.fields) {
                if (!attributes.states && (name in model.fields)) {
                    attributes.states = model.fields[name].description.states;
                }
                if (!text) {
                    text = model.fields[name].description.string;
                }
            }
            var separator = new Sao.View.Form.Separator(text, attributes);
            this.state_widgets.push(separator);
            container.add(attributes, separator);
        },
        _parse_label: function(model, node, container, attributes) {
            var name = attributes.name;
            var text = attributes.string;
            if (attributes.xexpand === undefined) {
                attributes.xexpand = 0;
            }
            if (name in model.fields) {
                if (name == this.screen.exclude_field) {
                    container.add(attributes);
                    return;
                }
                if (!attributes.states && (name in model.fields)) {
                    attributes.states = model.fields[name].description.states;
                }
                if (!text) {
                    // TODO RTL and translation
                    text = model.fields[name]
                        .description.string + ': ';
                }
                if (attributes.xalign === undefined) {
                    attributes.xalign = 1.0;
                }
            }
            var label;
            if (text) {
                label = new Sao.View.Form.Label(text, attributes);
                this.state_widgets.push(label);
            }
            container.add(attributes, label);
            return label;
        },
        _parse_button: function(node, container, attributes) {
            var button = new Sao.common.Button(attributes);
            this.state_widgets.push(button);
            container.add(attributes, button);
            button.el.click(button, this.button_clicked.bind(this));
        },
        _parse_notebook: function(model, node, container, attributes) {
            if (attributes.colspan === undefined) {
                attributes.colspan = 4;
            }
            var notebook = new Sao.View.Form.Notebook(attributes);
            this.notebooks.push(notebook);
            this.state_widgets.push(notebook);
            container.add(attributes, notebook);
            this.parse(model, node, notebook);
        },
        _parse_page: function(model, node, container, attributes) {
            var text = attributes.string;
            if (attributes.name in model.fields) {
                var field = model.fields[attributes.name];
                if (attributes.name == this.screen.exclude_field) {
                    return;
                }
                ['states', 'string'].forEach(function(attr) {
                    if ((attributes[attr] === undefined) &&
                            (field.description[attr] !== undefined)) {
                        attributes[attr] = field.description[attr];
                    }
                });
            }
            var page = this.parse(model, node);
            page = new Sao.View.Form.Page(
                    container.add(page.el, attributes.string), attributes);
            this.state_widgets.push(page);
        },
        _parse_field: function(model, node, container, attributes) {
            var name = attributes.name;
            if (!(name in model.fields) || name == this.screen.exclude_field) {
                container.add(attributes);
                return;
            }
            if (!attributes.widget) {
                attributes.widget = model.fields[name]
                    .description.type;
            }
            var attribute_names = ['relation', 'domain', 'selection', 'help',
                'relation_field', 'string', 'views', 'add_remove', 'sort',
                'context', 'size', 'filename', 'autocomplete', 'translate',
                'create', 'delete', 'selection_change_with', 'schema_model'];
            for (var i in attribute_names) {
                var attr = attribute_names[i];
                if ((attr in model.fields[name].description) &&
                        (node.getAttribute(attr) === null)) {
                    attributes[attr] = model.fields[name]
                        .description[attr];
                }
            }
            var WidgetFactory = Sao.View.form_widget_get(
                    attributes.widget);
            if (!WidgetFactory) {
                container.add(attributes);
                return;
            }
            var widget = new WidgetFactory(name, model, attributes);
            widget.position = this.widget_id += 1;
            widget.view = this;
            // TODO expand, fill, height, width
            container.add(attributes, widget);
            if (this.widgets[name] === undefined) {
                this.widgets[name] = [];
            }
            this.widgets[name].push(widget);
            this.fields[name] = true;
            return widget;
        },
        _parse_group: function(model, node, container, attributes) {
            var group = new Sao.View.Form.Group(attributes);
            group.add(this.parse(model, node));
            this.state_widgets.push(group);
            container.add(attributes, group);
        },
        _parse_paned: function(model, node, container, attributes,
                              orientation) {
            if (attributes.yexpand === undefined) {
                attributes.yexpand = true;
            }
            if (attributes.yfill === undefined) {
                attributes.yfill = true;
            }
            var paned = new Sao.common.Paned(orientation);
            // TODO position
            container.add(attributes, paned);
            this.parse(model, node, paned);
        },
        _parse_child: function(model, node, paned, attributes) {
            var container = this.parse(model, node);
            var child;
            if (!paned.get_child1().children().length) {
                child = paned.get_child1();
            } else {
                child = paned.get_child2();
            }
            child.append(container.el);
        },
        get_buttons: function() {
            var buttons = [];
            for (var j in this.state_widgets) {
                var widget = this.state_widgets[j];
                if (widget instanceof Sao.common.Button) {
                    buttons.push(widget);
                }
            }
            return buttons;
        },
        display: function() {
            var record = this.screen.current_record;
            var field;
            var name;
            var promesses = {};
            if (record) {
                // Force to set fields in record
                // Get first the lazy one to reduce number of requests
                var fields = [];
                for (name in record.model.fields) {
                    field = record.model.fields[name];
                    fields.push([name, field.description.loading || 'eager']);
                }
                fields.sort(function(a, b) {
                    return a[1].localeCompare(b[1]);
                });
                fields.forEach(function(e) {
                    var name = e[0];
                    promesses[name] = record.load(name);
                });
            }
            var set_state = function(record, field, name) {
                var prm = jQuery.when();
                if (name in promesses) {
                    prm = promesses[name];
                }
                prm.done(function() {
                    field.set_state(record);
                });
            };
            var display = function(record, field, name) {
                return function(widget) {
                    var prm = jQuery.when();
                    if (name in promesses) {
                        prm = promesses[name];
                    }
                    prm.done(function() {
                        widget.display(record, field);
                    });
                };
            };
            for (name in this.widgets) {
                var widgets = this.widgets[name];
                field = null;
                if (record) {
                    field = record.model.fields[name];
                }
                if (field) {
                    set_state(record, field, name);
                }
                widgets.forEach(display(record, field, name));
            }
            return jQuery.when.apply(jQuery,
                    jQuery.map(promesses, function(p) {
                        return p;
                    })
                ).done(function() {
                    var j;
                    for (j in this.state_widgets) {
                        var state_widget = this.state_widgets[j];
                        state_widget.set_state(record);
                    }
                    for (j in this.containers) {
                        var container = this.containers[j];
                        container.resize();
                    }
                    Sao.View.resize(this.el);
                }.bind(this));
        },
        set_value: function() {
            var record = this.screen.current_record;
            if (record) {
                var set_value = function(widget) {
                    widget.set_value(record, this);
                };
                for (var name in this.widgets) {
                    if (name in record.model.fields) {
                        var widgets = this.widgets[name];
                        var field = record.model.fields[name];
                        widgets.forEach(set_value, field);
                    }
                }
            }
        },
        button_clicked: function(event) {
            var button = event.data;
            button.el.prop('disabled', true);
            try {
                this.screen.button(button.attributes);
            } finally {
                button.el.prop('disabled', false);
            }
        },
        selected_records: function() {
            if (this.screen.current_record) {
                return [this.screen.current_record];
            }
            return [];
        },
        set_cursor: function(new_, reset_view) {
            var i, name, j;
            var focus_el, notebook, child;
            var widgets, error_el, pages, is_ancestor;

            var currently_focused = jQuery(document.activeElement);
            var has_focus = currently_focused.closest(this.el) > 0;
            if (reset_view || has_focus) {
                if (reset_view) {
                    for (i = 0; i < this.notebooks.length; i++) {
                        notebook = this.notebooks[i];
                        notebook.set_current_page(0);
                    }
                }
                if (this.attributes.cursor in this.widgets) {
                    focus_el = Sao.common.find_focusable_child(
                            this.widgets[this.attributes.cursor][0].el);
                } else {
                    child = Sao.common.find_focusable_child(this.el);
                    if (child) {
                        child.focus();
                    }
                }
            }

            var record = this.screen.current_record;
            if (record) {
                var invalid_widgets = [];
                // We use the has-error class to find the invalid elements
                // because Sao.common.find_focusable_child use the :visible
                // selector which acts differently than GTK's get_visible
                var error_els = this.el.find('.has-error');
                var invalid_fields = record.invalid_fields();
                for (name in invalid_fields) {
                    widgets = this.widgets[name];
                    for (i = 0; i < error_els.length; i++) {
                        error_el = jQuery(error_els[i]);
                        for (j = 0; j < widgets.length; j++) {
                            if (error_el.closest(widgets[j].el).length > 0) {
                                invalid_widgets.push(error_el);
                                break;
                            }
                        }
                    }
                }
                if (invalid_widgets.length > 0) {
                    focus_el = Sao.common.find_first_focus_widget(this.el,
                            invalid_widgets);
                }
            }

            if (focus_el) {
                for (i = 0; i < this.notebooks.length; i++) {
                    notebook = this.notebooks[i];
                    pages = notebook.get_n_pages();
                    for (j = 0; j < pages; j++) {
                        child = notebook.get_nth_page(j);
                        is_ancestor = (
                                jQuery(focus_el).closest(child).length > 0);
                        if (is_ancestor) {
                            notebook.set_current_page(j);
                            break;
                        }
                    }
                }
                // Only input & textarea can grab the focus
                jQuery(focus_el).find('input,select,textarea').focus();
            }
        }
    });

    Sao.View.Form.Container = Sao.class_(Object, {
        init: function(col) {
            if (col === undefined) col = 4;
            this.col = col;
            this.el = jQuery('<table/>', {
                'class': 'form-container responsive responsive-noheader'
            });
            this.add_row();
        },
        add_row: function() {
            this.el.append(jQuery('<tr/>'));
        },
        rows: function() {
            return this.el.children().children('tr');
        },
        row: function() {
            return this.rows().last();
        },
        add: function(attributes, widget) {
            var colspan = attributes.colspan;
            if (colspan === undefined) colspan = 1;
            var xfill = attributes.xfill;
            if (xfill === undefined) xfill = 1;
            var xexpand = attributes.xexpand;
            if (xexpand === undefined) xexpand = 1;
            var len = 0;
            var row = this.row();
            row.children().map(function(i, e) {
                len += Number(jQuery(e).attr('colspan') || 1);
            });
            if (len + colspan > this.col) {
                this.add_row();
                row = this.row();
            }
            var el;
            if (widget) {
                el = widget.el;
            }
            var cell = jQuery('<td/>', {
                'colspan': colspan,
                'class': widget ? widget.class_ || '' : ''
            }).append(el);
            row.append(cell);

            if (!widget) {
                return;
            }

            // TODO yexpand
            if (attributes.yfill) {
                cell.css('vertical-align', 'top');
            }

            if (attributes.xalign !== undefined) {
                // TODO replace by start/end when supported
                cell.css('text-align', attributes.xalign >= 0.5? 'right': 'left');
            }
            if (xexpand) {
                cell.addClass('xexpand');
                cell.css('width', '100%');
            }
            if (xfill) {
                cell.addClass('xfill');
                if (xexpand) {
                    el.css('width', '100%');
                }
            }

            if (attributes.help) {
                widget.el.data('toggle', 'tooltip');
                widget.el.attr('title', attributes.help);
                widget.el.tooltip();
            }
        },
        resize: function() {
            var rows = this.rows().toArray();
            var widths = [];
            var col = this.col;
            var has_expand = false;
            var i, j;
            var get_xexpands = function(row) {
                row = jQuery(row);
                var xexpands = [];
                i = 0;
                row.children().map(function() {
                    var cell = jQuery(this);
                    var colspan = Math.min(Number(cell.attr('colspan')), col);
                    if (cell.hasClass('xexpand') &&
                        (!jQuery.isEmptyObject(cell.children())) &&
                        (cell.children(':not(.tooltip)').css('display') != 'none')) {
                        xexpands.push([cell, i]);
                    }
                    i += colspan;
                });
                return xexpands;
            };
            // Sort rows to compute first the most constraining row
            // which are the one with the more xexpand cells
            // and with the less colspan
            rows.sort(function(a, b) {
                a = get_xexpands(a);
                b = get_xexpands(b);
                if (a.length == b.length) {
                    var reduce = function(previous, current) {
                        var cell = current[0];
                        var colspan = Math.min(
                            Number(cell.attr('colspan')), col);
                        return previous + colspan;
                    };
                    return a.reduce(reduce, 0) - b.reduce(reduce, 0);
                } else {
                    return b.length - a.length;
                }
            });
            rows.forEach(function(row) {
                row = jQuery(row);
                var xexpands = get_xexpands(row);
                var width = 100 / xexpands.length;
                xexpands.forEach(function(e) {
                    var cell = e[0];
                    i = e[1];
                    var colspan = Math.min(Number(cell.attr('colspan')), col);
                    var current_width = 0;
                    for (j = 0; j < colspan; j++) {
                        current_width += widths[i + j] || 0;
                    }
                    for (j = 0; j < colspan; j++) {
                        if (!current_width) {
                            widths[i + j] = width / colspan;
                        } else if (current_width > width) {
                            // Split proprotionally the difference over all cells
                            // following their current width
                            var diff = current_width - width;
                            if (widths[i + j]) {
                                widths[i + j] -= (diff /
                                    (current_width / widths[i + j]));
                            }
                        }
                    }
                });
                if (!jQuery.isEmptyObject(xexpands)) {
                    has_expand = true;
                }
            });
            rows.forEach(function(row) {
                row = jQuery(row);
                i = 0;
                row.children().map(function() {
                    var cell = jQuery(this);
                    var colspan = Math.min(Number(cell.attr('colspan')), col);
                    if (cell.hasClass('xexpand') &&
                        (cell.children(':not(.tooltip)').css('display') !=
                         'none')) {
                        var width = 0;
                        for (j = 0; j < colspan; j++) {
                            width += widths[i + j] || 0;
                        }
                        cell.css('width', width + '%');
                    } else {
                        cell.css('width', '');
                    }
                    if (cell.children().css('display') == 'none') {
                        cell.css('visibility', 'collapse');
                    } else {
                        cell.css('visibility', 'visible');
                    }
                    i += colspan;
                });
            });
            if (has_expand) {
                this.el.css('width', '100%');
            } else {
                this.el.css('width', '');
            }
        }
    });

    Sao.View.Form.StateWidget = Sao.class_(Object, {
        init: function(attributes) {
            this.attributes = attributes;
        },
        set_state: function(record) {
            var state_changes;
            if (record) {
                state_changes = record.expr_eval(this.attributes.states || {});
            } else {
                state_changes = {};
            }
            var invisible = state_changes.invisible;
            if (invisible === undefined) {
                invisible = this.attributes.invisible;
            }
            if (invisible) {
                this.hide();
            } else {
                this.show();
            }
        },
        show: function() {
            this.el.show();
        },
        hide: function() {
            this.el.hide();
        }
    });

    Sao.View.Form.LabelMixin = Sao.class_(Sao.View.Form.StateWidget, {
        set_state: function(record) {
            Sao.View.Form.LabelMixin._super.set_state.call(this, record);
            var field;
            if (this.attributes.name && record) {
                field = record.model.fields[this.attributes.name];
            }
            if ((this.attributes.string === undefined) && field) {
                var text = '';
                if (record) {
                    text = field.get_client(record) || '';
                }
                this.label_el.val(text);
            }
            var state_changes;
            if (record) {
                state_changes = record.expr_eval(this.attributes.states || {});
            } else {
                state_changes = {};
            }
            if ((field && field.description.required) ||
                    state_changes.required) {
                this.label_el.addClass('required');
            } else {
                this.label_el.removeClass('required');
            }
            if ((field && field.description.readonly) ||
                    state_changes.readonly) {
                this.label_el.removeClass('editable');
                this.label_el.removeClass('required');
            } else {
                this.label_el.addClass('editable');
            }
        }
    });

    Sao.View.Form.Separator = Sao.class_(Sao.View.Form.LabelMixin, {
        init: function(text, attributes) {
            Sao.View.Form.Separator._super.init.call(this, attributes);
            this.el = jQuery('<div/>', {
                'class': 'form-separator'
            });
            this.label_el = jQuery('<label/>');
            if (text) {
                this.label_el.text(text);
            }
            this.el.append(this.label_el);
            this.el.append(jQuery('<hr/>'));
        }
    });

    Sao.View.Form.Label = Sao.class_(Sao.View.Form.LabelMixin, {
        class_: 'form-label',
        init: function(text, attributes) {
            Sao.View.Form.Label._super.init.call(this, attributes);
            this.el = this.label_el = jQuery('<label/>', {
                text: text,
                'class': this.class_
            });
        }
    });

    Sao.View.Form.Notebook = Sao.class_(Sao.View.Form.StateWidget, {
        class_: 'form-notebook',
        init: function(attributes) {
            Sao.View.Form.Notebook._super.init.call(this, attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            this.nav = jQuery('<ul/>', {
                'class': 'nav nav-tabs',
                role: 'tablist'
            }).appendTo(this.el);
            this.panes = jQuery('<div/>', {
                'class': 'tab-content'
            }).appendTo(this.el);
            this.selected = false;
        },
        add: function(tab, text) {
            var pane = jQuery('<div/>', {
                'role': 'tabpanel',
                'class': 'tab-pane',
            }).uniqueId();
            var tab_id = pane.attr('id');
            var page = jQuery('<li/>', {
                'role': 'presentation'
            }).append(
                jQuery('<a/>', {
                    'aria-controls': tab_id,
                    'role': 'tab',
                    'data-toggle': 'tab',
                    'href': '#' + tab_id
                }).append(text)
                .on('shown.bs.tab', function() {
                    Sao.View.resize(tab);
                })).appendTo(this.nav);
            pane.html(tab).appendTo(this.panes);
            if (!this.selected) {
                // Can not use .tab('show')
                page.addClass('active');
                pane.addClass('active');
                this.selected = true;
            }
            return page;
        },
        set_current_page: function(page_index) {
            var tab = this.nav.find(
                    'li[role="presentation"]:eq(' + page_index + ') a');
            tab.tab('show');
        },
        get_n_pages: function() {
            return this.nav.find("li[role='presentation']").length;
        },
        get_nth_page: function(page_index) {
            return jQuery(this.panes.find("div[role='tabpanel']")[page_index]);
        }
    });

    Sao.View.Form.Page = Sao.class_(Sao.View.Form.StateWidget, {
        init: function(el, attributes) {
            Sao.View.Form.Page._super.init.call(this, attributes);
            this.el = el;
        }
    });

    Sao.View.Form.Group = Sao.class_(Sao.View.Form.StateWidget, {
        class_: 'form-group_',
        init: function(attributes) {
            Sao.View.Form.Group._super.init.call(this, attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
        },
        add: function(widget) {
            this.el.append(widget.el);
        }
    });

    Sao.View.Form.Image_ = Sao.class_(Sao.View.Form.StateWidget, {
        class_: 'form-image_',
        init: function(attributes) {
            Sao.View.Form.Image_._super.init.call(this, attributes);
            this.el = jQuery('<div/>', {
                'class_': this.class_
            });
            this.img = jQuery('<img/>', {
                'class': 'center-block'
            }).appendTo(this.el);
            Sao.common.ICONFACTORY.register_icon(attributes.name)
                .done(function(url) {
                    this.img.attr('src', url);
                }.bind(this));
        }
    });

    Sao.View.form_widget_get = function(type) {
        switch (type) {
            case 'char':
                return Sao.View.Form.Char;
            case 'password':
                return Sao.View.Form.Password;
            case 'date':
                return Sao.View.Form.Date;
            case 'datetime':
                return Sao.View.Form.DateTime;
            case 'time':
                return Sao.View.Form.Time;
            case 'timedelta':
                return Sao.View.Form.TimeDelta;
            case 'integer':
            case 'biginteger':
                return Sao.View.Form.Integer;
            case 'float':
            case 'numeric':
                return Sao.View.Form.Float;
            case 'selection':
                return Sao.View.Form.Selection;
            case 'boolean':
                return Sao.View.Form.Boolean;
            case 'text':
                return Sao.View.Form.Text;
            case 'richtext':
                return Sao.View.Form.RichText;
            case 'many2one':
                return Sao.View.Form.Many2One;
            case 'one2one':
                return Sao.View.Form.One2One;
            case 'reference':
                return Sao.View.Form.Reference;
            case 'one2many':
                return Sao.View.Form.One2Many;
            case 'many2many':
                return Sao.View.Form.Many2Many;
            case 'binary':
                return Sao.View.Form.Binary;
            case 'multiselection':
                return Sao.View.Form.MultiSelection;
            case 'image':
                return Sao.View.Form.Image;
            case 'url':
                return Sao.View.Form.URL;
            case 'email':
                return Sao.View.Form.Email;
            case 'callto':
                return Sao.View.Form.CallTo;
            case 'sip':
                return Sao.View.Form.SIP;
            case 'progressbar':
                return Sao.View.Form.ProgressBar;
            case 'dict':
                return Sao.View.Form.Dict;
        }
    };


    Sao.View.Form.Widget = Sao.class_(Object, {
        init: function(field_name, model, attributes) {
            this.field_name = field_name;
            this.model = model;
            this.view = null;  // Filled later
            this.attributes = attributes;
            this.el = null;
            this.position = 0;
            this.visible = true;
            this.labelled = null;  // Element which received the labelledby
        },
        display: function(record, field) {
            var readonly = this.attributes.readonly;
            var invisible = this.attributes.invisible;
            if (!field) {
                if (readonly === undefined) {
                    readonly = true;
                }
                if (invisible === undefined) {
                    invisible = false;
                }
                this.set_readonly(readonly);
                this.set_invisible(invisible);
                return;
            }
            var state_attrs = field.get_state_attrs(record);
            if (readonly === undefined) {
                readonly = state_attrs.readonly;
                if (readonly === undefined) {
                    readonly = false;
                }
            }
            if (this.view.screen.attributes.readonly) {
                readonly = true;
            }
            this.set_readonly(readonly);
            var invalid = state_attrs.invalid;
            if (!readonly && invalid) {
                this.el.addClass('has-error');
            } else {
                this.el.removeClass('has-error');
            }
            if (invisible === undefined) {
                invisible = field.get_state_attrs(record).invisible;
                if (invisible === undefined) {
                    invisible = false;
                }
            }
            this.set_invisible(invisible);
        },
        record: function() {
            if (this.view && this.view.screen) {
                return this.view.screen.current_record;
            }
        },
        field: function() {
            var record = this.record();
            if (record) {
                return record.model.fields[this.field_name];
            }
        },
        focus_out: function() {
            if (!this.field()) {
                return;
            }
            if (!this.visible) {
                return;
            }
            this.set_value(this.record(), this.field());
        },
        set_value: function(record, field) {
        },
        set_readonly: function(readonly) {
            this.el.prop('disabled', readonly);
        },
        set_invisible: function(invisible) {
            this.visible = !invisible;
            if (invisible) {
                this.el.hide();
            } else {
                this.el.show();
            }
        }
    });

    Sao.View.Form.Char = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-char',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Char._super.init.call(this, field_name, model,
                attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            this.group = jQuery('<div/>', {
                'class': 'input-group input-group-sm'
            }).appendTo(this.el);
            this.input = this.labelled = jQuery('<input/>', {
                'type': 'text',
                'class': 'form-control input-sm'
            }).appendTo(this.group);
            if (attributes.autocomplete) {
                this.datalist = jQuery('<datalist/>').appendTo(this.el);
                this.datalist.uniqueId();
                this.input.attr('list', this.datalist.attr('id'));
            }
            this.el.change(this.focus_out.bind(this));

            if (!attributes.size) {
                this.group.css('width', '100%');
            }
        },
        display: function(record, field) {
            Sao.View.Form.Char._super.display.call(this, record, field);
            if (this.datalist) {
                this.datalist.children().remove();
                var selection = [];
                if (record) {
                    selection = record.autocompletion[this.field_name] || [];
                }
                selection.forEach(function(e) {
                    jQuery('<option/>', {
                        'value': e
                    }).appendTo(this.datalist);
                }.bind(this));
            }

            // Set size
            var length = '';
            var width = '100%';
            if (record) {
                length = record.expr_eval(this.attributes.size);
                if (length > 0) {
                    width = null;
                }
            }
            this.input.attr('maxlength', length);
            this.input.attr('size', length);
            this.group.css('width', width);

            if (record) {
                var value = record.field_get_client(this.field_name);
                this.input.val(value || '');
            } else {
                this.input.val('');
            }
        },
        set_value: function(record, field) {
            field.set_client(record, this.input.val());
        },
        set_readonly: function(readonly) {
            this.input.prop('readonly', readonly);
        },
        focus: function() {
            this.input.focus();
        }
    });

    Sao.View.Form.Password = Sao.class_(Sao.View.Form.Char, {
        class_: 'form-password',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Password._super.init.call(this, field_name, model,
                attributes);
            this.input.prop('type', 'password');
        }
    });

    Sao.View.Form.Date = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-date',
        _width: '12em',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Date._super.init.call(this, field_name, model,
                attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            this.date = this.labelled = jQuery('<div/>', {
                'class': 'input-group input-group-sm'
            }).appendTo(this.el);
            this.input = jQuery('<input/>', {
                'type': 'text',
                'class': 'form-control input-sm'
            }).appendTo(this.date);
            jQuery('<span/>', {
                'class': 'input-group-btn'
            }).append(jQuery('<button/>', {
                'class': 'btn btn-default',
                'type': 'button'
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-calendar'
            }))).appendTo(this.date);
            this.date.datetimepicker();
            this.date.css('width', this._width);
            this.date.on('dp.hide', this.focus_out.bind(this));
        },
        get_format: function(record, field) {
            return field.date_format(record);
        },
        get_value: function(record, field) {
            var value = this.date.data('DateTimePicker').date();
            if (value) {
                value.isDate = true;
            }
            return value;
        },
        display: function(record, field) {
            if (record && field) {
                this.date.data('DateTimePicker').format(
                    Sao.common.moment_format(this.get_format(record, field)));
            }
            Sao.View.Form.Date._super.display.call(this, record, field);
            var value;
            if (record) {
                value = field.get_client(record);
            } else {
                value = null;
            }
            this.date.data('DateTimePicker').date(value);
        },
        focus: function() {
            this.input.focus();
        },
        set_value: function(record, field) {
            field.set_client(record, this.get_value(record, field));
        },
        set_readonly: function(readonly) {
            this.date.find('button').prop('disabled', readonly);
            this.date.find('input').prop('readonly', readonly);
        }
    });

    Sao.View.Form.DateTime = Sao.class_(Sao.View.Form.Date, {
        class_: 'form-datetime',
        _width: '25em',
        get_format: function(record, field) {
            return field.date_format(record) + ' ' + field.time_format(record);
        },
        get_value: function(record, field) {
            var value = this.date.data('DateTimePicker').date();
            if (value) {
                value.isDateTime = true;
            }
            return value;
        }
    });

    Sao.View.Form.Time = Sao.class_(Sao.View.Form.Date, {
        class_: 'form-time',
        _width: '10em',
        get_format: function(record, field) {
            return field.time_format(record);
        },
        get_value: function(record, field) {
            var value = this.date.data('DateTimePicker').date();
            if (value) {
                value.isTime = true;
            }
            return value;
        }
    });

    Sao.View.Form.TimeDelta = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-timedelta',
        init: function(field_name, model, attributes) {
            Sao.View.Form.TimeDelta._super.init.call(this, field_name, model,
                attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            this.input = this.labelled = jQuery('<input/>', {
                'type': 'text',
                'class': 'form-control input-sm'
            }).appendTo(this.el);
            this.el.change(this.focus_out.bind(this));
        },
        display: function(record, field) {
            Sao.View.Form.TimeDelta._super.display.call(this, record, field);
            if (record) {
                var value = record.field_get_client(this.field_name);
                this.input.val(value || '');
            } else {
                this.input.val('');
            }
        },
        focus: function() {
            this.input.focus();
        },
        set_value: function(record, field) {
            field.set_client(record, this.input.val());
        },
        set_readonly: function(readonly) {
            this.input.prop('readonly', readonly);
        }
    });

    Sao.View.Form.Integer = Sao.class_(Sao.View.Form.Char, {
        class_: 'form-integer',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Integer._super.init.call(this, field_name, model,
                attributes);
            this.input.attr('type', 'text');
            this.input.attr('width', 8);
            this.group.css('width', '');
            this.factor = Number(attributes.factor || 1);
        },
        set_value: function(record, field) {
            field.set_client(record, this.input.val(), undefined, this.factor);
        },
        display: function(record, field) {
            // Skip Char call
            Sao.View.Form.Char._super.display.call(this, record, field);
            if (record) {
                var value = record.model.fields[this.field_name]
                    .get_client(record, this.factor);
                this.input.val(value);
            } else {
                this.input.val('');
            }
        }
    });

    Sao.View.Form.Float = Sao.class_(Sao.View.Form.Integer, {
        class_: 'form-float'
    });

    Sao.View.Form.Selection = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-selection',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Selection._super.init.call(this, field_name, model,
                attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            this.select = this.labelled = jQuery('<select/>', {
                'class': 'form-control input-sm'
            });
            this.el.append(this.select);
            this.select.change(this.focus_out.bind(this));
            Sao.common.selection_mixin.init.call(this);
            this.init_selection();
        },
        init_selection: function(key) {
            Sao.common.selection_mixin.init_selection.call(this, key,
                this.set_selection.bind(this));
        },
        update_selection: function(record, field, callbak) {
            Sao.common.selection_mixin.update_selection.call(this, record,
                field, function(selection) {
                    this.set_selection(selection);
                    if (callbak) {
                        callbak();
                    }
                }.bind(this));
        },
        set_selection: function(selection) {
            var select = this.select;
            select.empty();
            selection.forEach(function(e) {
                select.append(jQuery('<option/>', {
                    'value': JSON.stringify(e[0]),
                    'text': e[1]
                }));
            });
        },
        display_update_selection: function(record, field) {
            this.update_selection(record, field, function() {
                if (!field) {
                    this.select.val('');
                    return;
                }
                var value = field.get(record);
                var prm, found = false;
                for (var i = 0, len = this.selection.length; i < len; i++) {
                    if (this.selection[i][0] === value) {
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    prm = Sao.common.selection_mixin.get_inactive_selection
                        .call(this, value);
                    prm.done(function(inactive) {
                        this.select.append(jQuery('<option/>', {
                            value: JSON.stringify(inactive[0]),
                            text: inactive[1],
                            disabled: true
                        }));
                    }.bind(this));
                } else {
                    prm = jQuery.when();
                }
                prm.done(function() {
                    this.select.val(JSON.stringify(value));
                }.bind(this));
            }.bind(this));
        },
        display: function(record, field) {
            Sao.View.Form.Selection._super.display.call(this, record, field);
            this.display_update_selection(record, field);
        },
        focus: function() {
            this.select.focus();
        },
        value_get: function() {
            return JSON.parse(this.select.val());
        },
        set_value: function(record, field) {
            var value = this.value_get();
            field.set_client(record, value);
        },
        set_readonly: function(readonly) {
            this.select.prop('disabled', readonly);
        }
    });

    Sao.View.Form.Boolean = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-boolean',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Boolean._super.init.call(this, field_name, model,
                attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            this.input = this.labelled = jQuery('<input/>', {
                'type': 'checkbox',
                'class': 'form-control input-sm'
            }).appendTo(this.el);
            this.input.change(this.focus_out.bind(this));
            this.input.click(function() {
                // Dont trigger click if field is readonly as readonly has no
                // effect on checkbox
                return !jQuery(this).prop('readonly');
            });
        },
        display: function(record, field) {
            Sao.View.Form.Boolean._super.display.call(this, record, field);
            if (record) {
                this.input.prop('checked', record.field_get(this.field_name));
            } else {
                this.input.prop('checked', false);
            }
        },
        focus: function() {
            this.input.focus();
        },
        set_value: function(record, field) {
            var value = this.input.prop('checked');
            field.set_client(record, value);
        },
        set_readonly: function(readonly) {
            this.input.prop('readonly', readonly);
        }
    });

    Sao.View.Form.Text = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-text',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Text._super.init.call(this, field_name, model,
                attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            this.input = this.labelled = jQuery('<textarea/>', {
                'class': 'form-control input-sm'
            }).appendTo(this.el);
            this.input.change(this.focus_out.bind(this));
        },
        display: function(record, field) {
            Sao.View.Form.Text._super.display.call(this, record, field);
            if (record) {
                var value = record.field_get_client(this.field_name);
                this.input.val(value);
            } else {
                this.input.val('');
            }
        },
        focus: function() {
            this.input.focus();
        },
        set_value: function(record, field) {
            var value = this.input.val() || '';
            field.set_client(record, value);
        },
        set_readonly: function(readonly) {
            this.input.prop('readonly', readonly);
        }
    });

    Sao.View.Form.RichText = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-richtext',
        init: function(field_name, model, attributes) {
            var i, properties, button;
            Sao.View.Form.RichText._super.init.call(
                    this, field_name, model, attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_ + ' panel panel-default'
            });
            this.toolbar = jQuery('<div/>', {
                'class': 'btn-toolbar',
                'role': 'toolbar'
            }).appendTo(jQuery('<div/>', {
                'class': 'panel-heading'
            }).appendTo(this.el));

            var button_apply_command = function(evt) {
                document.execCommand(evt.data);
            };

            var add_buttons = function(buttons) {
                var group = jQuery('<div/>', {
                    'class': 'btn-group',
                    'role': 'group'
                }).appendTo(this.toolbar);
                for (i in buttons) {
                    properties = buttons[i];
                    button = jQuery('<button/>', {
                        'class': 'btn btn-default',
                        'type': 'button'
                    }).append(jQuery('<span/>', {
                        'class': 'glyphicon glyphicon-' + properties.icon
                    })).appendTo(group);
                    button.click(properties.command, button_apply_command);
                }
            }.bind(this);

            add_buttons([
                    {
                        'icon': 'bold',
                        'command': 'bold'
                    }, {
                        'icon': 'italic',
                        'command': 'italic'
                    }, {
                        'icon': 'text-color',  // XXX
                        'command': 'underline'
                    }]);

            var selections = [
            {
                'heading': Sao.i18n.gettext('Font'),
                'options': ['Normal', 'Serif', 'Sans', 'Monospace'],  // XXX
                'command': 'fontname'
            }, {
                'heading': Sao.i18n.gettext('Size'),
                'options': [1, 2, 3, 4, 5, 6, 7],
                'command': 'fontsize'
            }];
            var add_option = function(dropdown, properties) {
                return function(option) {
                    dropdown.append(jQuery('<li/>').append(jQuery('<a/>', {
                        'href': '#'
                    }).append(option).click(function() {
                        document.execCommand(properties.command, false, option);
                    })));
                };
            };
            for (i in selections) {
                properties = selections[i];
                var group = jQuery('<div/>', {
                    'class': 'btn-group',
                    'role': 'group'
                }).appendTo(this.toolbar);
                button = jQuery('<button/>', {
                    'class': 'btn btn-default dropdown-toggle',
                    'type': 'button',
                    'data-toggle': 'dropdown',
                    'aria-expanded': false,
                    'aria-haspopup': true
                }).append(properties.heading)
                .append(jQuery('<span/>', {
                    'class': 'caret'
                })).appendTo(group);
                var dropdown = jQuery('<ul/>', {
                    'class': 'dropdown-menu'
                }).appendTo(group);
                properties.options.forEach(add_option(dropdown, properties));
            }

            add_buttons([
                    {
                        'icon': 'align-left',
                        'command': 'justifyLeft'
                    }, {
                        'icon': 'align-center',
                        'command': 'justifyCenter'
                    }, {
                        'icon': 'align-right',
                        'command': 'justifyRight'
                    }, {
                        'icon': 'align-justify',
                        'command': 'justifyFull'
                    }]);

            // TODO backColor
            [['foreColor', '#000000']].forEach(
                    function(e) {
                        var command = e[0];
                        var color = e[1];
                        jQuery('<input/>', {
                            'class': 'btn btn-default',
                            'type': 'color'
                        }).appendTo(this.toolbar)
                        .change(function() {
                            document.execCommand(command, false, jQuery(this).val());
                        }).focusin(function() {
                            document.execCommand(command, false, jQuery(this).val());
                        }).val(color);
            }.bind(this));

            this.input = this.labelled = jQuery('<div/>', {
                'class': 'richtext',
                'contenteditable': true
            }).appendTo(jQuery('<div/>', {
                'class': 'panel-body'
            }).appendTo(this.el));
            this.el.focusout(this.focus_out.bind(this));
        },
        focus_out: function() {
            // Let browser set the next focus before testing
            // if it moved out of the widget
            window.setTimeout(function() {
                if (this.el.find(':focus').length === 0) {
                    Sao.View.Form.RichText._super.focus_out.call(this);
                }
            }.bind(this), 0);
        },
        display: function(record, field) {
            Sao.View.Form.RichText._super.display.call(this, record, field);
            var value = '';
            if (record) {
                value = record.field_get_client(this.field_name);
            }
            this.input.html(value);
        },
        focus: function() {
            this.input.focus();
        },
        set_value: function(record, field) {
            // TODO order attributes
            this.input.find('div').each(function(i, el) {
                el = jQuery(el);
                // Not all browsers respect the styleWithCSS
                if (el.css('text-align')) {
                    // Remove browser specific prefix
                    var align = el.css('text-align').split('-').pop();
                    el.attr('align', align);
                    el.css('text-align', '');
                }
                // Some browsers set start as default align
                if (el.attr('align') == 'start') {
                    el.attr('align', 'left');
                }
            });
            var value = this.input.html() || '';
            field.set_client(record, value);
        },
        set_readonly: function(readonly) {
            this.input.prop('contenteditable', !readonly);
            this.toolbar.find('button,select').prop('disabled', readonly);
        }
    });

    Sao.View.Form.Many2One = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-many2one',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Many2One._super.init.call(this, field_name, model,
                attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            var group = jQuery('<div/>', {
                'class': 'input-group input-group-sm'
            }).appendTo(this.el);
            this.entry = this.labelled = jQuery('<input/>', {
                'type': 'input',
                'class': 'form-control input-sm'
            }).appendTo(group);
            // Use keydown to not receive focus-in TAB
            this.entry.on('keydown', this.key_press.bind(this));

            if (!attributes.completion || attributes.completion == "1") {
                Sao.common.get_completion(group,
                    this._update_completion.bind(this),
                    this._completion_match_selected.bind(this),
                    this._completion_action_activated.bind(this));
                this.wid_completion = true;
            }

            // Append buttons after the completion to not break layout
            this.but_primary = jQuery('<button/>', {
                'class': 'btn btn-default',
                'type': 'button'
            }).append(jQuery('<span/>', {
                'class': 'glyphicon'
            })).appendTo(jQuery('<span/>', {
                'class': 'input-group-btn'
            }).prependTo(group));
            this.but_secondary = jQuery('<button/>', {
                'class': 'btn btn-default',
                'type': 'button'
            }).append(jQuery('<span/>', {
                'class': 'glyphicon'
            })).appendTo(jQuery('<span/>', {
                'class': 'input-group-btn'
            }).appendTo(group));
            this.but_primary.click('primary', this.edit.bind(this));
            this.but_secondary.click('secondary', this.edit.bind(this));

            this.el.change(this.focus_out.bind(this));
            this._readonly = false;
        },
        get_screen: function() {
            var domain = this.field().get_domain(this.record());
            var context = this.field().get_context(this.record());
            return new Sao.Screen(this.get_model(), {
                'context': context,
                'domain': domain,
                'mode': ['form'],
                'view_ids': (this.attributes.view_ids || '').split(','),
                'views_preload': this.attributes.views,
                'readonly': this._readonly
            });
        },
        set_text: function(value) {
            if (jQuery.isEmptyObject(value)) {
                value = '';
            }
            this.entry.val(value);
        },
        get_text: function() {
            var record = this.record();
            if (record) {
                return record.field_get_client(this.field_name);
            }
            return '';
        },
        focus_out: function() {
            if (!this.attributes.completion ||
                    this.attributes.completion == "1") {
                if (this.el.find('.dropdown').hasClass('open')) {
                    return;
                }
            }
            Sao.View.Form.Many2One._super.focus_out.call(this);
        },
        set_value: function(record, field) {
            if (field.get_client(record) != this.entry.val()) {
                field.set_client(record, this.value_from_id(null, ''));
                this.entry.val('');
            }
        },
        display: function(record, field) {
            var screen_record = this.record();
            if ((screen_record && record) && (screen_record.id != record.id)) {
                return;
            }

            var text_value, value;
            Sao.View.Form.Many2One._super.display.call(this, record, field);

            this._set_button_sensitive();
            this._set_completion();

            if (!record) {
                this.entry.val('');
                return;
            }
            this.set_text(field.get_client(record));
            var primary, secondary;
            value = field.get(record);
            if (this.has_target(value)) {
                primary = 'glyphicon-folder-open';
                secondary = 'glyphicon-erase';
            } else {
                primary = null;
                secondary = 'glyphicon-search';
            }
            if (this.entry.prop('readonly')) {
                secondary = null;
            }
            [
                [primary, this.but_primary],
                [secondary, this.but_secondary]
            ].forEach(function(items) {
                var icon_name = items[0];
                var button = items[1];
                var icon = button.find('.glyphicon');
                icon.removeClass().addClass('glyphicon');
                // don't use .hide/.show because the display value is not
                // correctly restored on modal.
                if (!icon_name) {
                    button.parent().css('display', 'none');
                } else {
                    button.parent().css('display', 'table-cell');
                    icon.addClass(icon_name);
                }
            });
        },
        focus: function() {
            this.entry.focus();
        },
        set_readonly: function(readonly) {
            this._readonly = readonly;
            this._set_button_sensitive();
        },
        _set_button_sensitive: function() {
            this.entry.prop('readonly', this._readonly);
            this.but_primary.prop('disabled', !this.read_access());
            this.but_secondary.prop('disabled', this._readonly);
        },
        get_access: function(type) {
            var model = this.get_model();
            if (model) {
                return Sao.common.MODELACCESS.get(model)[type];
            }
            return true;
        },
        read_access: function() {
            return this.get_access('read');
        },
        create_access: function() {
            return this.attributes.create && this.get_access('create');
        },
        id_from_value: function(value) {
            return value;
        },
        value_from_id: function(id, str) {
            if (str === undefined) {
                str = '';
            }
            return [id, str];
        },
        get_model: function() {
            return this.attributes.relation;
        },
        has_target: function(value) {
            return value !== undefined && value !== null;
        },
        edit: function(evt) {
            var model = this.get_model();
            if (!model || !Sao.common.MODELACCESS.get(model).read) {
                return;
            }
            var win, callback;
            var record = this.record();
            var value = record.field_get(this.field_name);

            if ((evt && evt.data == 'secondary') &&
                    !this._readonly &&
                    this.has_target(value)) {
                this.record().field_set_client(this.field_name,
                        this.value_from_id(null, ''));
                this.entry.val('');
                return;
            }
            if (this.has_target(value)) {
                var screen = this.get_screen();
                var m2o_id =
                    this.id_from_value(record.field_get(this.field_name));
                screen.new_group([m2o_id]);
                callback = function(result) {
                    if (result) {
                        var rec_name_prm = screen.current_record.rec_name();
                        rec_name_prm.done(function(name) {
                            var value = this.value_from_id(
                                screen.current_record.id, name);
                            this.record().field_set_client(this.field_name,
                                value, true);
                        }.bind(this));
                    }
                };
                win = new Sao.Window.Form(screen, callback.bind(this), {
                    save_current: true,
                    title: this.attributes.string
                });
                return;
            }
            if (model) {
                var dom;
                var domain = this.field().get_domain(record);
                var context = this.field().get_context(record);
                var text = this.entry.val();
                callback = function(result) {
                    if (!jQuery.isEmptyObject(result)) {
                        var value = this.value_from_id(result[0][0],
                                result[0][1]);
                        this.record().field_set_client(this.field_name,
                                value, true);
                    }
                };
                var parser = new Sao.common.DomainParser();
                win = new Sao.Window.Search(model,
                        callback.bind(this), {
                            sel_multi: false,
                            context: context,
                            domain: domain,
                            view_ids: (this.attributes.view_ids ||
                                '').split(','),
                            views_preload: (this.attributes.views || {}),
                            new_: this.create_access(),
                            search_filter: parser.quote(text),
                            title: this.attributes.string
                        });
                return;
            }
        },
        new_: function(evt) {
            var model = this.get_model();
            if (!model || ! Sao.common.MODELACCESS.get(model).create) {
                return;
            }
            var screen = this.get_screen();
            var callback = function(result) {
                if (result) {
                    var rec_name_prm = screen.current_record.rec_name();
                    rec_name_prm.done(function(name) {
                        var value = this.value_from_id(
                            screen.current_record.id, name);
                        this.record().field_set_client(this.field_name, value);
                    }.bind(this));
                }
            };
            var win = new Sao.Window.Form(screen, callback.bind(this), {
                new_: true,
                save_current: true,
                title: this.attributes.string,
                rec_name: this.entry.val()
            });
        },
        key_press: function(event_) {
            var editable = !this.entry.prop('readonly');
            var activate_keys = [Sao.common.TAB_KEYCODE];
            var delete_keys = [Sao.common.BACKSPACE_KEYCODE,
                Sao.common.DELETE_KEYCODE];
            if (!this.wid_completion) {
                activate_keys.push(Sao.common.RETURN_KEYCODE);
            }

            if (event_.which == Sao.common.F3_KEYCODE &&
                    editable &&
                    this.create_access()) {
                this.new_();
                event_.preventDefault();
            } else if (event_.which == Sao.common.F2_KEYCODE &&
                    this.read_access()) {
                this.edit();
                event_.preventDefault();
            } else if (~activate_keys.indexOf(event_.which) && editable) {
                if (!this.attributes.completion ||
                        this.attributes.completion == "1") {
                    if (this.el.find('.dropdown').hasClass('open')) {
                        return;
                    }
                }
                this.activate();
            } else if (this.has_target(this.record().field_get(
                            this.field_name)) && editable) {
                var value = this.get_text();
                if ((value != this.entry.val()) ||
                        ~delete_keys.indexOf(event_.which)) {
                    this.entry.val('');
                    this.record().field_set_client(this.field_name,
                        this.value_from_id(null, ''));
                }
            }
        },
        activate: function() {
            var model = this.get_model();
            if (!model || !Sao.common.MODELACCESS.get(model).read) {
                return;
            }
            var record = this.record();
            var value = record.field_get(this.field_name);
            var sao_model = new Sao.Model(model);

            if (model && !this.has_target(value)) {
                var text = this.entry.val();
                if (!this._readonly && (text ||
                            this.field().get_state_attrs(this.record())
                            .required)) {
                    var dom;
                    var domain = this.field().get_domain(record);
                    var context = this.field().get_context(record);

                    var callback = function(result) {
                        if (!jQuery.isEmptyObject(result)) {
                            var value = this.value_from_id(result[0][0],
                                result[0][1]);
                            this.record().field_set_client(this.field_name,
                                value, true);
                        } else {
                            this.entry.val('');
                        }
                    };
                    var parser = new Sao.common.DomainParser();
                    var win = new Sao.Window.Search(model,
                            callback.bind(this), {
                                sel_multi: false,
                                context: context,
                                domain: domain,
                                view_ids: (this.attributes.view_ids ||
                                    '').split(','),
                                views_preload: (this.attributes.views ||
                                    {}),
                                new_: this.create_access(),
                                search_filter: parser.quote(text),
                                title: this.attributes.string
                            });
                }
            }
        },
        _set_completion: function() {
            var search = this.el.find('.action-search');
            if (this.read_access()) {
                search.removeClass('disabled');
            } else {
                search.addClass('disabled');
            }
            var create = this.el.find('.action-create');
            if (this.create_access()) {
                create.removeClass('disabled');
            } else {
                create.addClass('disabled');
            }
        },
        _update_completion: function(text) {
            var record = this.record();
            if (!record) {
                return;
            }
            var field = this.field();
            var value = field.get(record);
            if (this.has_target(value)) {
                var id = this.id_from_value(value);
                if ((id !== undefined) && (id > 0)) {
                    return jQuery.when();
                }
            }
            var model = this.get_model();

            return Sao.common.update_completion(
                    this.entry, record, field, model);
        },
        _completion_match_selected: function(value) {
            this.record().field_set_client(this.field_name,
                    this.value_from_id(
                        value.id, value.rec_name), true);
        },
        _completion_action_activated: function(action) {
            if (action == 'search') {
                this.edit();
            } else if (action == 'create') {
                this.new_();
            }
        }
    });

    Sao.View.Form.One2One = Sao.class_(Sao.View.Form.Many2One, {
        class_: 'form-one2one'
    });

    Sao.View.Form.Reference = Sao.class_(Sao.View.Form.Many2One, {
        class_: 'form-reference',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Reference._super.init.call(this, field_name, model,
                attributes);
            this.el.addClass('form-inline');
            this.select = jQuery('<select/>', {
                'class': 'form-control input-sm',
                'aria-label': attributes.string
            });
            this.el.prepend(jQuery('<span/>').text('-'));
            this.el.prepend(this.select);
            this.select.change(this.select_changed.bind(this));
            Sao.common.selection_mixin.init.call(this);
            this.init_selection();
        },
        init_selection: function(key) {
            Sao.common.selection_mixin.init_selection.call(this, key,
                this.set_selection.bind(this));
        },
        update_selection: function(record, field, callback) {
            Sao.common.selection_mixin.update_selection.call(this, record,
                field, function(selection) {
                    this.set_selection(selection);
                    if (callback) {
                        callback();
                    }
                }.bind(this));
        },
        set_selection: function(selection) {
            var select = this.select;
            select.empty();
            selection.forEach(function(e) {
                select.append(jQuery('<option/>', {
                    'value': e[0],
                    'text': e[1]
                }));
            });
        },
        id_from_value: function(value) {
            return parseInt(value.split(',')[1], 10);
        },
        value_from_id: function(id, str) {
            if (!str) {
                str = '';
            }
            return [this.get_model(), [id, str]];
        },
        get_text: function() {
            var record = this.record();
            if (record) {
                return record.field_get_client(this.field_name)[1];
            }
            return '';
        },
        get_model: function() {
            return this.select.val();
        },
        has_target: function(value) {
            if (value === null) {
                return false;
            }
            var model = value.split(',')[0];
            value = value.split(',')[1];
            if (jQuery.isEmptyObject(value)) {
                value = null;
            } else {
                value = parseInt(value, 10);
                if (isNaN(value)) {
                    value = null;
                }
            }
            return (model == this.get_model()) && (value >= 0);
        },
        _set_button_sensitive: function() {
            Sao.View.Form.Reference._super._set_button_sensitive.call(this);
            this.select.prop('disabled', this.entry.prop('readonly'));
        },
        select_changed: function() {
            this.entry.val('');
            var model = this.get_model();
            var value;
            if (model) {
                value = [model, [-1, '']];
            } else {
                value = ['', ''];
            }
            this.record().field_set_client(this.field_name, value);
        },
        set_value: function(record, field) {
            var value;
            if (!this.get_model()) {
                value = this.entry.val();
                if (jQuery.isEmptyObject(value)) {
                    field.set_client(record, null);
                } else {
                    field.set_client(record, ['', value]);
                }
            } else {
                value = field.get_client(record, this.field_name);
                var model, name;
                if (value instanceof Array) {
                    model = value[0];
                    name = value[1];
                } else {
                    model = '';
                    name = '';
                }
                if ((model != this.get_model()) ||
                        (name != this.entry.val())) {
                    field.set_client(record, null);
                    this.entry.val('');
                }
            }
        },
        set_text: function(value) {
            var model;
            if (value) {
                model = value[0];
                value = value[1];
            } else {
                model = null;
                value = null;
            }
            Sao.View.Form.Reference._super.set_text.call(this, value);
            if (model) {
                this.select.val(model);
            } else {
                this.select.val('');
            }
        },
        display: function(record, field) {
            this.update_selection(record, field, function() {
                Sao.View.Form.Reference._super.display.call(this, record, field);
            }.bind(this));
        },
        set_readonly: function(readonly) {
            Sao.View.Form.Reference._super.set_readonly.call(this, readonly);
            this.select.prop('disabled', readonly);
        }
    });

    Sao.View.Form.One2Many = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-one2many',
        init: function(field_name, model, attributes) {
            Sao.View.Form.One2Many._super.init.call(this, field_name, model,
                attributes);

            this._readonly = true;

            this.el = jQuery('<div/>', {
                'class': this.class_ + ' panel panel-default'
            });
            this.menu = jQuery('<div/>', {
                'class': this.class_ + '-menu panel-heading'
            });
            this.el.append(this.menu);

            var label = jQuery('<label/>', {
                'class': this.class_ + '-string',
                text: attributes.string
            });
            this.menu.append(label);

            label.uniqueId();
            this.el.uniqueId();
            this.el.attr('aria-labelledby', label.attr('id'));
            label.attr('for', this.el.attr('id'));

            var toolbar = jQuery('<div/>', {
                'class': this.class_ + '-toolbar'
            });
            this.menu.append(toolbar);

            var group = jQuery('<div/>', {
                'class': 'input-group input-group-sm'
            }).appendTo(toolbar);

            this.wid_text = jQuery('<input/>', {
                type: 'text',
                'class': 'form-control input-sm'
            }).appendTo(group);
            this.wid_text.hide();

            var buttons = jQuery('<div/>', {
                'class': 'input-group-btn'
            }).appendTo(group);

            if (attributes.add_remove) {
                this.wid_text.show();
                // TODO add completion
                //
                this.but_add = jQuery('<button/>', {
                    'class': 'btn btn-default btn-sm',
                    'type': 'button',
                    'aria-label': Sao.i18n.gettext('Add')
                }).append(jQuery('<span/>', {
                    'class': 'glyphicon glyphicon-plus'
                })).appendTo(buttons);
                this.but_add.click(this.add.bind(this));

                this.but_remove = jQuery('<button/>', {
                    'class': 'btn btn-default btn-sm',
                    'type': 'button',
                    'aria-label': Sao.i18n.gettext('Remove')
                }).append(jQuery('<span/>', {
                    'class': 'glyphicon glyphicon-minus'
                })).appendTo(buttons);
                this.but_remove.click(this.remove.bind(this));
            }

            this.but_new = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'aria-label': Sao.i18n.gettext('New')
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-edit'
            })).appendTo(buttons);
            this.but_new.click(this.new_.bind(this));

            this.but_open = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'aria-label': Sao.i18n.gettext('Open')
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-folder-open'
            })).appendTo(buttons);
            this.but_open.click(this.open.bind(this));

            this.but_del = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'aria-label': Sao.i18n.gettext('Delete')
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-trash'
            })).appendTo(buttons);
            this.but_del.click(this.delete_.bind(this));

            this.but_undel = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'aria-label': Sao.i18n.gettext('Undelete')
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-repeat'
            })).appendTo(buttons);
            this.but_undel.click(this.undelete.bind(this));

            this.but_previous = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'aria-label': Sao.i18n.gettext('Previous')
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-chevron-left'
            })).appendTo(buttons);
            this.but_previous.click(this.previous.bind(this));

            this.label = jQuery('<span/>', {
                'class': 'btn'
            }).appendTo(buttons);
            this.label.text('(0, 0)');

            this.but_next = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'aria-label': Sao.i18n.gettext('Next')
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-chevron-right'
            })).appendTo(buttons);
            this.but_next.click(this.next.bind(this));

            this.but_switch = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'aria-label': Sao.i18n.gettext('Switch')
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-list-alt'
            })).appendTo(buttons);
            this.but_switch.click(this.switch_.bind(this));

            this.content = jQuery('<div/>', {
                'class': this.class_ + '-content panel-body'
            });
            this.el.append(this.content);

            var modes = (attributes.mode || 'tree,form').split(',');
            this.screen = new Sao.Screen(attributes.relation, {
                mode: modes,
                view_ids: (attributes.view_ids || '').split(','),
                views_preload: attributes.views || {},
                row_activate: this.activate.bind(this),
                exclude_field: attributes.relation_field || null,
                pre_validate: attributes.pre_validate
            });
            this.screen.pre_validate = attributes.pre_validate == 1;
            this.prm = this.screen.switch_view(modes[0]).done(function() {
                this.content.append(this.screen.screen_container.el);
            }.bind(this));

            // TODO key_press

            this.but_switch.prop('disabled', this.screen.number_of_views() <= 0);
        },
        set_readonly: function(readonly) {
            this._readonly = readonly;
            this._set_button_sensitive();
        },
        _set_button_sensitive: function() {
            var access = Sao.common.MODELACCESS.get(this.screen.model_name);
            var size_limit, o2m_size;
            var record = this.record();
            var field = this.field();
            if (record && field) {
                var field_size = record.expr_eval(this.attributes.size);
                o2m_size = field.get_eval(record);
                size_limit = (((field_size !== undefined) &&
                            (field_size !== null)) &&
                        (o2m_size >= field_size >= 0));
            } else {
                o2m_size = null;
                size_limit = false;
            }
            var create = this.attributes.create;
            if (create === undefined) {
                create = true;
            }
            this.but_new.prop('disabled', this._readonly || !create ||
                    size_limit || !access.create);

            var delete_ = this.attributes['delete'];
            if (delete_ === undefined) {
                delete_ = true;
            }
            // TODO position
            this.but_del.prop('disabled', this._readonly || !delete_ ||
                    !access['delete']);
            this.but_undel.prop('disabled', this._readonly || size_limit);
            this.but_open.prop('disabled', !access.read);
            // TODO but_next, but_previous
            if (this.attributes.add_remove) {
                this.wid_text.prop('disabled', this._readonly);
                this.but_add.prop('disabled', this._readonly || size_limit ||
                        !access.write || !access.read);
                this.but_remove.prop('disabled', this._readonly ||
                        !access.write || !access.read);
            }
        },
        display: function(record, field) {
            Sao.View.Form.One2Many._super.display.call(this, record, field);

            this._set_button_sensitive();

            this.prm.done(function() {
                if (!record) {
                    return;
                }
                if (field === undefined) {
                    this.screen.new_group();
                    this.screen.set_current_record(null);
                    this.screen.group.parent = null;
                    this.screen.display();
                    return;
                }

                var new_group = record.field_get_client(this.field_name);
                if (new_group != this.screen.group) {
                    this.screen.set_group(new_group);
                    if ((this.screen.current_view.view_type == 'tree') &&
                            this.screen.current_view.editable) {
                        this.screen.set_current_record(null);
                    }
                }
                var domain = [];
                var size_limit = null;
                if (record) {
                    domain = field.get_domain(record);
                    size_limit = record.expr_eval(this.attributes.size);
                }
                if (!Sao.common.compare(this.screen.domain, domain)) {
                    this.screen.domain = domain;
                }
                this.screen.size_limit = size_limit;
                this.screen.display();
            }.bind(this));
        },
        focus: function() {
            if (this.wid_text.is(':visible')) {
                this.wid_text.focus();
            }
        },
        activate: function(event_) {
            this.edit();
        },
        add: function(event_) {
            var access = Sao.common.MODELACCESS.get(this.screen.model_name);
            if (!access.write || !access.read) {
                return;
            }
            this.view.set_value();
            var domain = this.field().get_domain(this.record());
            var context = this.field().get_context(this.record());
            domain = [domain,
                this.record().expr_eval(this.attributes.add_remove)];
            var removed_ids = this.field().get_removed_ids(this.record());
            domain = ['OR', domain, ['id', 'in', removed_ids]];
            var text = this.wid_text.val();

            // TODO sequence

            var callback = function(result) {
                var prm = jQuery.when();
                if (!jQuery.isEmptyObject(result)) {
                    var ids = [];
                    var i, len;
                    for (i = 0, len = result.length; i < len; i++) {
                        ids.push(result[i][0]);
                    }
                    this.screen.group.load(ids, true);
                    prm = this.screen.display();
                }
                prm.done(function() {
                    this.screen.set_cursor();
                }.bind(this));
                this.wid_text.val('');
            }.bind(this);
            var parser = new Sao.common.DomainParser();
            var win = new Sao.Window.Search(this.attributes.relation,
                    callback, {
                        sel_multi: true,
                        context: context,
                        domain: domain,
                        view_ids: (this.attributes.view_ids ||
                                '').split(','),
                        views_preload: this.attributes.views || {},
                        new_: !this.but_new.prop('disabled'),
                        search_filter: parser.quote(text),
                        title: this.attributes.string
                    });
        },
        remove: function(event_) {
            var access = Sao.common.MODELACCESS.get(this.screen.model_name);
            if (!access.write || !access.read) {
                return;
            }
            this.screen.remove(false, true, false);
        },
        new_: function(event_) {
            if (!Sao.common.MODELACCESS.get(this.screen.model_name).create) {
                return;
            }
            this.validate().done(function() {
                if (this.attributes.product) {
                    this.new_product();
                } else {
                    this.new_single();
                }
            }.bind(this));
        },
        new_single: function() {
            var context = jQuery.extend({},
                    this.field().get_context(this.record()));
            // TODO sequence
            if (this.screen.current_view.type == 'form' ||
                    this.screen.current_view.editable) {
                this.screen.new_();
                this.screen.current_view.el.prop('disabled', false);
            } else {
                var record = this.record();
                var field_size = record.expr_eval(
                    this.attributes.size) || -1;
                field_size -= this.field().get_eval(record);
                var win = new Sao.Window.Form(this.screen, function() {}, {
                    new_: true,
                    many: field_size,
                    context: context,
                    title: this.attributes.string
                });
            }
        },
        new_product: function() {
            var fields = this.attributes.product.split(',');
            var product = {};
            var screen = this.screen;

            screen.new_(false).then(function(first) {
                first.default_get().then(function(default_) {
                    first.set_default(default_);

                    var search_set = function() {
                        if (jQuery.isEmptyObject(fields)) {
                            return make_product();
                        }
                        var field = screen.model.fields[fields.pop()];
                        var relation = field.description.relation;
                        if (!relation) {
                            search_set();
                        }

                        var domain = field.get_domain(first);
                        var context = field.get_context(first);

                        var callback = function(result) {
                            if (!jQuery.isEmptyObject(result)) {
                                product[field.name] = result;
                            }
                            search_set();
                        };
                        var win_search = new Sao.Window.Search(relation,
                                callback, {
                                    sel_multi: true,
                                    context: context,
                                    domain: domain,
                                    search_filter: '',
                                    title: this.attributes.string

                        });
                    }.bind(this);

                    var make_product = function() {
                        if (jQuery.isEmptyObject(product)) {
                            screen.group.remove(first, true);
                            return;
                        }

                        var fields = Object.keys(product);
                        var values = fields.map(function(field) {
                            return product[field];
                        });
                        Sao.common.product(values).forEach(function(values) {
                            var set_default = function(record) {
                                var default_value = jQuery.extend({}, default_);
                                fields.forEach(function(field, i) {
                                    default_value[field] = values[i][0];
                                    default_value[field + '.rec_name'] = values[i][1];
                                });
                                record.set_default(default_value);
                            };

                            var record;
                            if (first) {
                                set_default(first);
                                first = null;
                            } else {
                                screen.new_(false).then(set_default);
                            }
                        });
                    };

                    search_set();
                }.bind(this));
            }.bind(this));
        },
        open: function(event_) {
            this.edit();
        },
        delete_: function(event_) {
            if (!Sao.common.MODELACCESS.get(this.screen.model_name)['delete']) {
                return;
            }
            this.screen.remove(false, false, false);
        },
        undelete: function(event_) {
            this.screen.unremove();
        },
        previous: function(event_) {
            this.validate().done(function() {
                this.screen.display_previous();
            }.bind(this));
        },
        next: function(event_) {
            this.validate().done(function() {
                this.screen.display_next();
            }.bind(this));
        },
        switch_: function(event_) {
            this.screen.switch_view();
        },
        edit: function() {
            if (!Sao.common.MODELACCESS.get(this.screen.model_name).read) {
                return;
            }
            this.validate().done(function() {
                var record = this.screen.current_record;
                if (record) {
                    var win = new Sao.Window.Form(this.screen, function() {},
                        {title: this.attributes.string});
                }
            }.bind(this));
        },
        validate: function() {
            var prm = jQuery.Deferred();
            this.view.set_value();
            var record = this.screen.current_record;
            if (record) {
                var fields = this.screen.current_view.get_fields();
                record.validate(fields).then(function(validate) {
                    if (!validate) {
                        this.screen.display(true);
                        prm.reject();
                        return;
                    }
                    if (this.screen.pre_validate) {
                        return record.pre_validate().then(function(validate) {
                            if (!validate) {
                                prm.reject();
                                return;
                            }
                            prm.resolve();
                        });
                    }
                    prm.resolve();
                }.bind(this));
            } else {
                prm.resolve();
            }
            return prm;
        },
        set_value: function(record, field) {
            this.screen.save_tree_state();
        }
    });

    Sao.View.Form.Many2Many = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-many2many',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Many2Many._super.init.call(this, field_name, model,
                attributes);

            this._readonly = true;

            this.el = jQuery('<div/>', {
                'class': this.class_ + ' panel panel-default'
            });
            this.menu = jQuery('<div/>', {
                'class': this.class_ + '-menu panel-heading'
            });
            this.el.append(this.menu);

            var label = jQuery('<label/>', {
                'class': this.class_ + '-string',
                text: attributes.string
            });
            this.menu.append(label);

            label.uniqueId();
            this.el.uniqueId();
            this.el.attr('aria-labelledby', label.attr('id'));
            label.attr('for', this.el.attr('id'));

            var toolbar = jQuery('<div/>', {
                'class': this.class_ + '-toolbar'
            });
            this.menu.append(toolbar);

            var group = jQuery('<div/>', {
                'class': 'input-group input-group-sm'
            }).appendTo(toolbar);
            this.entry = jQuery('<input/>', {
                type: 'text',
                'class': 'form-control input-sm'
            }).appendTo(group);
            // Use keydown to not receive focus-in TAB
            this.entry.on('keydown', this.key_press.bind(this));

            // TODO completion

            var buttons = jQuery('<div/>', {
                'class': 'input-group-btn'
            }).appendTo(group);
            this.but_add = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'aria-label': Sao.i18n.gettext('Add')
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-plus'
            })).appendTo(buttons);
            this.but_add.click(this.add.bind(this));

            this.but_remove = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'aria-label': Sao.i18n.gettext('Remove')
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-minus'
            })).appendTo(buttons);
            this.but_remove.click(this.remove.bind(this));

            this.content = jQuery('<div/>', {
                'class': this.class_ + '-content panel-body'
            });
            this.el.append(this.content);

            this.screen = new Sao.Screen(attributes.relation, {
                mode: ['tree'],
                view_ids: (attributes.view_ids || '').split(','),
                views_preload: attributes.views || {},
                row_activate: this.activate.bind(this)
            });
            this.prm = this.screen.switch_view('tree').done(function() {
                this.content.append(this.screen.screen_container.el);
            }.bind(this));
        },
        set_readonly: function(readonly) {
            this._readonly = readonly;
            this._set_button_sensitive();
        },
        _set_button_sensitive: function() {
            var size_limit = false;
            if (this.record() && this.field()) {
                // TODO
            }

            this.entry.prop('disabled', this._readonly);
            this.but_add.prop('disabled', this._readonly || size_limit);
            // TODO position
            this.but_remove.prop('disabled', this._readonly);
        },
        display: function(record, field) {
            Sao.View.Form.Many2Many._super.display.call(this, record, field);

            this.prm.done(function() {
                if (!record) {
                    return;
                }
                if (field === undefined) {
                    this.screen.new_group();
                    this.screen.set_current_record(null);
                    this.screen.group.parent = null;
                    this.screen.display();
                    return;
                }
                var new_group = record.field_get_client(this.field_name);
                if (new_group != this.screen.group) {
                    this.screen.set_group(new_group);
                }
                this.screen.display();
            }.bind(this));
        },
        focus: function() {
            this.entry.focus();
        },
        activate: function() {
            this.edit();
        },
        add: function() {
            var dom;
            var domain = this.field().get_domain(this.record());
            var context = this.field().get_context(this.record());
            var value = this.entry.val();

            var callback = function(result) {
                if (!jQuery.isEmptyObject(result)) {
                    var ids = [];
                    var i, len;
                    for (i = 0, len = result.length; i < len; i++) {
                        ids.push(result[i][0]);
                    }
                    this.screen.group.load(ids, true);
                    this.screen.display();
                }
                this.entry.val('');
            }.bind(this);
            var parser = new Sao.common.DomainParser();
            var win = new Sao.Window.Search(this.attributes.relation,
                    callback, {
                        sel_multi: true,
                        context: context,
                        domain: domain,
                        view_ids: (this.attributes.view_ids ||
                            '').split(','),
                        views_preload: this.attributes.views || {},
                        new_: this.attributes.create,
                        search_filter: parser.quote(value),
                        title: this.attributes.string
                    });
        },
        remove: function() {
            this.screen.remove(false, true, false);
        },
        key_press: function(event_) {
            var activate_keys = [Sao.common.TAB_KEYCODE];
            if (!this.wid_completion) {
                activate_keys.push(Sao.common.RETURN_KEYCODE);
            }

            if (event_.which == Sao.common.F3_KEYCODE) {
                this.new_();
                event_.preventDefault();
            } else if (event_.which == Sao.common.F2_KEYCODE) {
                this.add();
                event_.preventDefault();
            } else if (~activate_keys.indexOf(event_.which) && this.entry.val()) {
                this.add();
            }
        },
        _get_screen_form: function() {
            var domain = this.field().get_domain(this.record());
            var add_remove = this.record().expr_eval(
                    this.attributes.add_remove);
            if (!jQuery.isEmptyObject(add_remove)) {
                domain = [domain, add_remove];
            }
            var context = this.field().get_context(this.record());
            var view_ids = (this.attributes.view_ids || '').split(',');
            if (!jQuery.isEmptyObject(view_ids)) {
                // Remove the first tree view as mode is form only
                view_ids.shift();
            }
            return new Sao.Screen(this.attributes.relation, {
                'domain': domain,
                'view_ids': view_ids,
                'mode': ['form'],
                'views_preload': this.attributes.views,
                'context': context
            });
        },
        edit: function() {
            if (jQuery.isEmptyObject(this.screen.current_record)) {
                return;
            }
            // Create a new screen that is not linked to the parent otherwise
            // on the save of the record will trigger the save of the parent
            var screen = this._get_screen_form();
            screen.new_group([this.screen.current_record.id]);
            var callback = function(result) {
                if (result) {
                    screen.current_record.save().done(function() {
                        // Force a reload on next display
                        this.screen.current_record.cancel();
                    }.bind(this));
                }
            }.bind(this);
            screen.switch_view().done(function() {
                new Sao.Window.Form(screen, callback,
                    {title: this.attributes.string});
            }.bind(this));
        },
        new_: function() {
            var screen = this._get_screen_form();
            var callback = function(result) {
                if (result) {
                    var record = screen.current_record;
                    this.screen.group.load([record.id], true);
                }
                this.entry.val('');
            }.bind(this);
            screen.switch_view().done(function() {
                new Sao.Window.Form(screen, callback, {
                    'new_': true,
                    'save_current': true,
                    title: this.attributes.string,
                    rec_name: this.entry.val()
                });
            }.bind(this));
        }
    });

    Sao.View.Form.BinaryMixin = Sao.class_(Sao.View.Form.Widget, {
        init: function(field_name, model, attributes) {
            Sao.View.Form.BinaryMixin._super.init.call(
                    this, field_name, model, attributes);
            this.filename = attributes.filename || null;
        },
        toolbar: function(class_) {
            var group = jQuery('<div/>', {
                'class': class_,
                'role': 'group'
            });

            this.but_select = jQuery('<button/>', {
                'class': 'btn btn-default',
                'type': 'button'
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-search'
            })).appendTo(group);
            this.but_select.click(this.select.bind(this));

            if (this.filename) {
                this.but_open = jQuery('<button/>', {
                    'class': 'btn btn-default',
                    'type': 'button'
                }).append(jQuery('<span/>', {
                    'class': 'glyphicon glyphicon-folder-open'
                })).appendTo(group);
                this.but_open.click(this.open.bind(this));
            }

            this.but_save_as = jQuery('<button/>', {
                'class': 'btn btn-default',
                'type': 'button'
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-save'
            })).appendTo(group);
            this.but_save_as.click(this.save_as.bind(this));

            this.but_clear = jQuery('<button/>', {
                'class': 'btn btn-default',
                'type': 'button'
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-erase'
            })).appendTo(group);
            this.but_clear.click(this.clear.bind(this));

            return group;
        },
        filename_field: function() {
            var record = this.record();
            if (record) {
                return record.model.fields[this.filename];
            }
        },
        select: function() {
            var record = this.record();

            var close = function() {
                file_dialog.modal.on('hidden.bs.modal', function(event) {
                    jQuery(this).remove();
                });
                file_dialog.modal.modal('hide');
            };

            var save_file = function() {
                var reader = new FileReader();
                reader.onload = function(evt) {
                    var uint_array = new Uint8Array(reader.result);
                    this.field().set_client(record, uint_array);
                }.bind(this);
                reader.onloadend = function(evt) {
                    close();
                };
                var file = file_selector[0].files[0];
                reader.readAsArrayBuffer(file);
                if (this.filename) {
                    this.filename_field().set_client(record, file.name);
                }
            }.bind(this);

            var file_dialog = new Sao.Dialog(
                    Sao.i18n.gettext('Select'), 'file-dialog');
            file_dialog.footer.append(jQuery('<button/>', {
                'class': 'btn btn-link',
                'type': 'button'
            }).append(Sao.i18n.gettext('Cancel')).click(close))
            .append(jQuery('<button/>', {
                'class': 'btn btn-primary',
                'type': 'submit'
            }).append(Sao.i18n.gettext('OK')).click(save_file));
            file_dialog.content.submit(function(e) {
                save_file();
                e.preventDefault();
            });

            var file_selector = jQuery('<input/>', {
                type: 'file'
            }).appendTo(file_dialog.body);

            file_dialog.modal.modal('show');
        },
        open: function() {
            var params = {};
            var filename_field = this.filename_field();
            if (filename_field) {
                var filename = filename_field.get_client(this.record());
                // Valid mimetype will make the browser directly open the file
                params.mimetype = Sao.common.guess_mimetype(filename);
            }
            this.save_as(params);
        },
        save_as: function(params) {
            var mimetype = params.mimetype || 'application/octet-binary';
            var field = this.field();
            var record = this.record();
            field.get_data(record).done(function(data) {
                var blob = new Blob([data], {type: mimetype});
                var blob_url = window.URL.createObjectURL(blob);
                if (this.blob_url) {
                    window.URL.revokeObjectURL(this.blob_url);
                }
                this.blob_url = blob_url;
                window.open(blob_url);
            }.bind(this));
        },
        clear: function() {
	    var filename_field = this.filename_field();
            if (filename_field) {
                filename_field.set_client(this.record(), null);
            }
            this.field().set_client(this.record(), null);
        }
    });

    Sao.View.Form.Binary = Sao.class_(Sao.View.Form.BinaryMixin, {
        class_: 'form-binary',
        blob_url: '',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Binary._super.init.call(this, field_name, model,
                attributes);

            this.el = jQuery('<div/>', {
                'class': this.class_
            });

            if (this.filename && attributes.filename_visible) {
                this.text = jQuery('<input/>', {
                    type: 'input',
                    'class': 'form-control input-sm'
                }).appendTo(this.el);
                this.text.change(this.focus_out.bind(this));
                // Use keydown to not receive focus-in TAB
                this.text.on('keydown', this.key_press.bind(this));
            }

            var group = jQuery('<div/>', {
                'class': 'input-group input-group-sm'
            }).appendTo(this.el);
            this.size = jQuery('<input/>', {
                type: 'input',
                'class': 'form-control input-sm',
                'readonly': true
            }).appendTo(group);

            this.toolbar('input-group-btn').appendTo(group);
        },
        display: function(record, field) {
            Sao.View.Form.Binary._super.display.call(this, record, field);
            if (!field) {
                this.size.val('');
                if (this.filename) {
                    this.but_open.button('disable');
                }
                if (this.text) {
                    this.text.val('');
                }
                this.but_save_as.button('disable');
                return;
            }
            var size = field.get_size(record);
            var button_sensitive;
            if (size) {
                button_sensitive = 'enable';
            } else {
                button_sensitive = 'disable';
            }

            if (this.filename) {
                if (this.text) {
                    this.text.val(this.filename_field().get(record) || '');
                }
                this.but_open.button(button_sensitive);
            }
            this.size.val(Sao.common.humanize(size));
            this.but_save_as.button(button_sensitive);
        },
        key_press: function(evt) {
            var editable = !this.wid_text.prop('readonly');
            if (evt.which == Sao.common.F3_KEYCODE && editable) {
                this.new_();
                evt.preventDefault();
            } else if (evt.which == Sao.common.F2_KEYCODE) {
                this.open();
                evt.preventDefault();
            }
        },
        set_value: function(record, field) {
            if (this.text) {
                this.filename_field().set_client(record,
                        this.text.val() || '');
            }
        },
        set_readonly: function(readonly) {
            if (readonly) {
                this.but_select.hide();
                this.but_clear.hide();

            } else {
                this.but_select.show();
                this.but_clear.show();
            }
            if (this.wid_text) {
                this.wid_text.prop('readonly', readonly);
            }
        }
    });

    Sao.View.Form.MultiSelection = Sao.class_(Sao.View.Form.Selection, {
        class_: 'form-multiselection',
        init: function(field_name, model, attributes) {
            this.nullable_widget = false;
            Sao.View.Form.MultiSelection._super.init.call(this, field_name,
                model, attributes);
            this.select.prop('multiple', true);
        },
        display_update_selection: function(record, field) {
            var i, len, element;
            this.update_selection(record, field, function() {
                if (!field) {
                    return;
                }
                var value = [];
                var group = record.field_get_client(this.field_name);
                for (i = 0, len = group.length; i < len; i++) {
                    element = group[i];
                    if (!~group.record_removed.indexOf(element) &&
                        !~group.record_deleted.indexOf(element)) {
                            value.push(element.id);
                    }
                }
                this.el.val(value);
            }.bind(this));
        },
        set_value: function(record, field) {
            var value = this.el.val();
            if (value) {
                value = value.map(function(e) { return parseInt(e, 10); });
            } else {
                value = [];
            field.set_client(record, value);
            }
        }
    });

    Sao.View.Form.Image = Sao.class_(Sao.View.Form.BinaryMixin, {
        class_: 'form-image',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Image._super.init.call(
                    this, field_name, model, attributes);
            this.height = parseInt(attributes.height || 100, 10);
            this.width = parseInt(attributes.width || 300, 10);

            this.el = jQuery('<div/>');
            this.image = jQuery('<img/>', {
                'class': 'center-block'
            }).appendTo(this.el);
            this.image.css('max-height', this.height);
            this.image.css('max-width', this.width);
            this.image.css('height', 'auto');
            this.image.css('width', 'auto');

            var group = this.toolbar('btn-group');
            if (!attributes.readonly) {
                jQuery('<div/>', {
                    'class': 'text-center'
                }).append(group).appendTo(this.el);
            }
            this.update_img();
        },
        set_readonly: function(readonly) {
            [this.but_select, this.but_open, this.but_save_as, this.but_clear]
                .forEach(function(button) {
                    if (button) {
                        button.prop('disable', readonly);
                    }
                });
        },
        clear: function() {
            Sao.View.Form.Image._super.clear.call(this);
            this.update_img();
        },
        update_img: function() {
            var value;
            var record = this.record();
            if (record) {
                value = record.field_get_client(this.field_name);
            }
            if (value) {
                if (value > Sao.common.BIG_IMAGE_SIZE) {
                    value = jQuery.when(null);
                } else {
                    value = record.model.fields[this.field_name]
                        .get_data(record);
                }
            } else {
                value = jQuery.when(null);
            }
            value.done(function(data) {
                var url, blob;
                if (!data) {
                    url = null;
                } else {
                    blob = new Blob([data]);
                    url = window.URL.createObjectURL(blob);
                }
                this.image.attr('src', url);
            }.bind(this));
        },
        display: function(record, field) {
            Sao.View.Form.Image._super.display.call(this, record, field);
            this.update_img();
        }
    });

    Sao.View.Form.URL = Sao.class_(Sao.View.Form.Char, {
        class_: 'form-url',
        init: function(field_name, model, attributes) {
            Sao.View.Form.URL._super.init.call(
                    this, field_name, model, attributes);
            this.button = jQuery('<a/>', {
                'class': 'btn btn-default',
                'target': '_new'
            }).appendTo(jQuery('<span/>', {
                'class': 'input-group-btn'
            }).appendTo(this.group));
            this.icon = jQuery('<img/>').appendTo(this.button);
            this.set_icon();
        },
        display: function(record, field) {
            Sao.View.Form.URL._super.display.call(this, record, field);
            var url = '';
            if (record) {
                url = record.field_get_client(this.field_name);
            }
            this.set_url(url);
            if (record & this.attributes.icon) {
                var icon = this.attributes.icon;
                var value;
                if (icon in record.model.fields) {
                    value = record.field_get_client(icon);
                } else {
                    value = icon;
                }
                this.set_icon(value);
            }
        },
        set_icon: function(value) {
            value = value || 'tryton-web-browser';
            Sao.common.ICONFACTORY.register_icon(value).done(function(url) {
                this.icon.attr('src', url);
            }.bind(this));
        },
        set_url: function(value) {
            this.button.attr('href', value);
        },
        set_readonly: function(readonly) {
            Sao.View.Form.URL._super.set_readonly.call(this, readonly);
            if (readonly) {
                this.input.hide();
                this.button.removeClass('btn-default');
                this.button.addClass('btn-link');
            } else {
                this.input.show();
                this.button.removeClass('btn-link');
                this.button.addClass('btn-default');
            }
        }
    });

    Sao.View.Form.Email = Sao.class_(Sao.View.Form.URL, {
        class_: 'form-email',
        set_url: function(value) {
            Sao.View.Form.Email._super.set_url.call(this, 'mailto:' + value);
        }
    });

    Sao.View.Form.CallTo = Sao.class_(Sao.View.Form.URL, {
        class_: 'form-callto',
        set_url: function(value) {
            Sao.View.Form.CallTo._super.set_url.call(this, 'callto:' + value);
        }
    });

    Sao.View.Form.SIP = Sao.class_(Sao.View.Form.URL, {
        class_: 'form-sip',
        set_url: function(value) {
            Sao.View.Form.SIP._super.set_url.call(this, 'sip:' + value);
        }
    });

    Sao.View.Form.ProgressBar = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-char',
        init: function(field_name, model, attributes) {
            Sao.View.Form.ProgressBar._super.init.call(
                    this, field_name, model, attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_ + ' progress'
            });
            this.progressbar = jQuery('<div/>', {
                'class': 'progress-bar',
                'role': 'progressbar',
                'aria-valuemin': 0,
                'aria-valuemax': 100
            }).appendTo(this.el);
            this.progressbar.css('min-width: 2em');
        },
        display: function(record, field) {
            Sao.View.Form.ProgressBar._super.display.call(
                    this, record, field);
            var value, text;
            if (!field) {
                value = 0;
                text = '';
            } else {
                value = field.get(record);
                text = field.get_client(record, 100);
                if (text) {
                    text = Sao.i18n.gettext('%1%', text);
                }
            }
            this.progressbar.attr('aria-valuenow', value * 100);
            this.progressbar.css('width', value * 100 + '%');
            this.progressbar.text(text);
        }
    });

    Sao.View.Form.Dict = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-dict',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Dict._super.init.call(
                    this, field_name, model, attributes);

            this.schema_model = new Sao.Model(attributes.schema_model);
            this.keys = {};
            this.fields = {};
            this.rows = {};

            this.el = jQuery('<div/>', {
                'class': this.class_ + ' panel panel-default'
            });
            var heading = jQuery('<div/>', {
                'class': this.class_ + '-heading panel-heading'
            }).appendTo(this.el);
            var label = jQuery('<label/>', {
                'class': this.class_ + '-string',
                'text': attributes.string
            }).appendTo(heading);

            label.uniqueId();
            this.el.uniqueId();
            this.el.attr('aria-labelledby', label.attr('id'));
            label.attr('for', this.el.attr('id'));

            var body = jQuery('<div/>', {
                'class': this.class_ + '-body panel-body'
            }).appendTo(this.el);
            this.container = jQuery('<div/>', {
                'class': this.class_ + '-container'
            }).appendTo(body);

            var group = jQuery('<div/>', {
                'class': 'input-group input-group-sm'
            }).appendTo(jQuery('<div>', {
                'class': 'col-md-12'
            }).appendTo(jQuery('<div/>', {
                'class': 'row'
            }).appendTo(jQuery('<div/>', {
                'class': 'container-fluid'
            }).appendTo(body))));
            this.wid_text = jQuery('<input/>', {
                'type': 'text',
                'class': 'form-control input-sm'
            }).appendTo(group);

            // TODO completion

            this.but_add = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'aria-label': Sao.i18n.gettext('Add')
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-plus'
            })).appendTo(jQuery('<div/>', {
                'class': 'input-group-btn'
            }).appendTo(group));
            this.but_add.click(this.add.bind(this));

            this._readonly = false;
            this._record_id = null;
        },
        add: function() {
            var context = this.field().get_context(this.record());
            var value = this.wid_text.val();
            var domain = this.field().get_domain(this.record());

            var callback = function(result) {
                if (!jQuery.isEmptyObject(result)) {
                    var ids = result.map(function(e) {
                        return e[0];
                    });
                    this.add_new_keys(ids);
                }
                this.wid_text.val('');
            }.bind(this);

            var parser = new Sao.common.DomainParser();
            var win = new Sao.Window.Search(this.schema_model.name,
                    callback, {
                        sel_multi: true,
                        context: context,
                        domain: domain,
                        new_: false,
                        search_filter: parser.quote(value),
                        title: this.attributes.string
                    });
        },
        add_new_keys: function(ids) {
            var context = this.field().get_context(this.record());
            this.schema_model.execute('get_keys', [ids], context)
                .then(function(new_fields) {
                    var focus = false;
                    new_fields.forEach(function(new_field) {
                        if (this.fields[new_field.name]) {
                            return;
                        }
                        this.keys[new_field.name] = new_field;
                        this.add_line(new_field.name);
                        if (!focus) {
                            this.fields[new_field.name].input.focus();
                            focus = true;
                        }
                    }.bind(this));
                }.bind(this));
        },
        remove: function(key, modified) {
            if (modified === undefined) {
                modified = true;
            }
            delete this.fields[key];
            this.rows[key].remove();
            delete this.rows[key];
            if (modified) {
                this.set_value(this.record(), this.field());
            }
        },
        set_value: function(record, field) {
            field.set_client(record, this.get_value());
        },
        get_value: function() {
            var value = {};
            for (var key in this.fields) {
                var widget = this.fields[key];
                value[key] = widget.get_value();
            }
            return value;
        },
        set_readonly: function(readonly) {
            this._readonly = readonly;
            this._set_button_sensitive();
            for (var key in this.fields) {
                var widget = this.fields[key];
                widget.set_readonly(readonly);
            }
            this.wid_text.prop('disabled', readonly);
        },
        _set_button_sensitive: function() {
            var create = this.attributes.create;
            if (create === undefined) {
                create = true;
            }
            var delete_ = this.attributes['delete'];
            if (delete_ === undefined) {
                delete_ = true;
            }
            this.but_add.prop('disabled', this._readonly || !create);
            for (var key in this.fields) {
                var button = this.fields[key].button;
                button.prop('disabled', this._readonly || !delete_);
            }
        },
        add_line: function(key) {
            var field, row;
            this.fields[key] = field = new (this.get_entries(
                        this.keys[key].type_))(key, this);
            this.rows[key] = row = jQuery('<div/>', {
                'class': 'row'
            });
            // TODO RTL
            var text = this.keys[key].string + Sao.i18n.gettext(':');
            var label = jQuery('<label/>', {
                'text': text
            }).appendTo(jQuery('<div/>', {
                'class': 'dict-label col-md-4'
            }).appendTo(row));

            field.el.addClass('col-md-8').appendTo(row);

            label.uniqueId();
            field.labelled.uniqueId();
            field.labelled.attr('aria-labelledby', label.attr('id'));
            label.attr('for', field.labelled.attr('id'));

            field.button.click(function() {
                this.remove(key, true);
            }.bind(this));

            row.appendTo(this.container);
        },
        add_keys: function(keys) {
            var context = this.field().get_context(this.record());
            var domain = this.field().get_domain(this.record());
            var batchlen = Math.min(10, Sao.config.limit);
            keys = jQuery.extend([], keys);

            var get_keys = function(key_ids) {
                return this.schema_model.execute('get_keys',
                        [key_ids], context).then(update_keys);
            }.bind(this);
            var update_keys = function(values) {
                for (var i = 0, len = values.length; i < len; i++) {
                    var k = values[i];
                    this.keys[k.name] = k;
                }
            }.bind(this);

            var prms = [];
            while (keys.length > 0) {
                var sub_keys = keys.splice(0, batchlen);
                prms.push(this.schema_model.execute('search',
                            [[['name', 'in', sub_keys], domain],
                            0, Sao.config.limit, null], context)
                        .then(get_keys));
            }
            return jQuery.when.apply(jQuery, prms);
        },
        display: function(record, field) {
            Sao.View.Form.Dict._super.display.call(this, record, field);

            if (!field) {
                return;
            }

            var record_id = record ? record.id : null;
            var key;

            if (record_id != this._record_id) {
                for (key in this.fields) {
                    this.remove(key, false);
                }
                this._record_id = record_id;
            }

            var value = field.get_client(record);
            var new_key_names = Object.keys(value).filter(function(e) {
                return !this.keys[e];
            }.bind(this));

            var prm;
            if (!jQuery.isEmptyObject(new_key_names)) {
                prm = this.add_keys(new_key_names);
            } else {
                prm = jQuery.when();
            }
            prm.then(function() {
                var i, len, key;
                var keys = Object.keys(value).sort();
                for (i = 0, len = keys.length; i < len; i++) {
                    key = keys[i];
                    var val = value[key];
                    if (!this.keys[key]) {
                        continue;
                    }
                    if (!this.fields[key]) {
                        this.add_line(key);
                    }
                    var widget = this.fields[key];
                    widget.set_value(val);
                    widget.set_readonly(this._readonly);
                }
                var removed_key_names = Object.keys(this.fields).filter(
                        function(e) {
                            return !value[e];
                        });
                for (i = 0, len = removed_key_names.length; i < len; i++) {
                    key = removed_key_names[i];
                    this.remove(key, false);
                }
            }.bind(this));
            this._set_button_sensitive();
        },
        get_entries: function(type) {
            switch (type) {
                case 'char':
                    return Sao.View.Form.Dict.Entry;
                case 'boolean':
                    return Sao.View.Form.Dict.Boolean;
                case 'selection':
                    return Sao.View.Form.Dict.Selection;
                case 'integer':
                    return Sao.View.Form.Dict.Integer;
                case 'float':
                    return Sao.View.Form.Dict.Float;
                case 'numeric':
                    return Sao.View.Form.Dict.Numeric;
                case 'date':
                    return Sao.View.Form.Dict.Date;
                case 'datetime':
                    return Sao.View.Form.Dict.DateTime;
            }
        }
    });

    Sao.View.Form.Dict.Entry = Sao.class_(Object, {
        class_: 'dict-char',
        init: function(name, parent_widget) {
            this.name = name;
            this.definition = parent_widget.keys[name];
            this.parent_widget = parent_widget;
            this.create_widget();
        },
        create_widget: function() {
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            var group = jQuery('<div/>', {
                'class': 'input-group input-group-sm'
            }).appendTo(this.el);
            this.input = this.labelled = jQuery('<input/>', {
                'type': 'text',
                'class': 'form-control input-sm'
            }).appendTo(group);
            this.button = jQuery('<button/>', {
                'class': 'btn btn-default',
                'type': 'button',
                'arial-label': Sao.i18n.gettext('Remove')
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-minus'
            })).appendTo(jQuery('<div/>', {
                'class': 'input-group-btn'
            }).appendTo(group));

            this.el.change(
                    this.parent_widget.focus_out.bind(this.parent_widget));
        },
        get_value: function() {
            return this.input.val();
        },
        set_value: function(value) {
            this.input.val(value || '');
        },
        set_readonly: function(readonly) {
            this.input.prop('readonly', readonly);
        }
    });

    Sao.View.Form.Dict.Boolean = Sao.class_(Sao.View.Form.Dict.Entry, {
        class_: 'dict-boolean',
        create_widget: function() {
            Sao.View.Form.Dict.Boolean._super.create_widget.call(this);
            this.input.attr('type', 'checkbox');
            this.input.change(
                    this.parent_widget.focus_out.bind(this.parent_widget));
        },
        get_value: function() {
            return this.input.prop('checked');
        },
        set_value: function(value) {
            this.input.prop('checked', value);
        }
    });

    Sao.View.Form.Dict.Selection = Sao.class_(Sao.View.Form.Dict.Entry, {
        class_: 'dict-selection',
        create_widget: function() {
            Sao.View.Form.Dict.Selection._super.create_widget.call(this);
            var select = jQuery('<select/>', {
                'class': 'form-control input-sm'
            });
            select.change(
                    this.parent_widget.focus_out.bind(this.parent_widget));
            this.input.replaceWith(select);
            this.input = this.labelled = select;
            var selection = jQuery.extend([], this.definition.selection);
            selection.splice(0, 0, [null, '']);
            selection.forEach(function(e) {
                select.append(jQuery('<option/>', {
                    'value': JSON.stringify(e[0]),
                    'text': e[1],
                }));
            });
        },
        get_value: function() {
            return JSON.parse(this.input.val());
        },
        set_value: function(value) {
            this.input.val(JSON.stringify(value));
        }
    });

    Sao.View.Form.Dict.Integer = Sao.class_(Sao.View.Form.Dict.Entry, {
        class_: 'dict-integer',
        get_value: function() {
            var value = parseInt(this.input.val(), 10);
            if (isNaN(value)) {
                return null;
            }
            return value;
        }
    });

    Sao.View.Form.Dict.Float = Sao.class_(Sao.View.Form.Dict.Integer, {
        class_: 'dict-float',
        get_value: function() {
            var value = Number(this.input.val());
            if (isNaN(value)) {
                return null;
            }
            return value;
        }
    });

    Sao.View.Form.Dict.Numeric = Sao.class_(Sao.View.Form.Dict.Float, {
        class_: 'dict-numeric',
        get_value: function() {
            var value = new Sao.Decimal(this.input.val());
            if (isNaN(value.valueOf())) {
                return null;
            }
            return value;
        }
    });

    Sao.View.Form.Dict.Date = Sao.class_(Sao.View.Form.Dict.Entry, {
        class_: 'dict-date',
        format: '%x',
        create_widget: function() {
            Sao.View.Form.Dict.Date._super.create_widget.call(this);
            var group = this.button.parent();
            jQuery('<button/>', {
                'class': 'datepickerbutton btn btn-default',
                'type': 'button'
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-calendar'
            })).prependTo(group);
            this.input.datetimepicker({
                'format': Sao.common.moment_format(this.format)
            });
            this.input.on('dp.hide',
                    this.parent_widget.focus_out.bind(this.parent_widget));
        },
        get_value: function() {
            var value = this.input.data('DateTimePicker').date();
            if (value) {
                value.isDate = true;
            }
            return value;
        },
        set_value: function(value) {
            this.date.data('DateTimePicker').date(value);
        }
    });

    Sao.View.Form.Dict.DateTime = Sao.class_(Sao.View.Form.Dict.Date, {
        class_: 'dict-datetime',
        format: '%x %X',
        get_value: function() {
            var value = this.input.data('DateTimePicker').date();
            if (value) {
                value.isDateTime = true;
            }
            return value;
        }
    });

}());
