"""Configuration classes for system limits and thresholds.

This module provides configurable limit settings for power system
analysis, enabling users to customize thresholds for voltage,
thermal loading, and other operational constraints.

Design Philosophy:
    - User-Configurable: All limits can be customized
    - Sensible Defaults: Standard industry values as defaults
    - Immutable after creation: Use dataclass(frozen=True) for safety

Example:
    >>> from psforge_grid.models.limits import LimitsConfig
    >>> # Use default limits
    >>> limits = LimitsConfig()
    >>> print(f"Voltage range: {limits.voltage_min_pu} - {limits.voltage_max_pu} pu")
    >>>
    >>> # Custom limits for emergency operation
    >>> emergency_limits = LimitsConfig(
    ...     voltage_min_pu=0.90,
    ...     voltage_max_pu=1.10,
    ...     thermal_limit_percent=120.0
    ... )
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class LimitsConfig:
    """Configuration for system operational limits.

    Provides centralized management of thresholds used for:
    - Voltage violation detection
    - Thermal overload detection
    - Status classification (normal/warning/critical)

    All limits are user-configurable with sensible defaults
    based on common industry practices.

    Attributes:
        voltage_min_pu: Minimum normal voltage [p.u.] (default: 0.95)
        voltage_max_pu: Maximum normal voltage [p.u.] (default: 1.05)
        voltage_critical_margin_pu: Margin for critical classification [p.u.] (default: 0.05)
        thermal_limit_percent: Branch loading limit [%] (default: 100.0)
        thermal_heavy_threshold_percent: Heavy loading threshold [%] (default: 80.0)
        thermal_light_threshold_percent: Light loading threshold [%] (default: 50.0)
        convergence_tolerance_pu: Power flow convergence tolerance [p.u.] (default: 1e-6)
        max_iterations: Maximum power flow iterations (default: 100)

    Educational Note:
        Typical voltage limits vary by system voltage level:
        - Transmission (>100kV): 0.95 - 1.05 pu
        - Sub-transmission (35-100kV): 0.95 - 1.05 pu
        - Distribution (<35kV): 0.95 - 1.05 pu (may vary by regulation)

        Thermal limits are typically rated for:
        - Normal operation: 100% of continuous rating
        - Emergency (short-term): 110-120% for 15-30 minutes
        - Extreme emergency: 130-150% for seconds to minutes

    Example:
        >>> limits = LimitsConfig()
        >>> # Check if voltage is within limits
        >>> v_pu = 0.943
        >>> if v_pu < limits.voltage_min_pu:
        ...     print(f"Voltage {v_pu} pu is below minimum {limits.voltage_min_pu} pu")
    """

    # Voltage limits
    voltage_min_pu: float = 0.95
    voltage_max_pu: float = 1.05
    voltage_critical_margin_pu: float = 0.05

    # Thermal limits
    thermal_limit_percent: float = 100.0
    thermal_heavy_threshold_percent: float = 80.0
    thermal_light_threshold_percent: float = 50.0

    # Convergence settings
    convergence_tolerance_pu: float = 1e-6
    max_iterations: int = 100

    def __post_init__(self) -> None:
        """Validate limit values after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate that limits are physically reasonable.

        Raises:
            ValueError: If limits are invalid or inconsistent
        """
        if self.voltage_min_pu <= 0:
            raise ValueError(f"voltage_min_pu must be positive, got {self.voltage_min_pu}")
        if self.voltage_max_pu <= self.voltage_min_pu:
            raise ValueError(
                f"voltage_max_pu ({self.voltage_max_pu}) must be greater than "
                f"voltage_min_pu ({self.voltage_min_pu})"
            )
        if self.voltage_critical_margin_pu < 0:
            raise ValueError(
                f"voltage_critical_margin_pu must be non-negative, "
                f"got {self.voltage_critical_margin_pu}"
            )
        if self.thermal_limit_percent <= 0:
            raise ValueError(
                f"thermal_limit_percent must be positive, got {self.thermal_limit_percent}"
            )
        if not (
            0
            < self.thermal_light_threshold_percent
            < self.thermal_heavy_threshold_percent
            < self.thermal_limit_percent
        ):
            raise ValueError(
                "Thermal thresholds must satisfy: "
                "0 < light < heavy < limit, "
                f"got light={self.thermal_light_threshold_percent}, "
                f"heavy={self.thermal_heavy_threshold_percent}, "
                f"limit={self.thermal_limit_percent}"
            )
        if self.convergence_tolerance_pu <= 0:
            raise ValueError(
                f"convergence_tolerance_pu must be positive, "
                f"got {self.convergence_tolerance_pu}"
            )
        if self.max_iterations <= 0:
            raise ValueError(f"max_iterations must be positive, got {self.max_iterations}")

    # =========================================================================
    # Derived properties
    # =========================================================================

    @property
    def voltage_critical_low_pu(self) -> float:
        """Lower critical voltage threshold [p.u.]."""
        return self.voltage_min_pu - self.voltage_critical_margin_pu

    @property
    def voltage_critical_high_pu(self) -> float:
        """Upper critical voltage threshold [p.u.]."""
        return self.voltage_max_pu + self.voltage_critical_margin_pu

    # =========================================================================
    # Factory methods for common scenarios
    # =========================================================================

    @classmethod
    def normal(cls) -> "LimitsConfig":
        """Create limits for normal operation (default values).

        Returns:
            LimitsConfig with standard operating limits
        """
        return cls()

    @classmethod
    def emergency(cls) -> "LimitsConfig":
        """Create limits for emergency operation.

        Relaxed limits allowing temporary exceedance during
        emergency conditions (e.g., post-contingency).

        Returns:
            LimitsConfig with emergency operating limits
        """
        return cls(
            voltage_min_pu=0.90,
            voltage_max_pu=1.10,
            thermal_limit_percent=120.0,
            thermal_heavy_threshold_percent=100.0,
        )

    @classmethod
    def strict(cls) -> "LimitsConfig":
        """Create strict limits for conservative operation.

        Tighter limits for systems requiring high reliability
        or operating near stability limits.

        Returns:
            LimitsConfig with strict operating limits
        """
        return cls(
            voltage_min_pu=0.97,
            voltage_max_pu=1.03,
            thermal_limit_percent=80.0,
            thermal_heavy_threshold_percent=60.0,
        )

    # =========================================================================
    # Utility methods
    # =========================================================================

    def is_voltage_normal(self, v_pu: float) -> bool:
        """Check if voltage is within normal limits.

        Args:
            v_pu: Voltage magnitude in per-unit

        Returns:
            True if voltage is within [voltage_min_pu, voltage_max_pu]
        """
        return self.voltage_min_pu <= v_pu <= self.voltage_max_pu

    def is_voltage_critical(self, v_pu: float) -> bool:
        """Check if voltage is in critical range.

        Args:
            v_pu: Voltage magnitude in per-unit

        Returns:
            True if voltage is below critical_low or above critical_high
        """
        return v_pu < self.voltage_critical_low_pu or v_pu > self.voltage_critical_high_pu

    def is_loading_normal(self, loading_percent: float) -> bool:
        """Check if branch loading is within normal limits.

        Args:
            loading_percent: Loading as percentage of thermal limit

        Returns:
            True if loading is below thermal_heavy_threshold_percent
        """
        return loading_percent < self.thermal_heavy_threshold_percent

    def is_overload(self, loading_percent: float) -> bool:
        """Check if branch is overloaded.

        Args:
            loading_percent: Loading as percentage of thermal limit

        Returns:
            True if loading exceeds thermal_limit_percent
        """
        return loading_percent > self.thermal_limit_percent

    def voltage_margin_percent(self, v_pu: float) -> float:
        """Calculate voltage margin to nearest limit.

        Args:
            v_pu: Voltage magnitude in per-unit

        Returns:
            Margin to nearest limit as percentage
            Positive = within limits, Negative = beyond limits
        """
        margin_to_min = (v_pu - self.voltage_min_pu) / self.voltage_min_pu * 100
        margin_to_max = (self.voltage_max_pu - v_pu) / self.voltage_max_pu * 100
        return min(margin_to_min, margin_to_max)

    def thermal_margin_percent(self, loading_percent: float) -> float:
        """Calculate thermal margin to limit.

        Args:
            loading_percent: Loading as percentage of thermal limit

        Returns:
            Margin to thermal limit as percentage points
            Positive = within limit, Negative = exceeds limit
        """
        return self.thermal_limit_percent - loading_percent

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation of limits
        """
        return {
            "voltage_min_pu": self.voltage_min_pu,
            "voltage_max_pu": self.voltage_max_pu,
            "voltage_critical_margin_pu": self.voltage_critical_margin_pu,
            "thermal_limit_percent": self.thermal_limit_percent,
            "thermal_heavy_threshold_percent": self.thermal_heavy_threshold_percent,
            "thermal_light_threshold_percent": self.thermal_light_threshold_percent,
            "convergence_tolerance_pu": self.convergence_tolerance_pu,
            "max_iterations": self.max_iterations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LimitsConfig":
        """Create from dictionary.

        Args:
            data: Dictionary with limit values

        Returns:
            LimitsConfig instance
        """
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_description(self) -> str:
        """Generate human/LLM-readable description of limits.

        Returns:
            Multi-line string describing the limits configuration
        """
        return f"""Limits Configuration:
  Voltage: {self.voltage_min_pu:.3f} - {self.voltage_max_pu:.3f} pu (normal)
           {self.voltage_critical_low_pu:.3f} - {self.voltage_critical_high_pu:.3f} pu (critical bounds)
  Thermal: {self.thermal_limit_percent:.1f}% limit
           {self.thermal_heavy_threshold_percent:.1f}% heavy threshold
           {self.thermal_light_threshold_percent:.1f}% light threshold
  Convergence: {self.convergence_tolerance_pu:.0e} pu tolerance
               {self.max_iterations} max iterations"""
