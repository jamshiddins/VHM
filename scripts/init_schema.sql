-- VendHub Database Schema
-- Файл: scripts/init_schema.sql

-- Создание расширений
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ===== ОСНОВНЫЕ ТАБЛИЦЫ =====

-- 1. Пользователи
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT gen_random_uuid() UNIQUE,
    telegram_id BIGINT UNIQUE,
    phone VARCHAR(20) UNIQUE,
    email VARCHAR(255) UNIQUE,
    username VARCHAR(100) UNIQUE,
    full_name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    last_login TIMESTAMP,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

-- 2. Роли
CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    description TEXT,
    is_system BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Разрешения
CREATE TABLE permissions (
    id SERIAL PRIMARY KEY,
    module VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    description TEXT,
    UNIQUE(module, action)
);

-- 4. Связь пользователей и ролей
CREATE TABLE user_roles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, role_id)
);

-- 5. Связь ролей и разрешений
CREATE TABLE role_permissions (
    id SERIAL PRIMARY KEY,
    role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
    permission_id INTEGER REFERENCES permissions(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(role_id, permission_id)
);

-- 6. Автоматы
CREATE TABLE machines (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT gen_random_uuid() UNIQUE,
    code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL, -- coffee, snack, combo
    model VARCHAR(100),
    serial_number VARCHAR(100),
    status VARCHAR(50) DEFAULT 'active', -- active, maintenance, inactive
    location_address TEXT,
    location_lat DECIMAL(10, 8),
    location_lng DECIMAL(11, 8),
    installation_date DATE,
    last_service_date DATE,
    responsible_user_id INTEGER REFERENCES users(id),
    settings JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

-- 7. Склады
CREATE TABLE warehouses (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    responsible_user_id INTEGER REFERENCES users(id),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. Ингредиенты
CREATE TABLE ingredients (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(50), -- coffee, syrup, milk, snack, etc
    unit VARCHAR(20) NOT NULL, -- kg, l, pcs
    cost_per_unit DECIMAL(10, 2),
    min_stock_level DECIMAL(10, 3),
    barcode VARCHAR(100),
    supplier_info JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. Остатки (историчные данные)
CREATE TABLE inventory (
    id SERIAL PRIMARY KEY,
    ingredient_id INTEGER REFERENCES ingredients(id),
    location_type VARCHAR(50) NOT NULL, -- warehouse, machine, bag
    location_id INTEGER NOT NULL, -- warehouse_id, machine_id, task_id
    quantity DECIMAL(10, 3) NOT NULL,
    batch_number VARCHAR(100),
    expiry_date DATE,
    action_timestamp TIMESTAMP NOT NULL, -- когда фактически
    entry_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- когда внесено
    created_by INTEGER REFERENCES users(id),
    notes TEXT
);

-- 10. Продукты
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(50),
    price DECIMAL(10, 2) NOT NULL,
    vat_rate DECIMAL(4, 2) DEFAULT 0.12,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 11. Рецепты
CREATE TABLE recipes (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 12. Ингредиенты в рецептах
CREATE TABLE recipe_ingredients (
    id SERIAL PRIMARY KEY,
    recipe_id INTEGER REFERENCES recipes(id),
    ingredient_id INTEGER REFERENCES ingredients(id),
    quantity DECIMAL(10, 3) NOT NULL,
    UNIQUE(recipe_id, ingredient_id)
);

-- 13. Маршруты
CREATE TABLE routes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 14. Автоматы на маршрутах
CREATE TABLE machine_routes (
    id SERIAL PRIMARY KEY,
    machine_id INTEGER REFERENCES machines(id),
    route_id INTEGER REFERENCES routes(id),
    sequence_order INTEGER,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(machine_id, route_id)
);

-- 15. Задачи по автоматам
CREATE TABLE machine_tasks (
    id SERIAL PRIMARY KEY,
    machine_id INTEGER REFERENCES machines(id),
    assigned_to INTEGER REFERENCES users(id),
    type VARCHAR(50) NOT NULL, -- refill, maintenance, collection
    status VARCHAR(50) DEFAULT 'pending', -- pending, in_progress, completed, cancelled
    description TEXT,
    scheduled_date DATE,
    completed_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 16. Продажи
CREATE TABLE sales (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT gen_random_uuid() UNIQUE,
    machine_id INTEGER REFERENCES machines(id),
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price DECIMAL(10, 2) NOT NULL,
    total_amount DECIMAL(10, 2) NOT NULL,
    payment_method VARCHAR(50), -- cash, payme, click, uzum
    transaction_id VARCHAR(255),
    action_timestamp TIMESTAMP NOT NULL,
    entry_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sync_status VARCHAR(50) DEFAULT 'pending',
    raw_data JSONB
);

-- 17. Платежи (для сверки)
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    sale_id INTEGER REFERENCES sales(id),
    payment_system VARCHAR(50) NOT NULL,
    external_id VARCHAR(255),
    amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 18. Финансовые счета
CREATE TABLE finance_accounts (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL, -- cash, bank, wallet
    currency VARCHAR(3) DEFAULT 'UZS',
    balance DECIMAL(15, 2) DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 19. Финансовые транзакции
CREATE TABLE finance_transactions (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT gen_random_uuid() UNIQUE,
    type VARCHAR(50) NOT NULL, -- income, expense, transfer
    category VARCHAR(100),
    from_account_id INTEGER REFERENCES finance_accounts(id),
    to_account_id INTEGER REFERENCES finance_accounts(id),
    amount DECIMAL(15, 2) NOT NULL,
    description TEXT,
    reference_type VARCHAR(50), -- sale, purchase, salary, etc
    reference_id INTEGER,
    action_timestamp TIMESTAMP NOT NULL,
    entry_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id),
    attachments JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}'
);

-- 20. Инвесторы в автоматы
CREATE TABLE machine_investors (
    id SERIAL PRIMARY KEY,
    machine_id INTEGER REFERENCES machines(id),
    user_id INTEGER REFERENCES users(id),
    investment_amount DECIMAL(15, 2) NOT NULL,
    share_percentage DECIMAL(5, 2) NOT NULL,
    investment_date DATE NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(machine_id, user_id)
);

-- 21. Выплаты инвесторам
CREATE TABLE investor_payouts (
    id SERIAL PRIMARY KEY,
    machine_investor_id INTEGER REFERENCES machine_investors(id),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    total_revenue DECIMAL(15, 2) NOT NULL,
    investor_share DECIMAL(15, 2) NOT NULL,
    payout_date DATE,
    status VARCHAR(50) DEFAULT 'pending', -- pending, paid, cancelled
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 22. Аудит всех действий
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id INTEGER,
    old_data JSONB,
    new_data JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== ИНДЕКСЫ ДЛЯ ПРОИЗВОДИТЕЛЬНОСТИ =====

-- Пользователи
CREATE INDEX idx_users_telegram ON users(telegram_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_phone ON users(phone) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;

-- Автоматы
CREATE INDEX idx_machines_status ON machines(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_machines_location ON machines(location_lat, location_lng);
CREATE INDEX idx_machines_responsible ON machines(responsible_user_id);

-- Остатки
CREATE INDEX idx_inventory_location ON inventory(location_type, location_id);
CREATE INDEX idx_inventory_timestamp ON inventory(action_timestamp);
CREATE INDEX idx_inventory_ingredient ON inventory(ingredient_id);

-- Продажи
CREATE INDEX idx_sales_machine_date ON sales(machine_id, action_timestamp);
CREATE INDEX idx_sales_sync ON sales(sync_status);
CREATE INDEX idx_sales_payment ON sales(payment_method);

-- Финансы
CREATE INDEX idx_finance_date ON finance_transactions(action_timestamp);
CREATE INDEX idx_finance_category ON finance_transactions(category);
CREATE INDEX idx_finance_accounts ON finance_transactions(from_account_id, to_account_id);

-- Аудит
CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_date ON audit_log(created_at);

-- ===== ТРИГГЕРЫ =====

-- Функция для автообновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Применение триггера к таблицам с updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_machines_updated_at BEFORE UPDATE ON machines
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_warehouses_updated_at BEFORE UPDATE ON warehouses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ingredients_updated_at BEFORE UPDATE ON ingredients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_products_updated_at BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_machine_tasks_updated_at BEFORE UPDATE ON machine_tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Функция для аудита (пример для users)
CREATE OR REPLACE FUNCTION audit_users_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (user_id, action, entity_type, entity_id, new_data)
        VALUES (NEW.id, 'CREATE', 'user', NEW.id, row_to_json(NEW));
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_log (user_id, action, entity_type, entity_id, old_data, new_data)
        VALUES (NEW.id, 'UPDATE', 'user', NEW.id, row_to_json(OLD), row_to_json(NEW));
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log (user_id, action, entity_type, entity_id, old_data)
        VALUES (OLD.id, 'DELETE', 'user', OLD.id, row_to_json(OLD));
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ language 'plpgsql';

-- Применение аудита к users
CREATE TRIGGER audit_users_trigger
    AFTER INSERT OR UPDATE OR DELETE ON users
    FOR EACH ROW EXECUTE FUNCTION audit_users_changes();
