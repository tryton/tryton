CREATE TABLE ir_configuration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    language VARCHAR,
    hostname VARCHAR
);

CREATE TABLE ir_model (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model VARCHAR,
    name VARCHAR,
    info TEXT,
    module VARCHAR
);

CREATE TABLE ir_model_field (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model INTEGER,
    name VARCHAR,
    relation VARCHAR,
    field_description VARCHAR,
    ttype VARCHAR,
    help TEXT,
    module VARCHAR
);


CREATE TABLE ir_ui_view (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model VARCHAR,
    "type" VARCHAR,
    data TEXT,
    field_childs VARCHAR,
    priority INTEGER
);

CREATE TABLE ir_ui_menu (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent INTEGER,
    name VARCHAR,
    icon VARCHAR
);

CREATE TABLE ir_translation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lang VARCHAR,
    src TEXT,
    name VARCHAR,
    res_id INTEGER,
    value TEXT,
    "type" VARCHAR,
    module VARCHAR,
    fuzzy BOOLEAN
);

CREATE TABLE ir_lang (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR,
    code VARCHAR,
    translatable BOOLEAN,
    parent VARCHAR,
    active BOOLEAN,
    direction VARCHAR
);

CREATE TABLE res_user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR,
    active BOOLEAN,
    login VARCHAR,
    password VARCHAR
);

INSERT INTO res_user (id, login, password, name, active) VALUES (0, 'root', NULL, 'Root', 0);

CREATE TABLE res_group (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR
);

CREATE TABLE "res_user-res_group" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    "user" INTEGER,
    "group" INTEGER
);

CREATE TABLE ir_module (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    create_uid INTEGER,
    create_date TIMESTAMP,
    write_date TIMESTAMP,
    write_uid INTEGER,
    name VARCHAR,
    state VARCHAR
);

CREATE TABLE ir_module_dependency (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    create_uid INTEGER,
    create_date TIMESTAMP,
    write_date TIMESTAMP,
    write_uid INTEGER,
    name VARCHAR,
    module INTEGER
);

CREATE TABLE ir_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR,
    "timestamp" TIMESTAMP
);
