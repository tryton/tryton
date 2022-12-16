-------------------------------------------------------------------------
-- Modules Description
-------------------------------------------------------------------------

CREATE TABLE ir_model (
  id serial,
  model varchar NOT NULL,
  name varchar,
  info text,
  module varchar,
  primary key(id)
);

CREATE TABLE ir_model_field (
  id serial,
  model int references ir_model on delete cascade,
  name varchar NOT NULL,
  relation varchar,
  field_description varchar,
  ttype varchar,
  help text,
  module varchar,
  primary key(id)
);


-------------------------------------------------------------------------
-- Actions
-------------------------------------------------------------------------
CREATE TABLE ir_ui_view (
	id serial NOT NULL,
	model varchar NOT NULL,
	"type" varchar,
	arch text NOT NULL,
	field_childs varchar,
	priority integer NOT NULL default 0,
	primary key(id)
);

CREATE TABLE ir_ui_menu (
	id serial NOT NULL,
	parent_id int references ir_ui_menu on delete set null,
	name varchar NOT NULL,
	icon varchar,
	primary key (id)
);



--------------------------------
-- Translation
--------------------------------

CREATE TABLE ir_translation (
    id serial NOT NULL,
    lang varchar,
    src text,
    name varchar NOT NULL,
    res_id integer not null default 0,
    value text,
    "type" varchar,
    module varchar,
    fuzzy boolean,
    primary key(id)
);

CREATE TABLE ir_lang (
    id serial NOT NULL,
    name varchar NOT NULL,
    code varchar NOT NULL,
    translatable boolean,
    active boolean,
    direction varchar NOT NULL,
    primary key(id)
);

---------------------------------
-- Res user
---------------------------------

-- level:
--   0  RESTRICT TO USER
--   1  RESTRICT TO GROUP
--   2  PUBLIC

CREATE TABLE res_user (
    id serial NOT NULL,
    name varchar not null,
    active boolean,
    login varchar NOT NULL UNIQUE,
    password varchar(40),
--  action_id int references ir_act_window on delete set null,
    action int,
    primary key(id)
);
alter table res_user add constraint res_user_login_uniq unique (login);

insert into res_user (id,login,password,name,action,active) values (0,'root',NULL,'Root',NULL,False);

CREATE TABLE res_group (
    id serial NOT NULL,
    name varchar NOT NULL,
    primary key(id)
);

CREATE TABLE "res_user-res_group" (
	uid integer NOT NULL references res_user on delete cascade,
	gid integer NOT NULL references res_group on delete cascade
);

---------------------------------
-- Workflows
---------------------------------

create table wkf
(
    id serial,
    name varchar,
    model varchar,
    on_create bool,
    primary key(id)
);

create table wkf_activity
(
    id serial,
    workflow int references wkf on delete cascade,
    subflow int references wkf on delete set null,
    split_mode varchar,
    join_mode varchar,
    kind varchar not null,
    name varchar,
    signal_send varchar,
    flow_start boolean,
    flow_stop boolean,
    action text,
    primary key(id)
);

create table wkf_transition
(
    id serial,
    act_from int references wkf_activity on delete cascade,
    act_to int references wkf_activity on delete cascade,
    condition varchar,
    trigger_expr_id varchar,
    signal varchar,
    "group" int references res_group on delete set null,

    primary key(id)
);

create table wkf_instance
(
    id serial,
    workflow int references wkf on delete restrict,
    uid int,
    res_id int not null,
    res_type varchar not null,
    state varchar not null,
    primary key(id)
);

create table wkf_workitem
(
    id serial,
    activity int not null references wkf_activity on delete cascade,
    instance int not null references wkf_instance on delete cascade,
    subflow int references wkf_instance on delete cascade,
    state varchar,
    primary key(id)
);

create table wkf_witm_trans
(
    trans_id int not null references wkf_transition on delete cascade,
    inst_id int not null references wkf_instance on delete cascade
);

---------------------------------
-- Modules
---------------------------------

CREATE TABLE ir_module_module (
    id serial NOT NULL,
    create_uid integer NOT NULL references res_user on delete set null,
    create_date timestamp without time zone NOT NULL,
    write_date timestamp without time zone,
    write_uid integer references res_user on delete set null,
    website varchar,
    name varchar NOT NULL,
    author varchar,
    url varchar,
    state varchar,
    shortdesc varchar,
    description text,
    primary key(id)
);
ALTER TABLE ir_module_module add constraint name_uniq unique (name);

CREATE TABLE ir_module_module_dependency (
    id serial NOT NULL,
    create_uid integer NOT NULL references res_user on delete set null,
    create_date timestamp without time zone NOT NULL,
    write_date timestamp without time zone,
    write_uid integer references res_user on delete set null,
    name varchar,
    module integer REFERENCES ir_module_module ON DELETE cascade,
    primary key(id)
);
