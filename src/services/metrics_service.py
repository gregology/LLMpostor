"""
Metrics Service - Server-side performance monitoring and metrics collection

Features:
- Request/response time monitoring
- Memory and CPU usage tracking
- Database operation performance
- WebSocket connection metrics
- Game-specific performance metrics
- Alert system for performance issues
- Metrics aggregation and reporting
"""

import time
import threading
import logging
import psutil
import os
from typing import Dict, List, Any, Optional, Callable, Union
from collections import defaultdict, deque
from datetime import datetime, timedelta
from dataclasses import dataclass
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """Single metric data point."""
    name: str
    value: Union[int, float]
    timestamp: float
    tags: Dict[str, str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}


@dataclass
class Alert:
    """Performance alert."""
    metric_name: str
    threshold: float
    current_value: float
    message: str
    timestamp: float
    severity: str = 'warning'  # info, warning, error, critical


class MetricsCollector:
    """Collects and stores performance metrics."""
    
    def __init__(self, max_points: int = 10000):
        self.max_points = max_points
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_points))
        self.lock = threading.RLock()
        
    def record(self, name: str, value: Union[int, float], tags: Dict[str, str] = None):
        """Record a metric point."""
        point = MetricPoint(name, value, time.time(), tags or {})
        
        with self.lock:
            self.metrics[name].append(point)
    
    def get_recent(self, name: str, seconds: int = 60) -> List[MetricPoint]:
        """Get recent metric points."""
        cutoff_time = time.time() - seconds
        
        with self.lock:
            if name not in self.metrics:
                return []
            
            return [point for point in self.metrics[name] if point.timestamp >= cutoff_time]
    
    def get_average(self, name: str, seconds: int = 60) -> Optional[float]:
        """Get average value for a metric over time period."""
        points = self.get_recent(name, seconds)
        
        if not points:
            return None
        
        return sum(point.value for point in points) / len(points)
    
    def get_percentile(self, name: str, percentile: float, seconds: int = 60) -> Optional[float]:
        """Get percentile value for a metric."""
        points = self.get_recent(name, seconds)
        
        if not points:
            return None
        
        values = sorted([point.value for point in points])
        index = int((percentile / 100) * len(values))
        index = min(index, len(values) - 1)
        
        return values[index]
    
    def clear_old_metrics(self, max_age_seconds: int = 3600):
        """Clear metrics older than specified age."""
        cutoff_time = time.time() - max_age_seconds
        
        with self.lock:
            for name in self.metrics:
                while (self.metrics[name] and 
                       self.metrics[name][0].timestamp < cutoff_time):
                    self.metrics[name].popleft()


class SystemMonitor:
    """Monitors system-level performance metrics."""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        self.process = psutil.Process()
        
    def collect_system_metrics(self):
        """Collect system performance metrics."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=None)
            self.collector.record('system.cpu.usage_percent', cpu_percent)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            self.collector.record('system.memory.usage_percent', memory.percent)
            self.collector.record('system.memory.available_bytes', memory.available)
            self.collector.record('system.memory.used_bytes', memory.used)
            
            # Process-specific metrics
            process_memory = self.process.memory_info()
            self.collector.record('process.memory.rss_bytes', process_memory.rss)
            self.collector.record('process.memory.vms_bytes', process_memory.vms)
            
            process_cpu = self.process.cpu_percent()
            self.collector.record('process.cpu.usage_percent', process_cpu)
            
            # File descriptors (Unix systems)
            if hasattr(self.process, 'num_fds'):
                try:
                    num_fds = self.process.num_fds()
                    self.collector.record('process.file_descriptors', num_fds)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Thread count
            try:
                thread_count = self.process.num_threads()
                self.collector.record('process.threads', thread_count)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
        except Exception as e:
            logger.error(f'Error collecting system metrics: {e}')


class RequestMonitor:
    """Monitors HTTP request performance."""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        self.active_requests = {}
        self.lock = threading.Lock()
    
    def start_request(self, request_id: str, method: str, endpoint: str):
        """Start monitoring a request."""
        with self.lock:
            self.active_requests[request_id] = {
                'method': method,
                'endpoint': endpoint,
                'start_time': time.time()
            }
    
    def end_request(self, request_id: str, status_code: int, response_size: int = 0):
        """End monitoring a request."""
        with self.lock:
            if request_id not in self.active_requests:
                return
            
            request_info = self.active_requests.pop(request_id)
            duration = time.time() - request_info['start_time']
            
            tags = {
                'method': request_info['method'],
                'endpoint': request_info['endpoint'],
                'status': str(status_code)
            }
            
            # Record metrics
            self.collector.record('http.request.duration_seconds', duration, tags)
            self.collector.record('http.request.count', 1, tags)
            
            if response_size > 0:
                self.collector.record('http.response.size_bytes', response_size, tags)
            
            # Record concurrent requests
            self.collector.record('http.requests.active', len(self.active_requests))
    
    @contextmanager
    def monitor_request(self, request_id: str, method: str, endpoint: str):
        """Context manager for request monitoring."""
        self.start_request(request_id, method, endpoint)
        try:
            yield
        finally:
            # Note: end_request should be called separately with status code
            pass


class GameMetricsMonitor:
    """Monitors game-specific performance metrics."""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
    
    def record_room_operation(self, operation: str, duration: float, room_id: str = None):
        """Record room operation performance."""
        tags = {'operation': operation}
        if room_id:
            tags['room_id'] = room_id
        
        self.collector.record('game.room.operation_duration_seconds', duration, tags)
    
    def record_player_action(self, action: str, room_id: str, player_count: int):
        """Record player action metrics."""
        tags = {
            'action': action,
            'room_id': room_id,
            'player_count': str(player_count)
        }
        
        self.collector.record('game.player.action_count', 1, tags)
    
    def record_websocket_event(self, event_type: str, duration: float, room_id: str = None):
        """Record WebSocket event performance."""
        tags = {'event_type': event_type}
        if room_id:
            tags['room_id'] = room_id
        
        self.collector.record('game.websocket.event_duration_seconds', duration, tags)
        self.collector.record('game.websocket.event_count', 1, tags)
    
    def record_room_count(self, active_rooms: int, total_players: int):
        """Record current room and player counts."""
        self.collector.record('game.rooms.active_count', active_rooms)
        self.collector.record('game.players.total_count', total_players)


class AlertManager:
    """Manages performance alerts."""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        self.alert_rules: Dict[str, Dict] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.lock = threading.RLock()
        
    def add_rule(self, metric_name: str, threshold: float, comparison: str = 'gt', 
                 severity: str = 'warning', message: str = None):
        """Add an alert rule."""
        if message is None:
            message = f'{metric_name} {comparison} {threshold}'
        
        with self.lock:
            self.alert_rules[metric_name] = {
                'threshold': threshold,
                'comparison': comparison,  # 'gt', 'lt', 'eq'
                'severity': severity,
                'message': message
            }
    
    def check_alerts(self):
        """Check all metrics against alert rules."""
        with self.lock:
            for metric_name, rule in self.alert_rules.items():
                current_value = self.collector.get_average(metric_name, 60)
                
                if current_value is None:
                    continue
                
                alert_key = f"{metric_name}_{rule['comparison']}_{rule['threshold']}"
                should_alert = False
                
                if rule['comparison'] == 'gt' and current_value > rule['threshold']:
                    should_alert = True
                elif rule['comparison'] == 'lt' and current_value < rule['threshold']:
                    should_alert = True
                elif rule['comparison'] == 'eq' and abs(current_value - rule['threshold']) < 0.01:
                    should_alert = True
                
                if should_alert:
                    if alert_key not in self.active_alerts:
                        alert = Alert(
                            metric_name=metric_name,
                            threshold=rule['threshold'],
                            current_value=current_value,
                            message=rule['message'],
                            timestamp=time.time(),
                            severity=rule['severity']
                        )
                        
                        self.active_alerts[alert_key] = alert
                        self.alert_history.append(alert)
                        
                        logger.warning(f'Performance Alert: {alert.message} (current: {current_value:.2f})')
                else:
                    # Clear alert if it was active
                    if alert_key in self.active_alerts:
                        del self.active_alerts[alert_key]
    
    def get_active_alerts(self) -> List[Alert]:
        """Get currently active alerts."""
        with self.lock:
            return list(self.active_alerts.values())
    
    def get_alert_history(self, hours: int = 24) -> List[Alert]:
        """Get alert history for specified time period."""
        cutoff_time = time.time() - (hours * 3600)
        
        with self.lock:
            return [alert for alert in self.alert_history 
                   if alert.timestamp >= cutoff_time]


class MetricsService:
    """Main metrics service."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Initialize components
        max_points = self.config.get('max_metric_points', 10000)
        self.collector = MetricsCollector(max_points)
        
        self.system_monitor = SystemMonitor(self.collector)
        self.request_monitor = RequestMonitor(self.collector)
        self.game_monitor = GameMetricsMonitor(self.collector)
        self.alert_manager = AlertManager(self.collector)
        
        # Background collection
        self.collection_interval = self.config.get('collection_interval', 30)  # seconds
        self.collection_thread = None
        self.shutdown_event = threading.Event()
        
        # Setup default alert rules
        self._setup_default_alerts()
        
        # Start background collection
        self.start_collection()
        
        logger.info('MetricsService initialized')
    
    def _setup_default_alerts(self):
        """Set up default performance alert rules."""
        # System alerts
        self.alert_manager.add_rule(
            'system.cpu.usage_percent', 80, 'gt', 'warning',
            'High CPU usage detected'
        )
        
        self.alert_manager.add_rule(
            'system.memory.usage_percent', 85, 'gt', 'warning',
            'High memory usage detected'
        )
        
        # Process alerts
        self.alert_manager.add_rule(
            'process.memory.rss_bytes', 1024 * 1024 * 1024, 'gt', 'warning',  # 1GB
            'Process memory usage high'
        )
        
        # Request alerts
        self.alert_manager.add_rule(
            'http.request.duration_seconds', 2.0, 'gt', 'warning',
            'Slow HTTP requests detected'
        )
    
    def start_collection(self):
        """Start background metrics collection."""
        if self.collection_thread and self.collection_thread.is_alive():
            return
        
        def collection_worker():
            while not self.shutdown_event.wait(self.collection_interval):
                try:
                    self.system_monitor.collect_system_metrics()
                    self.alert_manager.check_alerts()
                    self.collector.clear_old_metrics()
                except Exception as e:
                    logger.error(f'Error in metrics collection: {e}')
        
        self.collection_thread = threading.Thread(target=collection_worker, name='MetricsCollection')
        self.collection_thread.daemon = True
        self.collection_thread.start()
        
        logger.info('Metrics collection started')
    
    def stop_collection(self):
        """Stop background metrics collection."""
        self.shutdown_event.set()
        
        if self.collection_thread and self.collection_thread.is_alive():
            self.collection_thread.join(timeout=5)
        
        logger.info('Metrics collection stopped')
    
    def record_metric(self, name: str, value: Union[int, float], tags: Dict[str, str] = None):
        """Record a custom metric."""
        self.collector.record(name, value, tags)
    
    @contextmanager
    def time_operation(self, operation_name: str, tags: Dict[str, str] = None):
        """Time an operation and record the duration."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.collector.record(f'operation.{operation_name}.duration_seconds', duration, tags)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of current metrics."""
        summary = {
            'timestamp': datetime.utcnow().isoformat(),
            'system': {},
            'process': {},
            'http': {},
            'game': {},
            'alerts': {
                'active': len(self.alert_manager.get_active_alerts()),
                'total_today': len(self.alert_manager.get_alert_history(24))
            }
        }
        
        # System metrics
        for metric in ['system.cpu.usage_percent', 'system.memory.usage_percent']:
            value = self.collector.get_average(metric, 60)
            if value is not None:
                key = metric.split('.')[-1]  # Get last part of metric name
                summary['system'][key] = round(value, 2)
        
        # Process metrics
        for metric in ['process.memory.rss_bytes', 'process.cpu.usage_percent']:
            value = self.collector.get_average(metric, 60)
            if value is not None:
                key = metric.split('.')[-1]
                if key == 'rss_bytes':
                    key = 'memory_mb'
                    value = value / (1024 * 1024)  # Convert to MB
                summary['process'][key] = round(value, 2)
        
        # HTTP metrics
        request_duration = self.collector.get_average('http.request.duration_seconds', 300)
        if request_duration is not None:
            summary['http']['avg_response_time'] = round(request_duration * 1000, 2)  # Convert to ms
        
        request_count = len(self.collector.get_recent('http.request.count', 60))
        summary['http']['requests_per_minute'] = request_count
        
        # Game metrics
        active_rooms = self.collector.get_recent('game.rooms.active_count', 60)
        if active_rooms:
            summary['game']['active_rooms'] = int(active_rooms[-1].value)
        
        total_players = self.collector.get_recent('game.players.total_count', 60)
        if total_players:
            summary['game']['total_players'] = int(total_players[-1].value)
        
        return summary
    
    def get_detailed_metrics(self, metric_name: str, hours: int = 1) -> List[Dict]:
        """Get detailed metrics for a specific metric."""
        seconds = hours * 3600
        points = self.collector.get_recent(metric_name, seconds)
        
        return [
            {
                'timestamp': point.timestamp,
                'value': point.value,
                'tags': point.tags
            }
            for point in points
        ]
    
    def export_metrics(self, format: str = 'json', hours: int = 1) -> str:
        """Export metrics in specified format."""
        metrics_data = {}
        
        # Get all metric names
        with self.collector.lock:
            metric_names = list(self.collector.metrics.keys())
        
        for name in metric_names:
            metrics_data[name] = self.get_detailed_metrics(name, hours)
        
        if format.lower() == 'json':
            import json
            return json.dumps({
                'export_time': datetime.utcnow().isoformat(),
                'time_range_hours': hours,
                'metrics': metrics_data
            }, indent=2)
        else:
            raise ValueError(f'Unsupported export format: {format}')
    
    def shutdown(self):
        """Shutdown the metrics service."""
        logger.info('Shutting down MetricsService...')
        
        self.stop_collection()
        
        # Clear all metrics
        with self.collector.lock:
            self.collector.metrics.clear()
        
        logger.info('MetricsService shutdown complete')


# Global metrics instance
_metrics_instance: Optional[MetricsService] = None


def get_metrics_service(config: Optional[Dict[str, Any]] = None) -> MetricsService:
    """Get global metrics service instance."""
    global _metrics_instance
    
    if _metrics_instance is None:
        _metrics_instance = MetricsService(config)
    
    return _metrics_instance