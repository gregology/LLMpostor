"""
Database Optimizer - Performance optimization for data operations

Since the current application uses in-memory storage, this service provides:
- Query optimization patterns
- Data structure optimization
- Index simulation for fast lookups  
- Connection pooling simulation
- Batch operation optimization
- Memory-efficient data structures
"""

import threading
import time
import logging
from typing import Dict, List, Any, Optional, Callable, Set, Tuple
from collections import defaultdict, OrderedDict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class IndexManager:
    """Manages in-memory indexes for fast data access."""
    
    def __init__(self):
        self.indexes: Dict[str, Dict[str, Set]] = defaultdict(lambda: defaultdict(set))
        self.lock = threading.RLock()
        
    def add_to_index(self, index_name: str, key: str, item_id: str):
        """Add item to index."""
        with self.lock:
            self.indexes[index_name][key].add(item_id)
    
    def remove_from_index(self, index_name: str, key: str, item_id: str):
        """Remove item from index."""
        with self.lock:
            if key in self.indexes[index_name]:
                self.indexes[index_name][key].discard(item_id)
                if not self.indexes[index_name][key]:
                    del self.indexes[index_name][key]
    
    def find_by_index(self, index_name: str, key: str) -> Set[str]:
        """Find items by index key."""
        with self.lock:
            return self.indexes[index_name].get(key, set()).copy()
    
    def clear_index(self, index_name: str):
        """Clear entire index."""
        with self.lock:
            self.indexes[index_name].clear()


class QueryOptimizer:
    """Optimizes data queries and operations."""
    
    def __init__(self):
        self.query_cache = OrderedDict()
        self.max_cache_size = 1000
        self.query_stats = defaultdict(lambda: {'count': 0, 'avg_time': 0})
        self.lock = threading.RLock()
        
    def cached_query(self, query_key: str, query_func: Callable, ttl: int = 300) -> Any:
        """Execute query with caching."""
        with self.lock:
            # Check cache first
            if query_key in self.query_cache:
                cached_data, timestamp = self.query_cache[query_key]
                if time.time() - timestamp < ttl:
                    # Move to end (LRU)
                    self.query_cache.move_to_end(query_key)
                    return cached_data
                else:
                    del self.query_cache[query_key]
        
        # Execute query
        start_time = time.time()
        result = query_func()
        execution_time = time.time() - start_time
        
        with self.lock:
            # Cache result
            self.query_cache[query_key] = (result, time.time())
            
            # Maintain cache size
            if len(self.query_cache) > self.max_cache_size:
                self.query_cache.popitem(last=False)
            
            # Update stats
            stats = self.query_stats[query_key]
            stats['count'] += 1
            stats['avg_time'] = (stats['avg_time'] * (stats['count'] - 1) + execution_time) / stats['count']
        
        return result
    
    def get_query_stats(self) -> Dict:
        """Get query performance statistics."""
        with self.lock:
            return dict(self.query_stats)


class DataStructureOptimizer:
    """Optimizes data structures for performance."""
    
    @staticmethod
    def optimize_room_structure(room_data: Dict) -> Dict:
        """Optimize room data structure for performance."""
        # Create indexed player lookup
        if 'players' in room_data:
            players = room_data['players']
            
            # Add player index by socket_id for fast lookups
            if 'player_index' not in room_data:
                room_data['player_index'] = {}
            
            for player_id, player in players.items():
                if 'socket_id' in player:
                    room_data['player_index'][player['socket_id']] = player_id
        
        # Pre-compute frequently accessed aggregations
        if 'game_state' in room_data:
            game_state = room_data['game_state']
            
            # Cache response count
            if 'responses' in game_state:
                game_state['response_count'] = len(game_state['responses'])
            
            # Cache guess count
            if 'guesses' in game_state:
                game_state['guess_count'] = len(game_state['guesses'])
            
            # Pre-compute connected players
            if 'players' in room_data:
                connected_count = sum(1 for p in room_data['players'].values() if p.get('connected', False))
                room_data['connected_count'] = connected_count
        
        return room_data
    
    @staticmethod
    def optimize_player_data(players: Dict[str, Dict]) -> Dict[str, Dict]:
        """Optimize player data structures."""
        optimized = {}
        
        for player_id, player_data in players.items():
            # Ensure required fields have defaults
            optimized_player = {
                'player_id': player_id,
                'name': player_data.get('name', 'Unknown'),
                'score': player_data.get('score', 0),
                'connected': player_data.get('connected', False),
                'socket_id': player_data.get('socket_id'),
                'joined_at': player_data.get('joined_at', datetime.utcnow().isoformat()),
                'last_activity': player_data.get('last_activity', datetime.utcnow().isoformat())
            }
            
            # Add computed fields
            optimized_player['is_active'] = (
                optimized_player['connected'] and 
                datetime.fromisoformat(optimized_player['last_activity']) > 
                datetime.utcnow() - timedelta(minutes=5)
            )
            
            optimized[player_id] = optimized_player
        
        return optimized


class BatchProcessor:
    """Optimizes batch operations for better performance."""
    
    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
        self.pending_operations: List[Tuple[str, Callable, tuple, dict]] = []
        self.lock = threading.Lock()
        
    def add_operation(self, op_type: str, func: Callable, args: tuple = (), kwargs: dict = None):
        """Add operation to batch queue."""
        kwargs = kwargs or {}
        
        with self.lock:
            self.pending_operations.append((op_type, func, args, kwargs))
            
            # Auto-execute when batch is full
            if len(self.pending_operations) >= self.batch_size:
                self._execute_batch()
    
    def flush(self) -> List[Any]:
        """Execute all pending operations."""
        with self.lock:
            if self.pending_operations:
                return self._execute_batch()
            return []
    
    def _execute_batch(self) -> List[Any]:
        """Execute batch of operations."""
        results = []
        operations = self.pending_operations.copy()
        self.pending_operations.clear()
        
        # Group operations by type for optimization
        grouped_ops = defaultdict(list)
        for op_type, func, args, kwargs in operations:
            grouped_ops[op_type].append((func, args, kwargs))
        
        # Execute grouped operations
        for op_type, ops in grouped_ops.items():
            for func, args, kwargs in ops:
                try:
                    result = func(*args, **kwargs)
                    results.append(result)
                except Exception as e:
                    logger.error(f'Batch operation error ({op_type}): {e}')
                    results.append(None)
        
        return results


class DatabaseOptimizer:
    """Main database optimization service."""
    
    def __init__(self):
        self.index_manager = IndexManager()
        self.query_optimizer = QueryOptimizer() 
        self.data_optimizer = DataStructureOptimizer()
        self.batch_processor = BatchProcessor()
        
        # Performance monitoring
        self.operation_times = defaultdict(list)
        self.lock = threading.RLock()
        
        logger.info('DatabaseOptimizer initialized')
    
    def optimize_room_operations(self, room_manager):
        """Optimize room manager operations."""
        
        # Create indexes for common queries
        def rebuild_room_indexes():
            """Rebuild all room indexes."""
            self.index_manager.clear_index('rooms_by_player')
            self.index_manager.clear_index('rooms_by_phase')
            
            for room_id, room_data in room_manager._rooms.items():
                # Index by players
                for player_id in room_data.get('players', {}):
                    self.index_manager.add_to_index('rooms_by_player', player_id, room_id)
                
                # Index by game phase
                phase = room_data.get('game_state', {}).get('phase', 'unknown')
                self.index_manager.add_to_index('rooms_by_phase', phase, room_id)
        
        # Initial index build
        rebuild_room_indexes()
        
        # Optimize room data structures
        for room_id in list(room_manager._rooms.keys()):
            room_data = room_manager._rooms.get(room_id)
            if room_data:
                room_manager._rooms[room_id] = self.data_optimizer.optimize_room_structure(room_data)
    
    def get_rooms_by_player(self, player_id: str) -> Set[str]:
        """Get all rooms containing a specific player."""
        return self.index_manager.find_by_index('rooms_by_player', player_id)
    
    def get_rooms_by_phase(self, phase: str) -> Set[str]:
        """Get all rooms in a specific phase."""
        return self.index_manager.find_by_index('rooms_by_phase', phase)
    
    def update_room_indexes(self, room_id: str, room_data: Dict):
        """Update indexes when room data changes."""
        # Update player indexes
        for player_id in room_data.get('players', {}):
            self.index_manager.add_to_index('rooms_by_player', player_id, room_id)
        
        # Update phase index
        phase = room_data.get('game_state', {}).get('phase', 'unknown')
        self.index_manager.add_to_index('rooms_by_phase', phase, room_id)
    
    def remove_room_from_indexes(self, room_id: str, room_data: Dict):
        """Remove room from all indexes."""
        # Remove from player indexes
        for player_id in room_data.get('players', {}):
            self.index_manager.remove_from_index('rooms_by_player', player_id, room_id)
        
        # Remove from phase index
        phase = room_data.get('game_state', {}).get('phase', 'unknown')
        self.index_manager.remove_from_index('rooms_by_phase', phase, room_id)
    
    def optimized_query(self, query_name: str, query_func: Callable, ttl: int = 300) -> Any:
        """Execute optimized query with caching and monitoring."""
        start_time = time.time()
        
        try:
            result = self.query_optimizer.cached_query(query_name, query_func, ttl)
            return result
        finally:
            execution_time = time.time() - start_time
            
            with self.lock:
                self.operation_times[query_name].append(execution_time)
                # Keep only last 100 measurements
                if len(self.operation_times[query_name]) > 100:
                    self.operation_times[query_name].pop(0)
    
    def get_performance_stats(self) -> Dict:
        """Get database performance statistics."""
        with self.lock:
            stats = {
                'query_stats': self.query_optimizer.get_query_stats(),
                'operation_times': {},
                'index_stats': {
                    'total_indexes': len(self.index_manager.indexes),
                    'total_entries': sum(
                        sum(len(entries) for entries in index.values())
                        for index in self.index_manager.indexes.values()
                    )
                }
            }
            
            # Calculate average operation times
            for operation, times in self.operation_times.items():
                if times:
                    stats['operation_times'][operation] = {
                        'avg_time': sum(times) / len(times),
                        'min_time': min(times),
                        'max_time': max(times),
                        'total_calls': len(times)
                    }
            
            return stats
    
    def optimize_data_structure(self, data: Any, data_type: str = 'generic') -> Any:
        """Optimize data structure based on type."""
        if data_type == 'room':
            return self.data_optimizer.optimize_room_structure(data)
        elif data_type == 'players':
            return self.data_optimizer.optimize_player_data(data)
        else:
            return data
    
    def add_batch_operation(self, op_type: str, func: Callable, args: tuple = (), kwargs: dict = None):
        """Add operation to batch processor."""
        self.batch_processor.add_operation(op_type, func, args, kwargs)
    
    def flush_batch_operations(self) -> List[Any]:
        """Execute all pending batch operations."""
        return self.batch_processor.flush()
    
    def cleanup(self):
        """Clean up optimizer resources."""
        # Clear caches and indexes
        self.query_optimizer.query_cache.clear()
        self.index_manager.indexes.clear()
        self.operation_times.clear()
        
        # Flush remaining batch operations
        self.batch_processor.flush()
        
        logger.info('DatabaseOptimizer cleanup complete')


# Global optimizer instance
_optimizer_instance: Optional[DatabaseOptimizer] = None


def get_database_optimizer() -> DatabaseOptimizer:
    """Get global database optimizer instance."""
    global _optimizer_instance
    
    if _optimizer_instance is None:
        _optimizer_instance = DatabaseOptimizer()
    
    return _optimizer_instance