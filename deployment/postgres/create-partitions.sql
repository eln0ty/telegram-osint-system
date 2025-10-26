-- Creates monthly partitions for the messages table covering the current
-- month and the next eleven months. Re-run periodically to extend the window.

DO $$
DECLARE
    start_month DATE := date_trunc('month', NOW())::DATE;
    partition_start DATE;
    partition_end DATE;
    partition_name TEXT;
BEGIN
    FOR i IN 0..11 LOOP
        partition_start := (start_month + INTERVAL '1 month' * i)::DATE;
        partition_end := (start_month + INTERVAL '1 month' * (i + 1))::DATE;
        partition_name := FORMAT('messages_%s', TO_CHAR(partition_start, 'YYYYMM'));

        EXECUTE FORMAT(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF messages FOR VALUES FROM (%L) TO (%L);',
            partition_name,
            partition_start,
            partition_end
        );

        EXECUTE FORMAT(
            'CREATE UNIQUE INDEX IF NOT EXISTS %I_hash_idx ON %I (message_hash, date);',
            partition_name,
            partition_name
        );
    END LOOP;

    EXECUTE 'CREATE TABLE IF NOT EXISTS messages_default PARTITION OF messages DEFAULT';
    EXECUTE 'CREATE UNIQUE INDEX IF NOT EXISTS messages_default_hash_idx ON messages_default (message_hash, date)';
END $$;
