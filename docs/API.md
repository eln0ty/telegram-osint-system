# Data Schema & Interfaces

## Message Payload (Producer → RabbitMQ)

```json
{
  "type": "message",
  "run_id": "uuid",
  "key": "sha256",
  "channel_id": 123456789,
  "channel_username": "vxunderground",
  "message_id": 98765,
  "date": "2024-05-01T12:34:56+00:00",
  "text": "...",
  "views": 1000,
  "forwards": 25,
  "replies": 5,
  "reply_to_message_id": 98764,
  "has_media": true,
  "media_type": "MessageMediaDocument"
}
```

## Run Events

- `run_start` – emitted before collection begins for a channel.
- `run_end` – emitted once collection completes or fails.

Both include:

```json
{
  "type": "run_start",
  "run_id": "uuid",
  "channel_username": "vxunderground",
  "ts": 1714567890.123,
  "status": "running"
}
```

## Database Tables

### `collection_runs`

| Column | Description |
|--------|-------------|
| `run_id` | UUID for the run |
| `channel_username` | Channel shorthand |
| `messages_collected` | Incremented by worker on successful inserts |
| `start_time`, `end_time` | Run timestamps |
| `status` | `running`, `success`, `failed`, `flood_wait`, etc. |

### `messages`

Partitioned by month on `date`.

| Column | Description |
|--------|-------------|
| `channel_id`, `message_id`, `date` | Composite primary key |
| `message_hash` | Stable SHA-256 hash (channel + message id) |
| `channel_username` | Human readable channel name |
| `text` | Raw message text |
| `views`, `forwards`, `replies` | Engagement metrics |
| `reply_to_message_id` | Link to parent message |
| `has_media`, `media_type` | Media metadata |
| `run_id` | Foreign key reference to collection run |
| `collected_at` | Timestamp of ingestion |

## Automation Scripts

- See `scripts/` for operational helpers. Each script emits structured logs and uses `.env`.
