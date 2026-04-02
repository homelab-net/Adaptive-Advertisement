"""
Observation window — sliding time-window smoothing of ICD-2 cv-observations.

Responsibilities
----------------
- Hold a bounded sliding window of recent cv-observation dicts
- Prune observations older than WINDOW_MS on every add/query
- Compute smoothed ICD-3 state from the window on demand:
    presence.count        — arithmetic mean, rounded to nearest int
    presence.confidence   — arithmetic mean
    stability.state_stable    — True if obs count >= min_stability_observations
    stability.freeze_decision — True if not stable, or low confidence, or degraded
    stability.observations_in_window — raw count for observability

Testability
-----------
The constructor accepts an optional _time callable (default: time.monotonic) so
tests can inject a controllable clock without patching globals.

Privacy note
------------
No image data ever enters this window. Observations are validated by
ObservationConsumer before being added here. The window stores only dicts
that have already passed ICD-2 schema validation (privacy const:false enforced).
"""
import time
import logging
from dataclasses import dataclass
from typing import Callable, Optional

log = logging.getLogger(__name__)


@dataclass
class _Stored:
    data: dict
    received_at: float  # monotonic seconds


class ObservationWindow:
    def __init__(
        self,
        window_ms: int,
        min_stability_observations: int,
        confidence_freeze_threshold: float,
        _time: Optional[Callable[[], float]] = None,
    ) -> None:
        if window_ms < 100:
            raise ValueError(f"window_ms must be >= 100 ms, got {window_ms}")
        if min_stability_observations < 1:
            raise ValueError(
                f"min_stability_observations must be >= 1, got {min_stability_observations}"
            )
        if not (0.0 <= confidence_freeze_threshold <= 1.0):
            raise ValueError(
                f"confidence_freeze_threshold must be in [0.0, 1.0], "
                f"got {confidence_freeze_threshold}"
            )
        self._window_ms = window_ms
        self._min_stability = min_stability_observations
        self._conf_threshold = confidence_freeze_threshold
        self._now: Callable[[], float] = _time or time.monotonic
        self._observations: list[_Stored] = []
        self._total_added: int = 0

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(self, observation: dict) -> None:
        """Add a validated ICD-2 observation dict to the window."""
        self._prune()
        self._observations.append(_Stored(data=observation, received_at=self._now()))
        self._total_added += 1

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def compute_state(self) -> Optional[dict]:
        """
        Return the ICD-3 state block (presence + stability), or None if the
        window is empty after pruning.
        """
        self._prune()
        if not self._observations:
            return None

        obs = self._observations
        n = len(obs)

        counts = [o.data["counts"]["present"] for o in obs]
        confs = [o.data["counts"]["confidence"] for o in obs]
        smoothed_count = round(sum(counts) / n)
        smoothed_conf = round(sum(confs) / n, 4)

        pipeline_degraded = any(
            o.data["quality"].get("pipeline_degraded", False) for o in obs
        )
        state_stable = n >= self._min_stability
        freeze_decision = (
            not state_stable
            or smoothed_conf < self._conf_threshold
            or pipeline_degraded
        )

        return {
            "presence": {
                "count": smoothed_count,
                "confidence": smoothed_conf,
            },
            "stability": {
                "state_stable": state_stable,
                "freeze_decision": freeze_decision,
                "observations_in_window": n,
            },
        }

    def compute_demographics(self) -> Optional[dict]:
        """
        Return a smoothed demographics block, or None if demographics are
        absent from any observation in the window (suppressed by policy).

        If all observations have demographics AND confidence is above threshold,
        return averaged age_group distributions and the latest dwell_estimate_ms.
        Otherwise return {"suppressed": True}.
        """
        self._prune()
        if not self._observations:
            return None

        obs_with_demog = [
            o for o in self._observations if o.data.get("demographics") is not None
        ]

        # No observations have demographics → omit the field entirely
        if not obs_with_demog:
            return None

        # Some but not all have demographics → suppress
        if len(obs_with_demog) < len(self._observations):
            return {"suppressed": True}

        confs = [o.data["counts"]["confidence"] for o in self._observations]
        avg_conf = sum(confs) / len(confs)
        if avg_conf < self._conf_threshold:
            return {"suppressed": True}

        # Average age_group distributions
        age_bins = ["child", "young_adult", "adult", "senior"]
        smoothed_ages: dict[str, float] = {}
        for bin_name in age_bins:
            values = [
                o.data["demographics"].get("age_group", {}).get(bin_name)
                for o in obs_with_demog
            ]
            if any(v is None for v in values):
                # Bin absent in at least one observation → suppress
                return {"suppressed": True}
            smoothed_ages[bin_name] = round(sum(values) / len(values), 4)  # type: ignore[arg-type]

        # Average gender distributions (optional — only if ALL obs carry gender)
        gender_bins = ["male", "female"]
        smoothed_genders: dict[str, float] | None = None
        if all(o.data["demographics"].get("gender") is not None for o in obs_with_demog):
            genders: dict[str, float] = {}
            for bin_name in gender_bins:
                values = [
                    o.data["demographics"]["gender"].get(bin_name)
                    for o in obs_with_demog
                ]
                if any(v is None for v in values):
                    genders = {}
                    break
                genders[bin_name] = round(sum(values) / len(values), 4)  # type: ignore[arg-type]
            if genders:
                smoothed_genders = genders

        # Average attire distributions (optional — only if ALL obs carry attire)
        attire_bins = [
            "formal", "business_casual", "casual", "athletic",
            "outdoor_technical", "workwear_uniform", "streetwear",
            "luxury_premium", "lounge_comfort", "smart_occasion",
        ]
        smoothed_attire: dict[str, float] | None = None
        if all(o.data["demographics"].get("attire") is not None for o in obs_with_demog):
            attire: dict[str, float] = {}
            for bin_name in attire_bins:
                values = [
                    o.data["demographics"]["attire"].get(bin_name)
                    for o in obs_with_demog
                ]
                if any(v is None for v in values):
                    attire = {}
                    break
                attire[bin_name] = round(sum(values) / len(values), 4)  # type: ignore[arg-type]
            if attire:
                smoothed_attire = attire

        # Use the latest dwell estimate
        latest_dwell = obs_with_demog[-1].data["demographics"].get("dwell_estimate_ms")

        result: dict = {
            "age_group": smoothed_ages,
            "suppressed": False,
        }
        if smoothed_genders is not None:
            result["gender"] = smoothed_genders
        if smoothed_attire is not None:
            result["attire"] = smoothed_attire
        if latest_dwell is not None:
            result["dwell_estimate_ms"] = latest_dwell
        return result

    def compute_attention(self) -> Optional[dict]:
        """
        Return a smoothed attention block, or None if no observations in the
        window carry attention data.

        Averages engaged/ambient across all observations that include an
        attention block. Behavioral metric — not gated by demographics_suppressed.
        """
        self._prune()
        if not self._observations:
            return None

        obs_with_attn = [
            o for o in self._observations if o.data.get("attention") is not None
        ]
        if not obs_with_attn:
            return None

        result: dict = {}
        for field in ("engaged", "ambient"):
            values = [
                o.data["attention"].get(field)
                for o in obs_with_attn
            ]
            present = [v for v in values if v is not None]
            if present:
                result[field] = round(sum(present) / len(present), 4)

        return result if result else None

    def newest_observation_age_ms(self) -> Optional[int]:
        """
        Milliseconds since the most recent observation was received.
        Returns None if the window is empty after pruning.
        """
        self._prune()
        if not self._observations:
            return None
        return int((self._now() - self._observations[-1].received_at) * 1000)

    def any_pipeline_degraded(self) -> bool:
        self._prune()
        return any(
            o.data["quality"].get("pipeline_degraded", False)
            for o in self._observations
        )

    def observation_count(self) -> int:
        self._prune()
        return len(self._observations)

    @property
    def total_added(self) -> int:
        return self._total_added

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _prune(self) -> None:
        cutoff = self._now() - (self._window_ms / 1000)
        self._observations = [o for o in self._observations if o.received_at >= cutoff]
