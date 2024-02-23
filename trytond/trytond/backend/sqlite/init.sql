CREATE TABLE ir_configuration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    language VARCHAR,
    hostname VARCHAR,
    create_date TIMESTAMP,
    create_uid INTEGER,
    write_date TIMESTAMP,
    write_uid INTEGER
);

CREATE TABLE ir_model (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model VARCHAR,
    name VARCHAR,
    info TEXT,
    module VARCHAR,
    create_date TIMESTAMP,
    create_uid INTEGER,
    write_date TIMESTAMP,
    write_uid INTEGER
);

CREATE TABLE ir_model_field (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model VARCHAR,
    name VARCHAR,
    relation VARCHAR,
    field_description VARCHAR,
    ttype VARCHAR,
    help TEXT,
    module VARCHAR,
    "access" BOOLEAN,
    create_date TIMESTAMP,
    create_uid INTEGER,
    write_date TIMESTAMP,
    write_uid INTEGER
);


CREATE TABLE ir_ui_view (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model VARCHAR,
    "type" VARCHAR,
    data TEXT,
    field_childs VARCHAR,
    priority INTEGER,
    domain VARCHAR,
    inherit INTEGER,
    module VARCHAR,
    name VARCHAR,
    create_date TIMESTAMP,
    create_uid INTEGER,
    write_date TIMESTAMP,
    write_uid INTEGER
);

CREATE TABLE ir_ui_menu (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent INTEGER,
    name VARCHAR,
    icon VARCHAR,
    active BOOLEAN,
    sequence INTEGER,
    create_date TIMESTAMP,
    create_uid INTEGER,
    write_date TIMESTAMP,
    write_uid INTEGER
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
    fuzzy BOOLEAN,
    overriding_module VARCHAR,
    create_date TIMESTAMP,
    create_uid INTEGER,
    write_date TIMESTAMP,
    write_uid INTEGER
);

CREATE TABLE ir_lang (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR,
    code VARCHAR,
    translatable BOOLEAN,
    parent VARCHAR,
    active BOOLEAN,
    direction VARCHAR,
    am VARCHAR,
    pm VARCHAR,
    "date" VARCHAR,
    grouping VARCHAR,
    decimal_point VARCHAR,
    thousands_sep VARCHAR,
    mon_grouping VARCHAR,
    mon_decimal_point VARCHAR,
    mon_thousands_sep VARCHAR,
    p_sign_posn INTEGER,
    n_sign_posn INTEGER,
    positive_sign VARCHAR,
    negative_sign VARCHAR,
    p_cs_precedes BOOLEAN,
    n_cs_precedes BOOLEAN,
    p_sep_by_space BOOLEAN,
    n_sep_by_space BOOLEAN,
    pg_text_search VARCHAR,
    create_date TIMESTAMP,
    create_uid INTEGER,
    write_date TIMESTAMP,
    write_uid INTEGER
);

CREATE TABLE res_user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR,
    active BOOLEAN,
    login VARCHAR,
    password VARCHAR,
    email VARCHAR,
    language INTEGER,
    menu INTEGER,
    password_hash VARCHAR,
    password_reset VARCHAR,
    password_reset_expire TIMESTAMP,
    signature TEXT,
    create_date TIMESTAMP,
    create_uid INTEGER,
    write_date TIMESTAMP,
    write_uid INTEGER
);

INSERT INTO res_user (id, login, password, name, active) VALUES (0, 'root', NULL, 'Root', 0);

CREATE TABLE res_group (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR
);

CREATE TABLE "res_user-res_group" (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    "user" INTEGER,
    "group" INTEGER,
    active BOOLEAN,
    parent INTEGER,
    create_date TIMESTAMP,
    create_uid INTEGER,
    write_date TIMESTAMP,
    write_uid INTEGER
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
    "timestamp" TIMESTAMP,
    create_date TIMESTAMP,
    create_uid INTEGER,
    write_date TIMESTAMP,
    write_uid INTEGER
);
