/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.View.tree_column_get = function(type) {
        switch (type) {
            case 'char':
            case 'text':
            case 'binary':
                return Sao.View.Tree.CharColumn;
            case 'many2one':
                return Sao.View.Tree.Many2OneColumn;
            case 'one2one':
                return Sao.View.Tree.One2OneColumn;
            case 'date':
                return Sao.View.Tree.DateColumn;
            case 'time':
                return Sao.View.Tree.TimeColumn;
            case 'timedelta':
                return Sao.View.Tree.TimeDeltaColumn;
            case 'one2many':
                return Sao.View.Tree.One2ManyColumn;
            case 'many2many':
                return Sao.View.Tree.Many2ManyColumn;
            case 'selection':
                return Sao.View.Tree.SelectionColumn;
            case 'reference':
                return Sao.View.Tree.ReferenceColumn;
            case 'float':
            case 'numeric':
                return Sao.View.Tree.FloatColumn;
            case 'integer':
            case 'biginteger':
                return Sao.View.Tree.IntegerColumn;
            case 'boolean':
                return Sao.View.Tree.BooleanColumn;
            case 'image':
                return Sao.View.Tree.ImageColumn;
            case 'url':
            case 'email':
            case 'callto':
            case 'sip':
                return Sao.View.Tree.URLColumn;
            case 'progressbar':
                return Sao.View.Tree.ProgressBar;
        }
    };

    Sao.View.Tree = Sao.class_(Sao.View, {
        init: function(screen, xml, children_field) {
            Sao.View.Tree._super.init.call(this, screen, xml);
            this.view_type = 'tree';
            this.selection_mode = (screen.attributes.selection_mode ||
                Sao.common.SELECTION_SINGLE);
            this.el = jQuery('<div/>', {
                'class': 'treeview responsive'
            });
            this.expanded = {};
            this.children_field = children_field;
            this.editable = Boolean(this.attributes.editable);

            // Columns
            this.columns = [];
            this.create_columns(screen.model, xml);

            // Table of records
            this.rows = [];
            this.table = jQuery('<table/>', {
                'class': 'tree table table-hover table-striped'
            });
            if (this.columns.filter(function(c) {
                return !c.attributes.tree_invisible;
            }).length > 1) {
                this.table.addClass('responsive');
                this.table.addClass('responsive-header');
            }
            this.el.append(this.table);
            var thead = jQuery('<thead/>');
            this.table.append(thead);
            var tr = jQuery('<tr/>');
            if (this.selection_mode != Sao.common.SELECTION_NONE) {
                var th = jQuery('<th/>', {
                    'class': 'selection'
                });
                this.selection = jQuery('<input/>', {
                    'type': 'checkbox',
                    'class': 'selection'
                });
                this.selection.change(this.selection_changed.bind(this));
                th.append(this.selection);
                tr.append(th);
            }
            thead.append(tr);
            this.columns.forEach(function(column) {
                th = jQuery('<th/>');
                var label = jQuery('<label/>')
                    .text(column.attributes.string);
                if (this.editable) {
                    if (column.attributes.required) {
                        label.addClass('required');
                    }
                    if (!column.attributes.readonly) {
                        label.addClass('editable');
                    }
                }
                tr.append(th.append(label));
                column.header = th;
            }, this);
            this.tbody = jQuery('<tbody/>');
            this.table.append(this.tbody);

            // Footer for more
            var footer = jQuery('<div/>', {
                'class': 'treefooter'
            });
            this.more = jQuery('<button/>', {
                'class': 'btn btn-default',
                'type': 'button'
            }).append(Sao.i18n.gettext('More')
                ).click(function() {
                this.display_size += Sao.config.display_size;
                this.display();
            }.bind(this));
            footer.append(this.more);
            this.more.hide();
            this.display_size = Sao.config.display_size;
            this.el.append(footer);
        },
        create_columns: function(model, xml) {
            xml.find('tree').children().each(function(pos, child) {
                var column, editable_column, attribute;
                var attributes = {};
                for (var i = 0, len = child.attributes.length; i < len; i++) {
                    attribute = child.attributes[i];
                    attributes[attribute.name] = attribute.value;
                }
                ['readonly', 'tree_invisible', 'expand', 'completion'].forEach(
                    function(name) {
                        if (attributes[name]) {
                            attributes[name] = attributes[name] == 1;
                        }
                    });
                if (child.tagName == 'field') {
                    var name = attributes.name;
                    if (!attributes.widget) {
                        attributes.widget = model.fields[name].description.type;
                    }
                    var attribute_names = ['relation', 'domain', 'selection',
                        'relation_field', 'string', 'views', 'invisible',
                        'add_remove', 'sort', 'context', 'filename',
                        'autocomplete', 'translate', 'create', 'delete',
                        'selection_change_with', 'schema_model', 'required',
                        'readonly'];
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

                    var prefixes = [], suffixes = [];
                    if (~['url', 'email', 'callto', 'sip'
                            ].indexOf(attributes.widget)) {
                        column.prefixes.push(new Sao.View.Tree.Affix(
                                    attributes, attributes.widget));
                    }
                    if ('icon' in attributes) {
                        column.prefixes.push(new Sao.View.Tree.Affix(
                                    attributes));
                    }
                    var affix, affix_attributes;
                    var affixes = child.childNodes;
                    for (i = 0; i < affixes.length; i++) {
                        affix = affixes[i];
                        affix_attributes = {};
                        for (i = 0, len = affix.attributes.length; i < len;
                                i++) {
                            attribute = affix.attributes[i];
                            affix_attributes[attribute.name] = attribute.value;
                        }
                        if (!affix_attributes.name) {
                            affix_attributes.name = name;
                        }
                        if (affix.tagName == 'prefix') {
                            column.prefixes.push(new Sao.View.Tree.Affix(
                                        affix_attributes));
                        } else {
                            column.suffixes.push(new Sao.View.Tree.Affix(
                                        affix_attributes));
                        }
                    }

                    this.fields[name] = true;
                    // TODO sum
                } else if (child.tagName == 'button') {
                    column = new Sao.View.Tree.ButtonColumn(this.screen,
                            attributes);
                }
                this.columns.push(column);
            }.bind(this));
        },
        get_buttons: function() {
            var buttons = [];
            this.columns.forEach(function(column) {
                if (column instanceof Sao.View.Tree.ButtonColumn) {
                    buttons.push(column);
                }
            });
            return buttons;
        },
        display: function(selected, expanded) {
            var current_record = this.screen.current_record;
            if (!selected) {
                selected = this.get_selected_paths();
                if (current_record) {
                    var current_path = current_record.get_path(this.screen.group);
                    current_path = current_path.map(function(e) {
                        return e[1];
                    });
                    if (!Sao.common.contains(selected, current_path)) {
                        selected = [current_path];
                    }
                } else if (!current_record) {
                    selected = [];
                }
            }
            expanded = expanded || [];

            if ((this.screen.group.length != this.rows.length) ||
                    !Sao.common.compare(
                        this.screen.group, this.rows.map(function(row) {
                            return row.record;
                        })) || this.children_field) {  // XXX find better check
                                                       // to keep focus
                this.construct(selected, expanded);
            }

            // Set column visibility depending on attributes and domain
            var domain = [];
            if (!jQuery.isEmptyObject(this.screen.domain)) {
                domain.push(this.screen.domain);
            }
            var tab_domain = this.screen.screen_container.get_tab_domain();
            if (!jQuery.isEmptyObject(tab_domain)) {
                domain.push(tab_domain);
            }
            var inversion = new Sao.common.DomainInversion();
            domain = inversion.simplify(domain);
            this.columns.forEach(function(column) {
                var name = column.attributes.name;
                if (!name) {
                    return;
                }
                if (column.attributes.tree_invisible) {
                    column.header.hide();
                } else if (name === this.screen.exclude_field) {
                    column.header.hide();
                } else {
                    var inv_domain = inversion.domain_inversion(domain, name);
                    if (typeof inv_domain != 'boolean') {
                        inv_domain = inversion.simplify(inv_domain);
                    }
                    var unique = inversion.unique_value(inv_domain)[0];
                    if (unique && jQuery.isEmptyObject(this.children_field)) {
                        column.header.hide();
                    } else {
                        column.header.show();
                    }
                }
            }.bind(this));

            this.redraw(selected, expanded);
            return jQuery.when();
        },
        construct: function(selected, expanded) {
            this.rows = [];
            this.tbody.empty();
            var add_row = function(record, pos, group) {
                var RowBuilder;
                if (this.editable) {
                    RowBuilder = Sao.View.Tree.RowEditable;
                } else {
                    RowBuilder = Sao.View.Tree.Row;
                }
                var tree_row = new RowBuilder(this, record, pos);
                this.rows.push(tree_row);
                tree_row.construct(selected, expanded);
            };
            this.screen.group.slice(0, this.display_size).forEach(
                    add_row.bind(this));
            if (this.display_size >= this.screen.group.length) {
                this.more.hide();
            } else {
                this.more.show();
            }
        },
        redraw: function(selected, expanded) {
            var redraw_row = function(record, pos, group) {
               this.rows[pos].redraw(selected, expanded);
            };
            this.screen.group.slice(0, this.display_size).forEach(
                    redraw_row.bind(this));
        },
        switch_: function(path) {
            this.screen.row_activate();
        },
        select_changed: function(record) {
            var previous_record = this.screen.current_record;
            this.screen.set_current_record(record);
            if (this.editable && previous_record) {
                var go_previous = function() {
                    this.screen.set_current_record(previous_record);
                    this.set_cursor();
                }.bind(this);
                if (!this.screen.group.parent && previous_record !== record) {
                    previous_record.validate(this.get_fields())
                        .then(function(validate) {
                            if (!validate) {
                                go_previous();
                            } else {
                                previous_record.save().fail(go_previous);
                            }
                        });
                } else if (previous_record !== record &&
                        this.screen.attributes.pre_validate) {
                    previous_record.pre_validate().then(function(validate) {
                        if (!validate) {
                            go_previous();
                        }
                    });
                }
            }
            // TODO update_children
        },
        selected_records: function() {
            if (this.selection_mode == Sao.common.SELECTION_NONE) {
                return [];
            }
            var records = [];
            var add_record = function(row) {
                if (row.is_selected()) {
                    records.push(row.record);
                }
                row.rows.forEach(add_record);
            };
            this.rows.forEach(add_record);
            if (this.selection.prop('checked') &&
                    !this.selection.prop('indeterminate')) {
                this.screen.group.slice(this.rows.length)
                    .forEach(function(record) {
                        records.push(record);
                    });
            }
            return records;
        },
        selection_changed: function() {
            var value = this.selection.prop('checked');
            var set_checked = function(row) {
                row.set_selection(value);
                row.rows.forEach(set_checked);
            };
            this.rows.forEach(set_checked);
            if (value && this.rows[0]) {
                this.select_changed(this.rows[0].record);
            } else {
                this.select_changed(null);
            }
        },
        update_selection: function() {
            if (this.selection.prop('checked')) {
                return;
            }
            var selected_records = this.selected_records();
            this.selection.prop('indeterminate', false);
            if (jQuery.isEmptyObject(selected_records)) {
                this.selection.prop('checked', false);
            } else if (selected_records.length ==
                    this.tbody.children().length &&
                    this.display_size >= this.screen.group.length) {
                this.selection.prop('checked', true);
            } else {
                this.selection.prop('indeterminate', true);
                // Set checked to go first unchecked after first click
                this.selection.prop('checked', true);
            }
        },
        get_selected_paths: function() {
            var selected_paths = [];
            function get_selected(row, path) {
                var i, r, len, r_path;
                for (i = 0, len = row.rows.length; i < len; i++) {
                    r = row.rows[i];
                    r_path = path.concat([r.record.id]);
                    if (r.is_selected()) {
                        selected_paths.push(r_path);
                    }
                    get_selected(r, r_path);
                }
            }
            get_selected(this, []);
            return selected_paths;
        },
        get_expanded_paths: function(starting_path, starting_id_path) {
            var id_path, id_paths, row, children_rows, path;
            if (starting_path === undefined) {
                starting_path = [];
            }
            if (starting_id_path === undefined) {
                starting_id_path = [];
            }
            id_paths = [];
            row = this.find_row(starting_path);
            children_rows = row ? row.rows : this.rows;
            for (var path_idx = 0, len = this.n_children(row) ;
                    path_idx < len ; path_idx++) {
                path = starting_path.concat([path_idx]);
                row = children_rows[path_idx];
                if (row && row.is_expanded()) {
                    id_path = starting_id_path.concat(row.record.id);
                    id_paths.push(id_path);
                    id_paths = id_paths.concat(this.get_expanded_paths(path,
                                id_path));
                }
            }
            return id_paths;
        },
        find_row: function(path) {
            var index;
            var row = null;
            var group = this.rows;
            for (var i=0, len=path.length; i < len; i++) {
                index = path[i];
                if (!group || index >= group.length) {
                    return null;
                }
                row = group[index];
                group = row.rows;
                if (!this.children_field) {
                    break;
                }
            }
            return row;
        },
        n_children: function(row) {
            if (!row || !this.children_field) {
                return this.rows.length;
            }
            return row.record._values[this.children_field].length;
        },
        set_cursor: function(new_, reset_view) {
            var i, root_group, path, row_path, row, column;
            var row_idx, rest, td;

            if (!this.screen.current_record) {
                return;
            }

            path = null;
            for (i = 0; i < this.rows.length; i++) {
                row_path = this.rows[i].record_to_path(
                        this.screen.current_record);
                if (row_path) {
                    row_path.unshift(i);
                    path = row_path;
                    break;
                }
            }

            row = null;
            if (path) {
                row_idx = path[0];
                rest = path.slice(1);
                if (rest.length > 0) {
                    this.rows[row_idx].expand_to_path(rest);
                }
                row = this.find_row(path);
            } else if (this.rows.length > 0) {
                row = this.rows[0];
            }

            if (row) {
                column = row.next_column(null, new_);
                td = row._get_column_td(column);
                if (this.editable) {
                    td.triggerHandler('click');
                    if (new_) {
                        td.triggerHandler('click');
                    } else {
                        td.find(':input,[tabindex=0]').focus();
                    }
                } else {
                    td.find(':input,[tabindex=0]').focus();
                }
            }
        }
    });

    Sao.View.Tree.Row = Sao.class_(Object, {
        init: function(tree, record, pos, parent) {
            this.tree = tree;
            this.rows = [];
            this.record = record;
            this.parent_ = parent;
            this.children_field = tree.children_field;
            this.expander = null;
            var path = [];
            if (parent) {
                path = jQuery.extend([], parent.path.split('.'));
            }
            path.push(pos);
            this.path = path.join('.');
            this.el = jQuery('<tr/>');
        },
        is_expanded: function() {
            return (this.path in this.tree.expanded);
        },
        get_last_child: function() {
            if (!this.children_field || !this.is_expanded() ||
                    jQuery.isEmptyObject(this.rows)) {
                return this;
            }
            return this.rows[this.rows.length - 1].get_last_child();
        },
        get_id_path: function() {
            if (!this.parent_) {
                return [this.record.id];
            }
            return this.parent_.get_id_path().concat([this.record.id]);
        },
        build_widgets: function() {
            var table = jQuery('<table/>');
            table.css('width', '100%');
            var row = jQuery('<tr/>');
            table.append(row);
            return [table, row];
        },
        construct: function(selected, expanded) {
            selected = selected || [];
            expanded = expanded || [];

            var el_node = this.el[0];
            while (el_node.firstChild) {
                el_node.removeChild(el_node.firstChild);
            }

            var td;
            if (this.tree.selection_mode != Sao.common.SELECTION_NONE) {
                td = jQuery('<td/>');
                this.el.append(td);
                this.selection = jQuery('<input/>', {
                    'type': 'checkbox',
                    'class': 'selection'
                });
                this.selection.change(this.selection_changed.bind(this));
                td.append(this.selection);
            }

            var depth = this.path.split('.').length;
            for (var i = 0; i < this.tree.columns.length; i++) {
                var column = this.tree.columns[i];
                td = jQuery('<td/>', {
                    'data-title': column.attributes.string
                }).append(jQuery('<div/>', { // For responsive min-height
                    'aria-hidden': true
                }));
                td.css('overflow', 'hidden');
                td.on('click keypress', {column: i, td: td},
                        Sao.common.click_press(this.select_row.bind(this),
                            true));
                if (!this.tree.editable) {
                    td.dblclick(this.switch_row.bind(this));
                }
                var widgets = this.build_widgets();
                var table = widgets[0];
                var row = widgets[1];
                td.append(table);
                if ((i === 0) && this.children_field) {
                    var expanded_icon = 'glyphicon-plus';
                    if (this.is_expanded() ||
                            ~expanded.indexOf(this.record.id)) {
                        expanded_icon = 'glyphicon-minus';
                    }
                    this.expander = jQuery('<span/>', {
                        'class': 'glyphicon ' + expanded_icon,
                        'tabindex': 0
                    });
                    this.expander.html('&nbsp;');
                    this.expander.css('margin-left', (depth - 1) + 'em');
                    this.expander.css('float', 'left');
                    this.expander.on('click keypress',
                            Sao.common.click_press(this.toggle_row.bind(this)));
                    row.append(jQuery('<td/>', {
                        'class': 'expander'
                    }).append(this.expander).css('width', 1));
                }
                var j;
                if (column.prefixes) {
                    for (j = 0; j < column.prefixes.length; j++) {
                        var prefix = column.prefixes[j];
                        row.append(jQuery('<td/>', {
                            'class': 'prefix'
                        }).css('width', 1));
                    }
                }
                row.append(jQuery('<td/>', {
                    'class': 'widget'
                }));
                if (column.suffixes) {
                    for (j = 0; j < column.suffixes.length; j++) {
                        var suffix = column.suffixes[j];
                        row.append(jQuery('<td/>', {
                            'class': 'suffix'
                        }).css('width', 1));
                    }
                }

                this.el.append(td);
            }
            if (this.parent_) {
                var last_child = this.parent_.get_last_child();
                last_child.el.after(this.el);
            } else {
                this.tree.tbody.append(this.el);
            }
            var row_id_path = this.get_id_path();
            if (this.is_expanded() ||
                    Sao.common.contains(expanded, row_id_path)) {
                this.tree.expanded[this.path] = this;
                this.expand_children(selected, expanded);
            }
        },
        _get_column_td: function(column_index, row) {
            row = row || this.el;
            var child_offset = 0;
            if (this.tree.selection_mode != Sao.common.SELECTION_NONE) {
                child_offset += 1;
            }
            return jQuery(row.children()[column_index + child_offset]);
        },
        redraw: function(selected, expanded) {
            selected = selected || [];
            expanded = expanded || [];
            var update_expander = function() {
                if (jQuery.isEmptyObject(
                            this.record.field_get(
                                this.children_field))) {
                    this.expander.css('visibility', 'hidden');
                }
            };

            for (var i = 0; i < this.tree.columns.length; i++) {
                if ((i === 0) && this.children_field) {
                    this.record.load(this.children_field).done(
                        update_expander.bind(this));
                }
                var column = this.tree.columns[i];
                var td = this._get_column_td(i);
                var tr = td.find('tr');
                if (column.prefixes) {
                    for (var j = 0; j < column.prefixes.length; j++) {
                        var prefix = column.prefixes[j];
                        jQuery(tr.children('.prefix')[j])
                            .html(prefix.render(this.record));
                    }
                }
                jQuery(tr.children('.widget')).html(column.render(this.record));
                if (column.suffixes) {
                    for (var k = 0; k < column.suffixes.length; k++) {
                        var suffix = column.suffixes[k];
                        jQuery(tr.children('.suffix')[k])
                            .html(suffix.render(this.record));
                    }
                }
                if (column.attributes.tree_invisible ||
                        column.header.css('display') == 'none') {
                    td.hide();
                } else {
                    td.show();
                }
            }
            var row_id_path = this.get_id_path();
            this.set_selection(Sao.common.contains(selected, row_id_path));
            if (this.is_expanded() ||
                    Sao.common.contains(expanded, row_id_path)) {
                this.tree.expanded[this.path] = this;
                if (!this.record._values[this.children_field] ||
                        (this.record._values[this.children_field].length > 0 &&
                         this.rows.length === 0)) {
                    this.expand_children(selected, expanded);
                } else {
                    var child_row;
                    for (i = 0; i < this.rows.length; i++) {
                        child_row = this.rows[i];
                        child_row.redraw(selected, expanded);
                    }
                }
                if (this.expander) {
                    this.update_expander(true);
                }
            } else {
                if (this.expander) {
                    this.update_expander(false);
                }
            }
            if (this.record.deleted() || this.record.removed()) {
                this.el.css('text-decoration', 'line-through');
            } else {
                this.el.css('text-decoration', 'inherit');
            }
        },
        toggle_row: function() {
            if (this.is_expanded()) {
                this.update_expander(false);
                delete this.tree.expanded[this.path];
                this.collapse_children();
            } else {
                this.update_expander(true);
                this.tree.expanded[this.path] = this;
                this.expand_children();
            }
            return false;
        },
        update_expander: function(expanded) {
            if (expanded) {
                this.expander.removeClass('glyphicon-plus');
                this.expander.addClass('glyphicon-minus');
            } else {
                this.expander.removeClass('glyphicon-minus');
                this.expander.addClass('glyphicon-plus');
            }
        },
        collapse_children: function() {
            this.rows.forEach(function(row, pos, rows) {
                row.collapse_children();
                var node = row.el[0];
                node.parentNode.removeChild(node);
            });
            this.rows = [];
        },
        expand_children: function(selected, expanded) {
            var add_children = function() {
                if (!jQuery.isEmptyObject(this.rows)) {
                    return;
                }
                var add_row = function(record, pos, group) {
                    var tree_row = new this.Class(
                            this.tree, record, pos, this);
                    tree_row.construct(selected, expanded);
                    tree_row.redraw(selected, expanded);
                    this.rows.push(tree_row);
                };
                var children = this.record.field_get_client(
                        this.children_field);
                children.forEach(add_row.bind(this));
            };
            return this.record.load(this.children_field).done(
                    add_children.bind(this));
        },
        switch_row: function() {
            if (window.getSelection) {
                if (window.getSelection().empty) {  // Chrome
                    window.getSelection().empty();
                } else if (window.getSelection().removeAllRanges) {  // Firefox
                    window.getSelection().removeAllRanges();
                }
            } else if (document.selection) {  // IE?
                document.selection.empty();
            }
            if (this.tree.selection_mode != Sao.common.SELECTION_NONE) {
                this.set_selection(true);
                this.selection_changed();
                if (!this.is_selected()) {
                    return;
                }
            }
            this.tree.switch_(this.path);
        },
        select_row: function(event_) {
            if (this.tree.selection_mode == Sao.common.SELECTION_NONE) {
                this.tree.select_changed(this.record);
                this.switch_row();
            } else {
                if (!event_.ctrlKey &&
                        this.tree.selection_mode ==
                        Sao.common.SELECTION_SINGLE) {
                    this.tree.rows.forEach(function(row) {
                        row.set_selection(false);
                    }.bind(this));
                }
                this.set_selection(!this.is_selected());
                this.selection_changed();
            }

            // The 'click'-event must be handled next time the row is clicked
            var td = event_.data.td;
            var column = event_.data.column;
            td.on('click keypress', {column: column, td: td},
                    Sao.common.click_press(this.select_row.bind(this), true));
        },
        is_selected: function() {
            if (this.tree.selection_mode == Sao.common.SELECTION_NONE) {
                return false;
            }
            return this.selection.prop('checked');
        },
        set_selection: function(value) {
            if (this.tree.selection_mode == Sao.common.SELECTION_NONE) {
                return;
            }
            this.selection.prop('checked', value);
            if (!value) {
                this.tree.selection.prop('checked', false);
            }
        },
        selection_changed: function() {
            var is_selected = this.is_selected();
            this.set_selection(is_selected);
            if (is_selected) {
                this.tree.select_changed(this.record);
            } else {
                this.tree.select_changed(
                        this.tree.selected_records()[0] || null);
            }
            this.tree.update_selection();
        },
        record_to_path: function(record) {
            // recursively get the path to the record
            var i, path;
            if (record == this.record) {
                return [];
            } else {
                for (i = 0; i < this.rows.length; i++) {
                    path = this.rows[i].record_to_path(record);
                    if (path) {
                        path.unshift(i);
                        return path;
                    }
                }
            }
        },
        expand_to_path: function(path) {
            var row_idx, rest;
            row_idx = path[0];
            rest = path.slice(1);
            if (rest.length > 0) {
                this.rows[row_idx].expand_children().done(function() {
                    this.rows[row_idx].expand_to_path(rest);
                }.bind(this));
            }
        },
        next_column: function(column, editable, sign) {
            var i, readonly;
            var column_index, state_attrs;

            sign = sign || 1;
            if ((column === null) && (sign > 0)) {
                column = -1;
            } else if (column === null) {
                column = 0;
            }
            column_index = 0;
            for (i = 0; i < this.tree.columns.length; i++) {
                column_index = ((column + (sign * (i + 1))) %
                        this.tree.columns.length);
                // javascript modulo returns negative number for negative
                // numbers
                if (column_index < 0) {
                    column_index += this.tree.columns.length;
                }
                column = this.tree.columns[column_index];
                state_attrs = column.field.get_state_attrs(this.record);
                if (editable) {
                    readonly = (column.attributes.readonly ||
                            state_attrs.readonly);
                } else {
                    readonly = false;
                }
                if (!(state_attrs.invisible || readonly)) {
                    break;
                }
            }
            return column_index;
        }
    });

    Sao.View.Tree.RowEditable = Sao.class_(Sao.View.Tree.Row, {
        init: function(tree, record, pos, parent) {
            Sao.View.Tree.RowEditable._super.init.call(this, tree, record, pos,
                parent);
            this.edited_column = null;
        },
        redraw: function(selected, expanded) {
            var i, tr, td, widget;
            var field;

            Sao.View.Tree.RowEditable._super.redraw.call(this, selected,
                    expanded);
            // The autocompletion widget do not call display thus we have to
            // call it when redrawing the row
            for (i = 0; i < this.tree.columns.length; i++) {
                td = this._get_column_td(i);
                tr = td.find('tr');
                widget = jQuery(tr.children('.widget-editable')).data('widget');
                if (widget) {
                    field = this.record.model.fields[widget.field_name];
                    widget.display(this.record, field);
                }
            }
        },
        select_row: function(event_) {
            var previously_selected, previous_td;
            var inner_rows, readonly_row, editable_row, current_td;
            var field, widget;

            function get_previously_selected(rows, selected) {
                var i, r;
                for (i = 0; i < rows.length; i++) {
                    r = rows[i];
                    if (r.is_selected()) {
                        previously_selected = r;
                    }
                    if (r != selected) {
                        r.set_selection(false);
                    }
                    get_previously_selected(r.rows, selected);
                }
            }
            get_previously_selected(this.tree.rows, this);
            this.selection_changed();

            var save_prm;
            if (previously_selected && previously_selected != this &&
                    !this.tree.screen.group.parent) {
                save_prm = previously_selected.record.save();
            } else {
                save_prm = jQuery.when();
            }
            save_prm.done(function () {
                if (previously_selected &&
                        previously_selected.edited_column !== null) {
                    previous_td = previously_selected.get_active_td();
                    previous_td.on('click keypress', {
                        td: previous_td,
                        column: previously_selected.edited_column
                    }, Sao.common.click_press(
                        previously_selected.select_row.bind(previously_selected),
                        true));
                    var previous_column = this.tree.columns[
                        previously_selected.edited_column];
                    previously_selected.get_static_el()
                        .html(previous_column.render(previously_selected.record))
                        .show();
                    previously_selected.empty_editable_el();
                }
                if (this.is_selected()) {
                    this.edited_column = event_.data.column;
                    current_td = this.get_active_td();
                    var attributes = this.tree.columns[this.edited_column]
                        .attributes;
                    var EditableBuilder = Sao.View.editabletree_widget_get(
                        attributes.widget);
                    widget = new EditableBuilder(attributes.name,
                            this.tree.screen.model, attributes);
                    widget.view = this.tree;
                    // We have to define an overflow:visible in order for the
                    // completion widget to be shown
                    widget.el.on('focusin', function() {
                        jQuery(this).parents('.treeview td')
                            .css('overflow', 'visible');
                    });
                    widget.el.on('focusout', function() {
                        jQuery(this).parents('.treeview td')
                            .css('overflow', 'hidden');
                    });
                    var editable_el = this.get_editable_el();
                    editable_el.append(widget.el);
                    editable_el.data('widget', widget);
                    // We use keydown to be able to catch TAB events
                    widget.el.on('keydown', this.key_press.bind(this));
                    field = this.record.model.fields[widget.field_name];
                    widget.display(this.record, field);
                    this.get_static_el().hide();
                    this.get_editable_el().show();
                    widget.el.focus();
                } else {
                    this.set_selection(true);
                    this.selection_changed();
                    var td = event_.data.td;
                    var column = event_.data.column;
                    td.on('click keypress', {column: column, td: td},
                        Sao.common.click_press(this.select_row.bind(this),
                            true));
                }
            }.bind(this));
        },
        get_static_el: function() {
            var td = this.get_active_td();
            return td.find('.widget');
        },
        get_editable_el: function() {
            var td = this.get_active_td();
            var editable = td.find('.widget-editable');
            if (!editable.length) {
                editable = jQuery('<td/>', {
                        'class': 'widget-editable'
                    }).insertAfter(td.find('.widget'));
            }
            return editable;
        },
        empty_editable_el: function() {
            var editable;
            editable = this.get_editable_el();
            editable.empty();
            editable.data('widget', null);
            this.edited_column = null;
        },
        get_active_td: function() {
            return this._get_column_td(this.edited_column);
        },
        key_press: function(event_) {
            var current_td, selector, next_column, next_idx, i, next_row;
            var states;

            if ((event_.which != Sao.common.TAB_KEYCODE) &&
                    (event_.which != Sao.common.UP_KEYCODE) &&
                    (event_.which != Sao.common.DOWN_KEYCODE) &&
                    (event_.which != Sao.common.ESC_KEYCODE) &&
                    (event_.which != Sao.common.RETURN_KEYCODE)) {
                return;
            }
            var column = this.tree.columns[this.edited_column];
            if (column.field.validate(this.record)) {
                if (event_.which == Sao.common.TAB_KEYCODE) {
                    var sign = 1;
                    if (event_.shiftKey) {
                        sign = -1;
                    }
                    event_.preventDefault();
                    next_idx = this.next_column(this.edited_column, true, sign);
                    window.setTimeout(function() {
                        var td = this._get_column_td(next_idx);
                        td.triggerHandler('click', {
                            column: next_idx,
                            td: td
                        });
                    }.bind(this), 0);
                } else if (event_.which == Sao.common.UP_KEYCODE ||
                    event_.which == Sao.common.DOWN_KEYCODE) {
                    if (event_.which == Sao.common.UP_KEYCODE) {
                        next_row = this.el.prev('tr');
                    } else {
                        next_row = this.el.next('tr');
                    }
                    next_column = this.edited_column;
                    this.record.validate(this.tree.get_fields())
                        .then(function(validate) {
                            if (!validate) {
                                next_row = null;
                                var invalid_fields =
                                    this.record.invalid_fields();
                                for (i = 0; i < this.tree.columns.length; i++) {
                                    var col = this.tree.columns[i];
                                    if (col.attributes.name in invalid_fields) {
                                        next_column = i;
                                    }
                                }
                            } else {
                                if (this.tree.screen.attributes.pre_validate) {
                                    return this.record.pre_validate()
                                        .fail(function() {
                                            next_row = null;
                                        });
                                } else if (!this.tree.screen.model.parent) {
                                    return this.record.save()
                                        .fail(function() {
                                            next_row = null;
                                        });
                                }
                            }
                        }.bind(this)).then(function() {
                            window.setTimeout(function() {
                                this._get_column_td(next_column, next_row)
                                .trigger('click').trigger('click');
                            }.bind(this), 0);
                        }.bind(this));
                } else if (event_.which == Sao.common.ESC_KEYCODE) {
                    this.get_static_el().show();
                    current_td = this.get_active_td();
                    current_td.on('click keypress',
                            {column: this.edited_column, td: current_td},
                            Sao.common.click_press(this.select_row.bind(this),
                                true));
                    this.empty_editable_el();
                } else if (event_.which == Sao.common.RETURN_KEYCODE) {
                    var focus_cell = function(row) {
                        var td = this._get_column_td(this.edited_column, row);
                        td.triggerHandler('click');
                        td.triggerHandler('click');
                    }.bind(this);
                    if (this.tree.attributes.editable == 'bottom') {
                        next_row = this.el.next('tr');
                    } else {
                        next_row = this.el.prev('tr');
                    }
                    if (next_row.length) {
                        focus_cell(next_row);
                    } else {
                        // TODO access and size_limit
                        this.tree.screen.new_().done(function() {
                            var new_row;
                            var rows = this.tree.tbody.children('tr');
                            if (this.tree.attributes.editable == 'bottom') {
                                new_row = rows.last();
                            } else {
                                new_row = rows.first();
                            }
                            focus_cell(new_row);
                        }.bind(this));
                    }
                }
            }
        }
    });

    Sao.View.Tree.Affix = Sao.class_(Object, {
        init: function(attributes, protocol) {
            this.attributes = attributes;
            this.protocol = protocol || null;
            this.icon = attributes.icon;
            if (this.protocol && !this.icon) {
                this.icon = 'tryton-web-browser';
            }
        },
        get_cell: function() {
            var cell;
            if (this.protocol) {
                cell = jQuery('<a/>', {
                    'target': '_new'
                });
                cell.append(jQuery('<img/>'));
                cell.click({'cell': cell}, this.clicked.bind(this));
            } else if (this.icon) {
                cell = jQuery('<img/>');
            } else {
                cell = jQuery('<span/>');
                cell.attr('tabindex', 0);
            }
            cell.addClass('column-affix');
            return cell;
        },
        render: function(record) {
            var cell = this.get_cell();
            record.load(this.attributes.name).done(function() {
                var value, icon_prm;
                var field = record.model.fields[this.attributes.name];
                var invisible = field.get_state_attrs(record).invisible;
                if (invisible) {
                    cell.hide();
                } else {
                    cell.show();
                }
                if (this.protocol) {
                    value = field.get(record);
                    if (!jQuery.isEmptyObject(value)) {
                        switch (this.protocol) {
                            case 'email':
                                value = 'mailto:' + value;
                                break;
                            case 'callto':
                                value = 'callto:' + value;
                                break;
                            case 'sip':
                                value = 'sip:' + value;
                                break;
                        }
                    }
                    cell.attr('src', value);
                }
                if (this.icon) {
                    if (this.icon in record.model.fields) {
                        var icon_field = record.model.fields[this.icon];
                        value = icon_field.get_client(record);
                    }
                    else {
                        value = this.icon;
                    }
                    icon_prm = Sao.common.ICONFACTORY.register_icon(value);
                    icon_prm.done(function(url) {
                        var img_tag;
                        if (cell.children('img').length) {
                            img_tag = cell.children('img');
                        } else {
                            img_tag = cell;
                        }
                        img_tag.attr('src', url);
                    }.bind(this));
                } else {
                    value = this.attributes.string || '';
                    if (!value) {
                        value = field.get_client(record) || '';
                    }
                    cell.text(value);
                }
            }.bind(this));
            return cell;
        },
        clicked: function(event) {
            event.preventDefault();  // prevent edition
            window.open(event.data.cell.attr('src'), '_blank');
        }
    });

    Sao.View.Tree.CharColumn = Sao.class_(Object, {
        class_: 'column-char',
        init: function(model, attributes) {
            this.type = 'field';
            this.model = model;
            this.field = model.fields[attributes.name];
            this.attributes = attributes;
            this.prefixes = [];
            this.suffixes = [];
            this.header = null;
        },
        get_cell: function() {
            var cell = jQuery('<div/>', {
                'class': this.class_,
                'tabindex': 0
            });
            return cell;
        },
        update_text: function(cell, record) {
            cell.text(this.field.get_client(record));
        },
        render: function(record) {
            var cell = this.get_cell();
            record.load(this.attributes.name).done(function() {
                this.update_text(cell, record);
                this.field.set_state(record);
                var state_attrs = this.field.get_state_attrs(record);
                if (state_attrs.invisible) {
                    cell.hide();
                } else {
                    cell.show();
                }
            }.bind(this));
            return cell;
        }
    });

    Sao.View.Tree.IntegerColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-integer',
        init: function(model, attributes) {
            Sao.View.Tree.IntegerColumn._super.init.call(this, model, attributes);
            this.factor = Number(attributes.factor || 1);
        },
        get_cell: function() {
            return Sao.View.Tree.IntegerColumn._super.get_cell.call(this);
        },
        update_text: function(cell, record) {
            cell.text(this.field.get_client(record, this.factor));
        }
    });

    Sao.View.Tree.FloatColumn = Sao.class_(Sao.View.Tree.IntegerColumn, {
        class_: 'column-float'
    });

    Sao.View.Tree.BooleanColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-boolean',
        get_cell: function() {
            return jQuery('<input/>', {
                'type': 'checkbox',
                'disabled': true,
                'class': this.class_,
                'tabindex': 0
            });
        },
        update_text: function(cell, record) {
            cell.prop('checked', this.field.get(record));
        }
    });

    Sao.View.Tree.Many2OneColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-many2one'
    });

    Sao.View.Tree.One2OneColumn = Sao.class_(Sao.View.Tree.Many2OneColumn, {
        class_: 'column-one2one'
    });

    Sao.View.Tree.SelectionColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-selection',
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
        update_text: function(cell, record) {
            this.update_selection(record, function() {
                var value = this.field.get(record);
                var prm, text, found = false;
                for (var i = 0, len = this.selection.length; i < len; i++) {
                    if (this.selection[i][0] === value) {
                        found = true;
                        text = this.selection[i][1];
                        break;
                    }
                }
                if (!found) {
                    prm = Sao.common.selection_mixin.get_inactive_selection
                        .call(this, value).then(function(inactive) {
                            return inactive[1];
                        });
                } else {
                    prm = jQuery.when(text);
                }
                prm.done(function(text_value) {
                    cell.text(text_value);
                }.bind(this));
            }.bind(this));
        }
    });

    Sao.View.Tree.ReferenceColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-reference',
        init: function(model, attributes) {
            Sao.View.Tree.ReferenceColumn._super.init.call(this, model,
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
        update_text: function(cell, record) {
            this.update_selection(record, function() {
                var value = this.field.get_client(record);
                var model, name;
                if (!value) {
                    model = '';
                    name = '';
                } else {
                    model = value[0];
                    name = value[1];
                }
                if (model) {
                    cell.text(this.selection[model] || model + ',' + name);
                } else {
                    cell.text(name);
                }
            }.bind(this));
        }
    });

    Sao.View.Tree.DateColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-date',
        update_text: function(cell, record) {
            var value = this.field.get_client(record);
            var date_format = this.field.date_format(record);
            cell.text(Sao.common.format_date(date_format, value));
        }
    });

    Sao.View.Tree.TimeColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-time',
        update_text: function(cell, record) {
            var value = this.field.get_client(record);
            cell.text(Sao.common.format_time(
                    this.field.time_format(record), value));
        }
    });

    Sao.View.Tree.TimeDeltaColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-timedelta'
    });

    Sao.View.Tree.One2ManyColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-one2many',
        update_text: function(cell, record) {
            cell.text('( ' + this.field.get_client(record).length + ' )');
        }
    });

    Sao.View.Tree.Many2ManyColumn = Sao.class_(Sao.View.Tree.One2ManyColumn, {
        class_: 'column-many2many'
    });

    Sao.View.Tree.ImageColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-image',
        get_cell: function() {
            var cell = jQuery('<img/>', {
                'class': this.class_,
                'tabindex': 0
            });
            cell.css('width', '100%');
            return cell;
        },
        render: function(record) {
            var cell = this.get_cell();
            record.load(this.attributes.name).done(function() {
                var value = this.field.get_client(record);
                if (value) {
                    if (value > Sao.common.BIG_IMAGE_SIZE) {
                        value = jQuery.when(null);
                    } else {
                        value = this.field.get_data(record);
                    }
                } else {
                    value = jQuery.when(null);
                }
                value.done(function(data) {
                    var img_url, blob;
                    if (!data) {
                        img_url = null;
                    } else {
                        blob = new Blob([data[0][this.field.name]]);
                        img_url = window.URL.createObjectURL(blob);
                    }
                    cell.attr('src', img_url);
                }.bind(this));
            }.bind(this));
            return cell;
        }
    });

    Sao.View.Tree.URLColumn = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-url',
        render: function(record) {
            var cell = Sao.View.Tree.URLColumn._super.render.call(this, record);
            this.field.set_state(record);
            var state_attrs = this.field.get_state_attrs(record);
            if (state_attrs.readonly) {
                cell.hide();
            } else {
                cell.show();
            }
        }
    });

    Sao.View.Tree.ProgressBar = Sao.class_(Sao.View.Tree.CharColumn, {
        class_: 'column-progressbar',
        get_cell: function() {
            var cell = jQuery('<div/>', {
                'class': this.class_ + ' progress',
                'tabindex': 0
            });
            var progressbar = jQuery('<div/>', {
                'class': 'progress-bar',
                'role': 'progressbar',
                'aria-valuemin': 0,
                'aria-valuemax': 100
            }).appendTo(cell);
            progressbar.css('min-width: 2em');
            return cell;
        },
        update_text: function(cell, record) {
            var text = this.field.get_client(record, 100);
            if (text) {
                text = Sao.i18n.gettext('%1%', text);
            }
            var value = this.field.get(record) || 0;
            var progressbar = cell.find('.progress-bar');
            progressbar.attr('aria-valuenow', value * 100);
            progressbar.css('width', value * 100 + '%');
            progressbar.text(text);
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
            var states = record.expr_eval(this.attributes.states || {});
            if (states.invisible || states.readonly) {
                return;
            }
            this.screen.button(this.attributes);
        }
    });

    Sao.View.editabletree_widget_get = function(type) {
        switch (type) {
            case 'char':
            case 'text':
            case 'url':
            case 'email':
            case 'callto':
            case 'sip':
                return Sao.View.EditableTree.Char;
            case 'date':
                return Sao.View.EditableTree.Date;
            case 'time':
                return Sao.View.EditableTree.Time;
            case 'timedelta':
                return Sao.View.EditableTree.TimeDelta;
            case 'integer':
            case 'biginteger':
                return Sao.View.EditableTree.Integer;
            case 'float':
            case 'numeric':
                return Sao.View.EditableTree.Float;
            case 'selection':
                return Sao.View.EditableTree.Selection;
            case 'boolean':
                return Sao.View.EditableTree.Boolean;
            case 'many2one':
                return Sao.View.EditableTree.Many2One;
            case 'one2one':
                return Sao.View.EditableTree.One2One;
            case 'one2many':
            case 'many2many':
                return Sao.View.EditableTree.One2Many;
            case 'binary':
                return Sao.View.EditableTree.Binary;
        }
    };

    Sao.View.EditableTree = {};

    Sao.View.EditableTree.editable_mixin = function(widget) {
        var key_press = function(event_) {
            if ((event_.which == Sao.common.TAB_KEYCODE) ||
                    (event_.which == Sao.common.UP_KEYCODE) ||
                    (event_.which == Sao.common.DOWN_KEYCODE) ||
                    (event_.which == Sao.common.ESC_KEYCODE) ||
                    (event_.which == Sao.common.RETURN_KEYCODE)) {
                this.focus_out();
            }
        };
        widget.el.on('keydown', key_press.bind(widget));
    };

    Sao.View.EditableTree.Char = Sao.class_(Sao.View.Form.Char, {
        class_: 'editabletree-char',
        init: function(field_name, model, attributes) {
            Sao.View.EditableTree.Char._super.init.call(this, field_name,
                model, attributes);
            Sao.View.EditableTree.editable_mixin(this);
        }
    });

    Sao.View.EditableTree.Date = Sao.class_(Sao.View.Form.Date, {
        class_: 'editabletree-date',
        init: function(field_name, model, attributes) {
            Sao.View.EditableTree.Date._super.init.call(this, field_name,
                model, attributes);
            Sao.View.EditableTree.editable_mixin(this);
        }
    });

    Sao.View.EditableTree.Time = Sao.class_(Sao.View.Form.Time, {
        class_: 'editabletree-time',
        init: function(field_name, model, attributes) {
            Sao.View.EditableTree.Time._super.init.call(this, field_name,
                model, attributes);
            Sao.View.EditableTree.editable_mixin(this);
        }
    });

    Sao.View.EditableTree.TimeDelta = Sao.class_(Sao.View.Form.TimeDelta, {
        class_: 'editabletree-timedelta',
        init: function(field_name, model, attributes) {
            Sao.View.EditableTree.TimeDelta._super.init.call(this, field_name,
                model, attributes);
            Sao.View.EditableTree.editable_mixin(this);
        }
    });

    Sao.View.EditableTree.Integer = Sao.class_(Sao.View.Form.Integer, {
        class_: 'editabletree-integer',
        init: function(field_name, model, attributes) {
            Sao.View.EditableTree.Integer._super.init.call(this, field_name,
                model, attributes);
            Sao.View.EditableTree.editable_mixin(this);
        }
    });

    Sao.View.EditableTree.Float = Sao.class_(Sao.View.Form.Float, {
        class_: 'editabletree-float',
        init: function(field_name, model, attributes) {
            Sao.View.EditableTree.Float._super.init.call(this, field_name,
                model, attributes);
            Sao.View.EditableTree.editable_mixin(this);
        }
    });

    Sao.View.EditableTree.Selection = Sao.class_(Sao.View.Form.Selection, {
        class_: 'editabletree-selection',
        init: function(field_name, model, attributes) {
            Sao.View.EditableTree.Selection._super.init.call(this, field_name,
                model, attributes);
            Sao.View.EditableTree.editable_mixin(this);
        }
    });

    Sao.View.EditableTree.Boolean = Sao.class_(Sao.View.Form.Boolean, {
        class_: 'editabletree-boolean',
        init: function(field_name, model, attributes) {
            Sao.View.EditableTree.Boolean._super.init.call(this, field_name,
                model, attributes);
            Sao.View.EditableTree.editable_mixin(this);
        }
    });

    Sao.View.EditableTree.Many2One = Sao.class_(Sao.View.Form.Many2One, {
        class_: 'editabletree-many2one',
        init: function(field_name, model, attributes) {
            Sao.View.EditableTree.Many2One._super.init.call(this, field_name,
                model, attributes);
            this.el.on('keydown', this.key_press.bind(this));
        },
        key_press: function(event_) {
            if (event_.which == Sao.common.TAB_KEYCODE) {
                this.focus_out();
            } else {
                Sao.View.EditableTree.Many2One._super.key_press.call(this,
                    event_);
            }
        }
    });

    Sao.View.EditableTree.One2One = Sao.class_(Sao.View.Form.One2One, {
        class_: 'editabletree-one2one',
        init: function(field_name, model, attributes) {
            Sao.View.EditableTree.One2One._super.init.call(this, field_name,
                model, attributes);
            this.el.on('keydown', this.key_press.bind(this));
        },
        key_press: function(event_) {
            if (event_.which == Sao.common.TAB_KEYCODE) {
                this.focus_out();
            } else {
                Sao.View.EditableTree.One2One._super.key_press.call(this,
                    event_);
            }
        }
    });

    Sao.View.EditableTree.One2Many = Sao.class_(Sao.View.EditableTree.Char, {
        class_: 'editabletree-one2many',
        init: function(field_name, model, attributes) {
            Sao.View.EditableTree.One2Many._super.init.call(this, field_name,
                model, attributes);
        },
        display: function(record, field) {
            if (record) {
                this.el.val('(' + field.get_client(record).length + ')');
            } else {
                this.el.val('');
            }
        },
        key_press: function(event_) {
            if (event_.which == Sao.common.TAB_KEYCODE) {
                this.focus_out();
            }
        },
        set_value: function(record, field) {
        }
    });

    Sao.View.EditableTree.Binary = Sao.class_(Sao.View.Form.Binary, {
        class_: 'editabletree-binary',
        init: function(field_name, model, attributes) {
            Sao.View.EditableTree.Binary._super.init.call(this, field_name,
                model, attributes);
            Sao.View.EditableTree.editable_mixin(this);
        }
    });

}());
