-- Row Level Security (RLS) setup for multi-tenant architecture
-- This script enables RLS and creates policies for tenant data isolation

-- Enable Row Level Security on all tenant-specific tables
ALTER TABLE guests ENABLE ROW LEVEL SECURITY;
ALTER TABLE triggers ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE staff_notifications ENABLE ROW LEVEL SECURITY;

-- Note: hotels table doesn't need RLS as it's the tenant definition table

-- Create RLS policies for guests table
CREATE POLICY tenant_isolation_guests ON guests
    FOR ALL TO hotel_bot_tenant
    USING (hotel_id = get_current_tenant_id());

-- Create RLS policies for triggers table
CREATE POLICY tenant_isolation_triggers ON triggers
    FOR ALL TO hotel_bot_tenant
    USING (hotel_id = get_current_tenant_id());

-- Create RLS policies for conversations table
CREATE POLICY tenant_isolation_conversations ON conversations
    FOR ALL TO hotel_bot_tenant
    USING (hotel_id = get_current_tenant_id());

-- Create RLS policies for messages table
-- Messages are isolated through their conversation's hotel_id
CREATE POLICY tenant_isolation_messages ON messages
    FOR ALL TO hotel_bot_tenant
    USING (
        EXISTS (
            SELECT 1 FROM conversations 
            WHERE conversations.id = messages.conversation_id 
            AND conversations.hotel_id = get_current_tenant_id()
        )
    );

-- Create RLS policies for staff_notifications table
CREATE POLICY tenant_isolation_staff_notifications ON staff_notifications
    FOR ALL TO hotel_bot_tenant
    USING (hotel_id = get_current_tenant_id());

-- Create additional policies for different operations if needed

-- Policy for hotel_bot_admin role (bypass RLS for admin operations)
-- Admin can access all data for migrations and maintenance
CREATE POLICY admin_bypass_guests ON guests
    FOR ALL TO hotel_bot_admin
    USING (true);

CREATE POLICY admin_bypass_triggers ON triggers
    FOR ALL TO hotel_bot_admin
    USING (true);

CREATE POLICY admin_bypass_conversations ON conversations
    FOR ALL TO hotel_bot_admin
    USING (true);

CREATE POLICY admin_bypass_messages ON messages
    FOR ALL TO hotel_bot_admin
    USING (true);

CREATE POLICY admin_bypass_staff_notifications ON staff_notifications
    FOR ALL TO hotel_bot_admin
    USING (true);

-- Create policies for specific operations (SELECT, INSERT, UPDATE, DELETE)
-- These provide more granular control if needed

-- Read-only policy for reporting (if you have a reporting role)
-- CREATE ROLE hotel_bot_reporter;
-- CREATE POLICY reporter_read_guests ON guests
--     FOR SELECT TO hotel_bot_reporter
--     USING (hotel_id = get_current_tenant_id());

-- Audit policy to log all access attempts
CREATE OR REPLACE FUNCTION log_rls_access() RETURNS TRIGGER AS $$
BEGIN
    -- Log access attempts for audit purposes
    INSERT INTO tenant_audit_log (
        tenant_id, 
        user_role, 
        action, 
        table_name, 
        record_id,
        timestamp
    ) VALUES (
        get_current_tenant_id(),
        current_user,
        TG_OP,
        TG_TABLE_NAME,
        COALESCE(NEW.id, OLD.id),
        NOW()
    );
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create audit triggers for all tenant tables
CREATE TRIGGER audit_guests_access
    AFTER INSERT OR UPDATE OR DELETE ON guests
    FOR EACH ROW EXECUTE FUNCTION log_rls_access();

CREATE TRIGGER audit_triggers_access
    AFTER INSERT OR UPDATE OR DELETE ON triggers
    FOR EACH ROW EXECUTE FUNCTION log_rls_access();

CREATE TRIGGER audit_conversations_access
    AFTER INSERT OR UPDATE OR DELETE ON conversations
    FOR EACH ROW EXECUTE FUNCTION log_rls_access();

CREATE TRIGGER audit_messages_access
    AFTER INSERT OR UPDATE OR DELETE ON messages
    FOR EACH ROW EXECUTE FUNCTION log_rls_access();

CREATE TRIGGER audit_staff_notifications_access
    AFTER INSERT OR UPDATE OR DELETE ON staff_notifications
    FOR EACH ROW EXECUTE FUNCTION log_rls_access();

-- Create function to test RLS policies
CREATE OR REPLACE FUNCTION test_rls_isolation(test_tenant_id UUID) RETURNS TABLE(
    table_name TEXT,
    policy_name TEXT,
    test_result BOOLEAN,
    error_message TEXT
) AS $$
DECLARE
    original_tenant_id UUID;
    test_record RECORD;
BEGIN
    -- Store original tenant context
    original_tenant_id := get_current_tenant_id();
    
    -- Set test tenant context
    PERFORM set_tenant_context(test_tenant_id);
    
    -- Test guests table
    BEGIN
        SELECT COUNT(*) INTO test_record FROM guests WHERE hotel_id != test_tenant_id;
        RETURN QUERY SELECT 'guests'::TEXT, 'tenant_isolation_guests'::TEXT, 
                           (test_record.count = 0), NULL::TEXT;
    EXCEPTION WHEN OTHERS THEN
        RETURN QUERY SELECT 'guests'::TEXT, 'tenant_isolation_guests'::TEXT, 
                           FALSE, SQLERRM;
    END;
    
    -- Test triggers table
    BEGIN
        SELECT COUNT(*) INTO test_record FROM triggers WHERE hotel_id != test_tenant_id;
        RETURN QUERY SELECT 'triggers'::TEXT, 'tenant_isolation_triggers'::TEXT, 
                           (test_record.count = 0), NULL::TEXT;
    EXCEPTION WHEN OTHERS THEN
        RETURN QUERY SELECT 'triggers'::TEXT, 'tenant_isolation_triggers'::TEXT, 
                           FALSE, SQLERRM;
    END;
    
    -- Test conversations table
    BEGIN
        SELECT COUNT(*) INTO test_record FROM conversations WHERE hotel_id != test_tenant_id;
        RETURN QUERY SELECT 'conversations'::TEXT, 'tenant_isolation_conversations'::TEXT, 
                           (test_record.count = 0), NULL::TEXT;
    EXCEPTION WHEN OTHERS THEN
        RETURN QUERY SELECT 'conversations'::TEXT, 'tenant_isolation_conversations'::TEXT, 
                           FALSE, SQLERRM;
    END;
    
    -- Test staff_notifications table
    BEGIN
        SELECT COUNT(*) INTO test_record FROM staff_notifications WHERE hotel_id != test_tenant_id;
        RETURN QUERY SELECT 'staff_notifications'::TEXT, 'tenant_isolation_staff_notifications'::TEXT, 
                           (test_record.count = 0), NULL::TEXT;
    EXCEPTION WHEN OTHERS THEN
        RETURN QUERY SELECT 'staff_notifications'::TEXT, 'tenant_isolation_staff_notifications'::TEXT, 
                           FALSE, SQLERRM;
    END;
    
    -- Restore original tenant context
    IF original_tenant_id IS NOT NULL THEN
        PERFORM set_tenant_context(original_tenant_id);
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission on test function
GRANT EXECUTE ON FUNCTION test_rls_isolation(UUID) TO hotel_bot_admin;

-- Create function to get RLS policy information
CREATE OR REPLACE FUNCTION get_rls_policies() RETURNS TABLE(
    schemaname TEXT,
    tablename TEXT,
    policyname TEXT,
    permissive TEXT,
    roles TEXT[],
    cmd TEXT,
    qual TEXT,
    with_check TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.schemaname::TEXT,
        p.tablename::TEXT,
        p.policyname::TEXT,
        p.permissive::TEXT,
        p.roles,
        p.cmd::TEXT,
        p.qual::TEXT,
        p.with_check::TEXT
    FROM pg_policies p
    WHERE p.schemaname = 'public'
    AND p.tablename IN ('guests', 'triggers', 'conversations', 'messages', 'staff_notifications')
    ORDER BY p.tablename, p.policyname;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission on policy info function
GRANT EXECUTE ON FUNCTION get_rls_policies() TO hotel_bot_admin;

-- Create function to enable/disable RLS for maintenance
CREATE OR REPLACE FUNCTION toggle_rls(enable_rls BOOLEAN) RETURNS TEXT AS $$
DECLARE
    result TEXT := '';
BEGIN
    IF enable_rls THEN
        ALTER TABLE guests ENABLE ROW LEVEL SECURITY;
        ALTER TABLE triggers ENABLE ROW LEVEL SECURITY;
        ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
        ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
        ALTER TABLE staff_notifications ENABLE ROW LEVEL SECURITY;
        result := 'RLS enabled on all tenant tables';
    ELSE
        ALTER TABLE guests DISABLE ROW LEVEL SECURITY;
        ALTER TABLE triggers DISABLE ROW LEVEL SECURITY;
        ALTER TABLE conversations DISABLE ROW LEVEL SECURITY;
        ALTER TABLE messages DISABLE ROW LEVEL SECURITY;
        ALTER TABLE staff_notifications DISABLE ROW LEVEL SECURITY;
        result := 'RLS disabled on all tenant tables';
    END IF;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission only to admin
GRANT EXECUTE ON FUNCTION toggle_rls(BOOLEAN) TO hotel_bot_admin;

-- Display current RLS status
SELECT 
    schemaname,
    tablename,
    rowsecurity as rls_enabled,
    CASE 
        WHEN rowsecurity THEN 'Enabled'
        ELSE 'Disabled'
    END as status
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename IN ('hotels', 'guests', 'triggers', 'conversations', 'messages', 'staff_notifications')
ORDER BY tablename;

-- Display created policies
SELECT * FROM get_rls_policies();
