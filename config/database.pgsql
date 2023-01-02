CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


CREATE TABLE IF NOT EXISTS guild_settings(
    guild_id BIGINT PRIMARY KEY,
    prefix VARCHAR(30)
);


CREATE TABLE IF NOT EXISTS user_settings(
    user_id BIGINT PRIMARY KEY,
    plant_limit SMALLINT DEFAULT 1,
    pot_type VARCHAR(50),
    user_experience INTEGER DEFAULT 0,
    last_plant_shop_time TIMESTAMP,
    plant_pot_hue SMALLINT,
    has_premium BOOLEAN NOT NULL DEFAULT FALSE,
    premium_expiry_time TIMESTAMP,
    premium_subscription_delete_url TEXT
);


CREATE TABLE IF NOT EXISTS plant_levels(
    id UUID NOT NULL PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT NOT NULL,
    plant_name CITEXT NOT NULL,
    plant_type TEXT NOT NULL,
    plant_variant SMALLINT NOT NULL DEFAULT 0,
    plant_nourishment SMALLINT NOT NULL,
    last_water_time TIMESTAMP NOT NULL,
    original_owner_id BIGINT NOT NULL,
    plant_pot_hue SMALLINT NOT NULL,
    plant_adoption_time TIMESTAMP NOT NULL,
    notification_sent BOOLEAN NOT NULL DEFAULT TRUE,
    immortal BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (user_id, plant_name)
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


CREATE TABLE IF NOT EXISTS user_achievement_counts(
    user_id BIGINT PRIMARY KEY,
    trade_count SMALLINT DEFAULT 0,
    revive_count SMALLINT DEFAULT 0,
    immortalize_count SMALLINT DEFAULT 0,
    max_plant_lifetime INTERVAL DEFAULT INTERVAL '0 seconds',
    water_count SMALLINT DEFAULT 0,
    give_count SMALLINT DEFAULT 0,
    death_count SMALLINT DEFAULT 0
);
