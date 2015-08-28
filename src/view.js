/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.View = Sao.class_(Object, {
        init: function(screen, xml) {
            this.screen = screen;
            this.view_type = null;
            this.el = null;
            this.view_id = null;
            this.fields = {};
            var attributes = xml.children()[0].attributes;
            this.attributes = {};
            for (var i = 0, len = attributes.length; i < len; i++) {
                var attribute = attributes[i];
                this.attributes[attribute.name] = attribute.value;
            }
            screen.set_on_write(this.attributes.on_write);
        },
        set_value: function() {
        },
        get_fields: function() {
            return Object.keys(this.fields);
        },
        get_buttons: function() {
            return [];
        }
    });

    Sao.View.idpath2path = function(tree, idpath) {
        var path = [];
        var child_path;
        if (!idpath) {
            return [];
        }
        for (var i = 0, len = tree.rows.length; i < len; i++) {
            if (tree.rows[i].record.id == idpath[0]) {
                path.push(i);
                child_path = Sao.View.idpath2path(tree.rows[i],
                        idpath.slice(1, idpath.length));
                path = path.concat(child_path);
                break;
            }
        }
        return path;
    };

    Sao.View.parse = function(screen, xml, children_field) {
        switch (xml.children().prop('tagName')) {
            case 'tree':
                return new Sao.View.Tree(screen, xml, children_field);
            case 'form':
                return new Sao.View.Form(screen, xml);
            case 'graph':
                return new Sao.View.Graph(screen, xml);
        }
    };

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
                'class': 'treeview'
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
                'class': 'tree table table-hover'
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
                if (column.attributes.required) {
                    label.addClass('required');
                }
                tr.append(th.append(label));
                column.header = th;
            });
            this.tbody = jQuery('<tbody/>');
            this.table.append(this.tbody);

            // Footer for more
            var footer = jQuery('<div/>', {
                'class': 'treefooter'
            });
            this.more = jQuery('<button/>').button({
                'label': Sao.i18n.gettext('More')
            }).click(function() {
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
                        'selection_change_with', 'schema_model', 'required'];
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
                if (current_record && !Sao.common.contains(selected,
                            [[current_record.id]])) {
                    selected = [[current_record.id]];
                }
            }
            expanded = expanded || [];

            if ((this.screen.group.length != this.rows.length) ||
                    !Sao.common.compare(this.screen.group, this.rows.map(function(row) {
                        return row.record;
                    }))) {
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
                    if (unique) {
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
                    // TODO set_cursor
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
                td.one('click', {column: i, td: td},
                        this.select_row.bind(this));
                td.dblclick(this.switch_row.bind(this));
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
                        'class': 'glyphicon ' + expanded_icon
                    });
                    this.expander.html('&nbsp;');
                    this.expander.css('margin-left', (depth - 1) + 'em');
                    this.expander.css('float', 'left');
                    this.expander.click(this.toggle_row.bind(this));
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
                    var tree_row = new Sao.View.Tree.Row(this.tree, record,
                            pos, this);
                    tree_row.construct(selected, expanded);
                    tree_row.redraw(selected, expanded);
                    this.rows.push(tree_row);
                };
                var children = this.record.field_get_client(
                        this.children_field);
                children.forEach(add_row.bind(this));
            };
            this.record.load(this.children_field).done(
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
            td.one('click', {column: column, td: td},
                    this.select_row.bind(this));
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
        }
    });

    Sao.View.Tree.RowEditable = Sao.class_(Sao.View.Tree.Row, {
        init: function(tree, record, pos, parent) {
            Sao.View.Tree.RowEditable._super.init.call(this, tree, record, pos,
                parent);
            this.edited_column = undefined;
        },
        select_row: function(event_) {
            var previously_selected, previous_td;
            var inner_rows, readonly_row, editable_row, current_td;
            var field, widget;

            this.tree.rows.forEach(function(row) {
                if (row.is_selected()) {
                    previously_selected = row;
                }
                if (row != this) {
                    row.set_selection(false);
                }
            }.bind(this));
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
                    previously_selected.edited_column !== undefined) {
                    previous_td = previously_selected.get_active_td();
                    previous_td.one('click', {
                        td: previous_td,
                        column: previously_selected.edited_column
                    }, previously_selected.select_row.bind(previously_selected));
                    var previous_column = this.tree.columns[
                        previously_selected.edited_column];
                    previously_selected.get_widget()
                        .html(previous_column.render(previously_selected.record))
                        .show();
                    previously_selected.get_widget_editable().hide();
                    previously_selected.edited_column = undefined;
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
                    this.get_widget_editable().empty().append(widget.el);
                    // We use keydown to be able to catch TAB events
                    widget.el.on('keydown', this.key_press.bind(this));
                    field = this.record.model.fields[widget.field_name];
                    widget.display(this.record, field);
                    this.get_widget().hide();
                    this.get_widget_editable().show();
                    widget.focus();
                } else {
                    this.set_selection(true);
                    this.selection_changed();
                    var td = event_.data.td;
                    var column = event_.data.column;
                    td.one('click', {column: column, td: td},
                        this.select_row.bind(this));
                }
            }.bind(this));
        },
        get_widget: function() {
            var td = this.get_active_td();
            return td.find('.widget');
        },
        get_widget_editable: function() {
            var td = this.get_active_td();
            var editable = td.find('.widget-editable');
            if (!editable.length) {
                editable = jQuery('<td/>', {
                        'class': 'widget-editable'
                    }).insertAfter(td.find('.widget'));
            }
            return editable;
        },
        get_active_td: function() {
            return this._get_column_td(this.edited_column);
        },
        key_press: function(event_) {
            var current_td, selector, next_column, next_idx, i;
            var states;

            if ((event_.which != Sao.common.TAB_KEYCODE) &&
                    (event_.which != Sao.common.UP_KEYCODE) &&
                    (event_.which != Sao.common.DOWN_KEYCODE) &&
                    (event_.which != Sao.common.ESC_KEYCODE)) {
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
                    next_idx = ((this.edited_column + sign) %
                            this.tree.columns.length);
                    // javascript modulo returns negative number for negative
                    // numbers
                    if (next_idx < 0) {
                        next_idx += this.tree.columns.length;
                    }
                    while(next_idx != this.edited_column) {
                        next_column = this.tree.columns[next_idx];
                        states = next_column.field.get_state_attrs(this.record);
                        if (!next_column.attributes.tree_invisible &&
                                next_column.header.css('display') != 'none' &&
                                !states.readonly) {
                            break;
                        }
                        next_idx = ((next_idx + sign) %
                                this.tree.columns.length);
                        if (next_idx < 0) {
                            next_idx += this.tree.columns.length;
                        }
                    }
                    window.setTimeout(function() {
                        var td = this._get_column_td(next_idx);
                        td.triggerHandler('click', {
                            column: next_idx,
                            td: td
                        });
                    }.bind(this), 0);
                } else if (event_.which == Sao.common.UP_KEYCODE ||
                    event_.which == Sao.common.DOWN_KEYCODE) {
                    var next_row;
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
                    this.get_widget().show();
                    this.get_widget_editable().hide();
                    current_td = this.get_active_td();
                    current_td.one('click',
                            {column: this.edited_column, td: current_td},
                            this.select_row.bind(this));
                    this.edited_column = undefined;
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
            var cell = jQuery('<div/>');
            cell.addClass(this.class_);
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
                // TODO editable: readonly and required
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
                'class': this.class_
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
            var cell = jQuery('<img/>');
            cell.addClass(this.class_);
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
                'class': this.class_ + ' progress'
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
            var value = this.field.get_client(record, 100);
            var progressbar = cell.find('.progress-bar');
            progressbar.prop('aria-valuenow', value);
            progressbar.css('width', value + '%');
            progressbar.text(Sao.i18n.gettext('%1%', value));
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
            this.containers = [];
            var root = xml.children()[0];
            var container = this.parse(screen.model, root);
            this.el.append(container.el);
        },
        parse: function(model, node, container) {
            if (container === undefined) {
                container = new Sao.View.Form.Container(
                    Number(node.getAttribute('col') || 4));
                this.containers.push(container);
            }
            var labels = {}, widget;
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
                switch (child.tagName) {
                    case 'image':
                        // TODO
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
            } else if (!text) {
                // TODO get content
            }
            var label;
            if (text) {
                label = new Sao.View.Form.Label(text, attributes);
                this.state_widgets.push(label);
            }
            container.add(attributes, label);
            // TODO help
            return label;
        },
        _parse_button: function(node, container, attributes) {
            var button = new Sao.common.Button(attributes);
            this.state_widgets.push(button);
            container.add(attributes, button);
            button.el.click(button, this.button_clicked.bind(this));
            // TODO help
        },
        _parse_notebook: function(model, node, container, attributes) {
            if (attributes.colspan === undefined) {
                attributes.colspan = 4;
            }
            var notebook = new Sao.View.Form.Notebook(attributes);
            this.state_widgets.push(notebook);
            container.add(attributes, notebook);
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
                text = Sao.i18n.gettext('No String Attr.');
            }
            var page = this.parse(model, node);
            page = new Sao.View.Form.Page(container.add(page.el, text),
                    attributes);
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
            var attribute_names = ['relation', 'domain', 'selection',
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
            // TODO expand, fill, help, height, width
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
            this.screen.button(button.attributes);
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
                if (xexpand && el) {
                    el.css('width', '100%');
                }
            }
            row.append(cell);
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
                        (cell.children().css('display') != 'none')) {
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
                        (cell.children().css('display') != 'none')) {
                        var width = 0;
                        for (j = 0; j < colspan; j++) {
                            width += widths[i + j] || 0;
                        }
                        cell.css('width', width + '%');
                    }
                    if (cell.children().css('display') == 'none') {
                        cell.hide();
                    } else {
                        cell.show();
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
                this.el.append(jQuery('<label/>', {
                    text: text
                }));
            }
            this.el.append(jQuery('<hr/>'));
        }
    });

    Sao.View.Form.Label = Sao.class_(StateWidget, {
        class_: 'form-label',
        init: function(text, attributes) {
            Sao.View.Form.Label._super.init.call(this, attributes);
            this.el = jQuery('<label/>', {
                text: text,
                'class': this.class_ + ' form-label'
            });
        },
        set_state: function(record) {
            Sao.View.Form.Label._super.set_state.call(this, record);
            var field;
            if (this.attributes.name && record) {
                field = record.model.fields[this.attributes.name];
            }
            if ((this.attributes.string === undefined) && field) {
                var text = '';
                if (record) {
                    text = field.get_client(record) || '';
                }
                this.el.val(text);
            }
            var state_changes;
            if (record) {
                state_changes = record.expr_eval(this.attributes.states || {});
            } else {
                state_changes = {};
            }
            if ((field && field.description.required) ||
                    state_changes.required) {
                this.el.addClass('required');
            } else {
                this.el.removeClass('required');
            }
        }
    });

    Sao.View.Form.Notebook = Sao.class_(StateWidget, {
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
                }).append(text)).appendTo(this.nav);
            pane.html(tab).appendTo(this.panes);
            if (!this.selected) {
                // Can not use .tab('show')
                page.addClass('active');
                pane.addClass('active');
                this.selected = true;
            }
            return page;
        }
    });

    Sao.View.Form.Page = Sao.class_(StateWidget, {
        init: function(el, attributes) {
            Sao.View.Form.Page._super.init.call(this, attributes);
            this.el = el;
        }
    });

    Sao.View.Form.Group = Sao.class_(StateWidget, {
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
            this.date.on('dp.change', this.focus_out.bind(this));
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
                this.input.val(value || '');
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
            var buttons = jQuery('<span/>', {
                'class': 'input-group-btn'
            }).appendTo(group);
            this.but_open = jQuery('<button/>', {
                'class': 'btn btn-default',
                'type': 'button'
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-search'
            })).appendTo(buttons);
            this.but_open.click(this.edit.bind(this));
            if (!attributes.completion || attributes.completion == "1") {
                Sao.common.get_completion(this.entry,
                        this._update_completion.bind(this),
                        this._completion_match_selected.bind(this));
                this.wid_completion = true;
            }
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
            this.value(value);
        },
        // This function is required because once typeahead is activated on an
        // entry then .val() function should not be used anymore.
        // In order to keep the same semantics as .val() we use the same
        // signature
        value: function(value) {
            if (this.wid_completion) {
                if (!arguments.length) {
                    return this.entry.typeahead('val');
                } else {
                    return this.entry.typeahead('val', value);
                }
            } else {
                if (!arguments.length) {
                    return this.entry.val();
                } else {
                    return this.entry.val(value);
                }
            }

        },
        get_text: function() {
            var record = this.record();
            if (record) {
                return record.field_get_client(this.field_name);
            }
            return '';
        },
        _set_completion: function() {
            this.entry.data('search', this.read_access());
            this.entry.data('create', this.create_access());
        },
        _update_completion: function(query, process) {
            var record = this.record();
            if (!record) {
                return;
            }
            var field = this.field();
            var value = field.get(record);
            if (this.has_target(value)) {
                var id = this.id_from_value(value);
                if ((id !== undefined) && (id > 0)) {
                    return;
                }
            }
            var model = this.get_model();

            var prm = Sao.common.update_completion(this.entry, record, field,
                    model);
            prm.done(process);
        },
        _completion_match_selected: function(event_, selected_item, name) {
            if (selected_item.id == 'search') {
                // it's necessary to set the value so that edit() can get it
                // and make the search on the user provided content
                this.value(selected_item.query);
                this.edit();
                this.value('');
            } else if (selected_item.id == 'create') {
                this.new_();
                this.value('');
            } else {
                this.record().field_set_client(this.field_name,
                        this.value_from_id(selected_item.id,
                            selected_item.rec_name), true);
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
                this.value('');
                return;
            }
            this.set_text(field.get_client(record));
            value = field.get(record);
            if (this.has_target(value)) {
                this.but_open.button({
                    'icons': {
                        'primary': 'glyphicon-folder-open'
                    }});
            } else {
                this.but_open.button({
                    'icons': {
                        'primary': 'glyphicon-search'
                    }});
            }
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
            this.but_open.prop('disabled',
                    this._readonly || !this.read_access());
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
            if (model && this.has_target(value)) {
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
                    save_current: true
                });
            } else if (model) {
                var dom;
                var domain = this.field().get_domain(record);
                var context = this.field().get_context(record);
                var text = this.value();
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
                            search_filter: parser.quote(text)
                        });
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
                this.activate();
            } else if (this.has_target(this.record().field_get(
                            this.field_name)) && editable) {
                var value = this.get_text();
                if ((value != this.value()) ||
                        ~delete_keys.indexOf(event_.which)) {
                    this.value('');
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
                var text = this.value();
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
                            this.value('');
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
                                search_filter: parser.quote(text)
                            });
                }
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
            this.value('');
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
                value = this.value();
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
                        (name != this.value())) {
                    field.set_client(record, null);
                    this.value('');
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
                    'aria-label': Sao.i18n.gettext('Add')
                }).append(jQuery('<span/>', {
                    'class': 'glyphicon glyphicon-plus'
                })).appendTo(buttons);
                this.but_add.click(this.add.bind(this));

                this.but_remove = jQuery('<button/>', {
                    'class': 'btn btn-default btn-sm',
                    'aria-label': Sao.i18n.gettext('Remove')
                }).append(jQuery('<span/>', {
                    'class': 'glyphicon glyphicon-minus'
                })).appendTo(buttons);
                this.but_remove.click(this.remove.bind(this));
            }

            this.but_new = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'aria-label': Sao.i18n.gettext('New')
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-edit'
            })).appendTo(buttons);
            this.but_new.click(this.new_.bind(this));

            this.but_open = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'aria-label': Sao.i18n.gettext('Open')
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-folder-open'
            })).appendTo(buttons);
            this.but_open.click(this.open.bind(this));

            this.but_del = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'aria-label': Sao.i18n.gettext('Delete')
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-trash'
            })).appendTo(buttons);
            this.but_del.click(this.delete_.bind(this));

            this.but_undel = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'aria-label': Sao.i18n.gettext('Undelete')
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-repeat'
            })).appendTo(buttons);
            this.but_undel.click(this.undelete.bind(this));

            this.but_previous = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
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
                'aria-label': Sao.i18n.gettext('Next')
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-chevron-right'
            })).appendTo(buttons);
            this.but_next.click(this.next.bind(this));

            this.but_switch = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
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
                readonly: attributes.readonly || false,
                exclude_field: attributes.relation_field || null,
                pre_validate: attributes.pre_validate
            });
            this.prm = this.screen.switch_view(modes[0]).done(function() {
                this.content.append(this.screen.screen_container.el);
            }.bind(this));
            // TODO sensitivity of buttons
        },
        set_readonly: function(readonly) {
            this._readonly = readonly;
            this._set_button_sensitive();
        },
        _set_button_sensitive: function() {
            var access = Sao.common.MODELACCESS.get(this.screen.model_name);
            var size_limit = false;
            if (this.record() && this.field()) {
                // TODO
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
                    // TODO handle editable tree
                    // TODO set readonly, domain, size_limit
                }
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
                    context: context
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
                                    search_filter: ''
                        });
                    };

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
                });
            });
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
                'aria-label': Sao.i18n.gettext('Add')
            }).append(jQuery('<span/>', {
                'class': 'glyphicon glyphicon-plus'
            })).appendTo(buttons);
            this.but_add.click(this.add.bind(this));

            this.but_remove = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
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
                        search_filter: parser.quote(value)
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
        edit: function() {
            if (jQuery.isEmptyObject(this.screen.current_record)) {
                return;
            }
            // Create a new screen that is not linked to the parent otherwise
            // on the save of the record will trigger the save of the parent
            var domain = this.field().get_domain(this.record());
            var add_remove = this.record().expr_eval(
                    this.attributes.add_remove);
            if (!jQuery.isEmptyObject(add_remove)) {
                domain = [domain, add_remove];
            }
            var context = this.field().get_context(this.record());
            var screen = new Sao.Screen(this.attributes.relation, {
                'domain': domain,
                'view_ids': (this.attributes.view_ids || '').split(','),
                'mode': ['form'],
                'views_preload': this.attributes.views,
                'readonly': this.attributes.readonly || false,
                'context': context
            });
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
                new Sao.Window.Form(screen, callback);
            });
        },
        new_: function() {
            var domain = this.field().get_domain(this.record());
            var add_remove = this.record().expr_eval(
                    this.attributes.add_remove);
            if (!jQuery.isEmptyObject(add_remove)) {
                domain = [domain, add_remove];
            }
            var context = this.field().get_context(this.record());

            var screen = new Sao.Screen(this.attributes.relation, {
                'domain': domain,
                'view_ids': (this.attributes.view_ids || '').split(','),
                'mode': ['form'],
                'views_preload': this.attributes.views,
                'context': context
            });
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
                    'save_current': true
                });
            });
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
            // TODO find a way to make the difference
            // between downloading and opening
            this.save_as();
        },
        save_as: function() {
            var field = this.field();
            var record = this.record();
            field.get_data(record).done(function(data) {
                var blob = new Blob([data[0].binary],
                        {type: 'application/octet-binary'});
                var blob_url = window.URL.createObjectURL(blob);
                if (this.blob_url) {
                    window.URL.revokeObjectURL(this.blob_url);
                }
                this.blob_url = blob_url;
                window.open(blob_url);
            }.bind(this));
        },
        clear: function() {
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
                'class': 'form-control input-sm'
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
        set_readonly: function(readonly) {
            if (readonly) {
                this.but_select.hide();
                this.but_clear.hide();

            } else {
                this.but_select.show();
                this.but_clear.show();
            }
        }
    });

    Sao.View.Form.MultiSelection = Sao.class_(Sao.View.Form.Selection, {
        class_: 'form-multiselection',
        init: function(field_name, model, attributes) {
            this.nullable_widget = false;
            Sao.View.Form.MultiSelection._super.init.call(this, field_name,
                model, attributes);
            this.el.prop('multiple', true);
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
                    blob = new Blob([data[0][this.field_name]]);
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
            var value;
            if (!field) {
                value = 0;
            } else {
                value = record.model.fields[this.field_name].get_client(
                        record, 100);
            }
            this.set_fraction(value);
        },
        set_fraction: function(value) {
            this.progressbar.prop('aria-valuenow', value);
            this.progressbar.css('width', value + '%');
            this.progressbar.text(Sao.i18n.gettext('%1%', value));
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
            if (event_.which == Sao.common.TAB_KEYCODE) {
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
            var key2columns = {};
            var fields2load = [this.xfield.name];
            for (i = 0, len = this.yfields.length; i < len; i++) {
                yfield = this.yfields[i];
                data.columns.push([yfield.string]);
                key2columns[yfield.key || yfield.name] = i + 1;
                fields2load.push(yfield.name);
            }

            var prms = [];
            var set_data = function(index) {
                return function () {
                    record = group[index];
                    var x = record.field_get(this.xfield.name);
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
            var pie_columns = [];
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
                pie_columns.push([label, values[i]]);
            }

            config.data.columns = pie_columns;
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
