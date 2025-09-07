/**
 * PerformanceMonitor - Comprehensive performance monitoring and metrics collection
 * 
 * Features:
 * - Real-time performance metrics collection
 * - Memory usage monitoring
 * - Network performance tracking
 * - User experience metrics (FCP, LCP, CLS, FID)
 * - Custom performance markers
 * - Performance alerts and thresholds
 * - Export capabilities for analysis
 */

class PerformanceMonitor {
    constructor(config = {}) {
        this.config = {
            enableAutoCollection: true,
            collectionInterval: 5000, // 5 seconds
            maxMetricsHistory: 1000,
            memoryThreshold: 80, // 80% memory usage threshold
            responseTimeThreshold: 1000, // 1 second
            ...config
        };
        
        // Metrics storage
        this.metrics = {
            memory: [],
            network: [],
            userExperience: {},
            custom: {},
            system: {
                startTime: Date.now(),
                totalCollections: 0,
                errors: 0
            }
        };
        
        // Performance observers
        this.observers = new Map();
        
        // Collection state
        this.isCollecting = false;
        this.collectionTimer = null;
        
        // Initialize monitoring
        this.initialize();
        
        console.log('PerformanceMonitor initialized');
    }
    
    /**
     * Initialize performance monitoring
     */
    initialize() {
        try {
            this.setupPerformanceObservers();
            
            if (this.config.enableAutoCollection) {
                this.startCollection();
            }
            
            // Monitor for page visibility changes
            this.setupVisibilityMonitoring();
            
            // Set up error monitoring
            this.setupErrorMonitoring();
            
        } catch (error) {
            console.error('Failed to initialize PerformanceMonitor:', error);
        }
    }
    
    /**
     * Set up performance observers for Web Vitals
     */
    setupPerformanceObservers() {
        // Only run in browser environment
        if (typeof window === 'undefined') return;
        
        // Largest Contentful Paint (LCP)
        if ('PerformanceObserver' in window) {
            try {
                const lcpObserver = new PerformanceObserver((list) => {
                    const entries = list.getEntries();
                    const lastEntry = entries[entries.length - 1];
                    
                    this.metrics.userExperience.lcp = {
                        value: lastEntry.startTime,
                        timestamp: Date.now(),
                        rating: this.rateLCP(lastEntry.startTime)
                    };
                });
                
                lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] });
                this.observers.set('lcp', lcpObserver);
                
            } catch (error) {
                console.warn('LCP observer not supported:', error);
            }
            
            // First Input Delay (FID)
            try {
                const fidObserver = new PerformanceObserver((list) => {
                    const entries = list.getEntries();
                    entries.forEach(entry => {
                        this.metrics.userExperience.fid = {
                            value: entry.processingStart - entry.startTime,
                            timestamp: Date.now(),
                            rating: this.rateFID(entry.processingStart - entry.startTime)
                        };
                    });
                });
                
                fidObserver.observe({ entryTypes: ['first-input'] });
                this.observers.set('fid', fidObserver);
                
            } catch (error) {
                console.warn('FID observer not supported:', error);
            }
            
            // Cumulative Layout Shift (CLS)
            try {
                let clsValue = 0;
                const clsObserver = new PerformanceObserver((list) => {
                    const entries = list.getEntries();
                    entries.forEach(entry => {
                        if (!entry.hadRecentInput) {
                            clsValue += entry.value;
                        }
                    });
                    
                    this.metrics.userExperience.cls = {
                        value: clsValue,
                        timestamp: Date.now(),
                        rating: this.rateCLS(clsValue)
                    };
                });
                
                clsObserver.observe({ entryTypes: ['layout-shift'] });
                this.observers.set('cls', clsObserver);
                
            } catch (error) {
                console.warn('CLS observer not supported:', error);
            }
            
            // Long Tasks
            try {
                const longTaskObserver = new PerformanceObserver((list) => {
                    const entries = list.getEntries();
                    entries.forEach(entry => {
                        this.recordCustomMetric('longTask', {
                            duration: entry.duration,
                            startTime: entry.startTime,
                            name: entry.name,
                            timestamp: Date.now()
                        });
                    });
                });
                
                longTaskObserver.observe({ entryTypes: ['longtask'] });
                this.observers.set('longtask', longTaskObserver);
                
            } catch (error) {
                console.warn('Long task observer not supported:', error);
            }
        }
        
        // First Contentful Paint (FCP) - from navigation timing
        if (window.performance && window.performance.getEntriesByType) {
            const paintEntries = window.performance.getEntriesByType('paint');
            const fcpEntry = paintEntries.find(entry => entry.name === 'first-contentful-paint');
            
            if (fcpEntry) {
                this.metrics.userExperience.fcp = {
                    value: fcpEntry.startTime,
                    timestamp: Date.now(),
                    rating: this.rateFCP(fcpEntry.startTime)
                };
            }
        }
    }
    
    /**
     * Set up visibility monitoring
     */
    setupVisibilityMonitoring() {
        if (typeof document !== 'undefined') {
            document.addEventListener('visibilitychange', () => {
                if (document.hidden) {
                    this.pauseCollection();
                } else {
                    this.resumeCollection();
                }
            });
        }
    }
    
    /**
     * Set up error monitoring
     */
    setupErrorMonitoring() {
        if (typeof window !== 'undefined') {
            window.addEventListener('error', (event) => {
                this.metrics.system.errors++;
                this.recordCustomMetric('jsError', {
                    message: event.message,
                    filename: event.filename,
                    lineno: event.lineno,
                    colno: event.colno,
                    timestamp: Date.now()
                });
            });
            
            window.addEventListener('unhandledrejection', (event) => {
                this.metrics.system.errors++;
                this.recordCustomMetric('promiseRejection', {
                    reason: event.reason?.message || event.reason,
                    timestamp: Date.now()
                });
            });
        }
    }
    
    /**
     * Start performance data collection
     */
    startCollection() {
        if (this.isCollecting) return;
        
        this.isCollecting = true;
        
        this.collectionTimer = setInterval(() => {
            this.collectMetrics();
        }, this.config.collectionInterval);
        
        console.log('Performance collection started');
    }
    
    /**
     * Stop performance data collection
     */
    stopCollection() {
        if (!this.isCollecting) return;
        
        this.isCollecting = false;
        
        if (this.collectionTimer) {
            clearInterval(this.collectionTimer);
            this.collectionTimer = null;
        }
        
        console.log('Performance collection stopped');
    }
    
    /**
     * Pause collection (e.g., when page is hidden)
     */
    pauseCollection() {
        if (this.collectionTimer) {
            clearInterval(this.collectionTimer);
            this.collectionTimer = null;
        }
    }
    
    /**
     * Resume collection
     */
    resumeCollection() {
        if (this.isCollecting && !this.collectionTimer) {
            this.collectionTimer = setInterval(() => {
                this.collectMetrics();
            }, this.config.collectionInterval);
        }
    }
    
    /**
     * Collect performance metrics
     */
    collectMetrics() {
        try {
            const timestamp = Date.now();
            
            // Collect memory metrics
            this.collectMemoryMetrics(timestamp);
            
            // Collect network metrics
            this.collectNetworkMetrics(timestamp);
            
            // Collect system metrics
            this.collectSystemMetrics(timestamp);
            
            this.metrics.system.totalCollections++;
            
        } catch (error) {
            console.error('Error collecting metrics:', error);
            this.metrics.system.errors++;
        }
    }
    
    /**
     * Collect memory metrics
     */
    collectMemoryMetrics(timestamp) {
        if (!window.performance || !window.performance.memory) return;
        
        const memory = window.performance.memory;
        const memoryData = {
            used: memory.usedJSHeapSize,
            total: memory.totalJSHeapSize,
            limit: memory.jsHeapSizeLimit,
            timestamp
        };
        
        // Calculate usage percentage
        memoryData.usagePercent = (memoryData.used / memoryData.total) * 100;
        
        this.metrics.memory.push(memoryData);
        
        // Trim history to max size
        if (this.metrics.memory.length > this.config.maxMetricsHistory) {
            this.metrics.memory.shift();
        }
        
        // Check threshold
        if (memoryData.usagePercent > this.config.memoryThreshold) {
            this.triggerAlert('memory', `Memory usage high: ${memoryData.usagePercent.toFixed(1)}%`);
        }
    }
    
    /**
     * Collect network metrics
     */
    collectNetworkMetrics(timestamp) {
        if (!window.performance || !window.performance.getEntriesByType) return;
        
        // Get navigation timing
        const navigation = window.performance.getEntriesByType('navigation')[0];
        if (navigation) {
            const networkData = {
                dnsLookup: navigation.domainLookupEnd - navigation.domainLookupStart,
                tcpConnect: navigation.connectEnd - navigation.connectStart,
                request: navigation.responseStart - navigation.requestStart,
                response: navigation.responseEnd - navigation.responseStart,
                domLoad: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
                pageLoad: navigation.loadEventEnd - navigation.loadEventStart,
                timestamp
            };
            
            // Only add if we have new data
            const lastNetwork = this.metrics.network[this.metrics.network.length - 1];
            if (!lastNetwork || lastNetwork.timestamp !== timestamp) {
                this.metrics.network.push(networkData);
                
                // Trim history
                if (this.metrics.network.length > this.config.maxMetricsHistory) {
                    this.metrics.network.shift();
                }
            }
        }
        
        // Get resource timing for recent resources
        const resources = window.performance.getEntriesByType('resource');
        const recentResources = resources.filter(resource => 
            timestamp - resource.startTime < this.config.collectionInterval * 2
        );
        
        if (recentResources.length > 0) {
            this.recordCustomMetric('resourceTiming', {
                resources: recentResources.map(resource => ({
                    name: resource.name,
                    duration: resource.duration,
                    size: resource.transferSize || resource.encodedBodySize,
                    type: this.getResourceType(resource.name)
                })),
                timestamp
            });
        }
    }
    
    /**
     * Collect system metrics
     */
    collectSystemMetrics(timestamp) {
        const systemData = {
            timestamp,
            uptime: timestamp - this.metrics.system.startTime,
            userAgent: navigator.userAgent,
            language: navigator.language,
            cookieEnabled: navigator.cookieEnabled,
            onLine: navigator.onLine
        };
        
        // Connection information
        if (navigator.connection) {
            systemData.connection = {
                effectiveType: navigator.connection.effectiveType,
                downlink: navigator.connection.downlink,
                rtt: navigator.connection.rtt,
                saveData: navigator.connection.saveData
            };
        }
        
        // Screen information
        if (screen) {
            systemData.screen = {
                width: screen.width,
                height: screen.height,
                colorDepth: screen.colorDepth,
                pixelDepth: screen.pixelDepth
            };
        }
        
        this.recordCustomMetric('system', systemData);
    }
    
    /**
     * Record custom performance metric
     */
    recordCustomMetric(name, data) {
        if (!this.metrics.custom[name]) {
            this.metrics.custom[name] = [];
        }
        
        this.metrics.custom[name].push({
            ...data,
            timestamp: data.timestamp || Date.now()
        });
        
        // Trim history
        if (this.metrics.custom[name].length > this.config.maxMetricsHistory) {
            this.metrics.custom[name].shift();
        }
    }
    
    /**
     * Mark performance event
     */
    mark(name, metadata = {}) {
        if (window.performance && window.performance.mark) {
            window.performance.mark(name);
        }
        
        this.recordCustomMetric('marks', {
            name,
            metadata,
            timestamp: Date.now()
        });
    }
    
    /**
     * Measure performance between two marks
     */
    measure(name, startMark, endMark) {
        let duration = null;
        
        if (window.performance && window.performance.measure) {
            try {
                window.performance.measure(name, startMark, endMark);
                const measure = window.performance.getEntriesByName(name, 'measure')[0];
                if (measure) {
                    duration = measure.duration;
                }
            } catch (error) {
                console.warn('Performance measure failed:', error);
            }
        }
        
        this.recordCustomMetric('measures', {
            name,
            startMark,
            endMark,
            duration,
            timestamp: Date.now()
        });
        
        return duration;
    }
    
    /**
     * Get performance summary
     */
    getSummary() {
        const summary = {
            timestamp: Date.now(),
            uptime: Date.now() - this.metrics.system.startTime,
            collections: this.metrics.system.totalCollections,
            errors: this.metrics.system.errors
        };
        
        // Memory summary
        if (this.metrics.memory.length > 0) {
            const latestMemory = this.metrics.memory[this.metrics.memory.length - 1];
            const avgMemory = this.metrics.memory.reduce((sum, m) => sum + m.usagePercent, 0) / this.metrics.memory.length;
            
            summary.memory = {
                current: Math.round(latestMemory.usagePercent * 100) / 100,
                average: Math.round(avgMemory * 100) / 100,
                peak: Math.max(...this.metrics.memory.map(m => m.usagePercent))
            };
        }
        
        // User Experience summary
        summary.userExperience = { ...this.metrics.userExperience };
        
        // Custom metrics count
        summary.customMetrics = Object.keys(this.metrics.custom).reduce((acc, key) => {
            acc[key] = this.metrics.custom[key].length;
            return acc;
        }, {});
        
        return summary;
    }
    
    /**
     * Export metrics data
     */
    exportMetrics(format = 'json') {
        const exportData = {
            metadata: {
                exportTime: new Date().toISOString(),
                version: '1.0',
                config: this.config
            },
            metrics: this.metrics
        };
        
        switch (format.toLowerCase()) {
            case 'json':
                return JSON.stringify(exportData, null, 2);
            case 'csv':
                return this.convertToCSV(exportData);
            default:
                return exportData;
        }
    }
    
    /**
     * Convert metrics to CSV format
     */
    convertToCSV(data) {
        const csvLines = [];
        
        // Memory metrics
        if (data.metrics.memory.length > 0) {
            csvLines.push('Memory Metrics');
            csvLines.push('timestamp,used,total,limit,usagePercent');
            data.metrics.memory.forEach(m => {
                csvLines.push(`${m.timestamp},${m.used},${m.total},${m.limit},${m.usagePercent}`);
            });
            csvLines.push('');
        }
        
        // User Experience metrics
        csvLines.push('User Experience Metrics');
        csvLines.push('metric,value,rating,timestamp');
        Object.entries(data.metrics.userExperience).forEach(([key, value]) => {
            csvLines.push(`${key},${value.value},${value.rating},${value.timestamp}`);
        });
        
        return csvLines.join('\n');
    }
    
    /**
     * Trigger performance alert
     */
    triggerAlert(type, message) {
        const alert = {
            type,
            message,
            timestamp: Date.now()
        };
        
        console.warn(`Performance Alert [${type}]: ${message}`);
        
        // Record alert as custom metric
        this.recordCustomMetric('alerts', alert);
        
        // Dispatch custom event
        if (typeof window !== 'undefined') {
            window.dispatchEvent(new CustomEvent('performanceAlert', { detail: alert }));
        }
    }
    
    /**
     * Rate Web Vitals metrics
     */
    rateFCP(value) {
        if (value <= 1800) return 'good';
        if (value <= 3000) return 'needs-improvement';
        return 'poor';
    }
    
    rateLCP(value) {
        if (value <= 2500) return 'good';
        if (value <= 4000) return 'needs-improvement';
        return 'poor';
    }
    
    rateFID(value) {
        if (value <= 100) return 'good';
        if (value <= 300) return 'needs-improvement';
        return 'poor';
    }
    
    rateCLS(value) {
        if (value <= 0.1) return 'good';
        if (value <= 0.25) return 'needs-improvement';
        return 'poor';
    }
    
    /**
     * Get resource type from URL
     */
    getResourceType(url) {
        if (url.match(/\.(css)$/i)) return 'stylesheet';
        if (url.match(/\.(js)$/i)) return 'script';
        if (url.match(/\.(png|jpg|jpeg|gif|svg|webp)$/i)) return 'image';
        if (url.match(/\.(woff|woff2|ttf|eot)$/i)) return 'font';
        return 'other';
    }
    
    /**
     * Clean up resources
     */
    destroy() {
        this.stopCollection();
        
        // Disconnect all observers
        this.observers.forEach(observer => {
            try {
                observer.disconnect();
            } catch (error) {
                console.warn('Error disconnecting observer:', error);
            }
        });
        this.observers.clear();
        
        // Clear metrics
        this.metrics = {
            memory: [],
            network: [],
            userExperience: {},
            custom: {},
            system: {
                startTime: Date.now(),
                totalCollections: 0,
                errors: 0
            }
        };
        
        console.log('PerformanceMonitor destroyed');
    }
}


export default PerformanceMonitor;