import { describe, it, expect, beforeEach, vi } from 'vitest';
import { createMockGameState, createMockPlayer, createMockRoomData } from '../helpers/testUtils.js';

// Since we're testing ES6 modules, we need to import them properly
// We'll need to adjust the import path based on the actual file structure
const GameStateManager = (await import('../../static/js/modules/GameStateManager.js')).default || 
                         (await import('../../static/js/modules/GameStateManager.js')).GameStateManager;

describe('GameStateManager', () => {
  let gameStateManager;

  beforeEach(() => {
    gameStateManager = new GameStateManager();
  });

  describe('Initialization', () => {
    it('should initialize with default state', () => {
      expect(gameStateManager.gameState).toBe(null);
      expect(gameStateManager.players).toEqual([]);
      expect(gameStateManager.roomInfo.roomId).toBe(null);
      expect(gameStateManager.roomInfo.playerId).toBe(null);
      expect(gameStateManager.roomInfo.playerName).toBe(null);
      expect(gameStateManager.hasSubmittedResponse).toBe(false);
      expect(gameStateManager.hasSubmittedGuess).toBe(false);
      expect(gameStateManager.submittedResponseText).toBe(null);
    });

    it('should initialize with provided room data', () => {
      const roomId = 'test-room-123';
      const playerId = 'player-456';
      const playerName = 'TestPlayer';

      gameStateManager.initialize(roomId, playerId, playerName);

      expect(gameStateManager.roomInfo.roomId).toBe(roomId);
      expect(gameStateManager.roomInfo.playerId).toBe(playerId);
      expect(gameStateManager.roomInfo.playerName).toBe(playerName);
    });
  });

  describe('Room Management', () => {
    it('should update room info after joining', () => {
      const roomData = createMockRoomData({
        room_id: 'joined-room',
        player_id: 'new-player-id',
        player_name: 'JoinedPlayer'
      });

      gameStateManager.updateAfterRoomJoin(roomData);

      expect(gameStateManager.roomInfo.roomId).toBe('joined-room');
      expect(gameStateManager.roomInfo.playerId).toBe('new-player-id');
      expect(gameStateManager.roomInfo.playerName).toBe('JoinedPlayer');
    });

    it('should call room info update callback', () => {
      const callback = vi.fn();
      gameStateManager.onRoomInfoUpdate = callback;

      const roomData = createMockRoomData();
      gameStateManager.updateAfterRoomJoin(roomData);

      expect(callback).toHaveBeenCalledWith(gameStateManager.roomInfo);
    });
  });

  describe('Player Management', () => {
    it('should update players list', () => {
      const players = [
        createMockPlayer({ name: 'Player1', player_id: 'p1' }),
        createMockPlayer({ name: 'Player2', player_id: 'p2' })
      ];

      gameStateManager.updatePlayers(players);

      expect(gameStateManager.players).toEqual(players);
    });

    it('should call players update callback', () => {
      const callback = vi.fn();
      gameStateManager.onPlayersUpdate = callback;

      const players = [createMockPlayer()];
      gameStateManager.updatePlayers(players);

      expect(callback).toHaveBeenCalledWith(players);
    });

    it('should update player count', () => {
      gameStateManager.updatePlayerCount(5, 8);

      expect(gameStateManager.roomInfo.connectedCount).toBe(5);
      expect(gameStateManager.roomInfo.totalCount).toBe(8);
    });

    it('should find player by ID', () => {
      const players = [
        createMockPlayer({ name: 'Player1', player_id: 'p1' }),
        createMockPlayer({ name: 'Player2', player_id: 'p2' })
      ];
      
      gameStateManager.updatePlayers(players);
      
      const foundPlayer = gameStateManager.getPlayer('p2');
      expect(foundPlayer).toEqual(players[1]);
      
      const notFoundPlayer = gameStateManager.getPlayer('p3');
      expect(notFoundPlayer).toBe(null);
    });

    it('should get current player', () => {
      // Set up current player ID
      gameStateManager.roomInfo.playerId = 'current-player';
      
      const players = [
        createMockPlayer({ name: 'Other', player_id: 'other-player' }),
        createMockPlayer({ name: 'Current', player_id: 'current-player' })
      ];
      
      gameStateManager.updatePlayers(players);
      
      const currentPlayer = gameStateManager.getCurrentPlayer();
      expect(currentPlayer).toEqual(players[1]);
    });

    it('should return null for current player when not found', () => {
      gameStateManager.roomInfo.playerId = 'nonexistent';
      
      const currentPlayer = gameStateManager.getCurrentPlayer();
      expect(currentPlayer).toBe(null);
    });
  });

  describe('Game State Management', () => {
    it('should update complete game state', () => {
      const gameState = createMockGameState({
        phase: 'responding',
        round_number: 2
      });

      gameStateManager.updateGameState(gameState);

      expect(gameStateManager.gameState).toEqual(gameState);
    });

    it('should update room state with nested game state', () => {
      const roomState = {
        room_id: 'room-123',
        players: [createMockPlayer()],
        connected_count: 1,
        total_count: 2,
        game_state: createMockGameState({ phase: 'guessing' })
      };

      gameStateManager.updateRoomState(roomState);

      expect(gameStateManager.gameState).toEqual(roomState.game_state);
      expect(gameStateManager.players).toEqual(roomState.players);
      expect(gameStateManager.roomInfo.connectedCount).toBe(1);
      expect(gameStateManager.roomInfo.totalCount).toBe(2);
    });

    it('should call state change callback', () => {
      const callback = vi.fn();
      gameStateManager.onStateChange = callback;

      const gameState = createMockGameState();
      gameStateManager.updateGameState(gameState);

      expect(callback).toHaveBeenCalledWith({
        gameState,
        players: gameStateManager.players,
        roomInfo: gameStateManager.roomInfo,
        roundsCompleted: gameStateManager.roundsCompleted,
        hasSubmittedResponse: gameStateManager.hasSubmittedResponse,
        hasSubmittedGuess: gameStateManager.hasSubmittedGuess
      });
    });
  });

  describe('Submission Tracking', () => {
    it('should mark response as submitted', () => {
      const responseText = 'My test response';
      
      gameStateManager.markResponseSubmitted(responseText);

      expect(gameStateManager.hasSubmittedResponse).toBe(true);
      expect(gameStateManager.submittedResponseText).toBe(responseText);
    });

    it('should mark response as submitted without text', () => {
      gameStateManager.markResponseSubmitted();

      expect(gameStateManager.hasSubmittedResponse).toBe(true);
      expect(gameStateManager.submittedResponseText).toBe(null);
    });

    it('should trim response text when marking as submitted', () => {
      gameStateManager.markResponseSubmitted('  My response  ');

      expect(gameStateManager.submittedResponseText).toBe('My response');
    });

    it('should mark guess as submitted', () => {
      gameStateManager.markGuessSubmitted();

      expect(gameStateManager.hasSubmittedGuess).toBe(true);
    });

    it('should reset submission flags', () => {
      // Set up submitted state
      gameStateManager.markResponseSubmitted('test response');
      gameStateManager.markGuessSubmitted();

      // Reset
      gameStateManager.resetSubmissionFlags();

      expect(gameStateManager.hasSubmittedResponse).toBe(false);
      expect(gameStateManager.hasSubmittedGuess).toBe(false);
      expect(gameStateManager.submittedResponseText).toBe(null);
    });
  });

  describe('Validation Methods', () => {
    it('should allow response submission in responding phase', () => {
      gameStateManager.gameState = createMockGameState({ phase: 'responding' });
      gameStateManager.hasSubmittedResponse = false;

      expect(gameStateManager.canSubmitResponse()).toBe(true);
    });

    it('should not allow response submission if already submitted', () => {
      gameStateManager.gameState = createMockGameState({ phase: 'responding' });
      gameStateManager.hasSubmittedResponse = true;

      expect(gameStateManager.canSubmitResponse()).toBe(false);
    });

    it('should not allow response submission in wrong phase', () => {
      gameStateManager.gameState = createMockGameState({ phase: 'guessing' });
      gameStateManager.hasSubmittedResponse = false;

      expect(gameStateManager.canSubmitResponse()).toBe(false);
    });

    it('should allow guess submission in guessing phase', () => {
      gameStateManager.gameState = createMockGameState({ phase: 'guessing' });
      gameStateManager.hasSubmittedGuess = false;

      expect(gameStateManager.canSubmitGuess()).toBe(true);
    });

    it('should not allow guess submission if already submitted', () => {
      gameStateManager.gameState = createMockGameState({ phase: 'guessing' });
      gameStateManager.hasSubmittedGuess = true;

      expect(gameStateManager.canSubmitGuess()).toBe(false);
    });

    it('should allow round start with enough players', () => {
      gameStateManager.gameState = createMockGameState({ phase: 'waiting' });
      gameStateManager.roomInfo.connectedCount = 3;

      expect(gameStateManager.canStartRound()).toBe(true);
    });

    it('should not allow round start with insufficient players', () => {
      gameStateManager.gameState = createMockGameState({ phase: 'waiting' });
      gameStateManager.roomInfo.connectedCount = 1;

      expect(gameStateManager.canStartRound()).toBe(false);
    });

    it('should not allow round start in wrong phase', () => {
      gameStateManager.gameState = createMockGameState({ phase: 'responding' });
      gameStateManager.roomInfo.connectedCount = 3;

      expect(gameStateManager.canStartRound()).toBe(false);
    });
  });

  describe('State Retrieval', () => {
    it('should return complete state object', () => {
      const gameState = createMockGameState({ phase: 'results' });
      const players = [createMockPlayer()];
      
      gameStateManager.gameState = gameState;
      gameStateManager.players = players;
      gameStateManager.roundsCompleted = 5;
      gameStateManager.hasSubmittedResponse = true;

      const state = gameStateManager.getState();

      expect(state).toEqual({
        gameState,
        players,
        roomInfo: gameStateManager.roomInfo,
        roundsCompleted: 5,
        hasSubmittedResponse: true,
        hasSubmittedGuess: false
      });
    });

    it('should get current phase', () => {
      gameStateManager.gameState = createMockGameState({ phase: 'guessing' });

      expect(gameStateManager.getCurrentPhase()).toBe('guessing');
    });

    it('should return null for current phase when no game state', () => {
      expect(gameStateManager.getCurrentPhase()).toBe(null);
    });
  });

  describe('Edge Cases', () => {
    it('should handle null game state gracefully', () => {
      expect(() => gameStateManager.canSubmitResponse()).not.toThrow();
      expect(() => gameStateManager.canSubmitGuess()).not.toThrow();
      expect(() => gameStateManager.canStartRound()).not.toThrow();
    });

    it('should handle empty players array', () => {
      gameStateManager.updatePlayers([]);
      
      expect(gameStateManager.players).toEqual([]);
      expect(gameStateManager.getPlayer('any-id')).toBe(null);
      expect(gameStateManager.getCurrentPlayer()).toBe(null);
    });

    it('should handle callback being null', () => {
      gameStateManager.onStateChange = null;
      gameStateManager.onPlayersUpdate = null;
      gameStateManager.onRoomInfoUpdate = null;

      expect(() => {
        gameStateManager.updateGameState(createMockGameState());
        gameStateManager.updatePlayers([createMockPlayer()]);
        gameStateManager.updateAfterRoomJoin(createMockRoomData());
      }).not.toThrow();
    });
  });
});