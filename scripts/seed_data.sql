-- VendHub Initial Data
-- Файл: scripts/seed_data.sql

-- ===== РОЛИ =====
INSERT INTO roles (name, display_name, description, is_system) VALUES
('admin', 'Администратор', 'Полный доступ ко всем функциям системы', true),
('manager', 'Менеджер', 'Управление автоматами, отчеты, финансы', true),
('warehouse', 'Складской работник', 'Управление складом и остатками', true),
('operator', 'Оператор', 'Обслуживание автоматов, сбор выручки', true),
('investor', 'Инвестор', 'Просмотр отчетов по инвестициям', true);

-- ===== РАЗРЕШЕНИЯ =====
-- Пользователи
INSERT INTO permissions (module, action, description) VALUES
('users', 'create', 'Создание пользователей'),
('users', 'read', 'Просмотр пользователей'),
('users', 'update', 'Редактирование пользователей'),
('users', 'delete', 'Удаление пользователей');

-- Автоматы
INSERT INTO permissions (module, action, description) VALUES
('machines', 'create', 'Добавление автоматов'),
('machines', 'read', 'Просмотр автоматов'),
('machines', 'update', 'Редактирование автоматов'),
('machines', 'delete', 'Удаление автоматов'),
('machines', 'service', 'Обслуживание автоматов');

-- Склад и остатки
INSERT INTO permissions (module, action, description) VALUES
('inventory', 'create', 'Создание записей остатков'),
('inventory', 'read', 'Просмотр остатков'),
('inventory', 'update', 'Корректировка остатков'),
('inventory', 'delete', 'Удаление записей остатков'),
('warehouse', 'manage', 'Управление складом');

-- Продажи
INSERT INTO permissions (module, action, description) VALUES
('sales', 'create', 'Создание продаж'),
('sales', 'read', 'Просмотр продаж'),
('sales', 'update', 'Редактирование продаж'),
('sales', 'delete', 'Удаление продаж');

-- Финансы
INSERT INTO permissions (module, action, description) VALUES
('finance', 'create', 'Создание финансовых операций'),
('finance', 'read', 'Просмотр финансов'),
('finance', 'update', 'Редактирование финансовых операций'),
('finance', 'delete', 'Удаление финансовых операций'),
('finance', 'reports', 'Финансовые отчеты');

-- Рецепты и продукты
INSERT INTO permissions (module, action, description) VALUES
('products', 'create', 'Создание продуктов'),
('products', 'read', 'Просмотр продуктов'),
('products', 'update', 'Редактирование продуктов'),
('products', 'delete', 'Удаление продуктов'),
('recipes', 'create', 'Создание рецептов'),
('recipes', 'read', 'Просмотр рецептов'),
('recipes', 'update', 'Редактирование рецептов'),
('recipes', 'delete', 'Удаление рецептов');

-- Инвестиции
INSERT INTO permissions (module, action, description) VALUES
('investments', 'create', 'Создание инвестиций'),
('investments', 'read', 'Просмотр инвестиций'),
('investments', 'update', 'Редактирование инвестиций'),
('investments', 'reports', 'Отчеты по инвестициям');

-- Отчеты
INSERT INTO permissions (module, action, description) VALUES
('reports', 'sales', 'Отчеты по продажам'),
('reports', 'inventory', 'Отчеты по остаткам'),
('reports', 'finance', 'Финансовые отчеты'),
('reports', 'machines', 'Отчеты по автоматам');

-- Система
INSERT INTO permissions (module, action, description) VALUES
('system', 'settings', 'Настройки системы'),
('system', 'audit', 'Просмотр аудита'),
('system', 'backup', 'Создание резервных копий');

-- ===== НАЗНАЧЕНИЕ РАЗРЕШЕНИЙ РОЛЯМ =====

-- Администратор - все разрешения
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.name = 'admin';

-- Менеджер
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.name = 'manager'
AND p.module IN ('machines', 'sales', 'finance', 'products', 'recipes', 'reports', 'investments')
AND p.action != 'delete';

-- Складской работник
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.name = 'warehouse'
AND (
    (p.module = 'inventory') OR
    (p.module = 'warehouse') OR
    (p.module = 'machines' AND p.action = 'read') OR
    (p.module = 'products' AND p.action = 'read') OR
    (p.module = 'reports' AND p.action = 'inventory')
);

-- Оператор
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.name = 'operator'
AND (
    (p.module = 'machines' AND p.action IN ('read', 'service')) OR
    (p.module = 'sales' AND p.action IN ('create', 'read')) OR
    (p.module = 'inventory' AND p.action IN ('read', 'update')) OR
    (p.module = 'products' AND p.action = 'read')
);

-- Инвестор
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.name = 'investor'
AND (
    (p.module = 'investments' AND p.action IN ('read', 'reports')) OR
    (p.module = 'reports' AND p.action IN ('sales', 'finance')) OR
    (p.module = 'machines' AND p.action = 'read')
);

-- ===== ОСНОВНЫЕ ФИНАНСОВЫЕ СЧЕТА =====
INSERT INTO finance_accounts (code, name, type, currency) VALUES
('CASH_MAIN', 'Основная касса', 'cash', 'UZS'),
('BANK_MAIN', 'Основной банковский счет', 'bank', 'UZS'),
('PAYME_WALLET', 'Кошелек Payme', 'wallet', 'UZS'),
('CLICK_WALLET', 'Кошелек Click', 'wallet', 'UZS'),
('UZUM_WALLET', 'Кошелек Uzum', 'wallet', 'UZS');

-- ===== ОСНОВНЫЕ ИНГРЕДИЕНТЫ =====
INSERT INTO ingredients (code, name, category, unit, cost_per_unit, min_stock_level) VALUES
-- Кофе
('COFFEE_ARABICA', 'Арабика молотая', 'coffee', 'kg', 45000.00, 5.0),
('COFFEE_ROBUSTA', 'Робуста молотая', 'coffee', 'kg', 35000.00, 5.0),
('COFFEE_INSTANT', 'Растворимый кофе', 'coffee', 'kg', 25000.00, 3.0),

-- Молочные продукты
('MILK_POWDER', 'Сухое молоко', 'milk', 'kg', 18000.00, 10.0),
('CREAM_POWDER', 'Сухие сливки', 'milk', 'kg', 22000.00, 5.0),

-- Сиропы
('SYRUP_VANILLA', 'Ванильный сироп', 'syrup', 'l', 15000.00, 2.0),
('SYRUP_CARAMEL', 'Карамельный сироп', 'syrup', 'l', 15000.00, 2.0),
('SYRUP_CHOCOLATE', 'Шоколадный сироп', 'syrup', 'l', 16000.00, 2.0),

-- Другое
('SUGAR', 'Сахар', 'sweetener', 'kg', 8000.00, 20.0),
('CUPS_PAPER', 'Бумажные стаканчики', 'supplies', 'pcs', 120.00, 1000.0),
('LIDS_PLASTIC', 'Пластиковые крышки', 'supplies', 'pcs', 80.00, 1000.0);

-- ===== ОСНОВНЫЕ ПРОДУКТЫ =====
INSERT INTO products (code, name, category, price) VALUES
-- Кофе
('ESPRESSO', 'Эспрессо', 'coffee', 8000.00),
('AMERICANO', 'Американо', 'coffee', 10000.00),
('CAPPUCCINO', 'Капучино', 'coffee', 12000.00),
('LATTE', 'Латте', 'coffee', 14000.00),
('MOCHA', 'Мокка', 'coffee', 16000.00),

-- Горячие напитки
('HOT_CHOCOLATE', 'Горячий шоколад', 'hot_drinks', 12000.00),
('TEA_BLACK', 'Черный чай', 'hot_drinks', 6000.00),
('TEA_GREEN', 'Зеленый чай', 'hot_drinks', 6000.00),

-- Холодные напитки  
('COLA', 'Кола', 'cold_drinks', 5000.00),
('WATER', 'Вода', 'cold_drinks', 3000.00);

-- ===== РЕЦЕПТЫ =====
-- Эспрессо
INSERT INTO recipes (product_id, version, is_active) 
SELECT id, 1, true FROM products WHERE code = 'ESPRESSO';

INSERT INTO recipe_ingredients (recipe_id, ingredient_id, quantity)
SELECT r.id, i.id, 0.007
FROM recipes r
JOIN products p ON p.id = r.product_id
JOIN ingredients i ON i.code = 'COFFEE_ARABICA'
WHERE p.code = 'ESPRESSO';

-- Американо  
INSERT INTO recipes (product_id, version, is_active)
SELECT id, 1, true FROM products WHERE code = 'AMERICANO';

INSERT INTO recipe_ingredients (recipe_id, ingredient_id, quantity)
SELECT r.id, i.id, 0.008
FROM recipes r
JOIN products p ON p.id = r.product_id
JOIN ingredients i ON i.code = 'COFFEE_ARABICA'
WHERE p.code = 'AMERICANO';

-- Капучино
INSERT INTO recipes (product_id, version, is_active)
SELECT id, 1, true FROM products WHERE code = 'CAPPUCCINO';

INSERT INTO recipe_ingredients (recipe_id, ingredient_id, quantity)
SELECT r.id, i.id, CASE 
    WHEN i.code = 'COFFEE_ARABICA' THEN 0.008
    WHEN i.code = 'MILK_POWDER' THEN 0.015
    WHEN i.code = 'SUGAR' THEN 0.010
END
FROM recipes r
JOIN products p ON p.id = r.product_id
JOIN ingredients i ON i.code IN ('COFFEE_ARABICA', 'MILK_POWDER', 'SUGAR')
WHERE p.code = 'CAPPUCCINO';

-- ===== СОЗДАНИЕ АДМИНА ПО УМОЛЧАНИЮ =====
-- Пароль: admin123 (будет захеширован в приложении)
INSERT INTO users (telegram_id, full_name, username, email, is_active, is_verified)
VALUES (123456789, 'Системный администратор', 'admin', 'admin@vendhub.uz', true, true);

-- Назначение роли админа
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u, roles r
WHERE u.username = 'admin' AND r.name = 'admin';

-- ===== ТЕСТОВЫЙ СКЛАД =====
INSERT INTO warehouses (code, name, address, is_active)
VALUES ('MAIN_WAREHOUSE', 'Основной склад', 'г. Ташкент, ул. Тестовая, 1', true);

-- Связать склад с админом
UPDATE warehouses SET responsible_user_id = (
    SELECT id FROM users WHERE username = 'admin'
) WHERE code = 'MAIN_WAREHOUSE';
