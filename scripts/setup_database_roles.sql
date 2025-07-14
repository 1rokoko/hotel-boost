-- Database roles setup for multi-tenant architecture
-- This script creates the necessary roles for Row Level Security

-- Create admin role (for migrations and schema management)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'hotel_bot_admin') THEN
        CREATE ROLE hotel_bot_admin WITH LOGIN PASSWORD 'admin_password_change_in_production';
        COMMENT ON ROLE hotel_bot_admin IS 'Admin role for schema management and migrations';
    END IF;
END
$$;

-- Create tenant user role (for application data access)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'hotel_bot_tenant') THEN
        CREATE ROLE hotel_bot_tenant WITH LOGIN PASSWORD 'tenant_password_change_in_production';
        COMMENT ON ROLE hotel_bot_tenant IS 'Tenant role for multi-tenant data access with RLS';
    END IF;
END
$$;

-- Grant necessary permissions to admin role
GRANT ALL PRIVILEGES ON DATABASE hotel_bot TO hotel_bot_admin;
GRANT hotel_bot_tenant TO hotel_bot_admin;

-- Grant schema permissions to tenant role
GRANT USAGE ON SCHEMA public TO hotel_bot_tenant;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO hotel_bot_tenant;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hotel_bot_tenant;

-- Grant sequence permissions for auto-increment fields
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO hotel_bot_tenant;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO hotel_bot_tenant;

-- Enable UUID extension for UUID primary keys
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create function to generate UUIDs (alternative to uuid-ossp)
CREATE OR REPLACE FUNCTION generate_uuid() RETURNS UUID AS $$
BEGIN
    RETURN gen_random_uuid();
END;
$$ LANGUAGE plpgsql;

-- Create function to set tenant context
CREATE OR REPLACE FUNCTION set_tenant_context(tenant_id UUID) RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', tenant_id::text, true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create function to get current tenant context
CREATE OR REPLACE FUNCTION get_current_tenant_id() RETURNS UUID AS $$
BEGIN
    RETURN current_setting('app.current_tenant_id', true)::UUID;
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Grant execute permissions on utility functions
GRANT EXECUTE ON FUNCTION set_tenant_context(UUID) TO hotel_bot_tenant;
GRANT EXECUTE ON FUNCTION get_current_tenant_id() TO hotel_bot_tenant;
GRANT EXECUTE ON FUNCTION generate_uuid() TO hotel_bot_tenant;

-- Create audit log table for tracking tenant access
CREATE TABLE IF NOT EXISTS tenant_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID,
    user_role TEXT,
    action TEXT,
    table_name TEXT,
    record_id UUID,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT
);

-- Grant permissions on audit log
GRANT SELECT, INSERT ON tenant_audit_log TO hotel_bot_tenant;

-- Create indexes for audit log
CREATE INDEX IF NOT EXISTS idx_tenant_audit_log_tenant_id ON tenant_audit_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_audit_log_timestamp ON tenant_audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_tenant_audit_log_action ON tenant_audit_log(action);

-- Create function to log tenant actions
CREATE OR REPLACE FUNCTION log_tenant_action(
    p_tenant_id UUID,
    p_action TEXT,
    p_table_name TEXT,
    p_record_id UUID DEFAULT NULL,
    p_ip_address INET DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    INSERT INTO tenant_audit_log (
        tenant_id, user_role, action, table_name, record_id, ip_address, user_agent
    ) VALUES (
        p_tenant_id, current_user, p_action, p_table_name, p_record_id, p_ip_address, p_user_agent
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION log_tenant_action(UUID, TEXT, TEXT, UUID, INET, TEXT) TO hotel_bot_tenant;

-- Display role information
SELECT 
    rolname as role_name,
    rolsuper as is_superuser,
    rolinherit as can_inherit,
    rolcreaterole as can_create_roles,
    rolcreatedb as can_create_databases,
    rolcanlogin as can_login,
    rolconnlimit as connection_limit
FROM pg_roles 
WHERE rolname IN ('hotel_bot_admin', 'hotel_bot_tenant')
ORDER BY rolname;
