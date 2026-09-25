"""Single entry point used by the services to version their artifacts."""

from __future__ import annotations

from typing import Any, Mapping

from ..errors import ValidationError
from ..ids import SequenceIds
from .baseline import Baseline, BaselineRegistry
from .confirmation import Confirmation, ConfirmationLedger
from .expiry import Validity
from .generation import GenerationRegistry, GenerationToken


class VersionedArtifacts:
    """Generations, confirmations and baselines behind one facade."""

    __slots__ = ("_generations", "_confirmations", "_baselines", "_ids")

    def __init__(
        self,
        generations: GenerationRegistry,
        confirmations: ConfirmationLedger,
        baselines: BaselineRegistry,
        ids: SequenceIds,
    ) -> None:
        self._generations = generations
        self._confirmations = confirmations
        self._baselines = baselines
        self._ids = ids

    @classmethod
    def fresh(cls, ids: SequenceIds) -> "VersionedArtifacts":
        return cls(GenerationRegistry(), ConfirmationLedger(), BaselineRegistry(), ids)

    @property
    def generations(self) -> GenerationRegistry:
        return self._generations

    @property
    def confirmations(self) -> ConfirmationLedger:
        return self._confirmations

    @property
    def baselines(self) -> BaselineRegistry:
        return self._baselines

    def bump(self, subject: str, *, tick: int) -> GenerationToken:
        """Issue a new generation for ``subject``."""

        return self._generations.bump(subject, tick)

    def current_generation(self, subject: str) -> int:
        return self._generations.current(subject)

    def observe(self, subject: str, value: int) -> None:
        self._generations.observe(subject, value)

    def confirm(
        self,
        subject: str,
        *,
        tick: int,
        ttl_ticks: int,
        issuer: str,
    ) -> Confirmation:
        """Record a confirmation against the newest generation."""

        generation = self._generations.current(subject)
        if generation < 1:
            raise ValidationError("confirmations need an issued generation first", subject=subject)
        if not issuer:
            raise ValidationError("confirmation must name its issuer", subject=subject)
        confirmation = Confirmation(
            confirmation_id=self._ids.next("conf"),
            subject=subject,
            generation=generation,
            issuer=issuer,
            validity=Validity.of(tick, ttl_ticks),
        )
        self._confirmations.record(confirmation)
        return confirmation

    def require_confirmation(self, subject: str, *, generation: int, now: int) -> Confirmation:
        return self._confirmations.require(subject, generation=generation, now=now)

    def confirmation_state(self, subject: str, *, now: int) -> Mapping[str, Any] | None:
        confirmation = self._confirmations.latest(subject)
        if confirmation is None:
            return None
        return confirmation.describe(now)

    def publish_baseline(
        self,
        name: str,
        value: float,
        unit: str,
        *,
        tick: int,
        ttl_ticks: int,
    ) -> Baseline:
        """Publish a calibration value under a fresh generation."""

        token = self._generations.bump(name, tick)
        baseline = Baseline(
            name=name,
            value=value,
            unit=unit,
            generation=token.value,
            validity=Validity.of(tick, ttl_ticks),
        )
        self._baselines.publish(baseline)
        return baseline

    def adopt_baseline(self, name: str, value: float, unit: str, generation: int, *, validity: Validity) -> None:
        """Adopt a baseline read back from the stream during replay."""

        self._generations.observe(name, generation)
        self._baselines.publish(
            Baseline(name=name, value=value, unit=unit, generation=generation, validity=validity)
        )

    def require_baseline(self, name: str, *, generation: int, now: int) -> Baseline:
        return self._baselines.require(name, generation=generation, now=now)

    def baseline_value(self, name: str) -> float | None:
        baseline = self._baselines.current(name)
        return None if baseline is None else baseline.value

    def describe(self, now: int) -> dict[str, Any]:
        """Summarise the versioned artifacts for the console."""

        baselines = {
            name: self._baselines.current(name).describe(now)  # type: ignore[union-attr]
            for name in self._baselines.names()
        }
        confirmations = {
            subject: self._confirmations.latest(subject).describe(now)  # type: ignore[union-attr]
            for subject in self._confirmations.subjects()
        }
        return {
            "generations": self._generations.snapshot(),
            "baselines": baselines,
            "confirmations": confirmations,
        }
