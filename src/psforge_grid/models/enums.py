"""Semantic status enums for LLM-friendly output.

This module defines enumeration types that provide semantic meaning
to numerical values, enabling LLMs to interpret power system analysis
results without ambiguity.

Design Philosophy:
    - Explicit over Implicit: Status values are human-readable strings
    - Self-Documenting: Enum names describe the physical meaning
    - Configurable Thresholds: Class methods accept custom limits

Example:
    >>> from psforge_grid.models.enums import VoltageStatus
    >>> status = VoltageStatus.from_value(0.943, v_min=0.95, v_max=1.05)
    >>> print(status)  # VoltageStatus.LOW
    >>> print(status.value)  # "LOW"
"""

from enum import Enum


class Severity(Enum):
    """Severity level for findings and anomalies.

    Used to classify the importance of diagnostic findings,
    enabling prioritization of issues for both LLM analysis
    and human review.

    Levels:
        INFO: Informational finding, no action required
        WARNING: Potential issue, monitoring recommended
        ERROR: Significant issue, action recommended
        CRITICAL: Severe issue, immediate action required
    """

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    def __str__(self) -> str:
        """Return the string value for LLM-friendly output."""
        return self.value


class VoltageStatus(Enum):
    """Voltage magnitude status classification.

    Classifies bus voltage magnitudes into semantic categories
    based on configurable thresholds.

    Default Thresholds:
        - CRITICAL_LOW: < 0.90 pu (dangerous undervoltage)
        - LOW: 0.90 - 0.95 pu (below normal range)
        - NORMAL: 0.95 - 1.05 pu (acceptable operating range)
        - HIGH: 1.05 - 1.10 pu (above normal range)
        - CRITICAL_HIGH: > 1.10 pu (dangerous overvoltage)

    Educational Note:
        Voltage limits in power systems are critical for:
        - Equipment protection (insulation, tap changers)
        - Power quality (motors, electronics)
        - System stability (voltage collapse prevention)

    Example:
        >>> status = VoltageStatus.from_value(0.943)
        >>> print(f"Voltage is {status.value}")  # "Voltage is LOW"
    """

    CRITICAL_LOW = "CRITICAL_LOW"
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL_HIGH = "CRITICAL_HIGH"

    def __str__(self) -> str:
        """Return the string value for LLM-friendly output."""
        return self.value

    @classmethod
    def from_value(
        cls,
        v_pu: float,
        v_min: float = 0.95,
        v_max: float = 1.05,
        critical_margin: float = 0.05,
    ) -> "VoltageStatus":
        """Classify voltage magnitude into status.

        Args:
            v_pu: Voltage magnitude in per-unit
            v_min: Lower normal limit (default: 0.95 pu)
            v_max: Upper normal limit (default: 1.05 pu)
            critical_margin: Margin beyond limits for critical status (default: 0.05 pu)

        Returns:
            VoltageStatus enum value

        Example:
            >>> VoltageStatus.from_value(1.02)
            <VoltageStatus.NORMAL: 'NORMAL'>
            >>> VoltageStatus.from_value(0.88)
            <VoltageStatus.CRITICAL_LOW: 'CRITICAL_LOW'>
        """
        if v_pu < v_min - critical_margin:
            return cls.CRITICAL_LOW
        elif v_pu < v_min:
            return cls.LOW
        elif v_pu <= v_max:
            return cls.NORMAL
        elif v_pu <= v_max + critical_margin:
            return cls.HIGH
        else:
            return cls.CRITICAL_HIGH

    @property
    def is_normal(self) -> bool:
        """Check if voltage is within normal range."""
        return self == VoltageStatus.NORMAL

    @property
    def is_violation(self) -> bool:
        """Check if voltage violates normal limits."""
        return self != VoltageStatus.NORMAL

    @property
    def is_critical(self) -> bool:
        """Check if voltage is in critical range."""
        return self in (VoltageStatus.CRITICAL_LOW, VoltageStatus.CRITICAL_HIGH)

    @property
    def severity(self) -> Severity:
        """Get the severity level for this voltage status."""
        if self == VoltageStatus.NORMAL:
            return Severity.INFO
        elif self in (VoltageStatus.LOW, VoltageStatus.HIGH):
            return Severity.WARNING
        else:
            return Severity.CRITICAL


class LoadingStatus(Enum):
    """Branch thermal loading status classification.

    Classifies branch loading as a percentage of thermal limit
    into semantic categories.

    Default Thresholds:
        - LIGHT: < 50% (low utilization)
        - NORMAL: 50% - 80% (normal operation)
        - HEAVY: 80% - 100% (approaching limit)
        - OVERLOAD: > 100% (exceeds thermal limit)

    Educational Note:
        Thermal limits protect conductors from:
        - Excessive heating (sag, annealing)
        - Insulation degradation
        - Reduced equipment lifetime

    Example:
        >>> status = LoadingStatus.from_percent(85.0)
        >>> print(f"Branch loading: {status.value}")  # "Branch loading: HEAVY"
    """

    LIGHT = "LIGHT"
    NORMAL = "NORMAL"
    HEAVY = "HEAVY"
    OVERLOAD = "OVERLOAD"

    def __str__(self) -> str:
        """Return the string value for LLM-friendly output."""
        return self.value

    @classmethod
    def from_percent(
        cls,
        loading_percent: float,
        light_threshold: float = 50.0,
        heavy_threshold: float = 80.0,
        overload_threshold: float = 100.0,
    ) -> "LoadingStatus":
        """Classify loading percentage into status.

        Args:
            loading_percent: Loading as percentage of thermal limit
            light_threshold: Threshold for LIGHT/NORMAL boundary (default: 50%)
            heavy_threshold: Threshold for NORMAL/HEAVY boundary (default: 80%)
            overload_threshold: Threshold for HEAVY/OVERLOAD boundary (default: 100%)

        Returns:
            LoadingStatus enum value

        Example:
            >>> LoadingStatus.from_percent(45.0)
            <LoadingStatus.LIGHT: 'LIGHT'>
            >>> LoadingStatus.from_percent(110.0)
            <LoadingStatus.OVERLOAD: 'OVERLOAD'>
        """
        if loading_percent < light_threshold:
            return cls.LIGHT
        elif loading_percent < heavy_threshold:
            return cls.NORMAL
        elif loading_percent < overload_threshold:
            return cls.HEAVY
        else:
            return cls.OVERLOAD

    @property
    def is_normal(self) -> bool:
        """Check if loading is within normal range (LIGHT or NORMAL)."""
        return self in (LoadingStatus.LIGHT, LoadingStatus.NORMAL)

    @property
    def is_overload(self) -> bool:
        """Check if loading exceeds thermal limit."""
        return self == LoadingStatus.OVERLOAD

    @property
    def severity(self) -> Severity:
        """Get the severity level for this loading status."""
        if self in (LoadingStatus.LIGHT, LoadingStatus.NORMAL):
            return Severity.INFO
        elif self == LoadingStatus.HEAVY:
            return Severity.WARNING
        else:
            return Severity.ERROR


class ConvergenceStatus(Enum):
    """Power flow convergence status.

    Indicates the outcome of iterative power flow calculation.

    Values:
        CONVERGED: Solution found within tolerance
        NOT_CONVERGED: Solution not found (generic)
        MAX_ITERATIONS: Iteration limit reached
        DIVERGED: Solution diverged (numerical instability)

    Educational Note:
        Convergence issues often indicate:
        - System is heavily loaded or stressed
        - Voltage collapse proximity
        - Invalid or inconsistent input data
        - Need for better initial conditions
    """

    CONVERGED = "CONVERGED"
    NOT_CONVERGED = "NOT_CONVERGED"
    MAX_ITERATIONS = "MAX_ITERATIONS"
    DIVERGED = "DIVERGED"

    def __str__(self) -> str:
        """Return the string value for LLM-friendly output."""
        return self.value

    @property
    def is_successful(self) -> bool:
        """Check if power flow converged successfully."""
        return self == ConvergenceStatus.CONVERGED

    @property
    def severity(self) -> Severity:
        """Get the severity level for this convergence status."""
        if self == ConvergenceStatus.CONVERGED:
            return Severity.INFO
        else:
            return Severity.ERROR


class SystemHealthStatus(Enum):
    """Overall system health status.

    Provides a high-level assessment of system condition
    based on aggregation of individual findings.

    Values:
        HEALTHY: No violations, all within normal limits
        WARNING: Minor issues detected, monitoring recommended
        CRITICAL: Significant issues, action required

    Example:
        >>> # Determine system health from diagnostic findings
        >>> if any(f.severity == Severity.CRITICAL for f in findings):
        ...     health = SystemHealthStatus.CRITICAL
        >>> elif any(f.severity == Severity.WARNING for f in findings):
        ...     health = SystemHealthStatus.WARNING
        >>> else:
        ...     health = SystemHealthStatus.HEALTHY
    """

    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

    def __str__(self) -> str:
        """Return the string value for LLM-friendly output."""
        return self.value

    @classmethod
    def from_severities(cls, severities: list[Severity]) -> "SystemHealthStatus":
        """Determine system health from a list of severity levels.

        Args:
            severities: List of Severity values from findings

        Returns:
            SystemHealthStatus based on worst severity found
        """
        if not severities:
            return cls.HEALTHY

        if any(s in (Severity.CRITICAL, Severity.ERROR) for s in severities):
            return cls.CRITICAL
        elif any(s == Severity.WARNING for s in severities):
            return cls.WARNING
        else:
            return cls.HEALTHY


class BusType(Enum):
    """Bus type classification for power flow analysis.

    Standard bus type codes used in power flow calculations.

    Values:
        PQ (1): Load bus - P and Q are specified
        PV (2): Generator bus - P and V are specified
        SLACK (3): Swing/Reference bus - V and angle are specified
        ISOLATED (4): Isolated bus - not connected to the network

    Educational Note:
        In Newton-Raphson power flow:
        - PQ buses: Solve for V magnitude and angle
        - PV buses: Solve for V angle only (Q is variable)
        - Slack bus: Reference angle (typically 0), balances system P
    """

    PQ = 1
    PV = 2
    SLACK = 3
    ISOLATED = 4

    def __str__(self) -> str:
        """Return human-readable bus type name."""
        names = {
            BusType.PQ: "PQ (Load)",
            BusType.PV: "PV (Generator)",
            BusType.SLACK: "Slack (Reference)",
            BusType.ISOLATED: "Isolated",
        }
        return names.get(self, f"Unknown ({self.value})")

    @classmethod
    def from_code(cls, code: int) -> "BusType":
        """Create BusType from integer code.

        Args:
            code: Integer bus type code (1-4)

        Returns:
            BusType enum value

        Raises:
            ValueError: If code is not valid (1-4)
        """
        try:
            return cls(code)
        except ValueError:
            raise ValueError(f"Invalid bus type code: {code}. Valid codes are 1-4.") from None

    @property
    def is_generator(self) -> bool:
        """Check if bus type has generation (PV or Slack)."""
        return self in (BusType.PV, BusType.SLACK)

    @property
    def is_load(self) -> bool:
        """Check if bus type is a load bus (PQ)."""
        return self == BusType.PQ
