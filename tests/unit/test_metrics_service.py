"""
Metrics Service Unit Tests
Tests for the performance monitoring and metrics collection service.
"""

import pytest
import sys
import os
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from collections import deque

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Skip tests if psutil is not available
try:
    import psutil
    from src.services.metrics_service import (
        MetricPoint, Alert, MetricsCollector, SystemMonitor, 
        RequestMonitor, GameMetricsMonitor, AlertManager
    )
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    pytest.skip("psutil not available", allow_module_level=True)


class TestMetricPoint:
    """Test MetricPoint dataclass"""

    def test_metric_point_creation(self):
        """Test basic metric point creation"""
        timestamp = time.time()
        point = MetricPoint("test_metric", 42.0, timestamp)
        
        assert point.name == "test_metric"
        assert point.value == 42.0
        assert point.timestamp == timestamp
        assert point.tags == {}

    def test_metric_point_with_tags(self):
        """Test metric point creation with tags"""
        timestamp = time.time()
        tags = {"environment": "test", "service": "llmpostor"}
        point = MetricPoint("test_metric", 100, timestamp, tags)
        
        assert point.tags == tags

    def test_metric_point_post_init(self):
        """Test post-init handling of None tags"""
        point = MetricPoint("test", 1.0, time.time(), None)
        assert point.tags == {}


class TestAlert:
    """Test Alert dataclass"""

    def test_alert_creation(self):
        """Test basic alert creation"""
        timestamp = time.time()
        alert = Alert(
            metric_name="cpu_usage",
            threshold=80.0,
            current_value=95.0,
            message="CPU usage high",
            timestamp=timestamp,
            severity="warning"
        )
        
        assert alert.metric_name == "cpu_usage"
        assert alert.threshold == 80.0
        assert alert.current_value == 95.0
        assert alert.message == "CPU usage high"
        assert alert.timestamp == timestamp
        assert alert.severity == "warning"

    def test_alert_default_severity(self):
        """Test alert with default severity"""
        alert = Alert(
            metric_name="test",
            threshold=10.0,
            current_value=20.0,
            message="Test alert",
            timestamp=time.time()
        )
        assert alert.severity == "warning"


class TestMetricsCollector:
    """Test MetricsCollector functionality"""

    def setup_method(self):
        """Setup collector for each test"""
        self.collector = MetricsCollector(max_points=100)

    def test_initialization(self):
        """Test collector initialization"""
        assert self.collector.max_points == 100
        assert len(self.collector.metrics) == 0

    def test_record_metric(self):
        """Test recording a basic metric"""
        self.collector.record("test_metric", 42.0)
        
        assert "test_metric" in self.collector.metrics
        assert len(self.collector.metrics["test_metric"]) == 1
        
        point = self.collector.metrics["test_metric"][0]
        assert point.name == "test_metric"
        assert point.value == 42.0
        assert point.tags == {}

    def test_record_metric_with_tags(self):
        """Test recording metric with tags"""
        tags = {"method": "GET", "status": "200"}
        self.collector.record("http_requests", 1, tags)
        
        point = self.collector.metrics["http_requests"][0]
        assert point.tags == tags

    def test_record_multiple_metrics(self):
        """Test recording multiple metrics"""
        self.collector.record("metric1", 10)
        self.collector.record("metric1", 20)
        self.collector.record("metric2", 30)
        
        assert len(self.collector.metrics["metric1"]) == 2
        assert len(self.collector.metrics["metric2"]) == 1
        
        assert self.collector.metrics["metric1"][0].value == 10
        assert self.collector.metrics["metric1"][1].value == 20
        assert self.collector.metrics["metric2"][0].value == 30

    def test_max_points_limit(self):
        """Test that max_points limit is enforced"""
        collector = MetricsCollector(max_points=3)
        
        # Add more points than the limit
        for i in range(5):
            collector.record("test_metric", i)
        
        # Should only keep the last 3 points
        assert len(collector.metrics["test_metric"]) == 3
        values = [point.value for point in collector.metrics["test_metric"]]
        assert values == [2, 3, 4]  # Should have the last 3 values

    def test_get_recent_within_timeframe(self):
        """Test getting recent metrics within timeframe"""
        current_time = time.time()
        
        # Add some points with specific timestamps
        self.collector.record("test_metric", 10)
        time.sleep(0.1)  # Small delay
        self.collector.record("test_metric", 20)
        
        # Get recent points (should get both)
        recent = self.collector.get_recent("test_metric", 60)
        assert len(recent) == 2
        assert recent[0].value == 10
        assert recent[1].value == 20

    def test_get_recent_outside_timeframe(self):
        """Test getting recent metrics outside timeframe"""
        # Manually create old points
        old_time = time.time() - 120  # 2 minutes ago
        old_point = MetricPoint("test_metric", 10, old_time)
        self.collector.metrics["test_metric"].append(old_point)
        
        # Add recent point
        self.collector.record("test_metric", 20)
        
        # Get recent points (1 minute window)
        recent = self.collector.get_recent("test_metric", 60)
        assert len(recent) == 1
        assert recent[0].value == 20

    def test_get_recent_nonexistent_metric(self):
        """Test getting recent metrics for nonexistent metric"""
        recent = self.collector.get_recent("nonexistent", 60)
        assert recent == []

    def test_get_average_with_data(self):
        """Test getting average value with data"""
        self.collector.record("test_metric", 10)
        self.collector.record("test_metric", 20)
        self.collector.record("test_metric", 30)
        
        average = self.collector.get_average("test_metric", 60)
        assert average == 20.0

    def test_get_average_no_data(self):
        """Test getting average with no data"""
        average = self.collector.get_average("nonexistent", 60)
        assert average is None

    def test_get_percentile_with_data(self):
        """Test getting percentile value with data"""
        # Add values 1-10
        for i in range(1, 11):
            self.collector.record("test_metric", i)
        
        # Test different percentiles
        p50 = self.collector.get_percentile("test_metric", 50, 60)
        p90 = self.collector.get_percentile("test_metric", 90, 60)
        p99 = self.collector.get_percentile("test_metric", 99, 60)
        
        assert p50 == 5  # 50th percentile
        assert p90 == 9  # 90th percentile
        assert p99 == 10  # 99th percentile (clamped to max index)

    def test_get_percentile_no_data(self):
        """Test getting percentile with no data"""
        percentile = self.collector.get_percentile("nonexistent", 50, 60)
        assert percentile is None

    def test_clear_old_metrics(self):
        """Test clearing old metrics"""
        current_time = time.time()
        
        # Add old points
        old_time = current_time - 7200  # 2 hours ago
        old_point = MetricPoint("test_metric", 10, old_time)
        self.collector.metrics["test_metric"].append(old_point)
        
        # Add recent point
        self.collector.record("test_metric", 20)
        
        # Clear metrics older than 1 hour
        self.collector.clear_old_metrics(max_age_seconds=3600)
        
        # Should only have the recent point
        assert len(self.collector.metrics["test_metric"]) == 1
        assert self.collector.metrics["test_metric"][0].value == 20


class TestSystemMonitor:
    """Test SystemMonitor functionality"""

    def setup_method(self):
        """Setup system monitor for each test"""
        self.collector = MetricsCollector()
        
        # Mock psutil to avoid system dependency
        with patch('src.services.metrics_service.psutil') as mock_psutil:
            mock_process = Mock()
            mock_psutil.Process.return_value = mock_process
            
            self.monitor = SystemMonitor(self.collector)

    @patch('src.services.metrics_service.psutil')
    def test_collect_system_metrics_success(self, mock_psutil):
        """Test successful system metrics collection"""
        # Mock psutil functions
        mock_psutil.cpu_percent.return_value = 25.5
        mock_memory = Mock()
        mock_memory.percent = 60.0
        mock_memory.available = 4000000000
        mock_memory.used = 2000000000
        mock_psutil.virtual_memory.return_value = mock_memory
        
        # Mock process metrics
        mock_memory_info = Mock()
        mock_memory_info.rss = 100000000
        mock_memory_info.vms = 200000000
        
        self.monitor.process.memory_info.return_value = mock_memory_info
        self.monitor.process.cpu_percent.return_value = 15.0
        self.monitor.process.num_threads.return_value = 5
        
        # Mock num_fds (Unix-specific)
        self.monitor.process.num_fds = Mock(return_value=10)
        
        # Collect metrics
        self.monitor.collect_system_metrics()
        
        # Verify metrics were recorded
        assert "system.cpu.usage_percent" in self.collector.metrics
        assert "system.memory.usage_percent" in self.collector.metrics
        assert "system.memory.available_bytes" in self.collector.metrics
        assert "system.memory.used_bytes" in self.collector.metrics
        assert "process.memory.rss_bytes" in self.collector.metrics
        assert "process.memory.vms_bytes" in self.collector.metrics
        assert "process.cpu.usage_percent" in self.collector.metrics
        assert "process.threads" in self.collector.metrics
        assert "process.file_descriptors" in self.collector.metrics
        
        # Verify values
        assert self.collector.metrics["system.cpu.usage_percent"][0].value == 25.5
        assert self.collector.metrics["system.memory.usage_percent"][0].value == 60.0

    @patch('src.services.metrics_service.psutil')
    @patch('src.services.metrics_service.logger')
    def test_collect_system_metrics_handles_exception(self, mock_logger, mock_psutil):
        """Test system metrics collection handles exceptions"""
        mock_psutil.cpu_percent.side_effect = Exception("CPU error")
        
        # Should not raise exception
        self.monitor.collect_system_metrics()
        
        # Should log the error
        mock_logger.error.assert_called_once()

    @patch('src.services.metrics_service.psutil')
    def test_collect_system_metrics_without_fds(self, mock_psutil):
        """Test system metrics collection when num_fds is not available"""
        # Remove num_fds attribute to simulate Windows
        if hasattr(self.monitor.process, 'num_fds'):
            delattr(self.monitor.process, 'num_fds')
        
        # Mock other psutil functions
        mock_psutil.cpu_percent.return_value = 25.5
        mock_memory = Mock()
        mock_memory.percent = 60.0
        mock_memory.available = 4000000000
        mock_memory.used = 2000000000
        mock_psutil.virtual_memory.return_value = mock_memory
        
        mock_memory_info = Mock()
        mock_memory_info.rss = 100000000
        mock_memory_info.vms = 200000000
        self.monitor.process.memory_info.return_value = mock_memory_info
        self.monitor.process.cpu_percent.return_value = 15.0
        self.monitor.process.num_threads.return_value = 5
        
        # Should not raise exception
        self.monitor.collect_system_metrics()
        
        # Should not have file_descriptors metric
        assert "process.file_descriptors" not in self.collector.metrics


class TestRequestMonitor:
    """Test RequestMonitor functionality"""

    def setup_method(self):
        """Setup request monitor for each test"""
        self.collector = MetricsCollector()
        self.monitor = RequestMonitor(self.collector)

    def test_request_monitoring_lifecycle(self):
        """Test complete request monitoring lifecycle"""
        request_id = "req123"
        method = "GET"
        endpoint = "/api/rooms"
        status_code = 200
        response_size = 1024
        
        # Start monitoring
        self.monitor.start_request(request_id, method, endpoint)
        assert request_id in self.monitor.active_requests
        
        # Simulate request processing time
        time.sleep(0.01)
        
        # End monitoring
        self.monitor.end_request(request_id, status_code, response_size)
        assert request_id not in self.monitor.active_requests
        
        # Verify metrics were recorded
        assert "http.request.duration_seconds" in self.collector.metrics
        assert "http.request.count" in self.collector.metrics
        assert "http.response.size_bytes" in self.collector.metrics
        assert "http.requests.active" in self.collector.metrics
        
        # Verify tags
        duration_point = self.collector.metrics["http.request.duration_seconds"][0]
        assert duration_point.tags["method"] == method
        assert duration_point.tags["endpoint"] == endpoint
        assert duration_point.tags["status"] == str(status_code)

    def test_end_nonexistent_request(self):
        """Test ending a request that wasn't started"""
        # Should not raise exception
        self.monitor.end_request("nonexistent", 404)
        
        # Should not record metrics
        assert len(self.collector.metrics) == 0

    def test_monitor_request_context_manager(self):
        """Test request monitoring context manager"""
        request_id = "req456"
        method = "POST"
        endpoint = "/api/join"
        
        with self.monitor.monitor_request(request_id, method, endpoint):
            assert request_id in self.monitor.active_requests
            # Simulate some work
            time.sleep(0.001)
        
        # Should still be in active requests (end_request not called automatically)
        assert request_id in self.monitor.active_requests

    def test_concurrent_requests(self):
        """Test monitoring multiple concurrent requests"""
        requests = [
            ("req1", "GET", "/api/rooms"),
            ("req2", "POST", "/api/join"),
            ("req3", "GET", "/api/status")
        ]
        
        # Start all requests
        for req_id, method, endpoint in requests:
            self.monitor.start_request(req_id, method, endpoint)
        
        assert len(self.monitor.active_requests) == 3
        
        # End requests
        for req_id, _, _ in requests:
            self.monitor.end_request(req_id, 200)
        
        assert len(self.monitor.active_requests) == 0
        
        # Should have recorded 3 request count metrics
        count_metrics = self.collector.metrics["http.request.count"]
        assert len(count_metrics) == 3


class TestGameMetricsMonitor:
    """Test GameMetricsMonitor functionality"""

    def setup_method(self):
        """Setup game metrics monitor for each test"""
        self.collector = MetricsCollector()
        self.monitor = GameMetricsMonitor(self.collector)

    def test_record_room_operation(self):
        """Test recording room operation metrics"""
        operation = "create_room"
        duration = 0.05
        room_id = "room123"
        
        self.monitor.record_room_operation(operation, duration, room_id)
        
        assert "game.room.operation_duration_seconds" in self.collector.metrics
        point = self.collector.metrics["game.room.operation_duration_seconds"][0]
        assert point.value == duration
        assert point.tags["operation"] == operation
        assert point.tags["room_id"] == room_id

    def test_record_room_operation_without_room_id(self):
        """Test recording room operation without room_id"""
        operation = "cleanup"
        duration = 0.02
        
        self.monitor.record_room_operation(operation, duration)
        
        point = self.collector.metrics["game.room.operation_duration_seconds"][0]
        assert point.tags["operation"] == operation
        assert "room_id" not in point.tags

    def test_record_player_action(self):
        """Test recording player action metrics"""
        action = "submit_response"
        room_id = "room456"
        player_count = 4
        
        self.monitor.record_player_action(action, room_id, player_count)
        
        assert "game.player.action_count" in self.collector.metrics
        point = self.collector.metrics["game.player.action_count"][0]
        assert point.value == 1
        assert point.tags["action"] == action
        assert point.tags["room_id"] == room_id
        assert point.tags["player_count"] == str(player_count)

    def test_record_websocket_event(self):
        """Test recording WebSocket event metrics"""
        event_type = "join_room"
        duration = 0.001
        room_id = "room789"
        
        self.monitor.record_websocket_event(event_type, duration, room_id)
        
        assert "game.websocket.event_duration_seconds" in self.collector.metrics
        assert "game.websocket.event_count" in self.collector.metrics
        
        duration_point = self.collector.metrics["game.websocket.event_duration_seconds"][0]
        count_point = self.collector.metrics["game.websocket.event_count"][0]
        
        assert duration_point.value == duration
        assert count_point.value == 1
        assert duration_point.tags["event_type"] == event_type
        assert duration_point.tags["room_id"] == room_id

    def test_record_room_count(self):
        """Test recording room and player counts"""
        active_rooms = 10
        total_players = 25
        
        self.monitor.record_room_count(active_rooms, total_players)
        
        assert "game.rooms.active_count" in self.collector.metrics
        assert "game.players.total_count" in self.collector.metrics
        
        rooms_point = self.collector.metrics["game.rooms.active_count"][0]
        players_point = self.collector.metrics["game.players.total_count"][0]
        
        assert rooms_point.value == active_rooms
        assert players_point.value == total_players


class TestAlertManager:
    """Test AlertManager functionality"""

    def setup_method(self):
        """Setup alert manager for each test"""
        self.collector = MetricsCollector()
        self.alert_manager = AlertManager(self.collector)

    def test_add_rule(self):
        """Test adding alert rules"""
        metric_name = "cpu_usage"
        threshold = 80.0
        
        self.alert_manager.add_rule(metric_name, threshold, "gt", "warning")
        
        assert metric_name in self.alert_manager.alert_rules
        rule = self.alert_manager.alert_rules[metric_name]
        assert rule["threshold"] == threshold
        assert rule["comparison"] == "gt"
        assert rule["severity"] == "warning"

    def test_add_rule_with_custom_message(self):
        """Test adding alert rule with custom message"""
        metric_name = "memory_usage"
        threshold = 90.0
        message = "Memory usage is critically high"
        
        self.alert_manager.add_rule(metric_name, threshold, "gt", "critical", message)
        
        rule = self.alert_manager.alert_rules[metric_name]
        assert rule["message"] == message

    def test_add_rule_default_message(self):
        """Test adding alert rule with default message"""
        metric_name = "disk_usage"
        threshold = 85.0
        
        self.alert_manager.add_rule(metric_name, threshold, "gt")
        
        rule = self.alert_manager.alert_rules[metric_name]
        assert rule["message"] == "disk_usage gt 85.0"

    def test_check_alerts_trigger_gt(self):
        """Test alert triggering with greater-than comparison"""
        metric_name = "cpu_usage"
        threshold = 80.0
        
        # Add rule
        self.alert_manager.add_rule(metric_name, threshold, "gt", "warning")
        
        # Add metrics that exceed threshold
        self.collector.record(metric_name, 85.0)
        self.collector.record(metric_name, 90.0)
        
        # Check alerts
        self.alert_manager.check_alerts()
        
        # Should have triggered alert
        assert len(self.alert_manager.active_alerts) == 1
        alert_key = f"{metric_name}_gt_{threshold}"
        assert alert_key in self.alert_manager.active_alerts

    def test_check_alerts_trigger_lt(self):
        """Test alert triggering with less-than comparison"""
        metric_name = "available_memory"
        threshold = 100.0
        
        # Add rule
        self.alert_manager.add_rule(metric_name, threshold, "lt", "critical")
        
        # Add metrics below threshold
        self.collector.record(metric_name, 50.0)
        
        # Check alerts
        self.alert_manager.check_alerts()
        
        # Should have triggered alert
        assert len(self.alert_manager.active_alerts) == 1

    def test_check_alerts_no_trigger(self):
        """Test alerts not triggering when threshold not exceeded"""
        metric_name = "cpu_usage"
        threshold = 80.0
        
        # Add rule
        self.alert_manager.add_rule(metric_name, threshold, "gt")
        
        # Add metrics below threshold
        self.collector.record(metric_name, 70.0)
        self.collector.record(metric_name, 75.0)
        
        # Check alerts
        self.alert_manager.check_alerts()
        
        # Should not have triggered alert
        assert len(self.alert_manager.active_alerts) == 0

    def test_check_alerts_no_data(self):
        """Test alert checking with no metric data"""
        metric_name = "nonexistent_metric"
        threshold = 50.0
        
        # Add rule for nonexistent metric
        self.alert_manager.add_rule(metric_name, threshold, "gt")
        
        # Check alerts
        self.alert_manager.check_alerts()
        
        # Should not trigger alerts
        assert len(self.alert_manager.active_alerts) == 0


class TestMetricsServiceThreadSafety:
    """Test thread safety of metrics components"""

    def test_collector_thread_safety(self):
        """Test MetricsCollector thread safety"""
        collector = MetricsCollector()
        
        def worker(thread_id):
            for i in range(100):
                collector.record(f"metric_{thread_id}", i)
        
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have 5 metrics, each with 100 points
        assert len(collector.metrics) == 5
        for i in range(5):
            assert len(collector.metrics[f"metric_{i}"]) == 100

    def test_request_monitor_thread_safety(self):
        """Test RequestMonitor thread safety"""
        collector = MetricsCollector()
        monitor = RequestMonitor(collector)
        
        def worker(thread_id):
            for i in range(50):
                req_id = f"req_{thread_id}_{i}"
                monitor.start_request(req_id, "GET", "/api/test")
                time.sleep(0.001)  # Simulate processing
                monitor.end_request(req_id, 200)
        
        threads = []
        for i in range(3):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have recorded metrics from all threads
        assert "http.request.count" in collector.metrics
        # Should have 150 requests total (3 threads × 50 requests)
        assert len(collector.metrics["http.request.count"]) == 150