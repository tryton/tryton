/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.View = Sao.class_(Object, {
        init: function(screen, xml) {
            this.screen = screen;
            this.view_type = null;
            this.el = null;
            this.fields = {};
        },
        set_value: function() {
        },
        get_fields: function() {
            return Object.keys(this.fields);
        }
    });

    Sao.View.parse = function(screen, xml, children_field) {
        switch (xml.children().prop('tagName')) {
            case 'tree':
                return new Sao.View.Tree(screen, xml, children_field);
            case 'form':
                return new Sao.View.Form(screen, xml);
        }
    };

    Sao.View.tree_column_get = function(type) {
        switch (type) {
            case 'char':
                return Sao.View.Tree.CharColumn;
            case 'many2one':
                return Sao.View.Tree.Many2OneColumn;
            case 'date':
                return Sao.View.Tree.DateColumn;
            case 'one2many':
                return Sao.View.Tree.One2ManyColumn;
            case 'many2many':
                return Sao.View.Tree.Many2ManyColumn;
            case 'selection':
                return Sao.View.Tree.SelectionColumn;
            case 'float':
            case 'numeric':
                return Sao.View.Tree.FloatColumn;
            case 'float_time':
                return Sao.View.Tree.FloatTimeColumn;
            case 'integer':
            case 'biginteger':
                return Sao.View.Tree.IntegerColumn;
            case 'boolean':
                return Sao.View.Tree.BooleanColumn;
            default:
                return Sao.View.Tree.CharColumn;
        }
    };

    Sao.View.Tree = Sao.class_(Sao.View, {
        init: function(screen, xml, children_field) {
            Sao.View.Tree._super.init.call(this, screen, xml);
            this.view_type = 'tree';
            this.el = jQuery('<div/>', {
                'class': 'treeview'
            });
            this.expanded = {};
            this.children_field = children_field;
            this.keyword_open = xml.children()[0].getAttribute('keyword_open');

            // Columns
            this.columns = [];
            this.create_columns(screen.model, xml);

            // Table of records
            this.rows = [];
            this.table = jQuery('<table/>', {
                'class': 'tree'
            });
            this.el.append(this.table);
            var thead = jQuery('<thead/>');
            this.table.append(thead);
            var tr = jQuery('<tr/>');
            thead.append(tr);
            this.columns.forEach(function(column) {
                var th = jQuery('<th/>', {
                    'text': column.attributes.string
                });
                tr.append(th);
            });
            this.tbody = jQuery('<tbody/>');
            this.table.append(this.tbody);

            // Footer with pagination stuff
            var footer = jQuery('<div/>', {
                'class': 'treefooter'
            });
            this.previous_button = jQuery('<button/>').button({
                'disabled': true,
                'icons': {
                    primary: 'ui-icon-triangle-1-w'
                },
                'text': false,
                'label': 'Previous' //TODO translation
            });
            footer.append(this.previous_button);
            this.pagination = jQuery('<span/>', {
                text: '0 / 0'
            });
            footer.append(this.pagination);
            this.next_button = jQuery('<button/>').button({
                'disabled': true,
                'icons': {
                    primary: 'ui-icon-triangle-1-e'
                },
                'text': false,
                'label': 'Next' //TODO translation
            });
            this.pagination.append(this.next_button);
            this.el.append(footer);
        },
        create_columns: function(model, xml) {
            xml.find('tree').children().each(function(pos, child) {
                var column, i, len;
                var attributes = {};
                for (i = 0, len = child.attributes.length; i < len; i++) {
                    var attribute = child.attributes[i];
                    attributes[attribute.name] = attribute.value;
                }
                ['readonly', 'tree_invisible', 'expand', 'completion'].forEach(
                    function(name) {
                        if (attributes[name]) {
                            attributes[name] = attribute[name] == 1;
                        }
                    });
                if (child.tagName == 'field') {
                    var name = child.getAttribute('name');
                    if (name == this.screen.exclude_field) {
                        // TODO is it really the way to do it
                        return;
                    }
                    if (!attributes.widget) {
                        attributes.widget = model.fields[name].description.type;
                    }
                    var attribute_names = ['relation', 'domain', 'selection',
                        'relation_field', 'string', 'views', 'invisible',
                        'add_remove', 'sort', 'context', 'filename'];
                    for (i in attribute_names) {
                        var attr = attribute_names[i];
                        if ((attr in model.fields[name].description) &&
                            (child.getAttribute(attr) === null)) {
                            attributes[attr] = model.fields[name]
                                .description[attr];
                        }
                    }
                    var ColumnFactory = Sao.View.tree_column_get(
                        attributes.widget);
                    column = new ColumnFactory(model, attributes);
                    this.fields[name] = true;
                } else if (child.tagName == 'button') {
                    column = new Sao.View.Tree.ButtonColumn(this.screen,
                            attributes);
                }
                this.columns.push(column);
            }.bind(this));
        },
        display: function() {
            this.rows = [];
            this.tbody.empty();
            var add_row = function(record, pos, group) {
                var tree_row = new Sao.View.Tree.Row(this, record, pos);
                this.rows.push(tree_row);
                tree_row.display();
            };
            this.screen.group.forEach(add_row.bind(this));
        },
        switch_: function(path) {
            this.screen.row_activate();
        },
        select_changed: function(record) {
            this.screen.current_record = record;
            // TODO validate if editable
            // TODO update_children
        },
        selected_records: function() {
            var records = [];
            this.rows.forEach(function(row) {
                if (row.is_selected()) {
                    records.push(row.record);
                }
            });
            return records;
        }
    });

    Sao.View.Tree.Row = Sao.class_(Object, {
        init: function(tree, record, pos, parent) {
            this.tree = tree;
            this.record = record;
            this.children_field = tree.children_field;
            this.expander = null;
            this.expander_icon = null;
            var path = [];
            if (parent) {
                path = jQuery.extend([], parent.path.split('.'));
            }
            path.push(pos);
            this.path = path.join('.');
            this.el = jQuery('<tr/>');
            this.el.click(this.select_row.bind(this));
            var switch_ = function() {
                this.el.addClass('ui-state-highlight');
                this.tree.select_changed(this.record);
                this.tree.switch_(path);
            };
            this.el.dblclick(switch_.bind(this));
        },
        is_expanded: function() {
            return (this.path in this.tree.expanded);
        },
        display: function() {
            var depth = this.path.split('.').length;
            var update_expander = function() {
                if (jQuery.isEmptyObject(
                            this.record.field_get(
                                this.children_field))) {

                    this.expander_icon.hide();
                }
            };
            for (var i = 0; i < this.tree.columns.length; i++) {
                var td = jQuery('<td/>');
                if ((i === 0) && this.children_field) {
                    var expanded = 'ui-icon-plus';
                    if (this.is_expanded()) {
                        expanded = 'ui-icon-minus';
                    }
                    this.expander = jQuery('<span/>', {
                        'class': 'expander'
                    });
                    this.expander.html('&nbsp;');
                    // 16 == minimum width of icon
                    this.expander.css('width', ((depth * 10) + 16) + 'px');
                    this.expander.css('float', 'left');
                    this.expander.click(this.toggle_row.bind(this));
                    this.expander_icon = jQuery('<i/>', {
                        'class': 'ui-icon ' + expanded
                    });
                    this.expander.append(this.expander_icon);
                    this.expander_icon.css('float', 'right');
                    td.append(this.expander);
                    this.record.load(this.children_field).done(
                            update_expander.bind(this));
                }
                var column = this.tree.columns[i];
                td.append(column.render(this.record));
                this.el.append(td);
            }
            this.tree.tbody.append(this.el);
            if (this.is_expanded()) {
                var add_children = function() {
                    var add_row = function(record, pos, group) {
                        var tree_row = new Sao.View.Tree.Row(this.tree, record,
                                pos, this);
                        tree_row.display();
                    };
                    var children = this.record.field_get_client(children_field);
                    children.forEach(add_row.bind(this));
                };
                var children_field = this.children_field;
                this.record.load(this.children_field).done(
                        add_children.bind(this));
            }
            if (this.record.deleted() || this.record.removed()) {
                this.el.css('text-decoration', 'line-through');
            } else {
                this.el.css('text-decoration', 'inherit');
            }
        },
        toggle_row: function() {
            if (this.is_expanded()) {
                this.expander_icon.removeClass('ui-icon-minus');
                this.expander_icon.addClass('ui-icon-plus');
                delete this.tree.expanded[this.path];
            } else {
                this.expander_icon.removeClass('ui-icon-plus');
                this.expander_icon.addClass('ui-icon-minus');
                this.tree.expanded[this.path] = this;
            }
            this.tree.display();
        },
        select_row: function() {
            this.el.toggleClass('ui-state-highlight');
            if (this.is_selected()) {
                this.tree.select_changed(this.record);
            } else {
                this.tree.select_changed(null);
            }
        },
        is_selected: function() {
            return this.el.hasClass('ui-state-highlight');
        }
    });

    Sao.View.Tree.CharColumn = Sao.class_(Object, {
        init: function(model, attributes) {
            this.type = 'field';
            this.model = model;
            this.field = model.fields[attributes.name];
            this.attributes = attributes;
        },
        get_cell: function() {
            var cell = jQuery('<div/>');
            cell.css('text-overflow', 'ellipsis');
            cell.css('overflow', 'hidden');
            cell.css('white-space', 'nowrap');
            cell.addClass('column-char');
            return cell;
        },
        update_text: function(cell, record) {
            cell.text(this.field.get_client(record));
        },
        render: function(record) {
            var cell = this.get_cell();
            record.load(this.attributes.name).done(function() {
                this.update_text(cell, record);
            }.bind(this));
            return cell;
        }
    });

    Sao.View.Tree.IntegerColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        get_cell: function() {
            var cell = Sao.View.Tree.IntegerColumn._super.get_cell.call(this);
            cell.css('text-align', 'right');
            cell.removeClass('column-char');
            cell.addClass('column-integer');
            return cell;
        }
    });

    Sao.View.Tree.FloatColumn = Sao.class_(Sao.View.Tree.IntegerColumn, {
        init: function(model, attributes) {
            Sao.View.Tree.FloatColumn._super.init.call(this, model, attributes);
        },
        get_cell: function() {
            var cell = Sao.View.Tree.FloatColumn._super.get_cell.call(this);
            cell.removeClass('column-integer');
            cell.addClass('column-float');
            return cell;
        }
    });

    Sao.View.Tree.BooleanColumn = Sao.class_(Sao.View.Tree.IntegerColumn, {
        get_cell: function() {
            return jQuery('<input/>', {
                'type': 'checkbox',
                'disabled': true,
                'class': 'column-boolean'
            });
        },
        update_text: function(cell, record) {
            cell.prop('checked', this.field.get(record));
        }
    });

    Sao.View.Tree.Many2OneColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        get_cell: function() {
            var cell = Sao.View.Tree.Many2OneColumn._super.get_cell.call(this);
            cell.removeClass('column-char');
            cell.addClass('column-many2one');
            return cell;
        }
    });

    Sao.View.Tree.SelectionColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        init: function(model, attributes) {
            Sao.View.Tree.SelectionColumn._super.init.call(this, model,
                attributes);
            Sao.common.selection_mixin.init.call(this);
            this.init_selection();
        },
        init_selection: function(key) {
            Sao.common.selection_mixin.init_selection.call(this, key);
        },
        update_selection: function(record, callback) {
            Sao.common.selection_mixin.update_selection.call(this, record,
                this.field, callback);
        },
        get_cell: function() {
            var cell = Sao.View.Tree.Many2OneColumn._super.get_cell.call(this);
            cell.removeClass('column-char');
            cell.addClass('column-selection');
            return cell;
        },
        update_text: function(cell, record) {
            this.update_selection(record, function() {
                var value = this.field.get(record);
                this.selection.forEach(function(e) {
                    if (e[0] == value) {
                        cell.text(e[1]);
                    }
                });
            }.bind(this));
        }
    });

    Sao.View.Tree.DateColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        init: function(model, attributes) {
            Sao.View.Tree.DateColumn._super.init.call(this, model, attributes);
            this.date_format = Sao.common.date_format();
        },
        update_text: function(cell, record) {
            var text;
            var value = this.field.get_client(record);
            var pad = function(txt) {
                return (txt.toString().length < 2) ? '0' + txt : txt;
            };
            if (value) {
                text = this.date_format.replace('%d', pad(value.getDate()));
                text = text.replace('%m', pad(value.getMonth() + 1));
                text = text.replace('%Y', value.getFullYear());
                text = text.replace('%y', value.getFullYear().toString()
                    .substring(2, 4));
            } else {
                text = '';
            }
            cell.text(text);
        }
    });

    Sao.View.Tree.One2ManyColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        update_text: function(cell, record) {
            cell.text('( ' + this.field.get_client(record).length + ' )');
        }
    });

    Sao.View.Tree.Many2ManyColumn = Sao.class_(Sao.View.Tree.One2ManyColumn, {
    });

    Sao.View.Tree.FloatTimeColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        init: function(model, attributes) {
            Sao.View.Tree.FloatTimeColumn._super.init.call(this, model,
                attributes);
            this.conv = null; // TODO
        },
        update_text: function(cell, record) {
            cell.text(Sao.common.text_to_float_time(
                    this.field.get_client(record), this.conv));
        }
    });

    Sao.View.Tree.ButtonColumn = Sao.class_(Object, {
        init: function(screen, attributes) {
            this.screen = screen;
            this.type = 'button';
            this.attributes = attributes;
        },
        render: function(record) {
            var button = new Sao.common.Button(this.attributes);
            button.el.click(record, this.button_clicked.bind(this));
            var fields = jQuery.map(this.screen.model.fields,
                function(field, name) {
                    if ((field.description.loading || 'eager') ==
                        'eager') {
                        return name;
                    } else {
                        return undefined;
                    }
                });
            // Wait at least one eager field is loaded before evaluating states
            record.load(fields[0]).done(function() {
                button.set_state(record);
            });
            return button.el;
        },
        button_clicked: function(event) {
            var record = event.data;
            if (record != this.screen.current_record) {
                return;
            }
            // TODO check state
            this.screen.button(this.attributes);
        }
    });

    Sao.View.Form = Sao.class_(Sao.View, {
        init: function(screen, xml) {
            Sao.View.Form._super.init.call(this, screen, xml);
            this.view_type = 'form';
            this.el = jQuery('<div/>', {
                'class': 'form'
            });
            this.widgets = {};
            this.widget_id = 0;
            this.state_widgets = [];
            var root = xml.children()[0];
            var container = this.parse(screen.model, root);
            this.el.append(container.el);
        },
        parse: function(model, node, container) {
            if (container === undefined) {
                container = new Sao.View.Form.Container(
                    Number(node.getAttribute('col') || 4));
            }
            var _parse = function(index, child) {
                var attributes = {};
                for (var i = 0, len = child.attributes.length; i < len; i++) {
                    var attribute = child.attributes[i];
                    attributes[attribute.name] = attribute.value;
                }
                ['readonly', 'invisible'].forEach(function(name) {
                    if (attributes[name]) {
                        attributes[name] = attribute[name] == 1;
                    }
                });
                switch (child.tagName) {
                    case 'image':
                        // TODO
                        break;
                    case 'separator':
                        this._parse_separator(
                                model, child, container, attributes);
                        break;
                    case 'label':
                        this._parse_label(model, child, container, attributes);
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
                        this._parse_field(model, child, container, attributes);
                        break;
                    case 'group':
                        this._parse_group(model, child, container, attributes);
                        break;
                    case 'hpaned':
                        // TODO
                        break;
                    case 'vpaned':
                        // TODO
                        break;
                    case 'child':
                        // TODO
                        break;
                }
            };
            jQuery(node).children().each(_parse.bind(this));
            return container;
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
            container.add(
                    Number(node.getAttribute('colspan') || 1),
                    separator);
        },
        _parse_label: function(model, node, container, attributes) {
            var name = attributes.name;
            var text = attributes.string;
            if (name in model.fields) {
                if (name == this.screen.exclude_field) {
                    container.add(
                            Number(node.getAttribute('colspan') || 1));
                    return;
                }
                if (!attributes.states && (name in model.fields)) {
                    attributes.states = model.fields[name].description.states;
                }
                if (!text) {
                    // TODO RTL and translation
                    text = model.fields[name]
                        .description.string + ':';
                }
                if (node.getAttribute('xalign') === undefined) {
                    node.setAttribute('xalign', 1.0);
                }
            } else if (!text) {
                // TODO get content
            }
            var label;
            if (text) {
                label = new Sao.View.Form.Label(text, attributes);
                this.state_widgets.push(label);
            }
            container.add(
                    Number(node.getAttribute('colspan') || 1),
                    label);
            // TODO help
        },
        _parse_button: function(node, container, attributes) {
            var button = new Sao.common.Button(attributes);
            this.state_widgets.push(button);
            container.add(
                    Number(node.getAttribute('colspan') || 1),
                    button);
            button.el.click(button, this.button_clicked.bind(this));
            // TODO help
        },
        _parse_notebook: function(model, node, container, attributes) {
            var notebook = new Sao.View.Form.Notebook(attributes);
            this.state_widgets.push(notebook);
            container.add(
                    Number(node.getAttribute('colspan') || 1),
                    notebook);
            this.parse(model, node, notebook);
        },
        _parse_page: function(model, node, container, attributes) {
            var text = attributes.string;
            if (attributes.name in model.fields) {
                // TODO check exclude
                // sync attributes
                if (!text) {
                    text = model.fields[attributes.name]
                        .description.string;
                }
            }
            if (!text) {
                text = 'No String Attr.'; // TODO translate
            }
            var page = this.parse(model, node);
            page = new Sao.View.Form.Page(container.add(page.el, text),
                    attributes);
            this.state_widgets.push(page);
        },
        _parse_field: function(model, node, container, attributes) {
            var name = attributes.name;
            if (!(name in model.fields) || name == this.screen.exclude_field) {
                container.add(
                        Number(node.getAttribute('colspan') || 1));
                return;
            }
            if (!attributes.widget) {
                attributes.widget = model.fields[name]
                    .description.type;
            }
            var attribute_names = ['relation', 'domain', 'selection',
                'relation_field', 'string', 'views', 'add_remove', 'sort',
                'context', 'size', 'filename', 'autocomplete', 'translate',
                'create', 'delete'];
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
                container.add(
                    Number(node.getAttribute('colspan') || 1));
                return;
            }
            var widget = new WidgetFactory(name, model, attributes);
            widget.position = this.widget_id += 1;
            widget.view = this;
            // TODO expand, fill, help, height, width
            container.add(
                    Number(node.getAttribute('colspan') || 1),
                    widget);
            if (this.widgets[name] === undefined) {
                this.widgets[name] = [];
            }
            this.widgets[name].push(widget);
            this.fields[name] = true;
        },
        _parse_group: function(model, node, container, attributes) {
            var group = new Sao.View.Form.Group(attributes);
            group.add(this.parse(model, node));
            this.state_widgets.push(group);
            container.add(
                    Number(node.getAttribute('colspan') || 1),
                    group);
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
            jQuery.when.apply(jQuery,
                    jQuery.map(promesses, function(p) {
                        return p;
                    })
                ).done(function() {
                    for (var j in this.state_widgets) {
                        var state_widget = this.state_widgets[j];
                        state_widget.set_state(record);
                    }
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
            var record = this.screen.current_record;
            var fields = Object.keys(this.fields);
            record.validate(fields).then(function(validate) {
                if (!validate) {
                    this.screen.display();
                    return;
                } else {
                    this.screen.button(button.attributes);
                }
            });
        },
        selected_records: function() {
            if (this.screen.current_record) {
                return [this.screen.current_record];
            }
            return [];
        }
    });

    Sao.View.Form.Container = Sao.class_(Object, {
        init: function(col) {
            if (col === undefined) col = 4;
            this.col = col;
            this.el = jQuery('<table/>');
            this.add_row();
        },
        add_row: function() {
            this.el.append(jQuery('<tr/>'));
        },
        row: function() {
            return this.el.children().children('tr').last();
        },
        add: function(colspan, widget) {
            if (colspan === undefined) colspan = 1;
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
            var cell = row.append(jQuery('<td/>', {
                'colspan': colspan
            }).append(el));
        }
    });

    var StateWidget = Sao.class_(Object, {
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

    Sao.View.Form.Separator = Sao.class_(StateWidget, {
        init: function(text, attributes) {
            Sao.View.Form.Separator._super.init.call(this, attributes);
            this.el = jQuery('<div/>', {
                'class': 'form-separator'
            });
            if (text) {
                this.el.append(jQuery('<p/>', {
                    'text': text
                }));
            }
            this.el.append(jQuery('<hr/>'));
        }
    });

    Sao.View.Form.Label = Sao.class_(StateWidget, {
        init: function(text, attributes) {
            Sao.View.Form.Label._super.init.call(this, attributes);
            this.el = jQuery('<label/>', {
                text: text,
                'class': 'form-label'
            });
        },
        set_state: function(record) {
            Sao.View.Form.Label._super.set_state.call(this, record);
            if ((this.attributes.string === undefined) &&
                    this.attributes.name) {
                var text = '';
                if (record) {
                    text = record.field_get_client(this.attributes.name) || '';
                }
                this.el.val(text);
            }
        }
    });

    Sao.View.Form.Notebook = Sao.class_(StateWidget, {
        init: function(attributes) {
            Sao.View.Form.Notebook._super.init.call(this, attributes);
            this.el = jQuery('<div/>', {
                'class': 'form-notebook'
            });
            this.el.append(jQuery('<ul/>'));
            this.el.tabs();
            this.selected = false;
            this.counter = 0;
        },
        add: function(tab, text) {
            var tab_id = '#tab-form-' + this.counter++;
            this.el.tabs('add', tab_id, text);
            this.el.children(tab_id).html(tab);
            if (!this.selected) {
                this.el.tabs('select', tab_id);
                this.selected = true;
            }
            return jQuery('> ul li', this.el).last();
        }
    });

    Sao.View.Form.Page = Sao.class_(StateWidget, {
        init: function(el, attributes) {
            Sao.View.Form.Page._super.init.call(this, attributes);
            this.el = el;
        }
    });

    Sao.View.Form.Group = Sao.class_(StateWidget, {
        init: function(attributes) {
            Sao.View.Form.Group._super.init.call(this, attributes);
            this.el = jQuery('<div/>', {
                'class': 'form-group'
            });
        },
        add: function(widget) {
            this.el.append(widget.el);
        }
    });

    Sao.View.form_widget_get = function(type) {
        switch (type) {
            case 'char':
                return Sao.View.Form.Char;
            case 'sha':
                return Sao.View.Form.Sha;
            case 'date':
                return Sao.View.Form.Date;
            case 'integer':
            case 'biginteger':
                return Sao.View.Form.Integer;
            case 'float':
            case 'numeric':
                return Sao.View.Form.Float;
            case 'selection':
                return Sao.View.Form.Selection;
            case 'float_time':
                return Sao.View.Form.FloatTime;
            case 'boolean':
                return Sao.View.Form.Boolean;
            case 'text':
                return Sao.View.Form.Text;
            case 'many2one':
                return Sao.View.Form.Many2One;
            case 'one2many':
                return Sao.View.Form.One2Many;
            case 'many2many':
                return Sao.View.Form.Many2Many;
            case 'binary':
                return Sao.View.Form.Binary;
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
            this.set_readonly(readonly);
            var valid = true;
            if (state_attrs.valid !== undefined) {
                valid = state_attrs.valid;
            }
            // XXX allow to customize colors
            var color = 'inherit';
            if (readonly) {
            } else if (!valid) {
                color = 'red';
            } else if (state_attrs.required) {
                color = 'lightblue';
            }
            this.set_color(color);
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
        _get_color_el: function() {
            return this.el;
        },
        set_color: function(color) {
            var el = this._get_color_el();
            el.css('background-color', color);
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
            this.el = jQuery('<input/>', {
                'type': 'input',
                'class': this.class_
            });
            this.el.change(this.focus_out.bind(this));
        },
        display: function(record, field) {
            Sao.View.Form.Char._super.display.call(this, record, field);
            if (record) {
                var value = record.field_get_client(this.field_name);
                this.el.val(value || '');
            } else {
                this.el.val('');
            }
        },
        set_value: function(record, field) {
            var value = this.el.val() || '';
            field.set_client(record, value);
        }
    });

    Sao.View.Form.Sha = Sao.class_(Sao.View.Form.Char, {
        class_: 'form-sha',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Sha._super.init.call(this, field_name, model,
                attributes);
            this.el.prop('type', 'password');
        }
    });

    Sao.View.Form.Date = Sao.class_(Sao.View.Form.Widget, {
        init: function(field_name, model, attributes) {
            Sao.View.Form.Date._super.init.call(this, field_name, model,
                attributes);
            this.el = jQuery('<div/>', {
                'class': 'form-date'
            });
            this.date = jQuery('<input/>', {
                'type': 'input'
            });
            this.el.append(this.date);
            this.date.datepicker({
                showOn: 'button'
            });
            this.date.next('button').text('').button({
                icons: {
                    primary: 'ui-icon-calendar'
                },
                text: false
            });
            this.date.change(this.focus_out.bind(this));
        },
        _get_color_el: function() {
            return this.date;
        },
        display: function(record, field) {
            Sao.View.Form.Date._super.display.call(this, record, field);
            if (record) {
                var value = record.field_get_client(this.field_name);
                this.date.datepicker('setDate', value);
            } else {
                this.date.datepicker('setDate', null);
            }
        },
        set_value: function(record, field) {
            var value = this.date.datepicker('getDate');
            field.set_client(record, value);
        }
    });

    // TODO DateTime, Time

    Sao.View.Form.Integer = Sao.class_(Sao.View.Form.Char, {
        class_: 'form-integer',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Integer._super.init.call(this, field_name, model,
                attributes);
            this.el.css('text-align', 'right');
        },
        set_value: function(record, field) {
            var value = Number(this.el.val());
            field.set_client(record, value);
        }
    });

    Sao.View.Form.Float = Sao.class_(Sao.View.Form.Integer, {
        class_: 'form-float'
    });

    Sao.View.Form.Selection = Sao.class_(Sao.View.Form.Widget, {
        init: function(field_name, model, attributes) {
            Sao.View.Form.Selection._super.init.call(this, field_name, model,
                attributes);
            this.el = jQuery('<select/>', {
                'class': 'form-selection'
            });
            this.el.change(this.focus_out.bind(this));
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
            var select = this.el;
            select.empty();
            selection.forEach(function(e) {
                select.append(jQuery('<option/>', {
                    'value': e[0],
                    'text': e[1]
                }));
            });
        },
        display: function(record, field) {
            Sao.View.Form.Selection._super.display.call(this, record, field);
            this.update_selection(record, field, function() {
                if (!field) {
                    this.el.val('');
                    return;
                }
                var value = field.get(record);
                if (value === null) {
                    value = '';
                }
                this.el.val('' + value);
            }.bind(this));
        },
        value_get: function() {
            var val = this.el.val();
            if ('relation' in this.attributes) {
                return parseInt(val, 10);
            }
            return val;
        },
        set_value: function(record, field) {
            var value = this.value_get();
            field.set_client(record, value);
        }
    });

    Sao.View.Form.FloatTime = Sao.class_(Sao.View.Form.Char, {
        class_: 'form-float-time',
        init: function(field_name, model, attributes) {
            Sao.View.Form.FloatTime._super.init.call(this, field_name, model,
                attributes);
            this.el.css('text-align', 'right');
            this.conv = null; // TODO
        },
        display: function(record, field) {
            Sao.View.Form.FloatTime._super.display.call(this, record, field);
            if (record) {
                var value = record.field_get_client(this.field_name);
                this.el.val(Sao.common.text_to_float_time(value, this.conv));
            } else {
                this.el.val('');
            }
        }
    });

    Sao.View.Form.Boolean = Sao.class_(Sao.View.Form.Widget, {
        init: function(field_name, model, attributes) {
            Sao.View.Form.Boolean._super.init.call(this, field_name, model,
                attributes);
            this.el = jQuery('<input/>', {
                'type': 'checkbox',
                'class': 'form-boolean'
            });
            this.el.change(this.focus_out.bind(this));
        },
        display: function(record, field) {
            Sao.View.Form.Boolean._super.display.call(this, record, field);
            if (record) {
                this.el.prop('checked', record.field_get(this.field_name));
            } else {
                this.el.prop('checked', false);
            }
        },
        set_value: function(record, field) {
            var value = this.el.prop('checked');
            field.set_client(record, value);
        }
    });

    Sao.View.Form.Text = Sao.class_(Sao.View.Form.Widget, {
        init: function(field_name, model, attributes) {
            Sao.View.Form.Text._super.init.call(this, field_name, model,
                attributes);
            this.el = jQuery('<textarea/>', {
                'class': 'form-text'
            });
            this.el.change(this.focus_out.bind(this));
        },
        display: function(record, field) {
            Sao.View.Form.Text._super.display.call(this, record, field);
            if (record) {
                var value = record.field_get_client(this.field_name);
                this.el.val(value);
            } else {
                this.el.val('');
            }
        },
        set_value: function(record, field) {
            var value = this.el.val() || '';
            field.set_client(record, value);
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
            this.entry = jQuery('<input/>', {
                'type': 'input'
            });
            this.entry.on('keyup', this.key_press.bind(this));
            this.el.append(this.entry);
            this.but_open = jQuery('<button/>').button({
                'icons': {
                    'primary': 'ui-icon-search'
                },
                'text': false
            });
            this.but_open.click(this.edit.bind(this));
            this.el.append(this.but_open);
            this.but_new = jQuery('<button/>').button({
                'icons': {
                    'primary': 'ui-icon-document'
                },
                'text': false
            });
            this.but_new.click(this.new_.bind(this));
            this.el.append(this.but_new);
            this.model = attributes.relation;
            // TODO autocompletion
        },
        _get_color_el: function() {
            return this.entry;
        },
        get_screen: function() {
            var domain = this.field().get_domain(this.record());
            var context = this.field().get_context(this.record());
            return new Sao.Screen(this.get_model(), {
                'context': context,
                'domain': domain,
                'mode': ['form'],
                'view_ids': (this.attributes.view_ids || '').split(','),
                'views_preload': this.attributes.views
            });
        },
        display: function(record, field) {
            var text_value, value;
            Sao.View.Form.Many2One._super.display.call(this, record, field);

            this._set_button_sensitive();

            if (record) {
                text_value = record.field_get_client(this.field_name);
                value = record.field_get(this.field_name);
            } else {
                this.entry.val('');
                return;
            }
            this.entry.val(text_value || '');
            if (this.has_target(value)) {
                this.but_open.button({
                    'icons': {
                        'primary': 'ui-icon-folder-open'
                    }});
            } else {
                this.but_open.button({
                    'icons': {
                        'primary': 'ui-icon-search'
                    }});
            }
        },
        set_readonly: function(readonly) {
            this.entry.prop('disabled', readonly);
            this._set_button_sensitive();
        },
        _set_button_sensitive: function() {
            var model = this.get_model();
            var access = {
                create: true,
                read: true
            };
            if (model) {
                access = Sao.common.MODELACCESS.get(model);
            }
            var readonly = this.entry.prop('disabled');
            var create = this.attributes.create;
            if (create === undefined) {
                create = true;
            }
            this.but_new.prop('disabled', readonly || !create || !access.create);
            this.but_open.prop('disabled', !access.read);
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
        get_model: function(value) {
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
            var win;
            var record = this.record();
            var value = record.field_get(this.field_name);
            if (model && this.has_target(value)) {
                var screen = this.get_screen();
                var m2o_id =
                    this.id_from_value(record.field_get(this.field_name));
                screen.new_group([m2o_id]);
                var callback = function(result) {
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
                    save_current: true
                });
            } else if (model) {
                var dom;
                var domain = this.field().get_domain(record);
                var context = this.field().get_context(record);
                var text = this.entry.val();
                if (text) {
                    dom = [['rec_name', 'ilike', '%' + text + '%'], domain];
                } else {
                    dom = domain;
                }
                var sao_model = new Sao.Model(model);
                var ids_prm = sao_model.execute('search',
                        [dom, 0, Sao.config.limit, null], context);
                ids_prm.done(function(ids) {
                    if (ids.length == 1) {
                        this.record().field_set_client(this.field_name,
                            this.id_from_value(ids[0]), true);
                        return;
                    }
                    var callback = function(result) {
                        if (!jQuery.isEmptyObject(result)) {
                            var value = this.value_from_id(result[0][0],
                                result[0][1]);
                            this.record().field_set_client(this.field_name,
                                value, true);
                        }
                    };
                    win = new Sao.Window.Search(model,
                        callback.bind(this), {
                            sel_multi: false,
                            ids: ids,
                            context: context,
                            domain: domain,
                            view_ids: (this.attributes.view_ids ||
                                '').split(','),
                            views_preload: (this.attributes.views || {}),
                            new_: !this.but_new.prop('disabled')
                    });
                }.bind(this));
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
                save_current: true
            });
        },
        key_press: function(event_) {
            var editable = true; // TODO compute editable
            var activate_keys = [Sao.common.TAB_KEYCODE];
            var delete_keys = [Sao.common.BACKSPACE_KEYCODE,
                Sao.common.DELETE_KEYCODE];
            if (!this.wid_completion) {
                activate_keys.push(Sao.common.RETURN_KEYCODE);
            }

            if (event_.which == Sao.common.F3_KEYCODE && editable) {
                this.new_();
                event_.preventDefault();
            } else if (event_.which == Sao.common.F2_KEYCODE) {
                this.edit();
                event_.preventDefault();
            } else if (~activate_keys.indexOf(event_.which)) {
                this.activate();
            } else if (this.has_target(this.record().field_get(
                            this.field_name)) && editable) {
                var value = this.record().field_get_client(this.field_name);
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

                    if (text) {
                        dom = [['rec_name', 'ilike', '%' + text + '%'], domain];
                    } else {
                        dom = domain;
                    }
                    var ids_prm = sao_model.execute('search',
                            [dom, 0, Sao.config.limit, null], context);
                    ids_prm.done(function(ids) {
                        if (ids.length == 1) {
                            Sao.rpc({
                                'method': 'model.' + model + '.read',
                                'params': [[this.id_from_value(ids[0])],
                                ['rec_name'], context]
                            }, this.record().model.session
                            ).then(function(values) {
                                this.record().field_set_client(this.field_name,
                                    this.value_from_id(ids[0],
                                        values[0].rec_name), true);
                            }.bind(this));
                            return;
                        }
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
                        var win = new Sao.Window.Search(model,
                                callback.bind(this), {
                                    sel_multi: false,
                                    ids: ids,
                                    context: context,
                                    domain: domain,
                                    view_ids: (this.attributes.view_ids ||
                                        '').split(','),
                                    views_preload: (this.attributes.views ||
                                        {}),
                                    new_: false
                                    // TODO compute from but_new status
                                });
                    }.bind(this));
                }
            }
        }
    });

    Sao.View.Form.One2Many = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-one2many',
        init: function(field_name, model, attributes) {
            Sao.View.Form.One2Many._super.init.call(this, field_name, model,
                attributes);

            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            this.menu = jQuery('<div/>', {
                'class': this.class_ + '-menu'
            });
            this.el.append(this.menu);

            if (attributes.add_remove) {
                this.wid_text = jQuery('<input/>', {
                    type: 'input'
                });
                // TODO add completion
                this.menu.append(this.wid_text);

                this.but_add = jQuery('<button/>').button({
                    icons: {
                        primary: 'ui-icon-plus'
                    },
                    label: 'Add'
                });
                this.but_add.click(this.add.bind(this));
                this.menu.append(this.but_add);

                this.but_remove = jQuery('<button/>').button({
                    icons: {
                        primary: 'ui-icon-minus'
                    },
                    label: 'Remove'
                });
                this.but_remove.click(this.remove.bind(this));
                this.menu.append(this.but_remove);
            }

            this.but_new = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-document'
                },
                label: 'New'
            });
            this.but_new.click(this.new_.bind(this));
            this.menu.append(this.but_new);

            this.but_open = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-folder-open'
                },
                label: 'Open'
            });
            this.but_open.click(this.open.bind(this));
            this.menu.append(this.but_open);

            this.but_del = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-trash'
                },
                label: 'Delete'
            });
            this.but_del.click(this.delete_.bind(this));
            this.menu.append(this.but_del);

            this.but_undel = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-arrowreturn-1-s'
                },
                label: 'Undelete'
            });
            this.but_undel.click(this.undelete.bind(this));
            this.menu.append(this.but_undel);

            this.but_previous = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-arrowthick-1-w'
                },
                label: 'Previous'
            });
            this.but_previous.click(this.previous.bind(this));
            this.menu.append(this.but_previous);

            this.label = jQuery('<span/>', {
                'class': this.class_ + '-label'
            });
            this.label.text('(0, 0)');
            this.menu.append(this.label);

            this.but_next = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-arrowthick-1-e'
                },
                label: 'Next'
            });
            this.but_next.click(this.next.bind(this));
            this.menu.append(this.but_next);

            this.but_switch = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-newwin'
                },
                label: 'Switch'
            });
            this.but_switch.click(this.switch_.bind(this));
            this.menu.append(this.but_switch);

            this.content = jQuery('<div/>', {
                'class': this.class_ + '-content'
            });
            this.el.append(this.content);

            var modes = (attributes.mode || 'tree,form').split(',');
            this.screen = new Sao.Screen(attributes.relation, {
                mode: modes,
                view_ids: (attributes.view_ids || '').split(','),
                views_preload: attributes.views || {},
                row_activate: this.activate.bind(this),
                exclude_field: attributes.relation_field || null
            });
            this.prm = this.screen.switch_view(modes[0]).done(function() {
                this.content.append(this.screen.screen_container.el);
            }.bind(this));
            // TODO sensitivity of buttons
        },
        _get_color_el: function() {
            if (this.screen.current_view &&
                    (this.screen.current_view.view_type == 'tree') &&
                    this.screen.current_view.el) {
                return this.screen.current_view.el;
            }
            return Sao.View.Form.One2Many._super._get_color_el.call(this);
        },
        display: function(record, field) {
            Sao.View.Form.One2Many._super.display.call(this, record, field);

            this.prm.done(function() {
                if (!record) {
                    return;
                }
                if (field === undefined) {
                    this.screen.new_group();
                    this.screen.current_record = null;
                    this.screen.parent = true;
                    this.screen.display();
                    return;
                }

                var new_group = record.field_get_client(this.field_name);
                if (new_group != this.screen.group) {
                    this.screen.set_group(new_group);
                    // TODO handle editable tree
                    // TODO set readonly, domain, size_limit
                }
                this.screen.display();
            }.bind(this));
        },
        activate: function(event_) {
            this.edit();
        },
        add: function(event_) {
            var access = Sao.common.MODELACCESS.get(this.screen.model_name);
            if (!access.write || !access.read) {
                return;
            }
            // TODO
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
                        context: context
                    });
                }
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
            // TODO color_set
        },
        edit: function() {
            if (!Sao.common.MODELACCESS.get(this.screen.model_name).read) {
                return;
            }
            this.validate().done(function() {
                var record = this.screen.current_record;
                if (record) {
                    var win = new Sao.Window.Form(this.screen, function() {});
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
                        this.screen.display();
                        prm.reject();
                    }
                    // TODO pre-validate
                    prm.resolve();
                }.bind(this));
            } else {
                prm.resolve();
            }
            return prm;
        }
    });

    Sao.View.Form.Many2Many = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-many2many',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Many2Many._super.init.call(this, field_name, model,
                attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            this.menu = jQuery('<div/>', {
                'class': this.class_ + '-menu'
            });
            this.el.append(this.menu);

            var label = jQuery('<span/>', {
                text: attributes.string
            });
            this.menu.append(label);

            this.entry = jQuery('<input/>', {
                type: 'input'
            });
            this.entry.on('keyup', this.key_press.bind(this));
            this.menu.append(this.entry);

            // TODO completion

            this.but_add = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-plus'
                },
                text: false
            });
            this.but_add.click(this.add.bind(this));
            this.menu.append(this.but_add);

            this.but_remove = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-minus'
                },
                text: false
            });
            this.but_remove.click(this.remove.bind(this));
            this.menu.append(this.but_remove);

            this.content = jQuery('<div/>', {
                'class': this.class_ + '-content'
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
        _get_color_el: function() {
            if (this.screen.current_view &&
                    (this.screen.current_view.view_type == 'tree') &&
                    this.screen.current_view.el) {
                return this.screen.current_view.el;
            }
            return Sao.View.Form.Many2Many._super._get_color_el.call(this);
        },
        display: function(record, field) {
            Sao.View.Form.Many2Many._super.display.call(this, record, field);

            this.prm.done(function() {
                if (!record) {
                    return;
                }
                if (field === undefined) {
                    this.screen.new_group();
                    this.screen.current_record = null;
                    this.screen.parent = true;
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
        activate: function() {
            this.edit();
        },
        add: function() {
            var dom;
            var domain = this.field().get_domain(this.record());
            var context = this.field().get_context(this.record());
            var value = this.entry.val();
            if (value) {
                dom = [['rec_name', 'ilike', '%' + value + '%']].concat(domain);
            } else {
                dom = domain;
            }

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
            var model = new Sao.Model(this.attributes.relation);
            var ids_prm = model.execute('search',
                    [dom, 0, Sao.config.limit, null], context);
            ids_prm.done(function(ids) {
               if (ids.length != 1) {
                   var win = new Sao.Window.Search(this.attributes.relation,
                       callback, {
                           sel_multi: true,
                           ids: ids,
                           context: context,
                           domain: domain,
                           view_ids: (this.attributes.view_ids ||
                               '').split(','),
                           views_preload: this.attributes.views || {},
                           new_: this.attributes.create
                   });
               } else {
                   callback([[ids[0], null]]);
               }
            }.bind(this));
        },
        remove: function() {
            this.screen.remove(false, true, false);
        },
        key_press: function(event_) {
            var editable = true; // TODO compute editable
            var activate_keys = [Sao.common.TAB_KEYCODE];
            if (!this.wid_completion) {
                activate_keys.push(Sao.common.RETURN_KEYCODE);
            }

            if (event_.which == Sao.common.F3_KEYCODE) {
                this.add();
                event_.preventDefault();
            } else if (~activate_keys.indexOf(event_.which) && editable) {
                if (this.entry.val()) {
                    this.add();
                }

            }
        },
        edit: function() {
            if (this.screen.current_record) {
                var callback = function(result) {
                    if (result) {
                        this.screen.current_record.save().done(function() {
                            this.screen.display();
                        }.bind(this));
                    } else {
                        this.screen.current_record.cancel();
                    }
                };
                var win = new Sao.Window.Form(this.screen,
                        callback.bind(this));
            }
        }
    });

    Sao.View.Form.Binary = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-binary',
        blob_url: '',
        init: function(field_name, model, attributes) {
            Sao.View.Form.Binary._super.init.call(this, field_name, model,
                attributes);
            this.filename = attributes.filename || null;

            this.el = jQuery('<div/>', {
                'class': this.class_
            });

            if (this.filename && attributes.filename_visible) {
                this.text = jQuery('<input/>', {
                    type: 'input'
                });
                this.text.change(this.focus_out.bind(this));
                this.text.on('keyup', this.key_press.bind(this));
                this.el.append(this.text);
            }
            this.size = jQuery('<input/>', {
                type: 'input'
            });
            this.el.append(this.size);

            this.but_new = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-document'
                },
                text: false
            });
            this.but_new.click(this.new_.bind(this));
            this.el.append(this.but_new);

            if (this.filename) {
                this.but_open = jQuery('<a/>').button({
                    icons: {
                        primary: 'ui-icon-folder-open'
                    },
                    text: false
                });
                this.but_open.click(this.open.bind(this));
                this.el.append(this.but_open);
            }

            this.but_save_as = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-disk'
                },
                text: false
            });
            this.but_save_as.click(this.save_as.bind(this));
            this.el.append(this.but_save_as);

            this.but_remove = jQuery('<button/>').button({
                icons: {
                    primary: 'ui-icon-trash'
                },
                text: false
            });
            this.but_remove.click(this.remove.bind(this));
            this.el.append(this.but_remove);
        },
        filename_field: function() {
            var record = this.record();
            if (record) {
                return record.model.fields[this.filename];
            }
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
        save_as: function(evt) {
            var field = this.field();
            var record = this.record();
            field.get_data(record).done(function(data) {
                var blob = new Blob([data[0].binary],
                        {contentType: 'application/octet-binary'});
                var blob_url = window.URL.createObjectURL(blob);
                if (this.blob_url) {
                    window.URL.revokeObjectURL(this.blob_url);
                }
                this.blob_url = blob_url;
                window.open(blob_url);
            }.bind(this));
        },
        open: function(evt) {
            // TODO find a way to make the difference between downloading and
            // opening
            this.save_as(evt);
        },
        new_: function(evt) {
            var record = this.record();
            var file_dialog = jQuery('<div/>', {
                'class': 'file-dialog'
            });
            var file_selector = jQuery('<input/>', {
                type: 'file'
            });
            file_dialog.append(file_selector);
            var save_file = function() {
                var reader = new FileReader();
                reader.onload = function(evt) {
                    var uint_array = new Uint8Array(reader.result);
                    this.field().set_client(record, uint_array);
                }.bind(this);
                reader.onloadend = function(evt) {
                    file_dialog.dialog('close');
                };
                var file = file_selector[0].files[0];
                reader.readAsArrayBuffer(file);
                if (this.filename) {
                    this.filename_field().set_client(record, file.name);
                }
            };
            file_dialog.dialog({
                modal: true,
                title: 'Select a file', // TODO translation
                buttons: {
                    Cancel: function() {
                        $(this).dialog('close');
                    },
                    OK: save_file.bind(this)
                }
            });
            file_dialog.dialog('open');
        },
        remove: function(evt) {
            this.field().set_client(this.record(), null);
        },
        key_press: function(evt) {
            var editable = true; // TODO compute editable
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
        _get_color_el: function() {
            if (this.text) {
                return this.text;
            } else {
                return this.size;
            }
        },
        set_readonly: function(readonly) {
            if (readonly) {
                this.but_new.hide();
                this.but_remove.hide();

            } else {
                this.but_new.show();
                this.but_remove.show();
            }
        }
    });
}());
