import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Use jsdom for DOM testing
    environment: 'jsdom',
    
    // Enable global test functions (describe, it, expect, etc.)
    globals: true,
    
    // Test file patterns
    include: ['tests/**/*.test.js'],
    
    // Setup files to run before tests
    setupFiles: ['tests/setup.js'],
    
    // Coverage configuration
    coverage: {
      provider: 'v8',
      reporter: ['text', 'text-summary', 'html'],
      exclude: [
        'node_modules/',
        'tests/',
        'static/js/game.js', // Original monolithic file
        'static/js/game-modular.js' // Entry point loader
      ],
      // Aim for high coverage on our modules
      thresholds: {
        global: {
          branches: 70,
          functions: 80,
          lines: 80,
          statements: 80
        }
      }
    },
    
    // Mock configuration
    clearMocks: true,
    restoreMocks: true,
    
    // Timeout for async tests
    testTimeout: 5000
  }
});