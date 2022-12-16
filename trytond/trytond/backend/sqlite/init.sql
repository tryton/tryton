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
    arch TEXT,
    field_childs VARCHAR,
    priority INTEGER DEFAULT 0
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
    src_md5 VARCHAR(32) NOT NULL,
    name VARCHAR,
    res_id INTEGER DEFAULT 0,
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

CREATE TABLE wkf (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR,
    model VARCHAR,
    on_create BOOLEAN
);

CREATE TABLE wkf_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow INTEGER,
    subflow INTEGER,
    split_mode VARCHAR,
    join_mode VARCHAR,
    name VARCHAR,
    signal_send VARCHAR,
    flow_start BOOLEAN,
    flow_stop BOOLEAN,
    stop_other BOOLEAN,
    action VARCHAR
);

CREATE TABLE wkf_transition (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    act_from INTEGER,
    act_to INTEGER,
    condition VARCHAR,
    trigger_expr_id VARCHAR,
    signal VARCHAR,
    "group" INTEGER
);

CREATE TABLE wkf_instance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow INTEGER,
    uid INTEGER DEFAULT 0,
    res_id INTEGER DEFAULT 0,
    res_type VARCHAR,
    state VARCHAR
);

CREATE TABLE wkf_workitem (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity INTEGER,
    instance INTEGER,
    subflow INTEGER,
    state VARCHAR
);

CREATE TABLE wkf_witm_trans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trans_id INTEGER,
    inst_id INTEGER
);

CREATE TABLE ir_module_module (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    create_uid INTEGER,
    create_date TIMESTAMP,
    write_date TIMESTAMP,
    write_uid INTEGER,
    website VARCHAR,
    name VARCHAR,
    author VARCHAR,
    url VARCHAR,
    state VARCHAR,
    shortdesc VARCHAR,
    description TEXT
);

CREATE TABLE ir_module_module_dependency (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    create_uid INTEGER,
    create_date TIMESTAMP,
    write_date TIMESTAMP,
    write_uid INTEGER,
    name VARCHAR,
    module INTEGER
);
