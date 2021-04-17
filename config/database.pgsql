CREATE TABLE IF NOT EXISTS guild_settings(
    guild_id BIGINT PRIMARY KEY,
    prefix VARCHAR(30)
);


CREATE TABLE IF NOT EXISTS user_settings(
    user_id BIGINT PRIMARY KEY,
    plant_limit SMALLINT DEFAULT 1,
    pot_type VARCHAR(50),
    user_experience INTEGER,
    last_plant_shop_time TIMESTAMP,
    plant_pot_hue SMALLINT
);


CREATE TABLE IF NOT EXISTS role_list(
    guild_id BIGINT,
    role_id BIGINT,
    key VARCHAR(50),
    value VARCHAR(50),
    PRIMARY KEY (guild_id, role_id, key)
);


CREATE TABLE IF NOT EXISTS channel_list(
    guild_id BIGINT,
    channel_id BIGINT,
    key VARCHAR(50),
    value VARCHAR(50),
    PRIMARY KEY (guild_id, channel_id, key)
);


CREATE TABLE IF NOT EXISTS plant_levels(
    user_id BIGINT,
    plant_name VARCHAR(50),
    plant_type VARCHAR(20),
    plant_variant SMALLINT DEFAULT 0,
    plant_nourishment SMALLINT,
    last_water_time TIMESTAMP,
    original_owner_id BIGINT,
    plant_pot_hue SMALLINT,
    plant_adoption_time TIMESTAMP,
    notification_sent BOOLEAN DEFAULT TRUE,
    immortal BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (user_id, plant_name)
);


CREATE TABLE IF NOT EXISTS user_inventory(
    user_id BIGINT,
    item_name VARCHAR(50),
    amount SMALLINT DEFAULT 0,
    PRIMARY KEY (user_id, item_name)
);


CREATE TABLE IF NOT EXISTS user_available_plants(
    user_id BIGINT PRIMARY KEY,
    last_shop_timestamp TIMESTAMP NOT NULL,
    plant_level_0 VARCHAR(20),
    plant_level_1 VARCHAR(20),
    plant_level_2 VARCHAR(20),
    plant_level_3 VARCHAR(20),
    plant_level_4 VARCHAR(20),
    plant_level_5 VARCHAR(20),
    plant_level_6 VARCHAR(20)
);


CREATE TABLE IF NOT EXISTS user_garden_access(
    garden_access BIGINT,
    garden_owner BIGINT,
    PRIMARY KEY (garden_access, garden_owner)
);


CREATE TABLE IF NOT EXISTS blacklisted_suggestion_users(
    user_id BIGINT PRIMARY KEY
);


CREATE TABLE IF NOT EXISTS flower_achievement_counts(
    user_id BIGINT,
    plant_type VARCHAR(20),
    plant_count SMALLINT DEFAULT 0,
    plant_death_count SMALLINT DEFAULT 0,
    max_plant_nourishment SMALLINT DEFAULT 0,
    PRIMARY KEY (user_id, plant_type)
);


CREATE TABLE IF NOT EXISTS user_achievement_counts(
    user_id BIGINT PRIMARY KEY,
    trade_count SMALLINT DEFAULT 0,
    revive_count SMALLINT DEFAULT 0,
    immortalize_count SMALLINT DEFAULT 0,
    max_plant_lifetime INTERVAL DEFAULT INTERVAL '0 seconds'
);
