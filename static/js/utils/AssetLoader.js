/**
 * AssetLoader - Optimized asset loading and caching system
 * 
 * Performance optimizations:
 * - Lazy loading of non-critical assets
 * - Preloading of critical resources
 * - Intelligent caching with cache busting
 * - Resource prioritization
 * - Memory-efficient asset management
 */

class AssetLoader {
    constructor() {
        this.cache = new Map();
        this.loadingPromises = new Map();
        this.preloadQueue = [];
        this.lazyLoadQueue = [];
        
        // Performance monitoring
        this.loadTimes = new Map();
        this.cacheHitRatio = { hits: 0, misses: 0 };
        
        // Initialize critical resource preloading
        this.initializePreloading();
        
        console.log('AssetLoader initialized with performance optimizations');
    }
    
    /**
     * Initialize critical resource preloading
     */
    initializePreloading() {
        // Preload critical CSS and fonts
        this.preloadResource('/static/css/style.css', 'style');
        
        // Preload critical JavaScript modules
        const criticalModules = [
            '/static/js/modules/EventBus.js',
            '/static/js/modules/SocketManager.js',
            '/static/js/modules/GameClient.js'
        ];
        
        criticalModules.forEach(module => {
            this.preloadResource(module, 'script');
        });
    }
    
    /**
     * Preload a resource with caching
     * @param {string} url - Resource URL
     * @param {string} type - Resource type (script, style, image, etc.)
     * @returns {Promise} Loading promise
     */
    async preloadResource(url, type = 'script') {
        const cacheKey = `${type}:${url}`;
        
        // Check cache first
        if (this.cache.has(cacheKey)) {
            this.cacheHitRatio.hits++;
            return this.cache.get(cacheKey);
        }
        
        // Check if already loading
        if (this.loadingPromises.has(cacheKey)) {
            return this.loadingPromises.get(cacheKey);
        }
        
        this.cacheHitRatio.misses++;
        const startTime = performance.now();
        
        const loadPromise = this._loadResourceByType(url, type);
        this.loadingPromises.set(cacheKey, loadPromise);
        
        try {
            const result = await loadPromise;
            
            // Cache successful result
            this.cache.set(cacheKey, result);
            
            // Record load time
            const loadTime = performance.now() - startTime;
            this.loadTimes.set(cacheKey, loadTime);
            
            return result;
        } catch (error) {
            console.error(`Failed to preload ${type} resource: ${url}`, error);
            throw error;
        } finally {
            this.loadingPromises.delete(cacheKey);
        }
    }
    
    /**
     * Lazy load a resource when needed
     * @param {string} url - Resource URL
     * @param {string} type - Resource type
     * @param {Object} options - Loading options
     * @returns {Promise} Loading promise
     */
    async lazyLoadResource(url, type = 'script', options = {}) {
        const { priority = 'normal', timeout = 10000 } = options;
        
        // For high priority, load immediately
        if (priority === 'high') {
            return this.preloadResource(url, type);
        }
        
        // For normal/low priority, add to queue
        return new Promise((resolve, reject) => {
            const timeoutId = setTimeout(() => {
                reject(new Error(`Timeout loading ${type}: ${url}`));
            }, timeout);
            
            this.lazyLoadQueue.push({
                url,
                type,
                priority,
                resolve: (result) => {
                    clearTimeout(timeoutId);
                    resolve(result);
                },
                reject: (error) => {
                    clearTimeout(timeoutId);
                    reject(error);
                }
            });
            
            // Process queue with requestIdleCallback for better performance
            this._processLazyLoadQueue();
        });
    }
    
    /**
     * Load resource by type with optimized methods
     * @private
     */
    async _loadResourceByType(url, type) {
        switch (type) {
            case 'script':
                return this._loadScript(url);
            case 'style':
                return this._loadStylesheet(url);
            case 'image':
                return this._loadImage(url);
            case 'json':
                return this._loadJSON(url);
            default:
                return this._loadGeneric(url);
        }
    }
    
    /**
     * Load JavaScript with performance optimizations
     * @private
     */
    _loadScript(url) {
        return new Promise((resolve, reject) => {
            // Check if already loaded
            const existing = document.querySelector(`script[src="${url}"]`);
            if (existing && existing.dataset.loaded === 'true') {
                resolve(url);
                return;
            }
            
            const script = document.createElement('script');
            script.src = url;
            script.type = 'module';
            script.crossOrigin = 'anonymous';
            script.async = true;
            
            script.onload = () => {
                script.dataset.loaded = 'true';
                resolve(url);
            };
            
            script.onerror = () => {
                reject(new Error(`Failed to load script: ${url}`));
            };
            
            // Insert with priority (head for critical, body end for non-critical)
            const target = this.preloadQueue.includes(url) ? 
                document.head : document.body;
            target.appendChild(script);
        });
    }
    
    /**
     * Load CSS with performance optimizations
     * @private
     */
    _loadStylesheet(url) {
        return new Promise((resolve, reject) => {
            // Check if already loaded
            const existing = document.querySelector(`link[href="${url}"]`);
            if (existing) {
                resolve(url);
                return;
            }
            
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = url;
            link.crossOrigin = 'anonymous';
            
            link.onload = () => resolve(url);
            link.onerror = () => reject(new Error(`Failed to load stylesheet: ${url}`));
            
            document.head.appendChild(link);
        });
    }
    
    /**
     * Load image with performance optimizations
     * @private
     */
    _loadImage(url) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            
            img.onload = () => resolve(img);
            img.onerror = () => reject(new Error(`Failed to load image: ${url}`));
            
            // Enable loading attribute for modern browsers
            img.loading = 'lazy';
            img.decoding = 'async';
            img.src = url;
        });
    }
    
    /**
     * Load JSON data with caching
     * @private
     */
    async _loadJSON(url) {
        const response = await fetch(url, {
            cache: 'force-cache',
            headers: {
                'Accept': 'application/json'
            }
        });
        
        if (!response.ok) {
            throw new Error(`Failed to fetch JSON: ${response.status}`);
        }
        
        return response.json();
    }
    
    /**
     * Generic resource loader
     * @private
     */
    async _loadGeneric(url) {
        const response = await fetch(url, {
            cache: 'force-cache'
        });
        
        if (!response.ok) {
            throw new Error(`Failed to fetch resource: ${response.status}`);
        }
        
        return response.text();
    }
    
    /**
     * Process lazy loading queue with performance optimization
     * @private
     */
    _processLazyLoadQueue() {
        if (this.lazyLoadQueue.length === 0) return;
        
        // Use requestIdleCallback for non-blocking processing
        const processNext = (deadline) => {
            while (deadline.timeRemaining() > 0 && this.lazyLoadQueue.length > 0) {
                const item = this.lazyLoadQueue.shift();
                
                this.preloadResource(item.url, item.type)
                    .then(item.resolve)
                    .catch(item.reject);
            }
            
            if (this.lazyLoadQueue.length > 0) {
                requestIdleCallback(processNext);
            }
        };
        
        if (window.requestIdleCallback) {
            requestIdleCallback(processNext);
        } else {
            // Fallback for browsers without requestIdleCallback
            setTimeout(() => {
                const item = this.lazyLoadQueue.shift();
                if (item) {
                    this.preloadResource(item.url, item.type)
                        .then(item.resolve)
                        .catch(item.reject);
                }
            }, 0);
        }
    }
    
    /**
     * Prefetch resources for upcoming features
     * @param {Array<string>} urls - URLs to prefetch
     */
    prefetchResources(urls) {
        urls.forEach(url => {
            // Use low-priority fetch for prefetching
            if ('fetchpriority' in HTMLLinkElement.prototype) {
                const link = document.createElement('link');
                link.rel = 'prefetch';
                link.href = url;
                link.fetchPriority = 'low';
                document.head.appendChild(link);
            } else {
                // Fallback prefetch
                fetch(url, { cache: 'force-cache', priority: 'low' })
                    .catch(() => {}); // Ignore errors for prefetch
            }
        });
    }
    
    /**
     * Clear cache and free memory
     * @param {boolean} aggressive - Whether to clear all caches
     */
    clearCache(aggressive = false) {
        if (aggressive) {
            this.cache.clear();
            this.loadingPromises.clear();
            this.loadTimes.clear();
        } else {
            // Clear only old entries (older than 5 minutes)
            const fiveMinutesAgo = Date.now() - (5 * 60 * 1000);
            
            for (const [key, value] of this.cache.entries()) {
                if (value.timestamp && value.timestamp < fiveMinutesAgo) {
                    this.cache.delete(key);
                }
            }
        }
        
        console.log('AssetLoader cache cleared');
    }
    
    /**
     * Get performance metrics
     * @returns {Object} Performance metrics
     */
    getPerformanceMetrics() {
        const hitRate = this.cacheHitRatio.hits / 
            (this.cacheHitRatio.hits + this.cacheHitRatio.misses) * 100;
        
        const avgLoadTime = Array.from(this.loadTimes.values())
            .reduce((a, b) => a + b, 0) / this.loadTimes.size;
        
        return {
            cacheHitRate: Math.round(hitRate * 100) / 100,
            averageLoadTime: Math.round(avgLoadTime * 100) / 100,
            cachedResources: this.cache.size,
            totalRequests: this.cacheHitRatio.hits + this.cacheHitRatio.misses,
            queuedLazyLoads: this.lazyLoadQueue.length
        };
    }
    
    /**
     * Clean up resources and event listeners
     */
    destroy() {
        this.clearCache(true);
        this.preloadQueue.length = 0;
        this.lazyLoadQueue.length = 0;
        
        console.log('AssetLoader destroyed');
    }
}


export default AssetLoader;