# База данных и Транзакции

## 1. Схемы данных
База логически разделена на 4 схемы: `core` (пользователи, инвентарь), `crafting` (рецепты, патенты, варка), `economy` (транзакции, логи, рынок), `queue` (очереди задач).

## 2. Ключевые DDL (Структура таблиц)

-- Создание изолированных схем для разграничения контекстов микросервисов
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS crafting;
CREATE SCHEMA IF NOT EXISTS economy;
CREATE SCHEMA IF NOT EXISTS queue;

-- ==========================================
-- I. ОПРЕДЕЛЕНИЕ ПЕРЕЧИСЛЕНИЙ (ENUMS)
-- ==========================================

CREATE TYPE core.tavern_tier AS ENUM ('garage', 'tavern', 'brewery', 'factory', 'guild');
CREATE TYPE core.staff_role AS ENUM ('master_alchemist', 'caravaner', 'merchant');
CREATE TYPE core.staff_status AS ENUM ('healthy', 'light_injured', 'heavy_injured', 'dead');

-- ==========================================
-- II. СХЕМА CORE (ИГРОКИ И ПЕРСОНАЛ)
-- ==========================================

-- Таблица профилей игроков
CREATE TABLE core.players (
    player_id BIGSERIAL PRIMARY KEY,
    tg_id BIGINT UNIQUE NOT NULL,
    gold NUMERIC(15, 2) NOT NULL DEFAULT 1000.00 CONSTRAINT chk_player_gold CHECK (gold >= 0),
    prestige_crystals INT NOT NULL DEFAULT 0 CONSTRAINT chk_player_crystals CHECK (prestige_crystals >= 0),
    reputation SMALLINT NOT NULL DEFAULT 0 CONSTRAINT chk_player_reputation CHECK (reputation BETWEEN -100 AND 100),
    influence SMALLINT NOT NULL DEFAULT 0 CONSTRAINT chk_player_influence CHECK (influence BETWEEN 0 AND 100),
    tavern_level core.tavern_tier NOT NULL DEFAULT 'garage',
    hud_message_id BIGINT DEFAULT NULL, -- ID закрепленного HUD-сообщения в Telegram
    
    last_offline_calc_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_players_tg_id ON core.players(tg_id);

-- Таблица журнала событий игрока (PlayerEventLog)
CREATE TABLE core.player_events_log (
    event_id BIGSERIAL PRIMARY KEY,
    player_id BIGINT NOT NULL REFERENCES core.players(player_id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL, -- 'serial_brew', 'patent_registered', 'pvp_success', etc.
    summary TEXT NOT NULL,
    metadata_json JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_player_events_log_player_id ON core.player_events_log(player_id);

-- Таблица нанятых сотрудников
CREATE TABLE core.staff (
    staff_id BIGSERIAL PRIMARY KEY,
    player_id BIGINT NOT NULL REFERENCES core.players(player_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    role core.staff_role NOT NULL,
    skill SMALLINT NOT NULL CONSTRAINT chk_staff_skill CHECK (skill BETWEEN 1 AND 100),
    loyalty SMALLINT NOT NULL DEFAULT 100 CONSTRAINT chk_staff_loyalty CHECK (loyalty BETWEEN 0 AND 100),
    fatigue SMALLINT NOT NULL DEFAULT 0 CONSTRAINT chk_staff_fatigue CHECK (fatigue BETWEEN 0 AND 100),
    status core.staff_status NOT NULL DEFAULT 'healthy',
    
    blocked_until TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_staff_player_id ON core.staff(player_id);

-- Таблица ресурсов игрока (Инвентарь сырья)
CREATE TABLE core.resources (
    player_id BIGINT NOT NULL REFERENCES core.players(player_id) ON DELETE CASCADE,
    resource_type VARCHAR(20) NOT NULL, -- 'malt', 'water', 'hops', 'yeast'
    quantity NUMERIC(15, 2) NOT NULL DEFAULT 0.00 CONSTRAINT chk_resource_qty CHECK (quantity >= 0),
    PRIMARY KEY (player_id, resource_type)
);

-- ==========================================
-- III. СХЕМА CRAFTING (РЕЦЕПТЫ И ПРОИЗВОДСТВО)
-- ==========================================

-- Таблица рецептов
CREATE TABLE crafting.recipes (
    recipe_id BIGSERIAL PRIMARY KEY,
    creator_id BIGINT REFERENCES core.players(player_id) ON DELETE SET NULL,
    title VARCHAR(150) NOT NULL,
    
    malt_pct SMALLINT NOT NULL CONSTRAINT chk_malt_range CHECK (malt_pct BETWEEN 0 AND 100),
    water_pct SMALLINT NOT NULL CONSTRAINT chk_water_range CHECK (water_pct BETWEEN 0 AND 100),
    hop_pct SMALLINT NOT NULL CONSTRAINT chk_hop_range CHECK (hop_pct BETWEEN 0 AND 100),
    yeast_pct SMALLINT NOT NULL CONSTRAINT chk_yeast_range CHECK (yeast_pct BETWEEN 0 AND 100),
    
    strength NUMERIC(4, 2) NOT NULL CONSTRAINT chk_beer_strength CHECK (strength BETWEEN 0.00 AND 20.00),
    bitterness NUMERIC(4, 2) NOT NULL CONSTRAINT chk_beer_bitterness CHECK (bitterness BETWEEN 0.00 AND 20.00),
    aroma NUMERIC(4, 2) NOT NULL CONSTRAINT chk_beer_aroma CHECK (aroma BETWEEN 0.00 AND 20.00),
    stability SMALLINT NOT NULL CONSTRAINT chk_beer_stability CHECK (stability BETWEEN 0 AND 100),
    
    is_fake BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_total_proportions_100 CHECK (malt_pct + water_pct + hop_pct + yeast_pct = 100)
);

CREATE INDEX idx_recipes_stats_search ON crafting.recipes(strength, bitterness, aroma);

-- Таблица активных патентов
CREATE TABLE crafting.patents (
    patent_id BIGSERIAL PRIMARY KEY,
    player_id BIGINT NOT NULL REFERENCES core.players(player_id) ON DELETE CASCADE,
    recipe_id BIGINT NOT NULL REFERENCES crafting.recipes(recipe_id),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    daily_tax_base NUMERIC(10, 2) NOT NULL DEFAULT 50.00,
    royalty_earned_24h NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    lore_name VARCHAR(150) DEFAULT NULL, -- Название, сгенерированное LLM
    lore_text TEXT DEFAULT NULL, -- Художественный лор, сгенерированный LLM
    card_image_file_id VARCHAR(255) DEFAULT NULL, -- Telegram file_id обложки патента
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE INDEX idx_patents_active ON crafting.patents(player_id) WHERE (is_active = TRUE);

-- Таблица партий пива
CREATE TABLE crafting.batches (
    batch_id BIGSERIAL PRIMARY KEY,
    player_id BIGINT NOT NULL REFERENCES core.players(player_id) ON DELETE CASCADE, 
    recipe_id BIGINT NOT NULL REFERENCES crafting.recipes(recipe_id),
    quantity_barrels INT NOT NULL CONSTRAINT chk_batch_quantity CHECK (quantity_barrels >= 0),
    quality_modifier NUMERIC(3, 2) NOT NULL DEFAULT 1.00,
    
    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    ready_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_batches_player_inventory ON crafting.batches(player_id) WHERE (quantity_barrels > 0);
CREATE INDEX idx_batches_uncompleted ON crafting.batches(ready_at) WHERE (is_completed = FALSE);

-- ==========================================
-- IV. СХЕМА ECONOMY (РЫНОК И ТРАНЗАКЦИИ)
-- ==========================================

-- Таблица логов транзакций (Append-only)
CREATE TABLE economy.transactions_log (
    tx_id BIGSERIAL PRIMARY KEY,
    seller_id BIGINT NOT NULL,
    recipe_id BIGINT NOT NULL,
    market_type VARCHAR(20) NOT NULL, -- 'legal', 'grey', 'black', 'goblins'
    volume INT NOT NULL,
    total_revenue NUMERIC(15, 2) NOT NULL,
    processed_for_royalty BOOLEAN NOT NULL DEFAULT FALSE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Таблица текущих рыночных цен сырья (Плавающие цены)
CREATE TABLE economy.ingredient_prices (
    ingredient VARCHAR(20) PRIMARY KEY, -- 'malt', 'water', 'hops', 'yeast'
    price NUMERIC(15, 2) NOT NULL,
    trend SMALLINT NOT NULL DEFAULT 0, -- -1 (падающий), 0 (стабильный), 1 (растущий)
    last_updated TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Агрегированные данные о продажах за 24 часа (для расчета D_penalty)
CREATE TABLE economy.market_saturation (
    market_segment VARCHAR(20) PRIMARY KEY, -- 'gnomes', 'elves', 'goblins', 'legal', 'grey'
    volume_sold_24h INT NOT NULL DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

## 3. Паттерны блокировок (Anti-Exploit)

Защита от Race Conditions (Двойная трата):
Все списания ресурсов должны оборачиваться в пессимистичную транзакцию:
SQL
BEGIN;
SELECT gold FROM core.players WHERE player_id = %s FOR UPDATE;
UPDATE core.players SET gold = gold - %s WHERE player_id = %s AND gold >= %s;
COMMIT;

Обработка очередей фоновыми воркерами:
Для безопасного распараллеливания задач ИИ-генерации и выплат роялти:
SQL
UPDATE queue.tasks
SET status = 'processing'
WHERE task_id = (
    SELECT task_id FROM queue.tasks 
    WHERE status = 'pending' 
    ORDER BY created_at ASC LIMIT 1 
    FOR UPDATE SKIP LOCKED
) RETURNING payload;