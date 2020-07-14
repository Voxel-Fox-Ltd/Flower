CREATE TABLE guild_settings(
    guild_id BIGINT PRIMARY KEY,
    prefix VARCHAR(30)
);


CREATE TABLE user_settings(
    user_id BIGINT PRIMARY KEY,
    plant_limit SMALLINT DEFAULT 1,
    pot_type VARCHAR(50),
    user_experience INTEGER,
    pot_hue SMALLINT DEFAULT 180
);


CREATE TABLE role_list(
    guild_id BIGINT,
    role_id BIGINT,
    key VARCHAR(50),
    value VARCHAR(50),
    PRIMARY KEY (guild_id, role_id, key)
);


CREATE TABLE channel_list(
    guild_id BIGINT,
    channel_id BIGINT,
    key VARCHAR(50),
    value VARCHAR(50),
    PRIMARY KEY (guild_id, channel_id, key)
);


CREATE TABLE plant_levels(
    user_id BIGINT,
    plant_name VARCHAR(50),
    plant_type VARCHAR(10),
    plant_variant INTEGER DEFAULT 0,
    plant_nourishment INTEGER,
    last_water_time TIMESTAMP,
    PRIMARY KEY (user_id, plant_name)
);
