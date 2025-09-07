/**
 * BundleOptimizer - JavaScript bundle size and loading optimization
 * 
 * Performance optimizations:
 * - Dynamic module loading and code splitting
 * - Tree shaking simulation for unused code detection
 * - Module dependency analysis
 * - Lazy loading of non-critical modules
 * - Bundle size monitoring and alerts
 * - Preloading critical paths
 */

class BundleOptimizer {
    constructor() {
        this.loadedModules = new Map();
        this.moduleGraph = new Map();
        this.criticalModules = new Set([
            'EventBus',
            'SocketManager', 
            'GameClient',
            'UIManager'
        ]);
        this.lazyModules = new Set([
            'PerformanceMonitor',
            'DebugConsole',
            'AssetLoader'
        ]);
        
        // Bundle metrics
        this.bundleMetrics = {
            totalSize: 0,
            loadedSize: 0,
            moduleCount: 0,
            loadTime: 0
        };
        
        // Loading strategies
        this.loadingStrategies = {
            critical: 'immediate',
            standard: 'ondemand',
            lazy: 'deferred'
        };
        
        console.log('BundleOptimizer initialized');
    }
    
    /**
     * Initialize module loading with optimization
     */
    async initialize() {
        const startTime = performance.now();
        
        try {
            // Load critical modules immediately
            await this.loadCriticalModules();
            
            // Preload standard modules
            this.preloadStandardModules();
            
            // Set up lazy loading for non-critical modules
            this.setupLazyLoading();
            
            const loadTime = performance.now() - startTime;
            this.bundleMetrics.loadTime = loadTime;
            
            console.log(`Bundle optimization complete in ${loadTime.toFixed(2)}ms`);
            
        } catch (error) {
            console.error('Bundle optimization failed:', error);
            throw error;
        }
    }
    
    /**
     * Load critical modules immediately
     */
    async loadCriticalModules() {
        const criticalPaths = [
            '/static/js/modules/EventBus.js',
            '/static/js/modules/SocketManager.js',
            '/static/js/modules/GameClient.js',
            '/static/js/modules/UIManager.js'
        ];
        
        const loadPromises = criticalPaths.map(path => 
            this.loadModule(path, 'critical')
        );
        
        await Promise.all(loadPromises);
    }
    
    /**
     * Preload standard modules in the background
     */
    preloadStandardModules() {
        const standardPaths = [
            '/static/js/modules/TimerManager.js',
            '/static/js/utils/MemoryManager.js',
            '/static/js/utils/AssetLoader.js'
        ];
        
        // Use requestIdleCallback for background loading
        if (window.requestIdleCallback) {
            window.requestIdleCallback(() => {
                standardPaths.forEach(path => {
                    this.loadModule(path, 'standard').catch(() => {
                        // Ignore preload errors
                    });
                });
            });
        } else {
            // Fallback for browsers without requestIdleCallback
            setTimeout(() => {
                standardPaths.forEach(path => {
                    this.loadModule(path, 'standard').catch(() => {});
                });
            }, 100);
        }
    }
    
    /**
     * Set up lazy loading for non-critical modules
     */
    setupLazyLoading() {
        // Create loading triggers for lazy modules
        this.setupIntersectionObserver();
        this.setupEventBasedLoading();
    }
    
    /**
     * Load a module with specified strategy
     * @param {string} path - Module path
     * @param {string} strategy - Loading strategy
     * @returns {Promise} Module loading promise
     */
    async loadModule(path, strategy = 'standard') {
        if (this.loadedModules.has(path)) {
            return this.loadedModules.get(path);
        }
        
        const startTime = performance.now();
        
        try {
            let modulePromise;
            
            switch (strategy) {
                case 'critical':
                    modulePromise = this._loadModuleImmediate(path);
                    break;
                case 'lazy':
                    modulePromise = this._loadModuleLazy(path);
                    break;
                default:
                    modulePromise = this._loadModuleStandard(path);
            }
            
            const module = await modulePromise;
            const loadTime = performance.now() - startTime;
            
            // Cache the loaded module
            this.loadedModules.set(path, module);
            
            // Update metrics
            this.bundleMetrics.moduleCount++;
            this.bundleMetrics.totalSize += this._estimateModuleSize(path);
            
            // Track dependencies
            this._analyzeModuleDependencies(path, module);
            
            console.debug(`Loaded module ${path} in ${loadTime.toFixed(2)}ms (${strategy})`);
            
            return module;
            
        } catch (error) {
            console.error(`Failed to load module ${path}:`, error);
            throw error;
        }
    }
    
    /**
     * Load module immediately
     * @private
     */
    async _loadModuleImmediate(path) {
        return import(path);
    }
    
    /**
     * Load module with standard priority
     * @private
     */
    async _loadModuleStandard(path) {
        // Add small delay to not block critical loading
        await new Promise(resolve => setTimeout(resolve, 10));
        return import(path);
    }
    
    /**
     * Load module lazily when needed
     * @private
     */
    async _loadModuleLazy(path) {
        // Use dynamic import with lower priority
        return new Promise((resolve, reject) => {
            if (window.requestIdleCallback) {
                window.requestIdleCallback(async () => {
                    try {
                        const module = await import(path);
                        resolve(module);
                    } catch (error) {
                        reject(error);
                    }
                });
            } else {
                setTimeout(async () => {
                    try {
                        const module = await import(path);
                        resolve(module);
                    } catch (error) {
                        reject(error);
                    }
                }, 100);
            }
        });
    }
    
    /**
     * Set up intersection observer for lazy loading
     * @private
     */
    setupIntersectionObserver() {
        if (!window.IntersectionObserver) return;
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const lazyModule = entry.target.dataset.lazyModule;
                    if (lazyModule) {
                        this.loadModule(lazyModule, 'lazy');
                        observer.unobserve(entry.target);
                    }
                }
            });
        }, {
            rootMargin: '100px' // Load 100px before element comes into view
        });
        
        // Observe elements that trigger lazy loading
        document.querySelectorAll('[data-lazy-module]').forEach(el => {
            observer.observe(el);
        });
    }
    
    /**
     * Set up event-based lazy loading
     * @private
     */
    setupEventBasedLoading() {
        // Load performance modules when performance tab is opened
        document.addEventListener('click', (e) => {
            if (e.target.matches('.performance-tab, [data-performance]')) {
                this.loadModule('/static/js/utils/PerformanceMonitor.js', 'lazy');
            }
            
            if (e.target.matches('.debug-toggle, [data-debug]')) {
                this.loadModule('/static/js/utils/DebugConsole.js', 'lazy');
            }
        });
        
        // Load advanced UI modules on first user interaction
        const loadAdvancedUI = () => {
            this.loadModule('/static/js/modules/AdvancedUI.js', 'lazy');
            document.removeEventListener('click', loadAdvancedUI, { once: true });
        };
        
        document.addEventListener('click', loadAdvancedUI, { once: true });
    }
    
    /**
     * Analyze module dependencies for optimization
     * @private
     */
    _analyzeModuleDependencies(path, module) {
        if (!module || typeof module !== 'object') return;
        
        const dependencies = new Set();
        
        // Analyze import statements in module source
        if (module.toString) {
            const moduleSource = module.toString();
            const importMatches = moduleSource.match(/import\s+.*?from\s+['"]([^'"]+)['"]/g);
            
            if (importMatches) {
                importMatches.forEach(importStatement => {
                    const pathMatch = importStatement.match(/['"]([^'"]+)['"]/);
                    if (pathMatch) {
                        dependencies.add(pathMatch[1]);
                    }
                });
            }
        }
        
        this.moduleGraph.set(path, dependencies);
    }
    
    /**
     * Estimate module size for metrics
     * @private
     */
    _estimateModuleSize(path) {
        // Simple heuristic based on file path and type
        const sizeEstimates = {
            'EventBus.js': 5000,
            'SocketManager.js': 8000,
            'GameClient.js': 6000,
            'UIManager.js': 12000,
            'TimerManager.js': 4000,
            'MemoryManager.js': 6000,
            'AssetLoader.js': 7000
        };
        
        const filename = path.split('/').pop();
        return sizeEstimates[filename] || 3000; // Default estimate
    }
    
    /**
     * Check if module is loaded
     * @param {string} path - Module path
     * @returns {boolean} Whether module is loaded
     */
    isModuleLoaded(path) {
        return this.loadedModules.has(path);
    }
    
    /**
     * Get module if already loaded
     * @param {string} path - Module path
     * @returns {Object|null} Loaded module or null
     */
    getLoadedModule(path) {
        return this.loadedModules.get(path) || null;
    }
    
    /**
     * Preload a specific module
     * @param {string} path - Module path
     * @returns {Promise} Loading promise
     */
    async preloadModule(path) {
        if (this.criticalModules.has(path)) {
            return this.loadModule(path, 'critical');
        } else if (this.lazyModules.has(path)) {
            return this.loadModule(path, 'lazy');
        } else {
            return this.loadModule(path, 'standard');
        }
    }
    
    /**
     * Analyze bundle size and performance
     * @returns {Object} Bundle analysis
     */
    analyzeBundlePerformance() {
        const analysis = {
            metrics: { ...this.bundleMetrics },
            loadedModules: this.loadedModules.size,
            dependencyGraph: Object.fromEntries(this.moduleGraph),
            recommendations: []
        };
        
        // Generate recommendations
        if (this.bundleMetrics.totalSize > 50000) { // 50KB threshold
            analysis.recommendations.push('Consider code splitting for large modules');
        }
        
        if (this.bundleMetrics.loadTime > 1000) { // 1s threshold
            analysis.recommendations.push('Optimize critical module loading');
        }
        
        if (this.loadedModules.size > 10) {
            analysis.recommendations.push('Review module necessity and lazy load non-critical ones');
        }
        
        return analysis;
    }
    
    /**
     * Clear unused modules from memory
     */
    cleanupUnusedModules() {
        // Simple cleanup based on last access time
        const now = Date.now();
        const unusedThreshold = 5 * 60 * 1000; // 5 minutes
        
        for (const [path, module] of this.loadedModules.entries()) {
            if (module.lastAccessed && (now - module.lastAccessed) > unusedThreshold) {
                // Don't remove critical modules
                if (!this.criticalModules.has(path.split('/').pop().replace('.js', ''))) {
                    this.loadedModules.delete(path);
                    console.debug(`Cleaned up unused module: ${path}`);
                }
            }
        }
    }
    
    /**
     * Get bundle performance metrics
     * @returns {Object} Performance metrics
     */
    getPerformanceMetrics() {
        return {
            ...this.bundleMetrics,
            memoryUsage: this._estimateMemoryUsage(),
            cacheEfficiency: this._calculateCacheEfficiency(),
            loadedModulesList: Array.from(this.loadedModules.keys())
        };
    }
    
    /**
     * Estimate memory usage of loaded modules
     * @private
     */
    _estimateMemoryUsage() {
        let totalMemory = 0;
        
        for (const [path] of this.loadedModules) {
            totalMemory += this._estimateModuleSize(path);
        }
        
        return totalMemory;
    }
    
    /**
     * Calculate cache efficiency
     * @private
     */
    _calculateCacheEfficiency() {
        const total = this.bundleMetrics.moduleCount;
        const cached = this.loadedModules.size;
        
        return total > 0 ? (cached / total) * 100 : 0;
    }
    
    /**
     * Clean up optimizer resources
     */
    destroy() {
        this.loadedModules.clear();
        this.moduleGraph.clear();
        this.bundleMetrics = {
            totalSize: 0,
            loadedSize: 0,
            moduleCount: 0,
            loadTime: 0
        };
        
        console.log('BundleOptimizer destroyed');
    }
}


export default BundleOptimizer;