# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Removed
- **Removed unused optional services** to reduce codebase complexity:
  - `MetricsService` - Performance monitoring and metrics collection service
  - `PayloadOptimizer` - Network payload compression and optimization service  
  - `DatabaseOptimizer` - In-memory data structure optimization service
- **Removed backwards compatibility layer** that created tech debt:
  - `ErrorHandler` class - Legacy wrapper that created new service instances on every call
  - Replaced with direct usage of `ValidationService` and `ErrorResponseFactory`
- **Removed associated configuration options**:
  - `enable_metrics` - Metrics service toggle
  - `enable_payload_optimizer` - Payload optimizer toggle
  - `enable_database_optimizer` - Database optimizer toggle
  - `metrics_max_data_points` - Metrics data point limit
  - `metrics_cleanup_max_age_seconds` - Metrics cleanup interval
  - `db_optimizer_max_cache_size` - Database optimizer cache size
  - `db_optimizer_default_ttl_seconds` - Database optimizer TTL
- **Cleaned up dead code**:
  - Legacy payload optimization comments and TODO items in `BroadcastService`
  - Unused logger imports in `RoomStatePresenter`
  - Redundant test files for deleted services

### Changed
- **Improved error handling architecture**:
  - Socket handlers now use `ValidationService` and `ErrorResponseFactory` directly
  - Moved `with_error_handling` decorator to `ErrorResponseFactory` module
  - BroadcastService updated to use `ErrorResponseFactory` instead of legacy wrapper
- **Simplified service container** by removing unused service registration logic
- **Updated dependency injection** to use proper services instead of compatibility layers
- **Updated tests** to reflect removal of optional services and ErrorHandler
- Service lifecycle tests now verify deleted services are no longer available

### Technical Details
This cleanup was part of **Phase 10** of the refactoring implementation plan, focused on:
- Dead code pruning and optional features hardening
- Removing dormant features that were disabled by default and unused in the runtime
- Reducing cognitive load and maintenance burden
- Simplifying the dependency injection container

### Impact
- **No functional changes** - All removed services were disabled by default and unused in the application runtime
- **Significant codebase reduction** - Removed ~2,000+ lines of unused code and backwards compatibility layers  
- **Improved performance** - Eliminated redundant service instantiation in ErrorHandler wrapper
- **Simplified architecture** - Services now use proper dependency injection instead of compatibility layers
- **Faster test suite** execution due to fewer service initialization tests
- **Cleaner codebase** with only actively used services and no tech debt from backwards compatibility