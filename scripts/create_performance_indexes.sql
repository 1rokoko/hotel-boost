-- Performance indexes for WhatsApp Hotel Bot database
-- This script creates additional indexes for optimal query performance

-- Hotels table indexes (already defined in model, but listed for completeness)
-- CREATE INDEX IF NOT EXISTS idx_hotels_active ON hotels(is_active);
-- CREATE INDEX IF NOT EXISTS idx_hotels_whatsapp_number ON hotels(whatsapp_number);
-- CREATE INDEX IF NOT EXISTS idx_hotels_active_with_api ON hotels(is_active, green_api_instance_id) 
--     WHERE is_active = true AND green_api_instance_id IS NOT NULL;

-- Additional hotels indexes for performance
CREATE INDEX IF NOT EXISTS idx_hotels_name_trgm ON hotels USING gin(name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_hotels_settings_gin ON hotels USING gin(settings);
CREATE INDEX IF NOT EXISTS idx_hotels_created_at ON hotels(created_at);
CREATE INDEX IF NOT EXISTS idx_hotels_updated_at ON hotels(updated_at);

-- Guests table additional indexes
CREATE INDEX IF NOT EXISTS idx_guests_name_trgm ON guests USING gin(name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_guests_preferences_gin ON guests USING gin(preferences);
CREATE INDEX IF NOT EXISTS idx_guests_phone_trgm ON guests USING gin(phone gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_guests_recent_active ON guests(hotel_id, last_interaction) 
    WHERE last_interaction > NOW() - INTERVAL '7 days';
CREATE INDEX IF NOT EXISTS idx_guests_vip ON guests(hotel_id) 
    WHERE (preferences->>'profile'->>'vip_status')::boolean = true;

-- Triggers table additional indexes
CREATE INDEX IF NOT EXISTS idx_triggers_conditions_gin ON triggers USING gin(conditions);
CREATE INDEX IF NOT EXISTS idx_triggers_name_trgm ON triggers USING gin(name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_triggers_message_template_trgm ON triggers USING gin(message_template gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_triggers_active_time_based ON triggers(hotel_id, priority) 
    WHERE is_active = true AND trigger_type = 'time_based';
CREATE INDEX IF NOT EXISTS idx_triggers_active_event_based ON triggers(hotel_id, priority) 
    WHERE is_active = true AND trigger_type = 'event_based';

-- Conversations table additional indexes
CREATE INDEX IF NOT EXISTS idx_conversations_guest_status ON conversations(guest_id, status);
CREATE INDEX IF NOT EXISTS idx_conversations_recent_active ON conversations(hotel_id, last_message_at) 
    WHERE status = 'active' AND last_message_at > NOW() - INTERVAL '24 hours';
CREATE INDEX IF NOT EXISTS idx_conversations_escalated ON conversations(hotel_id, created_at) 
    WHERE status = 'escalated';

-- Messages table additional indexes
CREATE INDEX IF NOT EXISTS idx_messages_content_trgm ON messages USING gin(content gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_messages_metadata_gin ON messages USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_messages_sentiment_score ON messages(sentiment_score) 
    WHERE sentiment_score IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_recent_negative ON messages(conversation_id, created_at) 
    WHERE sentiment_type IN ('negative', 'requires_attention') 
    AND created_at > NOW() - INTERVAL '24 hours';
CREATE INDEX IF NOT EXISTS idx_messages_incoming_recent ON messages(conversation_id, created_at) 
    WHERE message_type = 'incoming' AND created_at > NOW() - INTERVAL '7 days';

-- Staff notifications table additional indexes
CREATE INDEX IF NOT EXISTS idx_staff_notifications_metadata_gin ON staff_notifications USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_staff_notifications_title_trgm ON staff_notifications USING gin(title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_staff_notifications_content_trgm ON staff_notifications USING gin(content gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_staff_notifications_urgent_pending ON staff_notifications(hotel_id, created_at) 
    WHERE notification_type IN ('urgent_request', 'guest_complaint', 'escalation') 
    AND status IN ('pending', 'sent');
CREATE INDEX IF NOT EXISTS idx_staff_notifications_acknowledged_at ON staff_notifications(acknowledged_at) 
    WHERE acknowledged_at IS NOT NULL;

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_guest_conversation_recent ON conversations(guest_id, last_message_at DESC);
CREATE INDEX IF NOT EXISTS idx_hotel_guest_messages ON messages(conversation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_hotel_notifications_priority ON staff_notifications(hotel_id, notification_type, status, created_at);

-- Indexes for analytics and reporting
CREATE INDEX IF NOT EXISTS idx_messages_daily_stats ON messages(
    conversation_id, 
    DATE(created_at), 
    message_type
);
CREATE INDEX IF NOT EXISTS idx_notifications_daily_stats ON staff_notifications(
    hotel_id, 
    DATE(created_at), 
    notification_type, 
    status
);
CREATE INDEX IF NOT EXISTS idx_conversations_duration ON conversations(
    hotel_id, 
    created_at, 
    last_message_at
) WHERE status IN ('closed', 'archived');

-- Indexes for audit and compliance
CREATE INDEX IF NOT EXISTS idx_tenant_audit_log_tenant_time ON tenant_audit_log(tenant_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_tenant_audit_log_action_time ON tenant_audit_log(action, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_tenant_audit_log_table_time ON tenant_audit_log(table_name, timestamp DESC);

-- Partial indexes for specific business logic
CREATE INDEX IF NOT EXISTS idx_guests_no_name ON guests(hotel_id, created_at) 
    WHERE name IS NULL OR name = '';
CREATE INDEX IF NOT EXISTS idx_conversations_long_running ON conversations(hotel_id, created_at) 
    WHERE status = 'active' AND created_at < NOW() - INTERVAL '7 days';
CREATE INDEX IF NOT EXISTS idx_messages_no_sentiment ON messages(conversation_id, created_at) 
    WHERE sentiment_score IS NULL AND message_type = 'incoming';

-- Function-based indexes for computed values
CREATE INDEX IF NOT EXISTS idx_messages_sentiment_category ON messages(
    CASE 
        WHEN sentiment_score >= 0.3 THEN 'positive'
        WHEN sentiment_score <= -0.3 THEN 'negative'
        WHEN sentiment_score <= -0.7 THEN 'very_negative'
        ELSE 'neutral'
    END
) WHERE sentiment_score IS NOT NULL;

-- Indexes for JSON queries
CREATE INDEX IF NOT EXISTS idx_guests_language ON guests((preferences->>'communication'->>'language'));
CREATE INDEX IF NOT EXISTS idx_guests_visit_count ON guests(((preferences->>'profile'->>'visit_count')::int));
CREATE INDEX IF NOT EXISTS idx_triggers_schedule_type ON triggers((conditions->>'schedule_type'));
CREATE INDEX IF NOT EXISTS idx_hotels_timezone ON hotels((settings->>'auto_responses'->>'business_hours'->>'timezone'));

-- Create function to analyze index usage
CREATE OR REPLACE FUNCTION analyze_index_usage() RETURNS TABLE(
    schemaname TEXT,
    tablename TEXT,
    indexname TEXT,
    num_rows BIGINT,
    table_size TEXT,
    index_size TEXT,
    unique_index BOOLEAN,
    number_of_scans BIGINT,
    tuples_read BIGINT,
    tuples_fetched BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.schemaname::TEXT,
        s.tablename::TEXT,
        s.indexname::TEXT,
        pg_class.reltuples::BIGINT as num_rows,
        pg_size_pretty(pg_total_relation_size(s.tablename::regclass))::TEXT as table_size,
        pg_size_pretty(pg_total_relation_size(s.indexname::regclass))::TEXT as index_size,
        s.indexdef LIKE '%UNIQUE%' as unique_index,
        pg_stat_user_indexes.idx_scan as number_of_scans,
        pg_stat_user_indexes.idx_tup_read as tuples_read,
        pg_stat_user_indexes.idx_tup_fetch as tuples_fetched
    FROM pg_indexes s
    LEFT JOIN pg_stat_user_indexes ON s.indexname = pg_stat_user_indexes.indexrelname
    LEFT JOIN pg_class ON s.tablename = pg_class.relname
    WHERE s.schemaname = 'public'
    AND s.tablename IN ('hotels', 'guests', 'triggers', 'conversations', 'messages', 'staff_notifications')
    ORDER BY s.tablename, pg_stat_user_indexes.idx_scan DESC NULLS LAST;
END;
$$ LANGUAGE plpgsql;

-- Create function to find unused indexes
CREATE OR REPLACE FUNCTION find_unused_indexes() RETURNS TABLE(
    schemaname TEXT,
    tablename TEXT,
    indexname TEXT,
    index_size TEXT,
    scans BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.schemaname::TEXT,
        s.tablename::TEXT,
        s.indexname::TEXT,
        pg_size_pretty(pg_total_relation_size(s.indexname::regclass))::TEXT as index_size,
        COALESCE(pg_stat_user_indexes.idx_scan, 0) as scans
    FROM pg_indexes s
    LEFT JOIN pg_stat_user_indexes ON s.indexname = pg_stat_user_indexes.indexrelname
    WHERE s.schemaname = 'public'
    AND s.tablename IN ('hotels', 'guests', 'triggers', 'conversations', 'messages', 'staff_notifications')
    AND COALESCE(pg_stat_user_indexes.idx_scan, 0) < 10
    AND s.indexname NOT LIKE '%_pkey'  -- Exclude primary keys
    ORDER BY COALESCE(pg_stat_user_indexes.idx_scan, 0), pg_total_relation_size(s.indexname::regclass) DESC;
END;
$$ LANGUAGE plpgsql;

-- Create function to get table statistics
CREATE OR REPLACE FUNCTION get_table_stats() RETURNS TABLE(
    schemaname TEXT,
    tablename TEXT,
    num_rows BIGINT,
    table_size TEXT,
    index_size TEXT,
    total_size TEXT,
    seq_scans BIGINT,
    seq_tup_read BIGINT,
    idx_scans BIGINT,
    idx_tup_fetch BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        'public'::TEXT as schemaname,
        pg_class.relname::TEXT as tablename,
        pg_class.reltuples::BIGINT as num_rows,
        pg_size_pretty(pg_relation_size(pg_class.oid))::TEXT as table_size,
        pg_size_pretty(pg_total_relation_size(pg_class.oid) - pg_relation_size(pg_class.oid))::TEXT as index_size,
        pg_size_pretty(pg_total_relation_size(pg_class.oid))::TEXT as total_size,
        pg_stat_user_tables.seq_scan as seq_scans,
        pg_stat_user_tables.seq_tup_read as seq_tup_read,
        pg_stat_user_tables.idx_scan as idx_scans,
        pg_stat_user_tables.idx_tup_fetch as idx_tup_fetch
    FROM pg_class
    LEFT JOIN pg_stat_user_tables ON pg_class.relname = pg_stat_user_tables.relname
    WHERE pg_class.relkind = 'r'
    AND pg_class.relname IN ('hotels', 'guests', 'triggers', 'conversations', 'messages', 'staff_notifications')
    ORDER BY pg_total_relation_size(pg_class.oid) DESC;
END;
$$ LANGUAGE plpgsql;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION analyze_index_usage() TO hotel_bot_admin;
GRANT EXECUTE ON FUNCTION find_unused_indexes() TO hotel_bot_admin;
GRANT EXECUTE ON FUNCTION get_table_stats() TO hotel_bot_admin;

-- Enable pg_trgm extension for text search indexes
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Update table statistics
ANALYZE hotels;
ANALYZE guests;
ANALYZE triggers;
ANALYZE conversations;
ANALYZE messages;
ANALYZE staff_notifications;

-- Display index creation summary
SELECT 
    'Index creation completed' as status,
    COUNT(*) as total_indexes_created
FROM pg_indexes 
WHERE schemaname = 'public' 
AND tablename IN ('hotels', 'guests', 'triggers', 'conversations', 'messages', 'staff_notifications');
