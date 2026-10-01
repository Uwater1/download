# Historical gap reporting

The previous report treated all naive timestamps as UTC and used approximate weekday/session rules. It did not account for exchange holidays or early closes and is no longer reliable after the timezone-aware migration.

Use `history/migration_manifest.json` for source inventory, timezone decisions, output row counts, and SHA-256 verification. All historical observations are retained; the migration does not filter or fabricate missing bars. A complete asset-specific market-calendar gap analysis is not implemented.
