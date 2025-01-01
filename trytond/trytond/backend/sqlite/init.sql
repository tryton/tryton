CREATE TABLE ir_configuration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    language VARCHAR,
    hostname VARCHAR
);

CREATE TABLE ir_model (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR,
    string VARCHAR,
    info TEXT,
    module VARCHAR
);

CREATE UNIQUE INDEX ir_model_name_unique ON ir_model (name);

INSERT INTO ir_model (id, name, module) VALUES (1, 'res.user', 'res');
INSERT INTO ir_model (id, name, module) VALUES (2, 'res.group', 'res');

CREATE TABLE ir_model_field (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    relation VARCHAR,
    string VARCHAR,
    ttype VARCHAR,
    help TEXT,
    module VARCHAR,
    "access" BOOLEAN
);

CREATE TABLE ir_model_data (
   id INTEGER PRIMARY KEy AUTOINCREMENT,
    db_id INTEGER,
    fs_id VARCHAR,
    model VARCHAR NOT NULL,
    module VARCHAR NOT NULL,
    noupdate BOOLEAN,
    fs_values TEXT,
    "values" TEXT
);

INSERT INTO ir_model_data (id, db_id, fs_id, model, module, noupdate, fs_values, "values") VALUES (1, 1, 'user_admin', 'res.user', 'res', False, '[["login","admin"],["name","Administrator"]]', '[["login","admin"],["name","Administrator"]]');
INSERT INTO ir_model_data (id, db_id, fs_id, model, module, noupdate, fs_values, "values") VALUES (2, 1, 'group_admin', 'res.group', 'res', False, '[["name","Administrator"]]', '[["name","Administrator"]]');

CREATE TABLE ir_ui_view (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model VARCHAR,
    "type" VARCHAR,
    data TEXT,
    field_childs VARCHAR,
    priority INTEGER NOT NULL
);

CREATE TABLE ir_ui_menu (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent INTEGER,
    name VARCHAR NOT NULL,
    icon VARCHAR,
    active BOOLEAN,
    sequence INTEGER
);

CREATE TABLE ir_translation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lang VARCHAR,
    src TEXT,
    name VARCHAR NOT NULL,
    res_id INTEGER,
    value TEXT,
    "type" VARCHAR,
    module VARCHAR,
    fuzzy BOOLEAN NOT NULL,
    overriding_module VARCHAR
);

CREATE TABLE ir_lang (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR NOT NULL,
    code VARCHAR NOT NULL,
    translatable BOOLEAN NOT NULL,
    parent VARCHAR,
    active BOOLEAN NOT NULL,
    direction VARCHAR NOT NULL
);

CREATE TABLE res_user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR,
    active BOOLEAN NOT NULL,
    login VARCHAR NOT NULL,
    password VARCHAR
);

CREATE UNIQUE INDEX res_user_login_key ON res_user (login);

INSERT INTO res_user (id, login, password, name, active) VALUES (0, 'root', NULL, 'Root', 0);
INSERT INTO res_user (id, login, password, name, active) VALUES (1, 'admin', NULL, 'Administrator', 1);

CREATE TABLE res_group (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR
);

INSERT INTO res_group (id, name) VALUES (1, 'Administration');

CREATE TABLE "res_user-res_group" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    "user" INTEGER NOT NULL,
    "group" INTEGER NOT NULL
);

CREATE TABLE ir_module (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    create_uid INTEGER,
    create_date TIMESTAMP,
    write_date TIMESTAMP,
    write_uid INTEGER,
    name VARCHAR NOT NULL,
    state VARCHAR
);

CREATE UNIQUE INDEX ir_module_name_uniq ON ir_module (name);

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
    name VARCHAR NOT NULL,
    "timestamp" TIMESTAMP,
    create_date TIMESTAMP,
    create_uid INTEGER,
    write_date TIMESTAMP,
    write_uid INTEGER
);
