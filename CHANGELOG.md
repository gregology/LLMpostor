# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Removed
- Removed unused optional services to reduce codebase complexity:
  - `MetricsService` - Performance monitoring and metrics collection service
  - `PayloadOptimizer` - Network payload compression and optimization service  
  - `DatabaseOptimizer` - In-memory data structure optimization service
- Removed associated configuration options:
  - `enable_metrics` - Metrics service toggle
  - `enable_payload_optimizer` - Payload optimizer toggle
  - `enable_database_optimizer` - Database optimizer toggle
  - `metrics_max_data_points` - Metrics data point limit
  - `metrics_cleanup_max_age_seconds` - Metrics cleanup interval
  - `db_optimizer_max_cache_size` - Database optimizer cache size
  - `db_optimizer_default_ttl_seconds` - Database optimizer TTL
- Cleaned up legacy payload optimization comments and TODO items in `BroadcastService`

### Changed
- Simplified service container by removing unused service registration logic
- Updated tests to reflect removal of optional services
- Service lifecycle tests now verify these services are no longer available

### Technical Details
This cleanup was part of **Phase 10** of the refactoring implementation plan, focused on:
- Dead code pruning and optional features hardening
- Removing dormant features that were disabled by default and unused in the runtime
- Reducing cognitive load and maintenance burden
- Simplifying the dependency injection container

### Impact
- **No functional changes** - All removed services were disabled by default and unused in the application runtime
- Reduced codebase size and complexity
- Simplified service configuration
- Faster test suite execution due to fewer service initialization tests
- Cleaner dependency injection container with only actively used services