"""
Adaptive Table Health Score Calculator

This module implements the usage-conditioned health scoring system for 
analytical tables (e.g., Apache Iceberg) as described in the specification.

The key innovation is separating metric quality from operational relevance,
where metric relevance is derived from execution-engine-reported workload behavior.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class UsageSignals:
    """Container for all usage signals."""
    file_size: float = 0.0
    scan_efficiency: float = 0.0
    delete_overhead: float = 0.0
    manifest_organization: float = 0.0
    partition_aware: float = 0.0


@dataclass
class HealthScoreResult:
    """Result of health score computation."""
    overall_health: float
    subscores: Dict[str, float]
    adjusted_weights: Dict[str, float]
    final_weights: Dict[str, float]
    usage_signals: UsageSignals


class HealthScoreCalculator:
    """
    Computes adaptive health scores for analytical tables.
    
    The calculator:
    1. Computes usage signals from workload behavior
    2. Calculates subscores based on usage signals
    3. Adjusts baseline weights based on usage
    4. Normalizes weights and computes final health score
    """
    
    # Baseline weights encoding inherent structural severity
    BASELINE_WEIGHTS = {
        'file_size': 1.0,
        'scan_efficiency': 1.0,
        'delete_overhead': 1.0,
        'manifest_organization': 1.0,
        'partition_aware': 1.0,
    }
    
    def __init__(self, baseline_weights: Optional[Dict[str, float]] = None):
        """
        Initialize calculator with optional custom baseline weights.
        
        Args:
            baseline_weights: Custom baseline weights. If None, uses defaults.
        """
        self.baseline_weights = baseline_weights or self.BASELINE_WEIGHTS.copy()
    
    def compute_subscore(self, usage_signal: float) -> float:
        """
        Compute subscore from usage signal.
        
        Formula: s_i = 1 / (1 + u_i)
        
        Args:
            usage_signal: Usage signal value in [0, 1]
            
        Returns:
            Subscore in (0, 1]
        """
        return 1.0 / (1.0 + usage_signal)
    
    def adjust_weight(self, baseline_weight: float, usage_signal: float) -> float:
        """
        Adjust baseline weight based on usage signal.
        
        Formula: w_i^adj = w_i^base * (1 + u_i)
        
        Args:
            baseline_weight: Baseline weight for the metric
            usage_signal: Usage signal value in [0, 1]
            
        Returns:
            Adjusted weight
        """
        return baseline_weight * (1.0 + usage_signal)
    
    def normalize_weights(self, adjusted_weights: Dict[str, float]) -> Dict[str, float]:
        """
        Normalize adjusted weights to sum to 1.
        
        Formula: w_i^final = w_i^adj / sum_j(w_j^adj)
        
        Args:
            adjusted_weights: Dictionary of adjusted weights
            
        Returns:
            Dictionary of normalized weights
        """
        total = sum(adjusted_weights.values())
        if total == 0:
            return {k: 0.0 for k in adjusted_weights.keys()}
        return {k: v / total for k, v in adjusted_weights.items()}
    
    def compute_health_score(
        self,
        usage_signals: UsageSignals
    ) -> HealthScoreResult:
        """
        Compute the overall health score from usage signals.
        
        Formula: Health = 100 * sum_i(w_i^final * s_i)
        
        Args:
            usage_signals: Usage signals for all metrics
            
        Returns:
            HealthScoreResult with detailed breakdown
        """
        # Map usage signals to metric names
        signal_map = {
            'file_size': usage_signals.file_size,
            'scan_efficiency': usage_signals.scan_efficiency,
            'delete_overhead': usage_signals.delete_overhead,
            'manifest_organization': usage_signals.manifest_organization,
            'partition_aware': usage_signals.partition_aware,
        }
        
        # Compute subscores
        subscores = {
            metric: self.compute_subscore(signal)
            for metric, signal in signal_map.items()
        }
        
        # Adjust weights based on usage
        adjusted_weights = {
            metric: self.adjust_weight(self.baseline_weights[metric], signal)
            for metric, signal in signal_map.items()
        }
        
        # Normalize weights
        final_weights = self.normalize_weights(adjusted_weights)
        
        # Compute final health score
        health = 100.0 * sum(
            final_weights[metric] * subscores[metric]
            for metric in signal_map.keys()
        )
        
        return HealthScoreResult(
            overall_health=health,
            subscores=subscores,
            adjusted_weights=adjusted_weights,
            final_weights=final_weights,
            usage_signals=usage_signals
        )
