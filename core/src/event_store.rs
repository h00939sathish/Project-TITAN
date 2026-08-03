use pyo3::prelude::*;
use pyo3::exceptions::PyRuntimeError;
use rusqlite::Connection;
use std::sync::Mutex;

use crate::messages::EventEnvelope;

/// An append-only event store backed by SQLite.
#[pyclass]
pub struct EventStore {
    conn: Mutex<Option<Connection>>,
}

impl EventStore {
    fn conn(&self) -> PyResult<std::sync::MutexGuard<'_, Option<Connection>>> {
        self.conn.lock().map_err(|e| {
            PyRuntimeError::new_err(format!("Lock error: {}", e))
        })
    }
}

#[pymethods]
impl EventStore {
    #[new]
    pub fn new(path: &str) -> PyResult<Self> {
        let conn = Connection::open(path).map_err(|e| {
            PyRuntimeError::new_err(format!("Failed to open event store: {}", e))
        })?;

        conn.execute_batch(
            "PRAGMA journal_mode=WAL;
             PRAGMA synchronous=NORMAL;
             CREATE TABLE IF NOT EXISTS events (
                message_id TEXT PRIMARY KEY,
                message_type TEXT NOT NULL,
                schema_version INTEGER NOT NULL,
                occurred_at TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                causation_id TEXT,
                aggregate_type TEXT NOT NULL,
                aggregate_id TEXT NOT NULL,
                source TEXT NOT NULL,
                payload TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_events_aggregate
                ON events(aggregate_type, aggregate_id);
            CREATE INDEX IF NOT EXISTS idx_events_type
                ON events(message_type);
            CREATE INDEX IF NOT EXISTS idx_events_correlation
                ON events(correlation_id);
            CREATE INDEX IF NOT EXISTS idx_events_occurred
                ON events(occurred_at);",
        )
        .map_err(|e| PyRuntimeError::new_err(format!("Failed to initialize schema: {}", e)))?;

        Ok(Self {
            conn: Mutex::new(Some(conn)),
        })
    }

    /// Close the database connection. Subsequent operations will fail.
    pub fn close(&self) -> PyResult<()> {
        let mut guard = self.conn()?;
        *guard = None;
        Ok(())
    }

    /// Append an event. Returns error if message_id already exists.
    pub fn append(&self, event: &EventEnvelope) -> PyResult<()> {
        let guard = self.conn()?;
        let conn = guard.as_ref().ok_or_else(|| PyRuntimeError::new_err("Event store is closed"))?;

        let result = conn.execute(
            "INSERT INTO events (message_id, message_type, schema_version, occurred_at,
             correlation_id, causation_id, aggregate_type, aggregate_id, source, payload, metadata)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11)",
            rusqlite::params![
                event.message_id,
                event.message_type,
                event.schema_version,
                event.occurred_at,
                event.correlation_id,
                event.causation_id,
                event.aggregate_type,
                event.aggregate_id,
                event.source,
                event.payload,
                event.metadata,
            ],
        );

        match result {
            Ok(_) => Ok(()),
            Err(e) => {
                if e.to_string().contains("UNIQUE constraint") {
                    Err(pyo3::exceptions::PyValueError::new_err(format!(
                        "Duplicate message_id: {}",
                        event.message_id
                    )))
                } else {
                    Err(PyRuntimeError::new_err(format!("Failed to append event: {}", e)))
                }
            }
        }
    }

    /// Replay events for an aggregate, in occurred_at order.
    pub fn replay_aggregate(
        &self,
        aggregate_type: &str,
        aggregate_id: &str,
    ) -> PyResult<Vec<EventEnvelope>> {
        let guard = self.conn()?;
        let conn = guard.as_ref().ok_or_else(|| PyRuntimeError::new_err("Event store is closed"))?;

        let mut stmt = conn
            .prepare(
                "SELECT message_id, message_type, schema_version, occurred_at,
                 correlation_id, causation_id, aggregate_type, aggregate_id,
                 source, payload, metadata
                 FROM events
                 WHERE aggregate_type = ?1 AND aggregate_id = ?2
                 ORDER BY occurred_at ASC, message_id ASC",
            )
            .map_err(|e| PyRuntimeError::new_err(format!("Prepare error: {}", e)))?;

        let events = stmt
            .query_map(rusqlite::params![aggregate_type, aggregate_id], |row| {
                Ok(EventEnvelope {
                    message_id: row.get(0)?,
                    message_type: row.get(1)?,
                    schema_version: row.get(2)?,
                    occurred_at: row.get(3)?,
                    correlation_id: row.get(4)?,
                    causation_id: row.get(5)?,
                    aggregate_type: row.get(6)?,
                    aggregate_id: row.get(7)?,
                    source: row.get(8)?,
                    payload: row.get(9)?,
                    metadata: row.get(10)?,
                })
            })
            .map_err(|e| PyRuntimeError::new_err(format!("Query error: {}", e)))?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| PyRuntimeError::new_err(format!("Row error: {}", e)))?;

        Ok(events)
    }

    /// Replay all events of a given type in time order.
    pub fn replay_by_type(&self, message_type: &str) -> PyResult<Vec<EventEnvelope>> {
        let guard = self.conn()?;
        let conn = guard.as_ref().ok_or_else(|| PyRuntimeError::new_err("Event store is closed"))?;

        let mut stmt = conn
            .prepare(
                "SELECT message_id, message_type, schema_version, occurred_at,
                 correlation_id, causation_id, aggregate_type, aggregate_id,
                 source, payload, metadata
                 FROM events
                 WHERE message_type = ?1
                 ORDER BY occurred_at ASC",
            )
            .map_err(|e| PyRuntimeError::new_err(format!("Prepare error: {}", e)))?;

        let events = stmt
            .query_map(rusqlite::params![message_type], |row| {
                Ok(EventEnvelope {
                    message_id: row.get(0)?,
                    message_type: row.get(1)?,
                    schema_version: row.get(2)?,
                    occurred_at: row.get(3)?,
                    correlation_id: row.get(4)?,
                    causation_id: row.get(5)?,
                    aggregate_type: row.get(6)?,
                    aggregate_id: row.get(7)?,
                    source: row.get(8)?,
                    payload: row.get(9)?,
                    metadata: row.get(10)?,
                })
            })
            .map_err(|e| PyRuntimeError::new_err(format!("Query error: {}", e)))?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| PyRuntimeError::new_err(format!("Row error: {}", e)))?;

        Ok(events)
    }

    /// Replay all events in time order.
    pub fn replay_all(&self) -> PyResult<Vec<EventEnvelope>> {
        let guard = self.conn()?;
        let conn = guard.as_ref().ok_or_else(|| PyRuntimeError::new_err("Event store is closed"))?;

        let mut stmt = conn
            .prepare(
                "SELECT message_id, message_type, schema_version, occurred_at,
                 correlation_id, causation_id, aggregate_type, aggregate_id,
                 source, payload, metadata
                 FROM events
                 ORDER BY occurred_at ASC, message_id ASC",
            )
            .map_err(|e| PyRuntimeError::new_err(format!("Prepare error: {}", e)))?;

        let events = stmt
            .query_map([], |row| {
                Ok(EventEnvelope {
                    message_id: row.get(0)?,
                    message_type: row.get(1)?,
                    schema_version: row.get(2)?,
                    occurred_at: row.get(3)?,
                    correlation_id: row.get(4)?,
                    causation_id: row.get(5)?,
                    aggregate_type: row.get(6)?,
                    aggregate_id: row.get(7)?,
                    source: row.get(8)?,
                    payload: row.get(9)?,
                    metadata: row.get(10)?,
                })
            })
            .map_err(|e| PyRuntimeError::new_err(format!("Query error: {}", e)))?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| PyRuntimeError::new_err(format!("Row error: {}", e)))?;

        Ok(events)
    }

    /// Get event count.
    pub fn count(&self) -> PyResult<u64> {
        let guard = self.conn()?;
        let conn = guard.as_ref().ok_or_else(|| PyRuntimeError::new_err("Event store is closed"))?;

        let count: u64 = conn
            .query_row("SELECT COUNT(*) FROM events", [], |row| row.get(0))
            .map_err(|e| PyRuntimeError::new_err(format!("Query error: {}", e)))?;

        Ok(count)
            }
        }

        // ─── Tests ───────────────────────────────────────────────────────────────────────

        #[cfg(test)]
        mod tests {
            use super::*;

            fn make_event(msg_type: &str, agg_type: &str, agg_id: &str) -> EventEnvelope {
                EventEnvelope::new(
                    msg_type.to_string(),
                    agg_type.to_string(),
                    agg_id.to_string(),
                    "test".to_string(),
                    r#"{"key":"value"}"#.to_string(),
                    None, None, None,
                )
            }

            #[test]
            fn test_empty_store_count() {
                let store = EventStore::new(":memory:").unwrap();
                assert_eq!(store.count().unwrap(), 0);
            }

            #[test]
            fn test_append_and_count() {
                let store = EventStore::new(":memory:").unwrap();
                let event = make_event("OrderSubmitted", "Order", "ord-1");
                store.append(&event).unwrap();
                assert_eq!(store.count().unwrap(), 1);
            }

            #[test]
            fn test_replay_all_empty() {
                let store = EventStore::new(":memory:").unwrap();
                let events = store.replay_all().unwrap();
                assert!(events.is_empty());
            }

            #[test]
            fn test_replay_all_returns_all() {
                let store = EventStore::new(":memory:").unwrap();
                store.append(&make_event("A", "Order", "1")).unwrap();
                store.append(&make_event("B", "Order", "1")).unwrap();
                store.append(&make_event("C", "Trade", "2")).unwrap();
                let events = store.replay_all().unwrap();
                assert_eq!(events.len(), 3);
            }

            #[test]
            fn test_replay_aggregate() {
                let store = EventStore::new(":memory:").unwrap();
                store.append(&make_event("Created", "Order", "ord-1")).unwrap();
                store.append(&make_event("Filled", "Order", "ord-1")).unwrap();
                store.append(&make_event("Created", "Order", "ord-2")).unwrap();

                let events = store.replay_aggregate("Order", "ord-1").unwrap();
                assert_eq!(events.len(), 2);
                assert_eq!(events[0].message_type, "Created");
                assert_eq!(events[1].message_type, "Filled");
            }

            #[test]
            fn test_replay_by_type() {
                let store = EventStore::new(":memory:").unwrap();
                store.append(&make_event("OrderSubmitted", "Order", "1")).unwrap();
                store.append(&make_event("TradeExecuted", "Trade", "2")).unwrap();
                store.append(&make_event("OrderSubmitted", "Order", "3")).unwrap();

                let events = store.replay_by_type("OrderSubmitted").unwrap();
                assert_eq!(events.len(), 2);
            }

            #[test]
            fn test_duplicate_message_id_rejected() {
                Python::initialize();
                let store = EventStore::new(":memory:").unwrap();
                let event = make_event("Test", "TestAgg", "agg-1");
                store.append(&event).unwrap();
                let result = store.append(&event);
                assert!(result.is_err());
                let err = result.unwrap_err();
                assert!(err.to_string().contains("Duplicate"), "expected Duplicate error, got: {}", err);
            }

            #[test]
            fn test_close_then_append_fails() {
                Python::initialize();
                let store = EventStore::new(":memory:").unwrap();
                store.close().unwrap();
                let event = make_event("Test", "TestAgg", "agg-1");
                let result = store.append(&event);
                assert!(result.is_err());
                assert!(result.unwrap_err().to_string().contains("closed"));
            }

            #[test]
            fn test_multiple_aggregates_independent() {
                let store = EventStore::new(":memory:").unwrap();
                store.append(&make_event("Buy", "Order", "AAPL")).unwrap();
                store.append(&make_event("Sell", "Order", "MSFT")).unwrap();
                store.append(&make_event("Buy", "Order", "AAPL")).unwrap();

                let aapl_events = store.replay_aggregate("Order", "AAPL").unwrap();
                assert_eq!(aapl_events.len(), 2);

                let msft_events = store.replay_aggregate("Order", "MSFT").unwrap();
                assert_eq!(msft_events.len(), 1);
            }

            #[test]
            fn test_causation_and_correlation_ids() {
                let store = EventStore::new(":memory:").unwrap();
                let event = EventEnvelope::new(
                    "Child".to_string(),
                    "Order".to_string(),
                    "ord-1".to_string(),
                    "test".to_string(),
                    "{}".to_string(),
                    Some("corr-1".to_string()),
                    Some("parent-1".to_string()),
                    Some(r#"{"source":"pytest"}"#.to_string()),
                );
                store.append(&event).unwrap();
                let events = store.replay_all().unwrap();
                assert_eq!(events.len(), 1);
                assert_eq!(events[0].correlation_id, "corr-1");
                assert_eq!(events[0].causation_id, Some("parent-1".to_string()));
                assert_eq!(events[0].metadata, Some(r#"{"source":"pytest"}"#.to_string()));
            }
        }
