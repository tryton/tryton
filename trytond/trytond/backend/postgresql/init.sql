CREATE SEQUENCE ir_model_id_seq;

CREATE TABLE ir_model (
    id INTEGER DEFAULT NEXTVAL('ir_model_id_seq') NOT NULL,
    model VARCHAR NOT NULL,
    name VARCHAR,
    info TEXT,
    module VARCHAR,
    PRIMARY KEY(id)
);

CREATE SEQUENCE ir_model_field_id_seq;

CREATE TABLE ir_model_field (
    id INTEGER DEFAULT NEXTVAL('ir_model_field_id_seq') NOT NULL,
    model INTEGER,
    name VARCHAR NOT NULL,
    relation VARCHAR,
    field_description VARCHAR,
    ttype VARCHAR,
    help TEXT,
    module VARCHAR,
    PRIMARY KEY(id),
    FOREIGN KEY (model) REFERENCES ir_model(id) ON DELETE CASCADE
);

CREATE SEQUENCE ir_ui_view_id_seq;

CREATE TABLE ir_ui_view (
    id INTEGER DEFAULT NEXTVAL('ir_ui_view_id_seq') NOT NULL,
    model VARCHAR NOT NULL,
    "type" VARCHAR,
    arch TEXT NOT NULL,
    field_childs VARCHAR,
    priority INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(id)
);

CREATE SEQUENCE ir_ui_menu_id_seq;

CREATE TABLE ir_ui_menu (
    id INTEGER DEFAULT NEXTVAL('ir_ui_menu_id_seq') NOT NULL,
    parent INTEGER,
    name VARCHAR NOT NULL,
    icon VARCHAR,
    PRIMARY KEY (id),
    FOREIGN KEY (parent) REFERENCES ir_ui_menu (id) ON DELETE SET NULL
);

CREATE SEQUENCE ir_translation_id_seq;

CREATE TABLE ir_translation (
    id INTEGER DEFAULT NEXTVAL('ir_translation_id_seq') NOT NULL,
    lang VARCHAR,
    src TEXT,
    src_md5 VARCHAR(32) NOT NULL,
    name VARCHAR NOT NULL,
    res_id INTEGER NOT NULL DEFAULT 0,
    value TEXT,
    "type" VARCHAR,
    module VARCHAR,
    fuzzy BOOLEAN NOT NULL,
    PRIMARY KEY(id)
);

CREATE SEQUENCE ir_lang_id_seq;

CREATE TABLE ir_lang (
    id INTEGER DEFAULT NEXTVAL('ir_lang_id_seq') NOT NULL,
    name VARCHAR NOT NULL,
    code VARCHAR NOT NULL,
    translatable BOOLEAN NOT NULL,
    active BOOLEAN NOT NULL,
    direction VARCHAR NOT NULL,
    PRIMARY KEY(id)
);

CREATE SEQUENCE res_user_id_seq;

CREATE TABLE res_user (
    id INTEGER DEFAULT NEXTVAL('res_user_id_seq') NOT NULL,
    name VARCHAR NOT NULL,
    active BOOLEAN NOT NULL,
    login VARCHAR NOT NULL UNIQUE,
    password VARCHAR,
    PRIMARY KEY(id)
);

ALTER TABLE res_user ADD CONSTRAINT res_user_login_uniq UNIQUE (login);

INSERT INTO res_user (id, login, password, name, active) VALUES (0, 'root', NULL, 'Root', False);

CREATE SEQUENCE res_group_id_seq;

CREATE TABLE res_group (
    id INTEGER DEFAULT NEXTVAL('res_group_id_seq') NOT NULL,
    name VARCHAR NOT NULL,
    PRIMARY KEY(id)
);

CREATE SEQUENCE "res_user-res_group_id_seq";

CREATE TABLE "res_user-res_group" (
    id INTEGER DEFAULT NEXTVAL('res_user-res_group_id_seq') NOT NULL,
    "user" INTEGER NOT NULL,
    "group" INTEGER NOT NULL,
    FOREIGN KEY ("user") REFERENCES res_user (id) ON DELETE CASCADE,
    FOREIGN KEY ("group") REFERENCES res_group (id) ON DELETE CASCADE,
    PRIMARY KEY(id)
);

CREATE SEQUENCE wkf_id_seq;

CREATE TABLE wkf (
    id INTEGER DEFAULT NEXTVAL('wkf_id_seq') NOT NULL,
    name VARCHAR,
    model VARCHAR,
    on_create BOOL NOT NULL,
    PRIMARY KEY(id)
);

CREATE SEQUENCE wkf_activity_id_seq;

CREATE TABLE wkf_activity (
    id INTEGER DEFAULT NEXTVAL('wkf_activity_id_seq') NOT NULL,
    workflow INTEGER,
    subflow INTEGER,
    split_mode VARCHAR NOT NULL,
    join_mode VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    signal_send VARCHAR,
    flow_start BOOLEAN NOT NULL,
    flow_stop BOOLEAN NOT NULL,
    stop_other BOOLEAN NOT NULL,
    action VARCHAR,
    PRIMARY KEY(id),
    FOREIGN KEY (workflow) REFERENCES wkf (id) ON DELETE CASCADE,
    FOREIGN KEY (subflow) REFERENCES wkf (id) ON DELETE SET NULL
);

CREATE SEQUENCE wkf_transition_id_seq;

CREATE TABLE wkf_transition (
    id INTEGER DEFAULT NEXTVAL('wkf_transition_id_seq') NOT NULL,
    act_from INTEGER NOT NULL,
    act_to INTEGER NOT NULL,
    condition VARCHAR NOT NULL,
    trigger_expr_id VARCHAR,
    signal VARCHAR,
    "group" INTEGER,
    PRIMARY KEY(id),
    FOREIGN KEY (act_from) REFERENCES wkf_activity (id) ON DELETE CASCADE,
    FOREIGN KEY (act_to) REFERENCES wkf_activity (id) ON DELETE CASCADE,
    FOREIGN KEY ("group") REFERENCES res_group (id) ON DELETE SET NULL
);

CREATE SEQUENCE wkf_instance_id_seq;

CREATE TABLE wkf_instance (
    id INTEGER DEFAULT NEXTVAL('wkf_instance_id_seq') NOT NULL,
    workflow INTEGER,
    uid INTEGER DEFAULT 0,
    res_id INT NOT NULL DEFAULT 0,
    res_type VARCHAR NOT NULL,
    state VARCHAR NOT NULL,
    PRIMARY KEY(id),
    FOREIGN KEY (workflow) REFERENCES wkf (id) ON DELETE RESTRICT
);

CREATE SEQUENCE wkf_workitem_id_seq;

CREATE TABLE wkf_workitem (
    id INTEGER DEFAULT NEXTVAL('wkf_workitem_id_seq') NOT NULL,
    activity INTEGER NOT NULL,
    instance INTEGER NOT NULL,
    subflow INTEGER,
    state VARCHAR,
    PRIMARY KEY(id),
    FOREIGN KEY (activity) REFERENCES wkf_activity (id) ON DELETE CASCADE,
    FOREIGN KEY (instance) REFERENCES wkf_instance (id) ON DELETE CASCADE,
    FOREIGN KEY (subflow) REFERENCES wkf_instance (id) ON DELETE CASCADE
);

CREATE SEQUENCE wkf_witm_trans_id_seq;

CREATE TABLE wkf_witm_trans (
    id INTEGER DEFAULT NEXTVAL('wkf_witm_trans_id_seq') NOT NULL,
    trans_id INTEGER NOT NULL,
    inst_id INTEGER NOT NULL,
    PRIMARY KEY(id),
    FOREIGN KEY (trans_id) REFERENCES wkf_transition ON DELETE CASCADE,
    FOREIGN KEY (inst_id) REFERENCES wkf_instance ON DELETE CASCADE
);

CREATE SEQUENCE ir_module_module_id_seq;

CREATE TABLE ir_module_module (
    id INTEGER DEFAULT NEXTVAL('ir_module_module_id_seq') NOT NULL,
    create_uid INTEGER NOT NULL,
    create_date TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    write_date TIMESTAMP WITHOUT TIME ZONE,
    write_uid INTEGER,
    website VARCHAR,
    name VARCHAR NOT NULL,
    author VARCHAR,
    url VARCHAR,
    state VARCHAR,
    shortdesc VARCHAR,
    description TEXT,
    PRIMARY KEY(id),
    FOREIGN KEY (create_uid) REFERENCES res_user ON DELETE SET NULL,
    FOREIGN KEY (write_uid) REFERENCES res_user ON DELETE SET NULL
);

ALTER TABLE ir_module_module ADD CONSTRAINT name_uniq UNIQUE (name);

CREATE SEQUENCE ir_module_module_dependency_id_seq;

CREATE TABLE ir_module_module_dependency (
    id INTEGER DEFAULT NEXTVAL('ir_module_module_dependency_id_seq') NOT NULL,
    create_uid INTEGER NOT NULL,
    create_date TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    write_date TIMESTAMP WITHOUT TIME ZONE,
    write_uid INTEGER,
    name VARCHAR,
    module INTEGER,
    PRIMARY KEY(id),
    FOREIGN KEY (create_uid) REFERENCES res_user ON DELETE SET NULL,
    FOREIGN KEY (write_uid) REFERENCES res_user ON DELETE SET NULL,
    FOREIGN KEY (module) REFERENCES ir_module_module ON DELETE CASCADE
);
