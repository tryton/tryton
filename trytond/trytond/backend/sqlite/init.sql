-------------------------------------------------------------------------
-- Modules Description
-------------------------------------------------------------------------

CREATE TABLE ir_model (
  id INTEGER PRIMARY KEY,
  model VARCHAR,
  name VARCHAR,
  info TEXT,
  module VARCHAR
);

CREATE TABLE ir_model_field (
  id INTEGER PRIMARY KEY,
  model INTEGER,
  name VARCHAR,
  relation VARCHAR,
  field_description VARCHAR,
  ttype VARCHAR,
  help TEXT,
  module VARCHAR
);


-------------------------------------------------------------------------
-- Actions
-------------------------------------------------------------------------
CREATE TABLE ir_ui_view (
	id INTEGER PRIMARY KEY,
	model VARCHAR,
	"type" VARCHAR,
	arch TEXT,
	field_childs VARCHAR,
	priority INTEGER DEFAULT 0
);

CREATE TABLE ir_ui_menu (
	id INTEGER PRIMARY KEY,
	parent_id INTEGER,
	name VARCHAR,
	icon VARCHAR
);



--------------------------------
-- Translation
--------------------------------

CREATE TABLE ir_translation (
    id INTEGER PRIMARY KEY,
    lang VARCHAR,
    src TEXT,
    name VARCHAR,
    res_id INTEGER DEFAULT 0,
    value TEXT,
    "type" VARCHAR,
    module VARCHAR,
    fuzzy BOOLEAN
);

CREATE TABLE ir_lang (
    id INTEGER PRIMARY KEY,
    name VARCHAR,
    code VARCHAR,
    translatable BOOLEAN,
    active BOOLEAN,
    direction VARCHAR
);

---------------------------------
-- Res user
---------------------------------

-- level:
--   0  RESTRICT TO USER
--   1  RESTRICT TO GROUP
--   2  PUBLIC

CREATE TABLE res_user (
    id INTEGER PRIMARY KEY,
    name VARCHAR,
    active BOOLEAN,
    login VARCHAR,
    password VARCHAR(40),
--  action_id INTEGER references ir_act_window on delete set null,
    action INTEGER
);

insert into res_user (id,login,password,name,action,active) values (0,'root',NULL,'Root',NULL,0);

CREATE TABLE res_group (
    id INTEGER PRIMARY KEY,
    name VARCHAR
);

CREATE TABLE "res_user-res_group" (
    id INTEGER PRIMARY KEY,
	uid INTEGER,
	gid INTEGER
);

---------------------------------
-- Workflows
---------------------------------

create table wkf
(
    id INTEGER PRIMARY KEY,
    name VARCHAR,
    model VARCHAR,
    on_create BOOLEAN
);

create table wkf_activity
(
    id INTEGER PRIMARY KEY,
    workflow INTEGER,
    subflow INTEGER,
    split_mode VARCHAR,
    join_mode VARCHAR,
    kind VARCHAR,
    name VARCHAR,
    signal_send VARCHAR,
    flow_start BOOLEAN,
    flow_stop BOOLEAN,
    action TEXT
);

create table wkf_transition
(
    id INTEGER PRIMARY KEY,
    act_from INTEGER,
    act_to INTEGER,
    condition VARCHAR,
    trigger_expr_id VARCHAR,
    signal VARCHAR,
    "group" INTEGER
);

create table wkf_instance
(
    id INTEGER PRIMARY KEY,
    workflow INTEGER,
    uid INTEGER DEFAULT 0,
    res_id INTEGER DEFAULT 0,
    res_type VARCHAR,
    state VARCHAR
);

create table wkf_workitem
(
    id INTEGER PRIMARY KEY,
    activity INTEGER,
    instance INTEGER,
    subflow INTEGER,
    state VARCHAR
);

create table wkf_witm_trans
(
    id INTEGER PRIMARY KEY,
    trans_id INTEGER,
    inst_id INTEGER
);

---------------------------------
-- Modules
---------------------------------

CREATE TABLE ir_module_module (
    id INTEGER PRIMARY KEY,
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
    id INTEGER PRIMARY KEY,
    create_uid INTEGER,
    create_date TIMESTAMP,
    write_date TIMESTAMP,
    write_uid INTEGER,
    name VARCHAR,
    module INTEGER
);
