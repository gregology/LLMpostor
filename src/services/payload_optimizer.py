"""
Payload Optimizer - Network communication and payload size optimization

Features:
- Data compression for large payloads
- Payload size analysis and reduction
- Delta compression for incremental updates
- Binary serialization for efficiency
- Payload caching to avoid redundant transfers
- Bandwidth adaptation based on connection quality
- Batch message optimization
"""

import gzip
import json
import pickle
import zlib
import time
import logging
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime
import hashlib
from dataclasses import dataclass
from enum import Enum
from .base_service import BaseService

logger = logging.getLogger(__name__)


class CompressionType(Enum):
    """Supported compression types."""
    NONE = "none"
    GZIP = "gzip"
    ZLIB = "zlib"
    BROTLI = "brotli"  # If available


@dataclass
class PayloadStats:
    """Statistics for payload optimization."""
    original_size: int
    compressed_size: int
    compression_ratio: float
    compression_time: float
    compression_type: str
    
    @property
    def size_reduction(self) -> float:
        """Size reduction percentage."""
        if self.original_size == 0:
            return 0.0
        return ((self.original_size - self.compressed_size) / self.original_size) * 100


class PayloadOptimizer(BaseService):
    """Optimizes network payloads for better performance."""
    
    def __init__(self, config: Dict[str, Any] = None):
        # Initialize parent BaseService
        super().__init__(config)
    
    def _initialize(self) -> None:
        """Initialize service-specific components."""
        # Optimization thresholds
        self.compression_threshold = self.get_config_value('compression_threshold', 1024)  # 1KB
        self.max_payload_size = self.get_config_value('max_payload_size', 1024 * 1024)  # 1MB
        
        # Compression settings
        self.gzip_level = self.get_config_value('gzip_level', 6)
        self.zlib_level = self.get_config_value('zlib_level', 6)
        
        # Caching
        self.enable_caching = self.get_config_value('enable_caching', True)
        self.payload_cache: Dict[str, bytes] = {}
        self.cache_hit_ratio = {'hits': 0, 'misses': 0}
        
        # Delta compression tracking
        self.previous_states: Dict[str, Dict] = {}
        
        # Performance metrics
        self.stats = {
            'total_processed': 0,
            'total_original_size': 0,
            'total_compressed_size': 0,
            'total_compression_time': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        self.log_info(f'PayloadOptimizer initialized with compression threshold: {self.compression_threshold} bytes')
    
    def optimize_outbound(self, data: Any, context: str = 'default', 
                         force_compression: bool = False) -> Tuple[bytes, Dict[str, Any]]:
        """Optimize outbound payload.
        
        Args:
            data: Data to optimize
            context: Context identifier for optimization decisions
            force_compression: Force compression regardless of size
            
        Returns:
            Tuple of (optimized_payload, metadata)
        """
        start_time = time.time()
        
        # Convert to JSON first
        if isinstance(data, (dict, list)):
            json_data = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        else:
            json_data = str(data)
        
        original_payload = json_data.encode('utf-8')
        original_size = len(original_payload)
        
        # Check cache first
        if self.enable_caching:
            cache_key = self._generate_cache_key(original_payload)
            cached_payload = self.payload_cache.get(cache_key)
            
            if cached_payload:
                self.cache_hit_ratio['hits'] += 1
                self.stats['cache_hits'] += 1
                
                metadata = {
                    'original_size': original_size,
                    'compressed_size': len(cached_payload),
                    'compression_type': 'cached',
                    'cached': True
                }
                
                return cached_payload, metadata
        
        self.cache_hit_ratio['misses'] += 1
        self.stats['cache_misses'] += 1
        
        # Determine if compression is beneficial
        should_compress = (
            force_compression or 
            original_size >= self.compression_threshold
        )
        
        optimized_payload = original_payload
        compression_type = CompressionType.NONE
        compressed_size = original_size
        
        if should_compress:
            # Try different compression methods and pick the best
            compression_results = []
            
            # GZIP compression
            try:
                gzip_start = time.time()
                gzip_compressed = gzip.compress(original_payload, compresslevel=self.gzip_level)
                gzip_time = time.time() - gzip_start
                
                compression_results.append({
                    'payload': gzip_compressed,
                    'size': len(gzip_compressed),
                    'type': CompressionType.GZIP,
                    'time': gzip_time
                })
            except Exception as e:
                logger.debug(f'GZIP compression failed: {e}')
            
            # ZLIB compression
            try:
                zlib_start = time.time()
                zlib_compressed = zlib.compress(original_payload, level=self.zlib_level)
                zlib_time = time.time() - zlib_start
                
                compression_results.append({
                    'payload': zlib_compressed,
                    'size': len(zlib_compressed),
                    'type': CompressionType.ZLIB,
                    'time': zlib_time
                })
            except Exception as e:
                logger.debug(f'ZLIB compression failed: {e}')
            
            # Choose best compression result
            if compression_results:
                best_result = min(compression_results, key=lambda x: x['size'])
                
                # Only use compression if it actually reduces size significantly
                if best_result['size'] < original_size * 0.9:  # At least 10% reduction
                    optimized_payload = best_result['payload']
                    compression_type = best_result['type']
                    compressed_size = best_result['size']
        
        # Cache the result
        if self.enable_caching:
            cache_key = self._generate_cache_key(original_payload)
            self.payload_cache[cache_key] = optimized_payload
            
            # Limit cache size
            if len(self.payload_cache) > 1000:
                # Remove oldest entries (simple FIFO)
                keys_to_remove = list(self.payload_cache.keys())[:100]
                for key in keys_to_remove:
                    del self.payload_cache[key]
        
        compression_time = time.time() - start_time
        
        # Update statistics
        self.stats['total_processed'] += 1
        self.stats['total_original_size'] += original_size
        self.stats['total_compressed_size'] += compressed_size
        self.stats['total_compression_time'] += compression_time
        
        metadata = {
            'original_size': original_size,
            'compressed_size': compressed_size,
            'compression_type': compression_type.value,
            'compression_time': compression_time,
            'compression_ratio': compressed_size / original_size if original_size > 0 else 1.0,
            'cached': False
        }
        
        return optimized_payload, metadata
    
    def decompress_inbound(self, payload: bytes, metadata: Dict[str, Any]) -> Any:
        """Decompress inbound payload.
        
        Args:
            payload: Compressed payload
            metadata: Compression metadata
            
        Returns:
            Decompressed data
        """
        compression_type = metadata.get('compression_type', 'none')
        
        try:
            if compression_type == CompressionType.GZIP.value:
                decompressed = gzip.decompress(payload)
            elif compression_type == CompressionType.ZLIB.value:
                decompressed = zlib.decompress(payload)
            else:
                decompressed = payload
            
            # Convert back to original format
            json_str = decompressed.decode('utf-8')
            return json.loads(json_str)
            
        except Exception as e:
            logger.error(f'Decompression failed: {e}')
            # Fallback: try to parse as uncompressed JSON
            try:
                json_str = payload.decode('utf-8')
                return json.loads(json_str)
            except:
                return None
    
    def optimize_room_state(self, current_state: Dict, room_id: str) -> Tuple[bytes, Dict[str, Any]]:
        """Optimize room state payload using delta compression.
        
        Args:
            current_state: Current room state
            room_id: Room identifier
            
        Returns:
            Tuple of (optimized_payload, metadata)
        """
        previous_state = self.previous_states.get(room_id)
        
        if previous_state is None:
            # First time - send full state
            optimized_payload, metadata = self.optimize_outbound(
                current_state, 
                context=f'room_state_{room_id}'
            )
            metadata['delta'] = False
            metadata['delta_size'] = metadata['compressed_size']
        else:
            # Generate delta
            delta = self._generate_state_delta(previous_state, current_state)
            
            # Check if delta is smaller than full state
            full_payload, full_metadata = self.optimize_outbound(current_state)
            delta_payload, delta_metadata = self.optimize_outbound(delta)
            
            if delta_metadata['compressed_size'] < full_metadata['compressed_size'] * 0.7:
                # Use delta if it's significantly smaller
                optimized_payload = delta_payload
                metadata = delta_metadata
                metadata['delta'] = True
                metadata['delta_size'] = delta_metadata['compressed_size']
                metadata['full_size'] = full_metadata['compressed_size']
            else:
                # Use full state
                optimized_payload = full_payload
                metadata = full_metadata
                metadata['delta'] = False
                metadata['delta_size'] = metadata['compressed_size']
        
        # Store current state as previous for next delta
        self.previous_states[room_id] = current_state.copy()
        
        return optimized_payload, metadata
    
    def optimize_player_list(self, players: List[Dict]) -> Tuple[bytes, Dict[str, Any]]:
        """Optimize player list payload by removing redundant data.
        
        Args:
            players: List of player data
            
        Returns:
            Tuple of (optimized_payload, metadata)
        """
        # Create lightweight player representation
        optimized_players = []
        
        for player in players:
            # Only include essential fields
            optimized_player = {
                'id': player.get('player_id'),
                'name': player.get('name'),
                'score': player.get('score', 0),
                'connected': player.get('connected', False)
            }
            
            # Add optional fields only if they have meaningful values
            if player.get('last_activity'):
                optimized_player['last_activity'] = player['last_activity']
            
            optimized_players.append(optimized_player)
        
        return self.optimize_outbound(optimized_players, context='player_list')
    
    def optimize_game_responses(self, responses: List[Dict]) -> Tuple[bytes, Dict[str, Any]]:
        """Optimize game responses by removing sensitive data and minimizing size.
        
        Args:
            responses: List of game responses
            
        Returns:
            Tuple of (optimized_payload, metadata)
        """
        # Remove author information and keep only essential data
        optimized_responses = []
        
        for i, response in enumerate(responses):
            optimized_response = {
                'index': i,
                'text': response.get('text', '').strip()
            }
            
            # Add response length for UI optimization
            optimized_response['length'] = len(optimized_response['text'])
            
            optimized_responses.append(optimized_response)
        
        return self.optimize_outbound(optimized_responses, context='game_responses')
    
    def batch_messages(self, messages: List[Tuple[str, Any]], 
                      max_batch_size: int = 10) -> List[Tuple[bytes, Dict[str, Any]]]:
        """Batch multiple messages for efficient transmission.
        
        Args:
            messages: List of (event_type, data) tuples
            max_batch_size: Maximum messages per batch
            
        Returns:
            List of (batched_payload, metadata) tuples
        """
        batches = []
        
        # Group messages into batches
        for i in range(0, len(messages), max_batch_size):
            batch = messages[i:i + max_batch_size]
            
            # Create batch payload
            batch_data = {
                'type': 'batch',
                'messages': [
                    {'event': event_type, 'data': data} 
                    for event_type, data in batch
                ],
                'count': len(batch),
                'timestamp': time.time()
            }
            
            optimized_payload, metadata = self.optimize_outbound(
                batch_data, 
                context='message_batch'
            )
            
            metadata['batch_size'] = len(batch)
            metadata['original_messages'] = len(batch)
            
            batches.append((optimized_payload, metadata))
        
        return batches
    
    def _generate_state_delta(self, previous: Dict, current: Dict) -> Dict:
        """Generate delta between two states.
        
        Args:
            previous: Previous state
            current: Current state
            
        Returns:
            Delta containing only changes
        """
        delta = {
            'type': 'delta',
            'timestamp': time.time(),
            'changes': {}
        }
        
        # Find changes in top-level keys
        for key in current:
            if key not in previous:
                delta['changes'][key] = {'action': 'add', 'value': current[key]}
            elif current[key] != previous[key]:
                delta['changes'][key] = {'action': 'update', 'value': current[key]}
        
        # Find removed keys
        for key in previous:
            if key not in current:
                delta['changes'][key] = {'action': 'remove'}
        
        return delta
    
    def apply_delta(self, base_state: Dict, delta: Dict) -> Dict:
        """Apply delta to base state.
        
        Args:
            base_state: Base state to apply delta to
            delta: Delta changes
            
        Returns:
            Updated state
        """
        if delta.get('type') != 'delta':
            return delta  # Not a delta, return as-is
        
        result = base_state.copy()
        changes = delta.get('changes', {})
        
        for key, change in changes.items():
            action = change.get('action')
            
            if action == 'add' or action == 'update':
                result[key] = change['value']
            elif action == 'remove':
                result.pop(key, None)
        
        return result
    
    def _generate_cache_key(self, payload: bytes) -> str:
        """Generate cache key for payload.
        
        Args:
            payload: Payload bytes
            
        Returns:
            Cache key string
        """
        return hashlib.md5(payload).hexdigest()
    
    def analyze_payload_size(self, data: Any) -> Dict[str, Any]:
        """Analyze payload size and provide optimization recommendations.
        
        Args:
            data: Data to analyze
            
        Returns:
            Analysis results with recommendations
        """
        # Convert to JSON for analysis
        json_str = json.dumps(data, separators=(',', ':'))
        size = len(json_str.encode('utf-8'))
        
        analysis = {
            'size': size,
            'size_human': self._format_bytes(size),
            'recommendations': []
        }
        
        if size > self.max_payload_size:
            analysis['recommendations'].append('Payload exceeds maximum size limit')
        
        if size > self.compression_threshold:
            analysis['recommendations'].append('Consider compression for this payload size')
        
        # Analyze data structure
        if isinstance(data, dict):
            # Check for redundant fields
            field_sizes = {}
            for key, value in data.items():
                field_size = len(json.dumps(value, separators=(',', ':')).encode('utf-8'))
                field_sizes[key] = field_size
            
            # Find largest fields
            largest_fields = sorted(field_sizes.items(), key=lambda x: x[1], reverse=True)[:5]
            analysis['largest_fields'] = [
                {'field': field, 'size': size, 'size_human': self._format_bytes(size)}
                for field, size in largest_fields
            ]
            
            # Check for potential optimizations
            if 'players' in data and isinstance(data['players'], list):
                analysis['recommendations'].append('Consider optimizing player list structure')
            
            if 'game_state' in data:
                analysis['recommendations'].append('Consider delta compression for game state')
        
        return analysis
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get payload optimization performance statistics.
        
        Returns:
            Performance statistics
        """
        total_processed = self.stats['total_processed']
        
        if total_processed == 0:
            return {
                'total_processed': 0,
                'average_compression_ratio': 1.0,
                'total_bandwidth_saved': 0,
                'cache_hit_rate': 0.0
            }
        
        bandwidth_saved = self.stats['total_original_size'] - self.stats['total_compressed_size']
        avg_compression_ratio = self.stats['total_compressed_size'] / self.stats['total_original_size']
        
        total_cache_requests = self.cache_hit_ratio['hits'] + self.cache_hit_ratio['misses']
        cache_hit_rate = (self.cache_hit_ratio['hits'] / total_cache_requests * 100) if total_cache_requests > 0 else 0
        
        return {
            'total_processed': total_processed,
            'average_compression_ratio': avg_compression_ratio,
            'total_bandwidth_saved': bandwidth_saved,
            'bandwidth_saved_human': self._format_bytes(bandwidth_saved),
            'average_compression_time': self.stats['total_compression_time'] / total_processed,
            'cache_hit_rate': cache_hit_rate,
            'cache_size': len(self.payload_cache)
        }
    
    def _format_bytes(self, bytes_value: int) -> str:
        """Format bytes value in human readable format.
        
        Args:
            bytes_value: Number of bytes
            
        Returns:
            Formatted string (e.g., "1.5 KB")
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_value < 1024:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024
        return f"{bytes_value:.1f} TB"
    
    def clear_cache(self):
        """Clear payload cache and reset statistics."""
        self.payload_cache.clear()
        self.previous_states.clear()
        self.cache_hit_ratio = {'hits': 0, 'misses': 0}
        
        logger.info('Payload optimizer cache cleared')
    
    def _cleanup(self) -> None:
        """Service-specific cleanup logic."""
        self.clear_cache()
        
        # Reset stats
        self.stats = {
            'total_processed': 0,
            'total_original_size': 0,
            'total_compressed_size': 0,
            'total_compression_time': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }


# Removed global singleton pattern - use DI container instead
# Services should be obtained via the dependency injection container