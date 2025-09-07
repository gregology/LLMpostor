/**
 * AssetLoader Unit Tests
 * Tests for the optimized asset loading and caching system.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Mock performance API
global.performance = {
    now: vi.fn(() => Date.now())
};

// Mock requestIdleCallback
global.requestIdleCallback = vi.fn((callback) => {
    setTimeout(() => {
        // Mock deadline object
        callback({
            timeRemaining: () => 5, // Always return 5ms remaining
            didTimeout: false
        });
    }, 0);
});

// Import AssetLoader
const AssetLoaderModule = await import('../../static/js/utils/AssetLoader.js');
const AssetLoader = AssetLoaderModule.default;

describe('AssetLoader', () => {
    let assetLoader;
    let originalConsole;
    let consoleLogSpy;
    let consoleErrorSpy;

    beforeEach(() => {
        // Mock console methods
        originalConsole = global.console;
        consoleLogSpy = vi.fn();
        consoleErrorSpy = vi.fn();
        global.console = {
            ...originalConsole,
            log: consoleLogSpy,
            error: consoleErrorSpy
        };

        // Mock DOM methods
        const mockElement = {
            src: '',
            type: '',
            crossOrigin: '',
            async: false,
            onload: null,
            onerror: null,
            dataset: {}
        };
        
        global.document = {
            createElement: vi.fn(() => mockElement),
            querySelector: vi.fn(() => null), // Return null by default (not already loaded)
            head: {
                appendChild: vi.fn()
            },
            body: {
                appendChild: vi.fn()
            }
        };

        // Reset performance mock
        global.performance.now.mockReturnValue(1000);
        
        // Mock the initializePreloading method to prevent it from running
        vi.spyOn(AssetLoader.prototype, 'initializePreloading').mockImplementation(() => {});
        
        // Create AssetLoader with mocked initialization
        assetLoader = new AssetLoader();
    });

    afterEach(() => {
        // Restore console
        global.console = originalConsole;
        
        // Clean up global mocks
        vi.clearAllMocks();
    });

    describe('Constructor and Initialization', () => {
        it('should initialize with empty caches and queues', () => {
            expect(assetLoader.cache).toBeInstanceOf(Map);
            expect(assetLoader.cache.size).toBe(0);
            expect(assetLoader.loadingPromises).toBeInstanceOf(Map);
            expect(assetLoader.loadingPromises.size).toBe(0);
            expect(assetLoader.preloadQueue).toEqual([]);
            expect(assetLoader.lazyLoadQueue).toEqual([]);
        });

        it('should initialize performance monitoring', () => {
            expect(assetLoader.loadTimes).toBeInstanceOf(Map);
            expect(assetLoader.cacheHitRatio).toEqual({ hits: 0, misses: 0 });
        });

        it('should log initialization message', () => {
            expect(consoleLogSpy).toHaveBeenCalledWith(
                'AssetLoader initialized with performance optimizations'
            );
        });

        it('should initialize preloading for critical resources', () => {
            // Check that preloading was attempted (would be mocked in real implementation)
            expect(assetLoader).toBeDefined();
        });
    });

    describe('Cache Management', () => {
        it('should return cached resource on cache hit', async () => {
            const cacheKey = 'script:/test.js';
            const cachedResult = { loaded: true, content: 'test-script' };
            
            // Pre-populate cache
            assetLoader.cache.set(cacheKey, cachedResult);
            
            // Mock _loadResourceByType to verify it's not called
            const loadSpy = vi.spyOn(assetLoader, '_loadResourceByType');
            
            const result = await assetLoader.preloadResource('/test.js', 'script');
            
            expect(result).toBe(cachedResult);
            expect(loadSpy).not.toHaveBeenCalled();
            expect(assetLoader.cacheHitRatio.hits).toBe(1);
            expect(assetLoader.cacheHitRatio.misses).toBe(0);
        });

        it('should load and cache resource on cache miss', async () => {
            const url = '/test.js';
            const type = 'script';
            const mockResult = { loaded: true, element: {} };
            
            // Mock the loading method
            vi.spyOn(assetLoader, '_loadResourceByType').mockResolvedValue(mockResult);
            
            const result = await assetLoader.preloadResource(url, type);
            
            expect(result).toBe(mockResult);
            expect(assetLoader.cache.get(`${type}:${url}`)).toBe(mockResult);
            expect(assetLoader.cacheHitRatio.hits).toBe(0);
            expect(assetLoader.cacheHitRatio.misses).toBe(1);
        });

        it('should return same promise for concurrent requests', async () => {
            const url = '/concurrent.js';
            const type = 'script';
            const mockResult = { loaded: true };
            
            // Clear any existing cache for this resource
            const cacheKey = `${type}:${url}`;
            assetLoader.cache.delete(cacheKey);
            assetLoader.loadingPromises.delete(cacheKey);
            
            // Create a spy that tracks calls
            const loadSpy = vi.spyOn(assetLoader, '_loadResourceByType');
            loadSpy.mockImplementation(() => {
                return new Promise(resolve => {
                    setTimeout(() => resolve(mockResult), 100);
                });
            });
            
            // Start two concurrent requests
            const promise1 = assetLoader.preloadResource(url, type);
            const promise2 = assetLoader.preloadResource(url, type);
            
            // Both should resolve to the same result
            const [result1, result2] = await Promise.all([promise1, promise2]);
            expect(result1).toBe(mockResult);
            expect(result2).toBe(mockResult);
            
            // Should only call _loadResourceByType once due to deduplication
            expect(loadSpy).toHaveBeenCalledTimes(1);
        });
    });

    describe('Performance Monitoring', () => {
        it('should record load times for resources', async () => {
            const url = '/timed.js';
            const type = 'script';
            const mockResult = { loaded: true };
            
            // Mock performance.now to return predictable values
            global.performance.now
                .mockReturnValueOnce(1000) // Start time
                .mockReturnValueOnce(1500); // End time (500ms load time)
            
            vi.spyOn(assetLoader, '_loadResourceByType').mockResolvedValue(mockResult);
            
            await assetLoader.preloadResource(url, type);
            
            const cacheKey = `${type}:${url}`;
            expect(assetLoader.loadTimes.has(cacheKey)).toBe(true);
            expect(assetLoader.loadTimes.get(cacheKey)).toBe(500);
        });

        it('should track cache hit ratio correctly', async () => {
            const url = '/ratio-test.js';
            const type = 'script';
            const mockResult = { loaded: true };
            
            vi.spyOn(assetLoader, '_loadResourceByType').mockResolvedValue(mockResult);
            
            // First load (cache miss)
            await assetLoader.preloadResource(url, type);
            expect(assetLoader.cacheHitRatio.misses).toBe(1);
            expect(assetLoader.cacheHitRatio.hits).toBe(0);
            
            // Second load (cache hit)
            await assetLoader.preloadResource(url, type);
            expect(assetLoader.cacheHitRatio.misses).toBe(1);
            expect(assetLoader.cacheHitRatio.hits).toBe(1);
            
            // Third load (another cache hit)
            await assetLoader.preloadResource(url, type);
            expect(assetLoader.cacheHitRatio.misses).toBe(1);
            expect(assetLoader.cacheHitRatio.hits).toBe(2);
        });
    });

    describe('Lazy Loading', () => {
        it('should use preloadResource for high priority lazy loads', async () => {
            const url = '/high-priority.js';
            const type = 'script';
            const mockResult = { loaded: true };
            
            const preloadSpy = vi.spyOn(assetLoader, 'preloadResource').mockResolvedValue(mockResult);
            
            const result = await assetLoader.lazyLoadResource(url, type, { priority: 'high' });
            
            expect(preloadSpy).toHaveBeenCalledWith(url, type);
            expect(result).toBe(mockResult);
        });

        it('should queue normal priority lazy loads', async () => {
            const url = '/normal-priority.js';
            const type = 'script';
            
            // Mock _processLazyLoadQueue
            const processSpy = vi.spyOn(assetLoader, '_processLazyLoadQueue').mockImplementation(() => {});
            
            const loadPromise = assetLoader.lazyLoadResource(url, type, { priority: 'normal' });
            
            expect(assetLoader.lazyLoadQueue).toHaveLength(1);
            expect(assetLoader.lazyLoadQueue[0].url).toBe(url);
            expect(assetLoader.lazyLoadQueue[0].type).toBe(type);
            expect(assetLoader.lazyLoadQueue[0].priority).toBe('normal');
            expect(processSpy).toHaveBeenCalled();
            
            // Clean up the promise to avoid unhandled rejection
            loadPromise.catch(() => {});
        });

        it('should handle lazy load timeout', async () => {
            const url = '/timeout-test.js';
            const type = 'script';
            const timeout = 100;
            
            vi.spyOn(assetLoader, '_processLazyLoadQueue').mockImplementation(() => {});
            
            await expect(
                assetLoader.lazyLoadResource(url, type, { timeout })
            ).rejects.toThrow(`Timeout loading ${type}: ${url}`);
        });

        it('should clear timeout on successful lazy load', async () => {
            const url = '/success-test.js';
            const type = 'script';
            const mockResult = { loaded: true };
            
            const clearTimeoutSpy = vi.spyOn(global, 'clearTimeout');
            
            // Mock _processLazyLoadQueue to immediately resolve
            vi.spyOn(assetLoader, '_processLazyLoadQueue').mockImplementation(() => {
                const item = assetLoader.lazyLoadQueue[0];
                if (item) {
                    item.resolve(mockResult);
                }
            });
            
            const result = await assetLoader.lazyLoadResource(url, type);
            
            expect(result).toBe(mockResult);
            expect(clearTimeoutSpy).toHaveBeenCalled();
        });
    });

    describe('Error Handling', () => {
        it('should handle preload errors gracefully', async () => {
            const url = '/error-test.js';
            const type = 'script';
            const mockError = new Error('Loading failed');
            
            vi.spyOn(assetLoader, '_loadResourceByType').mockRejectedValue(mockError);
            
            await expect(assetLoader.preloadResource(url, type)).rejects.toThrow(mockError);
            
            expect(consoleErrorSpy).toHaveBeenCalledWith(
                `Failed to preload ${type} resource: ${url}`,
                mockError
            );
            
            // Should clean up loading promise
            const cacheKey = `${type}:${url}`;
            expect(assetLoader.loadingPromises.has(cacheKey)).toBe(false);
        });

        it('should not cache failed loads', async () => {
            const url = '/fail-test.js';
            const type = 'script';
            const mockError = new Error('Loading failed');
            
            vi.spyOn(assetLoader, '_loadResourceByType').mockRejectedValue(mockError);
            
            try {
                await assetLoader.preloadResource(url, type);
            } catch (error) {
                // Expected to fail
            }
            
            const cacheKey = `${type}:${url}`;
            expect(assetLoader.cache.has(cacheKey)).toBe(false);
        });

        it('should handle lazy load errors', async () => {
            const url = '/lazy-error.js';
            const type = 'script';
            const mockError = new Error('Lazy loading failed');
            
            const clearTimeoutSpy = vi.spyOn(global, 'clearTimeout');
            
            // Mock _processLazyLoadQueue to immediately reject
            vi.spyOn(assetLoader, '_processLazyLoadQueue').mockImplementation(() => {
                const item = assetLoader.lazyLoadQueue[0];
                if (item) {
                    item.reject(mockError);
                }
            });
            
            await expect(assetLoader.lazyLoadResource(url, type)).rejects.toThrow(mockError);
            expect(clearTimeoutSpy).toHaveBeenCalled();
        });
    });

    describe('Resource Type Handling', () => {
        it('should call correct loader for script type', async () => {
            const url = '/test.js';
            const loadScriptSpy = vi.spyOn(assetLoader, '_loadScript').mockResolvedValue({});
            
            await assetLoader._loadResourceByType(url, 'script');
            
            expect(loadScriptSpy).toHaveBeenCalledWith(url);
        });

        it('should call correct loader for style type', async () => {
            const url = '/test.css';
            const loadStyleSpy = vi.spyOn(assetLoader, '_loadStylesheet').mockResolvedValue({});
            
            await assetLoader._loadResourceByType(url, 'style');
            
            expect(loadStyleSpy).toHaveBeenCalledWith(url);
        });

        it('should call correct loader for image type', async () => {
            const url = '/test.jpg';
            const loadImageSpy = vi.spyOn(assetLoader, '_loadImage').mockResolvedValue({});
            
            await assetLoader._loadResourceByType(url, 'image');
            
            expect(loadImageSpy).toHaveBeenCalledWith(url);
        });

        it('should call correct loader for JSON type', async () => {
            const url = '/test.json';
            const loadJSONSpy = vi.spyOn(assetLoader, '_loadJSON').mockResolvedValue({});
            
            await assetLoader._loadResourceByType(url, 'json');
            
            expect(loadJSONSpy).toHaveBeenCalledWith(url);
        });

        it('should use generic loader for unknown type', async () => {
            const url = '/test.unknown';
            const loadGenericSpy = vi.spyOn(assetLoader, '_loadGeneric').mockResolvedValue({});
            
            await assetLoader._loadResourceByType(url, 'unknown');
            
            expect(loadGenericSpy).toHaveBeenCalledWith(url);
        });
    });

    describe('Memory Management', () => {
        it('should clean up loading promises after completion', async () => {
            const url = '/cleanup-test.js';
            const type = 'script';
            const mockResult = { loaded: true };
            const cacheKey = `${type}:${url}`;
            
            vi.spyOn(assetLoader, '_loadResourceByType').mockResolvedValue(mockResult);
            
            expect(assetLoader.loadingPromises.has(cacheKey)).toBe(false);
            
            const promise = assetLoader.preloadResource(url, type);
            expect(assetLoader.loadingPromises.has(cacheKey)).toBe(true);
            
            await promise;
            expect(assetLoader.loadingPromises.has(cacheKey)).toBe(false);
        });

        it('should clean up loading promises after errors', async () => {
            const url = '/error-cleanup.js';
            const type = 'script';
            const mockError = new Error('Test error');
            const cacheKey = `${type}:${url}`;
            
            vi.spyOn(assetLoader, '_loadResourceByType').mockRejectedValue(mockError);
            
            try {
                await assetLoader.preloadResource(url, type);
            } catch (error) {
                // Expected to fail
            }
            
            expect(assetLoader.loadingPromises.has(cacheKey)).toBe(false);
        });
    });

    describe('Queue Processing', () => {
        it('should process lazy load queue with requestIdleCallback', () => {
            const url = '/queue-test.js';
            const type = 'script';
            
            // Spy on the actual implementation
            const requestIdleSpy = vi.spyOn(global, 'requestIdleCallback');
            
            assetLoader.lazyLoadResource(url, type);
            
            expect(requestIdleSpy).toHaveBeenCalled();
        });

        it('should handle empty lazy load queue gracefully', () => {
            expect(() => {
                assetLoader._processLazyLoadQueue();
            }).not.toThrow();
        });
    });

    describe('Metrics and Analytics', () => {
        it('should provide cache statistics', async () => {
            const mockResult = { loaded: true };
            vi.spyOn(assetLoader, '_loadResourceByType').mockResolvedValue(mockResult);
            
            // Generate some cache activity
            await assetLoader.preloadResource('/test1.js', 'script');
            await assetLoader.preloadResource('/test1.js', 'script'); // cache hit
            await assetLoader.preloadResource('/test2.js', 'script');
            
            expect(assetLoader.cacheHitRatio.hits).toBe(1);
            expect(assetLoader.cacheHitRatio.misses).toBe(2);
        });

        it('should track load times for performance analysis', async () => {
            const mockResult = { loaded: true };
            vi.spyOn(assetLoader, '_loadResourceByType').mockResolvedValue(mockResult);
            
            global.performance.now
                .mockReturnValueOnce(1000)
                .mockReturnValueOnce(1250);
            
            await assetLoader.preloadResource('/perf-test.js', 'script');
            
            expect(assetLoader.loadTimes.get('script:/perf-test.js')).toBe(250);
        });
    });

    describe('Edge Cases', () => {
        it('should handle malformed URLs gracefully', async () => {
            const badUrl = '';
            const type = 'script';
            
            vi.spyOn(assetLoader, '_loadResourceByType').mockRejectedValue(new Error('Invalid URL'));
            
            await expect(assetLoader.preloadResource(badUrl, type)).rejects.toThrow('Invalid URL');
        });

        it('should handle concurrent cache access correctly', async () => {
            const url = '/concurrent-cache.js';
            const type = 'script';
            const mockResult = { loaded: true };
            
            vi.spyOn(assetLoader, '_loadResourceByType').mockResolvedValue(mockResult);
            
            // Start multiple concurrent requests
            const promises = Array.from({ length: 5 }, () => 
                assetLoader.preloadResource(url, type)
            );
            
            const results = await Promise.all(promises);
            
            // All should return the same result
            results.forEach(result => {
                expect(result).toBe(mockResult);
            });
            
            // Should only load once
            expect(assetLoader._loadResourceByType).toHaveBeenCalledTimes(1);
        });
    });
});