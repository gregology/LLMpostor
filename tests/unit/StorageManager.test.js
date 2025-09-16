/**
 * StorageManager Tests
 *
 * Tests for browser storage management functionality including:
 * - localStorage availability detection
 * - Room session data persistence
 * - Data validation and sanitization
 * - Error handling and graceful degradation
 * - Storage quota handling
 * - Session data cleanup and management
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import StorageManager from '../../static/js/utils/StorageManager.js';

describe('StorageManager', () => {
  let storageManager;
  let mockLocalStorage;
  let mockConsole;
  let originalLocalStorage;

  beforeEach(() => {
    // Mock console methods
    mockConsole = {
      log: vi.fn(),
      warn: vi.fn(),
      error: vi.fn()
    };
    vi.stubGlobal('console', mockConsole);

    // Create localStorage mock
    mockLocalStorage = {
      data: new Map(),
      getItem: vi.fn((key) => mockLocalStorage.data.get(key) || null),
      setItem: vi.fn((key, value) => mockLocalStorage.data.set(key, value)),
      removeItem: vi.fn((key) => mockLocalStorage.data.delete(key)),
      clear: vi.fn(() => mockLocalStorage.data.clear())
    };

    // Store original and mock localStorage
    originalLocalStorage = global.localStorage;
    vi.stubGlobal('localStorage', mockLocalStorage);

    // Import a fresh instance - using default export singleton
    storageManager = StorageManager;
  });

  afterEach(() => {
    // Clean up localStorage mock
    mockLocalStorage.data.clear();

    // Restore original localStorage
    global.localStorage = originalLocalStorage;

    vi.restoreAllMocks();
  });

  describe('Initialization and Storage Availability', () => {
    it('should initialize with localStorage available', () => {
      expect(storageManager.isStorageAvailable()).toBe(true);
      expect(storageManager.isAvailable).toBe(true);
    });

    it('should detect when localStorage is not available', () => {
      // Mock localStorage to throw on access
      mockLocalStorage.setItem.mockImplementation(() => {
        throw new Error('localStorage not available');
      });

      // Create new manager instance to test availability check
      const testManager = new (StorageManager.constructor)();

      expect(testManager.isStorageAvailable()).toBe(false);
      expect(mockConsole.warn).toHaveBeenCalledWith('StorageManager: localStorage not available, persistence disabled');
    });

    it('should use correct storage key constant', () => {
      expect(storageManager.STORAGE_KEY).toBe('llmpostor_room_session');
    });

    it('should test localStorage functionality during availability check', () => {
      // Create new manager to trigger availability check
      new (StorageManager.constructor)();

      expect(mockLocalStorage.setItem).toHaveBeenCalledWith('__storage_test__', 'test');
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('__storage_test__');
    });
  });

  describe('Save Room Session', () => {
    it('should save valid room session data successfully', () => {
      const roomId = 'ROOM123';
      const playerId = 'player-456';
      const playerName = 'TestPlayer';

      const result = storageManager.saveRoomSession(roomId, playerId, playerName);

      expect(result).toBe(true);
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
        'llmpostor_room_session',
        expect.stringContaining(roomId)
      );
      expect(mockConsole.log).toHaveBeenCalledWith(
        `StorageManager: Saved session for ${playerName} in room ${roomId}`
      );
    });

    it('should trim whitespace from session data', () => {
      const result = storageManager.saveRoomSession('  ROOM123  ', '  player-456  ', '  TestPlayer  ');

      expect(result).toBe(true);

      // Verify stored data is trimmed
      const storedData = JSON.parse(mockLocalStorage.data.get('llmpostor_room_session'));
      expect(storedData.roomId).toBe('ROOM123');
      expect(storedData.playerId).toBe('player-456');
      expect(storedData.playerName).toBe('TestPlayer');
    });

    it('should include timestamp in saved session data', () => {
      const beforeSave = Date.now();
      storageManager.saveRoomSession('ROOM123', 'player-456', 'TestPlayer');
      const afterSave = Date.now();

      const storedData = JSON.parse(mockLocalStorage.data.get('llmpostor_room_session'));
      expect(storedData.timestamp).toBeGreaterThanOrEqual(beforeSave);
      expect(storedData.timestamp).toBeLessThanOrEqual(afterSave);
    });

    it('should convert parameters to strings', () => {
      // Pass non-string values
      storageManager.saveRoomSession(123, 456, 789);

      const storedData = JSON.parse(mockLocalStorage.data.get('llmpostor_room_session'));
      expect(storedData.roomId).toBe('123');
      expect(storedData.playerId).toBe('456');
      expect(storedData.playerName).toBe('789');
    });

    it('should return false for incomplete session data', () => {
      expect(storageManager.saveRoomSession('', 'player', 'name')).toBe(false);
      expect(storageManager.saveRoomSession('room', '', 'name')).toBe(false);
      expect(storageManager.saveRoomSession('room', 'player', '')).toBe(false);
      expect(storageManager.saveRoomSession(null, 'player', 'name')).toBe(false);
      expect(storageManager.saveRoomSession('room', null, 'name')).toBe(false);
      expect(storageManager.saveRoomSession('room', 'player', null)).toBe(false);

      expect(mockConsole.warn).toHaveBeenCalledWith('StorageManager: Cannot save incomplete session data');
      expect(mockLocalStorage.setItem).not.toHaveBeenCalled();
    });

    it('should return false when localStorage is not available', () => {
      // Create manager with unavailable storage by mocking the availability check
      const unavailableManager = new (StorageManager.constructor)();
      unavailableManager.isAvailable = false;

      // Clear the mock calls from constructor's availability check
      mockLocalStorage.setItem.mockClear();

      const result = unavailableManager.saveRoomSession('room', 'player', 'name');

      expect(result).toBe(false);
      expect(mockLocalStorage.setItem).not.toHaveBeenCalled();
    });

    it('should handle localStorage errors gracefully', () => {
      mockLocalStorage.setItem.mockImplementation(() => {
        throw new Error('Storage quota exceeded');
      });

      const result = storageManager.saveRoomSession('ROOM123', 'player-456', 'TestPlayer');

      expect(result).toBe(false);
      expect(mockConsole.error).toHaveBeenCalledWith(
        'StorageManager: Failed to save session data:',
        expect.any(Error)
      );
    });
  });

  describe('Get Room Session', () => {
    beforeEach(() => {
      // Set up valid session data
      const sessionData = {
        roomId: 'ROOM123',
        playerId: 'player-456',
        playerName: 'TestPlayer',
        timestamp: Date.now()
      };
      mockLocalStorage.data.set('llmpostor_room_session', JSON.stringify(sessionData));
    });

    it('should retrieve valid session data successfully', () => {
      const session = storageManager.getRoomSession();

      expect(session).toEqual({
        roomId: 'ROOM123',
        playerId: 'player-456',
        playerName: 'TestPlayer'
      });
      expect(mockConsole.log).toHaveBeenCalledWith(
        'StorageManager: Retrieved session for TestPlayer in room ROOM123'
      );
    });

    it('should return null when no session data exists', () => {
      mockLocalStorage.data.clear();

      const session = storageManager.getRoomSession();

      expect(session).toBeNull();
    });

    it('should return null when localStorage is not available', () => {
      const unavailableManager = new (StorageManager.constructor)();
      unavailableManager.isAvailable = false;

      const session = unavailableManager.getRoomSession();

      expect(session).toBeNull();
    });

    it('should handle invalid JSON gracefully', () => {
      mockLocalStorage.data.set('llmpostor_room_session', 'invalid-json');

      const session = storageManager.getRoomSession();

      expect(session).toBeNull();
      expect(mockConsole.error).toHaveBeenCalledWith(
        'StorageManager: Failed to retrieve session data:',
        expect.any(Error)
      );
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('llmpostor_room_session');
    });

    it('should validate session data structure and clear invalid data', () => {
      // Set invalid session data (missing required fields)
      const invalidData = {
        roomId: 'ROOM123',
        // missing playerId and playerName
        timestamp: Date.now()
      };
      mockLocalStorage.data.set('llmpostor_room_session', JSON.stringify(invalidData));

      const session = storageManager.getRoomSession();

      expect(session).toBeNull();
      expect(mockConsole.warn).toHaveBeenCalledWith('StorageManager: Invalid session data found, removing');
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('llmpostor_room_session');
    });

    it('should handle localStorage errors during retrieval', () => {
      mockLocalStorage.getItem.mockImplementation(() => {
        throw new Error('localStorage access denied');
      });

      const session = storageManager.getRoomSession();

      expect(session).toBeNull();
      expect(mockConsole.error).toHaveBeenCalledWith(
        'StorageManager: Failed to retrieve session data:',
        expect.any(Error)
      );
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('llmpostor_room_session');
    });
  });

  describe('Has Room Session', () => {
    it('should return true when valid session exists', () => {
      const sessionData = {
        roomId: 'ROOM123',
        playerId: 'player-456',
        playerName: 'TestPlayer',
        timestamp: Date.now()
      };
      mockLocalStorage.data.set('llmpostor_room_session', JSON.stringify(sessionData));

      expect(storageManager.hasRoomSession()).toBe(true);
    });

    it('should return false when no session exists', () => {
      mockLocalStorage.data.clear();

      expect(storageManager.hasRoomSession()).toBe(false);
    });

    it('should return false when session data is invalid', () => {
      const invalidData = { roomId: 'ROOM123' }; // missing required fields
      mockLocalStorage.data.set('llmpostor_room_session', JSON.stringify(invalidData));

      expect(storageManager.hasRoomSession()).toBe(false);
    });
  });

  describe('Clear Room Session', () => {
    beforeEach(() => {
      // Set up session data to clear
      const sessionData = {
        roomId: 'ROOM123',
        playerId: 'player-456',
        playerName: 'TestPlayer',
        timestamp: Date.now()
      };
      mockLocalStorage.data.set('llmpostor_room_session', JSON.stringify(sessionData));
    });

    it('should clear session data successfully', () => {
      const result = storageManager.clearRoomSession();

      expect(result).toBe(true);
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('llmpostor_room_session');
      expect(mockConsole.log).toHaveBeenCalledWith('StorageManager: Cleared room session');
    });

    it('should return false when localStorage is not available', () => {
      const unavailableManager = new (StorageManager.constructor)();
      unavailableManager.isAvailable = false;

      // Clear the mock calls from constructor's availability check
      mockLocalStorage.removeItem.mockClear();

      const result = unavailableManager.clearRoomSession();

      expect(result).toBe(false);
      expect(mockLocalStorage.removeItem).not.toHaveBeenCalled();
    });

    it('should handle localStorage errors gracefully', () => {
      mockLocalStorage.removeItem.mockImplementation(() => {
        throw new Error('localStorage error');
      });

      const result = storageManager.clearRoomSession();

      expect(result).toBe(false);
      expect(mockConsole.error).toHaveBeenCalledWith(
        'StorageManager: Failed to clear session data:',
        expect.any(Error)
      );
    });
  });

  describe('Update Player Name', () => {
    beforeEach(() => {
      // Set up existing session data
      const sessionData = {
        roomId: 'ROOM123',
        playerId: 'player-456',
        playerName: 'OldName',
        timestamp: Date.now()
      };
      mockLocalStorage.data.set('llmpostor_room_session', JSON.stringify(sessionData));
    });

    it('should update player name in existing session', () => {
      const result = storageManager.updatePlayerName('NewName');

      expect(result).toBe(true);

      // Verify updated data
      const session = storageManager.getRoomSession();
      expect(session.playerName).toBe('NewName');
      expect(session.roomId).toBe('ROOM123');
      expect(session.playerId).toBe('player-456');
    });

    it('should return false when no existing session', () => {
      mockLocalStorage.data.clear();

      const result = storageManager.updatePlayerName('NewName');

      expect(result).toBe(false);
    });

    it('should handle invalid new player names', () => {
      const result = storageManager.updatePlayerName('');

      expect(result).toBe(false);
    });
  });

  describe('Session Data Validation', () => {
    describe('Valid Session Data', () => {
      it('should validate complete session data', () => {
        const validData = {
          roomId: 'ROOM123',
          playerId: 'player-456',
          playerName: 'TestPlayer',
          timestamp: Date.now()
        };

        expect(storageManager._isValidSessionData(validData)).toBe(true);
      });

      it('should accept session data with extra properties', () => {
        const dataWithExtras = {
          roomId: 'ROOM123',
          playerId: 'player-456',
          playerName: 'TestPlayer',
          timestamp: Date.now(),
          extra: 'property'
        };

        expect(storageManager._isValidSessionData(dataWithExtras)).toBe(true);
      });
    });

    describe('Invalid Session Data', () => {
      it('should reject null or undefined data', () => {
        expect(storageManager._isValidSessionData(null)).toBe(false);
        expect(storageManager._isValidSessionData(undefined)).toBe(false);
      });

      it('should reject non-object data', () => {
        expect(storageManager._isValidSessionData('string')).toBe(false);
        expect(storageManager._isValidSessionData(123)).toBe(false);
        expect(storageManager._isValidSessionData([])).toBe(false);
      });

      it('should reject data missing required fields', () => {
        expect(storageManager._isValidSessionData({})).toBe(false);
        expect(storageManager._isValidSessionData({ roomId: 'ROOM123' })).toBe(false);
        expect(storageManager._isValidSessionData({
          roomId: 'ROOM123',
          playerId: 'player-456'
        })).toBe(false);
      });

      it('should reject data with empty string values', () => {
        const dataWithEmptyStrings = {
          roomId: '',
          playerId: 'player-456',
          playerName: 'TestPlayer'
        };

        expect(storageManager._isValidSessionData(dataWithEmptyStrings)).toBe(false);
      });

      it('should reject data with whitespace-only values', () => {
        const dataWithWhitespace = {
          roomId: '   ',
          playerId: 'player-456',
          playerName: 'TestPlayer'
        };

        expect(storageManager._isValidSessionData(dataWithWhitespace)).toBe(false);
      });

      it('should reject data with non-string values', () => {
        const dataWithNumbers = {
          roomId: 123,
          playerId: 'player-456',
          playerName: 'TestPlayer'
        };

        expect(storageManager._isValidSessionData(dataWithNumbers)).toBe(false);
      });

      it('should reject data with excessive string lengths', () => {
        const longString51 = 'a'.repeat(51);
        const longString101 = 'a'.repeat(101);

        // Room ID too long (>50 chars)
        expect(storageManager._isValidSessionData({
          roomId: longString51,
          playerId: 'player-456',
          playerName: 'TestPlayer'
        })).toBe(false);

        // Player ID too long (>50 chars)
        expect(storageManager._isValidSessionData({
          roomId: 'ROOM123',
          playerId: longString51,
          playerName: 'TestPlayer'
        })).toBe(false);

        // Player name too long (>100 chars)
        expect(storageManager._isValidSessionData({
          roomId: 'ROOM123',
          playerId: 'player-456',
          playerName: longString101
        })).toBe(false);
      });

      it('should accept data with maximum allowed string lengths', () => {
        const maxRoomId = 'a'.repeat(50);
        const maxPlayerId = 'a'.repeat(50);
        const maxPlayerName = 'a'.repeat(100);

        expect(storageManager._isValidSessionData({
          roomId: maxRoomId,
          playerId: maxPlayerId,
          playerName: maxPlayerName
        })).toBe(true);
      });
    });
  });

  describe('Error Scenarios and Edge Cases', () => {
    it('should handle storage quota exceeded errors', () => {
      mockLocalStorage.setItem.mockImplementation(() => {
        const error = new Error('QuotaExceededError');
        error.name = 'QuotaExceededError';
        throw error;
      });

      const result = storageManager.saveRoomSession('ROOM123', 'player-456', 'TestPlayer');

      expect(result).toBe(false);
      expect(mockConsole.error).toHaveBeenCalledWith(
        'StorageManager: Failed to save session data:',
        expect.objectContaining({ name: 'QuotaExceededError' })
      );
    });

    it('should handle DOM security errors', () => {
      mockLocalStorage.getItem.mockImplementation(() => {
        const error = new Error('Access denied');
        error.name = 'SecurityError';
        throw error;
      });

      const result = storageManager.getRoomSession();

      expect(result).toBeNull();
      expect(mockConsole.error).toHaveBeenCalledWith(
        'StorageManager: Failed to retrieve session data:',
        expect.objectContaining({ name: 'SecurityError' })
      );
    });

    it('should handle corrupted JSON data', () => {
      // Set partially corrupted JSON
      mockLocalStorage.data.set('llmpostor_room_session', '{"roomId":"ROOM123","playerId":');

      const result = storageManager.getRoomSession();

      expect(result).toBeNull();
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('llmpostor_room_session');
    });

    it('should handle localStorage being disabled mid-operation', () => {
      // Start with working localStorage
      storageManager.saveRoomSession('ROOM123', 'player-456', 'TestPlayer');

      // Then localStorage becomes unavailable
      mockLocalStorage.getItem.mockImplementation(() => {
        throw new Error('localStorage disabled');
      });

      const result = storageManager.getRoomSession();

      expect(result).toBeNull();
      expect(mockConsole.error).toHaveBeenCalled();
    });
  });

  describe('Integration Scenarios', () => {
    it('should handle complete session lifecycle', () => {
      // Save session
      expect(storageManager.saveRoomSession('ROOM123', 'player-456', 'TestPlayer')).toBe(true);

      // Check session exists
      expect(storageManager.hasRoomSession()).toBe(true);

      // Retrieve session
      const session = storageManager.getRoomSession();
      expect(session).toEqual({
        roomId: 'ROOM123',
        playerId: 'player-456',
        playerName: 'TestPlayer'
      });

      // Update player name
      expect(storageManager.updatePlayerName('UpdatedPlayer')).toBe(true);

      // Verify update
      const updatedSession = storageManager.getRoomSession();
      expect(updatedSession.playerName).toBe('UpdatedPlayer');

      // Clear session
      expect(storageManager.clearRoomSession()).toBe(true);

      // Verify cleared
      expect(storageManager.hasRoomSession()).toBe(false);
    });

    it('should handle session persistence across manager instances', () => {
      // Save with one instance
      storageManager.saveRoomSession('ROOM123', 'player-456', 'TestPlayer');

      // Create new manager instance (simulating page reload)
      const newManager = new (StorageManager.constructor)();

      // Should retrieve same session
      const session = newManager.getRoomSession();
      expect(session).toEqual({
        roomId: 'ROOM123',
        playerId: 'player-456',
        playerName: 'TestPlayer'
      });
    });

    it('should handle recovery from corrupted data', () => {
      // Start with corrupted data
      mockLocalStorage.data.set('llmpostor_room_session', 'corrupted-data');

      // Should clear corrupted data and return null
      expect(storageManager.getRoomSession()).toBeNull();
      expect(storageManager.hasRoomSession()).toBe(false);

      // Should be able to save new session after cleanup
      expect(storageManager.saveRoomSession('ROOM456', 'player-789', 'NewPlayer')).toBe(true);
      expect(storageManager.hasRoomSession()).toBe(true);
    });
  });

  describe('Singleton Behavior', () => {
    it('should maintain singleton instance across imports', () => {
      // The default export should be a singleton instance
      expect(StorageManager).toBeDefined();
      expect(typeof StorageManager.saveRoomSession).toBe('function');
      expect(StorageManager.STORAGE_KEY).toBe('llmpostor_room_session');
    });

    it('should preserve state across method calls', () => {
      // Save data
      StorageManager.saveRoomSession('PERSIST123', 'player-999', 'PersistentPlayer');

      // State should persist
      expect(StorageManager.hasRoomSession()).toBe(true);
      const session = StorageManager.getRoomSession();
      expect(session.roomId).toBe('PERSIST123');
    });
  });
});