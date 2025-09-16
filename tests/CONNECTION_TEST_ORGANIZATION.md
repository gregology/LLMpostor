# Connection Test Organization

This document outlines the organization of connection-related tests after consolidation.

## Test File Structure

### Unit Tests (Isolated Component Testing)
- **`tests/unit/ConnectionReliability.test.js`** - Pure unit tests for ConnectionReliability utility class
  - Connection timeout algorithms
  - Heartbeat interval management
  - Recovery backoff calculations

- **`tests/unit/ConnectionMetrics.test.js`** - Pure unit tests for ConnectionMetrics data collection class
  - Downtime tracking logic
  - Latency recording and calculation
  - Metrics aggregation

### Integration Tests (Multi-Component Testing)
- **`tests/integration/ConnectionIntegration.test.js`** - Comprehensive connection integration scenarios
  - Socket.IO connection lifecycle and state management
  - Connection resilience, recovery, and retry mechanisms
  - Network status changes and connection quality monitoring
  - Real-time communication and event flow
  - End-to-end connection scenarios and error recovery
  - Integration of ConnectionReliability + ConnectionMetrics + Socket.IO

- **`tests/integration/BrowserReliability.test.js`** - Browser environment reliability (non-connection)
  - Tab suspension and resumption
  - Browser navigation and page lifecycle
  - DOM manipulation safety
  - Memory management
  - Local storage reliability
  - Mobile-specific scenarios
  - Cross-browser compatibility

## Clear Boundaries

- **Unit tests** focus on individual classes in isolation
- **Integration tests** focus on component interactions and end-to-end flows
- **Browser tests** focus on environment reliability, not connection logic
- **No overlap** between connection scenarios across files

## Usage Guidelines

- Add new connection utility tests → `ConnectionReliability.test.js` or `ConnectionMetrics.test.js`
- Add new connection integration scenarios → `ConnectionIntegration.test.js`
- Add new browser environment tests → `BrowserReliability.test.js`
- Connection-related integration always goes to `ConnectionIntegration.test.js`