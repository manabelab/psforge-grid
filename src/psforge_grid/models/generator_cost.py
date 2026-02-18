"""Generator cost data model for power system analysis.

This module defines the GeneratorCost class representing generation cost functions.
Used by OPF (Optimal Power Flow) and UC (Unit Commitment) formulations.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GeneratorCost:
    """Generator cost data class for economic dispatch and OPF.

    Represents the cost function of a generator, supporting both polynomial
    and piecewise linear cost models as defined in the MATPOWER format.

    Attributes:
        gen_index: Index into System.generators list (0-based).
            Links this cost to a specific generator.
        model: Cost model type:
            - 1: Piecewise linear (points are (MW, $/hr) pairs)
            - 2: Polynomial (coefficients are c_n, ..., c_1, c_0)
        startup: Startup cost [$] (default: 0.0)
        shutdown: Shutdown cost [$] (default: 0.0)
        coefficients: Cost function parameters.
            For polynomial (model=2): [c_n, c_{n-1}, ..., c_1, c_0]
                where cost = c_n * P^n + ... + c_1 * P + c_0
            For piecewise linear (model=1): [x_1, f_1, x_2, f_2, ...]
                where (x_i, f_i) are break points in (MW, $/hr)
        description: Free-text description for LLM-friendly output.

    Note:
        - For polynomial model (model=2), the most common case is quadratic:
          coefficients = [c2, c1, c0] where cost = c2*P^2 + c1*P + c0
        - Power values in coefficients are in MW (not per-unit)
        - Cost values are in $/hr
        - gen_index is 0-based and corresponds to System.generators[gen_index]

    Example:
        >>> # Quadratic cost: 0.04*P^2 + 20*P + 100 $/hr
        >>> cost = GeneratorCost(
        ...     gen_index=0, model=2,
        ...     coefficients=[0.04, 20.0, 100.0]
        ... )
        >>> cost.evaluate(50.0)  # Cost at 50 MW
        1200.0
    """

    gen_index: int
    model: int
    startup: float = 0.0
    shutdown: float = 0.0
    coefficients: list[float] = field(default_factory=list)
    description: str | None = None

    def __post_init__(self) -> None:
        """Validate cost model type after initialization.

        Raises:
            ValueError: If model is not 1 or 2.
        """
        if self.model not in [1, 2]:
            raise ValueError(
                f"Invalid cost model: {self.model}. Must be 1 (piecewise linear) or 2 (polynomial)."
            )

    @property
    def is_polynomial(self) -> bool:
        """Check if this is a polynomial cost model."""
        return self.model == 2

    @property
    def is_piecewise_linear(self) -> bool:
        """Check if this is a piecewise linear cost model."""
        return self.model == 1

    @property
    def n_coefficients(self) -> int:
        """Return the number of coefficients/parameters."""
        return len(self.coefficients)

    def evaluate(self, p_mw: float) -> float:
        """Evaluate cost function at given power output.

        Args:
            p_mw: Active power output [MW]

        Returns:
            Generation cost [$/hr]

        Raises:
            ValueError: If model is piecewise linear (not yet supported)
                or if coefficients are empty.

        Example:
            >>> cost = GeneratorCost(gen_index=0, model=2,
            ...     coefficients=[0.04, 20.0, 100.0])
            >>> cost.evaluate(50.0)
            1200.0
        """
        if self.is_piecewise_linear:
            raise ValueError(
                "Piecewise linear cost evaluation is not yet supported. "
                "Use polynomial model (model=2) for evaluate()."
            )
        if not self.coefficients:
            return 0.0

        # Polynomial evaluation: c_n * P^n + c_{n-1} * P^{n-1} + ... + c_0
        # Using Horner's method for numerical stability
        result = 0.0
        for coeff in self.coefficients:
            result = result * p_mw + coeff
        return result

    def to_description(self) -> str:
        """Generate human/LLM-readable description of this cost function.

        Returns:
            Multi-line string describing the cost function for LLM context.

        Example:
            >>> cost = GeneratorCost(gen_index=0, model=2,
            ...     coefficients=[0.04, 20.0, 100.0])
            >>> print(cost.to_description())
            Generator Cost for gen_index=0: Polynomial
              Coefficients: [0.04, 20.0, 100.0]
              Cost function: 0.0400*P^2 + 20.0000*P + 100.0000
              Startup: $0.00, Shutdown: $0.00
        """
        model_name = "Polynomial" if self.is_polynomial else "Piecewise Linear"

        lines = [
            f"Generator Cost for gen_index={self.gen_index}: {model_name}",
            f"  Coefficients: {self.coefficients}",
        ]

        if self.is_polynomial and self.coefficients:
            terms = []
            n = len(self.coefficients) - 1
            for i, c in enumerate(self.coefficients):
                power = n - i
                if power == 0:
                    terms.append(f"{c:.4f}")
                elif power == 1:
                    terms.append(f"{c:.4f}*P")
                else:
                    terms.append(f"{c:.4f}*P^{power}")
            lines.append(f"  Cost function: {' + '.join(terms)}")

        lines.append(f"  Startup: ${self.startup:.2f}, Shutdown: ${self.shutdown:.2f}")

        if self.description:
            lines.append(f"  Note: {self.description}")

        return "\n".join(lines)
