CREATE TABLE ir_configuration (
    id BIGINT AUTO_INCREMENT NOT NULL,
    language VARCHAR(255),
    PRIMARY KEY(id)
) ENGINE=InnoDB;

CREATE TABLE ir_model (
    id BIGINT AUTO_INCREMENT NOT NULL,
    model VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    info TEXT,
    module VARCHAR(255),
    PRIMARY KEY(id)
) ENGINE=InnoDB;

CREATE TABLE ir_model_field (
    id BIGINT AUTO_INCREMENT NOT NULL,
    model BIGINT,
    name VARCHAR(255) NOT NULL,
    relation VARCHAR(255),
    field_description VARCHAR(255),
    ttype VARCHAR(255),
    help VARCHAR(255),
    module VARCHAR(255),
    PRIMARY KEY(id),
    CONSTRAINT ir_model_field_model_fkey FOREIGN KEY (model) REFERENCES ir_model (id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE ir_ui_view (
    id BIGINT AUTO_INCREMENT NOT NULL,
    model VARCHAR(255) NOT NULL,
    type VARCHAR(255),
    data TEXT NOT NULL,
    field_childs VARCHAR(255),
    priority BIGINT NOT NULL default 0,
    PRIMARY KEY(id)
) ENGINE=InnoDB;

CREATE TABLE ir_ui_menu (
    id BIGINT AUTO_INCREMENT NOT NULL,
    parent BIGINT,
    name VARCHAR(255) NOT NULL,
    icon VARCHAR(255),
    PRIMARY KEY (id),
    CONSTRAINT ir_ui_menu_parent_fkey FOREIGN KEY (parent) REFERENCES ir_ui_menu (id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE ir_translation (
    id BIGINT AUTO_INCREMENT NOT NULL,
    lang VARCHAR(255),
    src TEXT,
    src_md5 VARCHAR(32) NOT NULL,
    name VARCHAR(255) NOT NULL,
    res_id BIGINT,
    value TEXT,
    type VARCHAR(255),
    module VARCHAR(255),
    fuzzy BOOLEAN NOT NULL,
    PRIMARY KEY(id)
) ENGINE=InnoDB;

CREATE TABLE ir_lang (
    id BIGINT AUTO_INCREMENT NOT NULL,
    name VARCHAR(255) NOT NULL,
    code TEXT NOT NULL,
    translatable BOOLEAN NOT NULL,
    active BOOLEAN NOT NULL,
    direction VARCHAR(255) NOT NULL,
    PRIMARY KEY(id)
) ENGINE=InnoDB;

CREATE TABLE res_user (
    id BIGINT AUTO_INCREMENT NOT NULL,
    name VARCHAR(255) NOT NULL,
    active BOOLEAN NOT NULL,
    login VARCHAR(255) NOT NULL,
    password VARCHAR(40),
    PRIMARY KEY(id)
) ENGINE=InnoDB;

ALTER TABLE res_user ADD CONSTRAINT res_user_login_uniq UNIQUE (login);

INSERT INTO res_user (id, login, password, name, active) VALUES (0, 'root', NULL, 'Root', False);
UPDATE res_user set id = 0;
ALTER TABLE res_user AUTO_INCREMENT = 1;

CREATE TABLE res_group (
    id BIGINT AUTO_INCREMENT NOT NULL,
    name VARCHAR(255) NOT NULL,
    PRIMARY KEY(id)
) ENGINE=InnoDB;

CREATE TABLE `res_user-res_group` (
    `user` BIGINT NOT NULL,
    `group` BIGINT NOT NULL,
    CONSTRAINT `res_user-res_group_user_fkey` FOREIGN KEY (`user`) REFERENCES res_user (id) ON DELETE CASCADE,
    CONSTRAINT `res_user-res_group_group_fkey` FOREIGN KEY (`group`) REFERENCES res_group (id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE ir_module_module (
    id BIGINT AUTO_INCREMENT NOT NULL,
    create_uid BIGINT,
    create_date TIMESTAMP NOT NULL,
    write_date TIMESTAMP NULL,
    write_uid BIGINT,
    name VARCHAR(255) NOT NULL,
    state VARCHAR(255),
    PRIMARY KEY(id),
    CONSTRAINT ir_module_module_create_uid_fkey FOREIGN KEY (create_uid) REFERENCES res_user (id) ON DELETE SET NULL,
    CONSTRAINT ir_module_module_write_uid_fkey FOREIGN KEY (write_uid) REFERENCES res_user (id) ON DELETE SET NULL
) ENGINE=InnoDB;

ALTER TABLE ir_module_module ADD CONSTRAINT name_uniq UNIQUE (name);

CREATE TABLE ir_module_module_dependency (
    id BIGINT AUTO_INCREMENT NOT NULL,
    create_uid BIGINT,
    create_date TIMESTAMP NOT NULL,
    write_date TIMESTAMP NULL,
    write_uid BIGINT,
    name VARCHAR(255),
    module BIGINT,
    PRIMARY KEY(id),
    CONSTRAINT ir_module_module_dependency_create_uid_fkey FOREIGN KEY (create_uid) REFERENCES res_user (id) ON DELETE SET NULL,
    CONSTRAINT ir_module_module_dependency_write_uid_fkey FOREIGN KEY (write_uid) REFERENCES res_user (id) ON DELETE SET NULL,
    CONSTRAINT ir_module_module_dependency_module_fkey FOREIGN KEY (module) REFERENCES ir_module_module (id) ON DELETE CASCADE
) ENGINE=InnoDB;
