-- 更新 backup_configs 表的 storage_type 字段长度以支持JSON数组
-- Update storage_type field length in backup_configs table to support JSON array

ALTER TABLE backup_configs MODIFY COLUMN storage_type VARCHAR(200) NOT NULL;

-- 更新 backup_jobs 表的 storage_type 字段长度以支持JSON数组  
-- Update storage_type field length in backup_jobs table to support JSON array

ALTER TABLE backup_jobs MODIFY COLUMN storage_type VARCHAR(200);

-- 注意：现有的单一存储类型值（如 'ftp', 'email', 's3'）仍然兼容
-- Note: Existing single storage type values (like 'ftp', 'email', 's3') are still compatible
-- 新的多存储类型值将以JSON数组格式存储（如 '["ftp", "email"]'）
-- New multiple storage type values will be stored in JSON array format (like '["ftp", "email"]')
