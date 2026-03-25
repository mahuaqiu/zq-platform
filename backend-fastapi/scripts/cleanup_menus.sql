-- 删除菜单数据的SQL脚本
-- 请在PostgreSQL中执行

-- 1. 先删除角色-菜单关联
DELETE FROM core_role_menu WHERE menu_id IN (
    SELECT id FROM core_menu WHERE
    path LIKE '/tool%' OR
    path LIKE '/monitor%' OR
    path LIKE '/moniter%' OR
    path LIKE '/message%' OR
    path LIKE '/scheduler%' OR
    path LIKE '/database%' OR
    path LIKE '/online-development%' OR
    path LIKE '/data-source%'
);

-- 2. 删除权限（关联已删除菜单的权限）
DELETE FROM core_permission WHERE menu_id IN (
    SELECT id FROM core_menu WHERE
    path LIKE '/tool%' OR
    path LIKE '/monitor%' OR
    path LIKE '/moniter%' OR
    path LIKE '/message%' OR
    path LIKE '/scheduler%' OR
    path LIKE '/database%' OR
    path LIKE '/online-development%' OR
    path LIKE '/data-source%'
);

-- 3. 删除菜单（按路径删除）
DELETE FROM core_menu WHERE path LIKE '/tool%';
DELETE FROM core_menu WHERE path LIKE '/monitor%';
DELETE FROM core_menu WHERE path LIKE '/moniter%';
DELETE FROM core_menu WHERE path LIKE '/message%';
DELETE FROM core_menu WHERE path LIKE '/scheduler%';
DELETE FROM core_menu WHERE path LIKE '/database%';
DELETE FROM core_menu WHERE path LIKE '/online-development%';
DELETE FROM core_menu WHERE path LIKE '/data-source%';

-- 4. 删除子菜单（按名称删除可能遗漏的）
DELETE FROM core_menu WHERE name ILIKE '%file%';
DELETE FROM core_menu WHERE name ILIKE '%scheduler%';
DELETE FROM core_menu WHERE name ILIKE '%redis%';
DELETE FROM core_menu WHERE name ILIKE '%server%';
DELETE FROM core_menu WHERE name ILIKE '%database%' AND name NOT ILIKE '%analysis%';
DELETE FROM core_menu WHERE name ILIKE '%monitor%';
DELETE FROM core_menu WHERE name ILIKE '%message%';
DELETE FROM core_menu WHERE name ILIKE '%page%manager%';
DELETE FROM core_menu WHERE name ILIKE '%data%source%';

-- 5. 删除不再使用的表
DROP TABLE IF EXISTS core_scheduler_log;
DROP TABLE IF EXISTS core_scheduler_job;
DROP TABLE IF EXISTS core_message;
DROP TABLE IF EXISTS core_file_manager;
DROP TABLE IF EXISTS core_page_manager;

-- 查看剩余菜单
SELECT id, name, path, title FROM core_menu ORDER BY path;