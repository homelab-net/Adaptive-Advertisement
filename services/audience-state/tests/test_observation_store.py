"""
Unit tests for ObservationWindow — sliding window smoothing.
Uses an injected clock so no real sleeps are needed.
"""
import pytest
from audience_state.observation_store import ObservationWindow
from tests.conftest import make_observation


# ---------------------------------------------------------------------------
# Test clock helpers
# ---------------------------------------------------------------------------

class FakeClock:
    def __init__(self, t: float = 100.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def make_window(
    window_ms: int = 5000,
    min_stability: int = 3,
    conf_threshold: float = 0.5,
    clock: FakeClock | None = None,
) -> ObservationWindow:
    clk = clock or FakeClock()
    return ObservationWindow(
        window_ms=window_ms,
        min_stability_observations=min_stability,
        confidence_freeze_threshold=conf_threshold,
        _time=clk,
    )


# ---------------------------------------------------------------------------
# Empty window
# ---------------------------------------------------------------------------

class TestEmptyWindow:
    def test_compute_state_returns_none(self):
        w = make_window()
        assert w.compute_state() is None

    def test_newest_age_returns_none(self):
        w = make_window()
        assert w.newest_observation_age_ms() is None

    def test_observation_count_zero(self):
        w = make_window()
        assert w.observation_count() == 0

    def test_total_added_zero(self):
        w = make_window()
        assert w.total_added == 0

    def test_demographics_returns_none(self):
        w = make_window()
        assert w.compute_demographics() is None


# ---------------------------------------------------------------------------
# Basic state computation
# ---------------------------------------------------------------------------

class TestComputeState:
    def test_single_observation_state(self):
        w = make_window(min_stability=1, conf_threshold=0.5)
        w.add(make_observation(count=2, confidence=0.8))
        state = w.compute_state()
        assert state is not None
        assert state["presence"]["count"] == 2
        assert state["presence"]["confidence"] == pytest.approx(0.8)

    def test_mean_count_rounded(self):
        w = make_window(min_stability=1)
        w.add(make_observation(count=1, confidence=0.9, message_id="a"))
        w.add(make_observation(count=2, confidence=0.9, message_id="b"))
        w.add(make_observation(count=2, confidence=0.9, message_id="c"))
        state = w.compute_state()
        # mean of [1,2,2] = 1.67 → rounds to 2
        assert state["presence"]["count"] == 2

    def test_mean_confidence(self):
        w = make_window(min_stability=1)
        w.add(make_observation(confidence=0.6, message_id="a"))
        w.add(make_observation(confidence=0.8, message_id="b"))
        state = w.compute_state()
        assert state["presence"]["confidence"] == pytest.approx(0.7, abs=1e-3)

    def test_observations_in_window_count(self):
        w = make_window(min_stability=2)
        w.add(make_observation(message_id="a"))
        w.add(make_observation(message_id="b"))
        state = w.compute_state()
        assert state["stability"]["observations_in_window"] == 2


# ---------------------------------------------------------------------------
# Stability flags
# ---------------------------------------------------------------------------

class TestStabilityFlags:
    def test_state_stable_when_enough_obs(self):
        w = make_window(min_stability=2)
        w.add(make_observation(message_id="a"))
        w.add(make_observation(message_id="b"))
        state = w.compute_state()
        assert state["stability"]["state_stable"] is True

    def test_not_stable_when_too_few_obs(self):
        w = make_window(min_stability=3)
        w.add(make_observation(message_id="a"))
        w.add(make_observation(message_id="b"))
        state = w.compute_state()
        assert state["stability"]["state_stable"] is False

    def test_freeze_when_not_stable(self):
        w = make_window(min_stability=5)
        w.add(make_observation(message_id="a"))
        state = w.compute_state()
        assert state["stability"]["freeze_decision"] is True

    def test_freeze_when_low_confidence(self):
        w = make_window(min_stability=1, conf_threshold=0.7)
        w.add(make_observation(confidence=0.5))
        state = w.compute_state()
        assert state["stability"]["freeze_decision"] is True

    def test_no_freeze_when_stable_and_confident(self):
        w = make_window(min_stability=1, conf_threshold=0.5)
        w.add(make_observation(confidence=0.9))
        state = w.compute_state()
        assert state["stability"]["freeze_decision"] is False

    def test_freeze_when_pipeline_degraded(self):
        w = make_window(min_stability=1, conf_threshold=0.5)
        w.add(make_observation(pipeline_degraded=True, confidence=0.9))
        state = w.compute_state()
        assert state["stability"]["freeze_decision"] is True

    def test_pipeline_degraded_propagates_from_any_obs(self):
        w = make_window(min_stability=1, conf_threshold=0.5)
        w.add(make_observation(pipeline_degraded=False, message_id="a"))
        w.add(make_observation(pipeline_degraded=True,  message_id="b"))
        w.add(make_observation(pipeline_degraded=False, message_id="c"))
        assert w.any_pipeline_degraded() is True

    def test_not_degraded_when_all_clean(self):
        w = make_window(min_stability=1)
        w.add(make_observation(pipeline_degraded=False, message_id="a"))
        w.add(make_observation(pipeline_degraded=False, message_id="b"))
        assert w.any_pipeline_degraded() is False


# ---------------------------------------------------------------------------
# Window pruning (time-based)
# ---------------------------------------------------------------------------

class TestWindowPruning:
    def test_old_observations_pruned(self):
        clk = FakeClock(t=100.0)
        w = make_window(window_ms=2000, min_stability=1, clock=clk)

        w.add(make_observation(message_id="old"))
        clk.advance(3.0)  # 3 s later — 3000 ms > 2000 ms window
        w.add(make_observation(message_id="new"))

        # Only "new" should survive
        assert w.observation_count() == 1

    def test_recent_observations_retained(self):
        clk = FakeClock(t=100.0)
        w = make_window(window_ms=5000, clock=clk)

        w.add(make_observation(message_id="a"))
        clk.advance(2.0)
        w.add(make_observation(message_id="b"))
        clk.advance(1.0)

        assert w.observation_count() == 2

    def test_total_added_not_affected_by_pruning(self):
        clk = FakeClock(t=100.0)
        w = make_window(window_ms=1000, clock=clk)

        w.add(make_observation(message_id="a"))
        clk.advance(2.0)
        w.add(make_observation(message_id="b"))

        assert w.total_added == 2      # both were added
        assert w.observation_count() == 1  # only recent survives

    def test_compute_state_after_all_pruned(self):
        clk = FakeClock(t=100.0)
        w = make_window(window_ms=1000, clock=clk)
        w.add(make_observation())
        clk.advance(5.0)  # well past window
        assert w.compute_state() is None

    def test_newest_age_uses_most_recent_obs(self):
        clk = FakeClock(t=100.0)
        w = make_window(window_ms=10000, clock=clk)
        w.add(make_observation(message_id="a"))
        clk.advance(1.5)
        w.add(make_observation(message_id="b"))
        clk.advance(0.5)  # now = 102.0; b was at 101.5

        age = w.newest_observation_age_ms()
        assert age is not None
        assert 400 <= age <= 600  # ~500 ms


# ---------------------------------------------------------------------------
# Demographics
# ---------------------------------------------------------------------------

class TestDemographics:
    def _demog(self) -> dict:
        return {
            "age_group": {
                "child": 0.1,
                "young_adult": 0.4,
                "adult": 0.4,
                "senior": 0.1,
            },
            "dwell_estimate_ms": 3000,
        }

    def test_no_demographics_returns_none(self):
        w = make_window(min_stability=1)
        w.add(make_observation())  # no demographics
        assert w.compute_demographics() is None

    def test_all_have_demographics_returns_averages(self):
        w = make_window(min_stability=1, conf_threshold=0.5)
        w.add(make_observation(confidence=0.9, message_id="a", demographics=self._demog()))
        w.add(make_observation(confidence=0.9, message_id="b", demographics=self._demog()))
        d = w.compute_demographics()
        assert d is not None
        assert d["suppressed"] is False
        assert d["age_group"]["adult"] == pytest.approx(0.4)

    def test_mixed_demographics_suppressed(self):
        w = make_window(min_stability=1, conf_threshold=0.5)
        w.add(make_observation(confidence=0.9, message_id="a", demographics=self._demog()))
        w.add(make_observation(confidence=0.9, message_id="b"))  # no demographics
        d = w.compute_demographics()
        assert d is not None
        assert d["suppressed"] is True

    def test_low_confidence_suppresses_demographics(self):
        w = make_window(min_stability=1, conf_threshold=0.7)
        w.add(make_observation(confidence=0.4, demographics=self._demog()))
        d = w.compute_demographics()
        assert d is not None
        assert d["suppressed"] is True


# ---------------------------------------------------------------------------
# Gender smoothing (CRM-003)
# ---------------------------------------------------------------------------

class TestGenderSmoothing:
    def _demog_with_gender(self, male: float = 0.7, female: float = 0.3) -> dict:
        return {
            "age_group": {
                "child": 0.0,
                "young_adult": 0.3,
                "adult": 0.5,
                "senior": 0.2,
            },
            "gender": {"male": male, "female": female},
            "dwell_estimate_ms": 2000,
        }

    def test_gender_smoothed_when_all_obs_have_it(self):
        w = make_window(min_stability=1, conf_threshold=0.5)
        w.add(make_observation(confidence=0.9, message_id="a",
                               demographics=self._demog_with_gender(male=0.8, female=0.2)))
        w.add(make_observation(confidence=0.9, message_id="b",
                               demographics=self._demog_with_gender(male=0.6, female=0.4)))
        d = w.compute_demographics()
        assert d is not None
        assert d["suppressed"] is False
        assert "gender" in d
        assert d["gender"]["male"] == pytest.approx(0.7, abs=1e-3)
        assert d["gender"]["female"] == pytest.approx(0.3, abs=1e-3)

    def test_gender_omitted_when_no_obs_have_it(self):
        w = make_window(min_stability=1, conf_threshold=0.5)
        demog_no_gender = {
            "age_group": {"child": 0.0, "young_adult": 0.3, "adult": 0.5, "senior": 0.2},
        }
        w.add(make_observation(confidence=0.9, message_id="a", demographics=demog_no_gender))
        w.add(make_observation(confidence=0.9, message_id="b", demographics=demog_no_gender))
        d = w.compute_demographics()
        assert d is not None
        assert d["suppressed"] is False
        assert "gender" not in d

    def test_gender_omitted_when_only_some_obs_have_it(self):
        w = make_window(min_stability=1, conf_threshold=0.5)
        demog_no_gender = {
            "age_group": {"child": 0.0, "young_adult": 0.3, "adult": 0.5, "senior": 0.2},
        }
        w.add(make_observation(confidence=0.9, message_id="a",
                               demographics=self._demog_with_gender()))
        w.add(make_observation(confidence=0.9, message_id="b", demographics=demog_no_gender))
        d = w.compute_demographics()
        assert d is not None
        assert d["suppressed"] is False
        assert "gender" not in d


# ---------------------------------------------------------------------------
# Attire smoothing (CRM-005)
# ---------------------------------------------------------------------------

_ATTIRE_BINS = [
    "formal", "business_casual", "casual", "athletic",
    "outdoor_technical", "workwear_uniform", "streetwear",
    "luxury_premium", "lounge_comfort", "smart_occasion",
]


class TestAttireSmoothing:
    def _base_demog(self) -> dict:
        return {
            "age_group": {"child": 0.0, "young_adult": 0.3, "adult": 0.5, "senior": 0.2},
        }

    def _attire_dict(self, value: float = 0.5) -> dict:
        return {b: value for b in _ATTIRE_BINS}

    def _demog_with_attire(self, value: float = 0.5) -> dict:
        d = self._base_demog()
        d["attire"] = self._attire_dict(value)
        return d

    def test_attire_smoothed_when_all_obs_have_it(self):
        w = make_window(min_stability=1, conf_threshold=0.5)
        w.add(make_observation(confidence=0.9, message_id="a",
                               demographics=self._demog_with_attire(0.6)))
        w.add(make_observation(confidence=0.9, message_id="b",
                               demographics=self._demog_with_attire(0.4)))
        d = w.compute_demographics()
        assert d is not None
        assert d["suppressed"] is False
        assert "attire" in d
        assert d["attire"]["athletic"] == pytest.approx(0.5, abs=1e-3)

    def test_attire_omitted_when_no_obs_have_it(self):
        w = make_window(min_stability=1, conf_threshold=0.5)
        w.add(make_observation(confidence=0.9, message_id="a",
                               demographics=self._base_demog()))
        w.add(make_observation(confidence=0.9, message_id="b",
                               demographics=self._base_demog()))
        d = w.compute_demographics()
        assert d is not None
        assert d["suppressed"] is False
        assert "attire" not in d

    def test_attire_omitted_when_only_partial_obs_have_it(self):
        w = make_window(min_stability=1, conf_threshold=0.5)
        w.add(make_observation(confidence=0.9, message_id="a",
                               demographics=self._demog_with_attire()))
        w.add(make_observation(confidence=0.9, message_id="b",
                               demographics=self._base_demog()))
        d = w.compute_demographics()
        assert d is not None
        assert d["suppressed"] is False
        assert "attire" not in d

    def test_all_ten_attire_bins_present(self):
        w = make_window(min_stability=1, conf_threshold=0.5)
        w.add(make_observation(confidence=0.9, demographics=self._demog_with_attire(0.1)))
        d = w.compute_demographics()
        assert d is not None
        assert "attire" in d
        for bin_name in _ATTIRE_BINS:
            assert bin_name in d["attire"]


# ---------------------------------------------------------------------------
# Attention smoothing (CRM-004)
# ---------------------------------------------------------------------------

class TestAttentionSmoothing:
    def test_attention_absent_returns_none(self):
        w = make_window(min_stability=1)
        w.add(make_observation())  # no attention
        assert w.compute_attention() is None

    def test_empty_window_returns_none(self):
        w = make_window()
        assert w.compute_attention() is None

    def test_single_obs_with_attention_returns_value(self):
        w = make_window(min_stability=1)
        w.add(make_observation(attention={"engaged": 0.6, "ambient": 0.4}))
        attn = w.compute_attention()
        assert attn is not None
        assert attn["engaged"] == pytest.approx(0.6)
        assert attn["ambient"] == pytest.approx(0.4)

    def test_attention_averaged_across_obs(self):
        w = make_window(min_stability=1)
        w.add(make_observation(message_id="a", attention={"engaged": 0.8}))
        w.add(make_observation(message_id="b", attention={"engaged": 0.6}))
        attn = w.compute_attention()
        assert attn is not None
        assert attn["engaged"] == pytest.approx(0.7, abs=1e-3)

    def test_attention_partial_obs_averages_only_present(self):
        """If only some obs have attention, average only those that do."""
        w = make_window(min_stability=1)
        w.add(make_observation(message_id="a", attention={"engaged": 0.8}))
        w.add(make_observation(message_id="b"))  # no attention
        attn = w.compute_attention()
        assert attn is not None
        assert attn["engaged"] == pytest.approx(0.8)

    def test_attention_engaged_only_no_ambient(self):
        w = make_window(min_stability=1)
        w.add(make_observation(attention={"engaged": 0.5}))
        attn = w.compute_attention()
        assert attn is not None
        assert "engaged" in attn
        assert "ambient" not in attn

    def test_attention_independent_of_demographics_suppressed(self):
        """Attention is a behavioral metric — not gated by demographic suppression."""
        age = {"child": 0.0, "young_adult": 0.3, "adult": 0.5, "senior": 0.2}
        # Low confidence forces demographics to be suppressed
        w = make_window(min_stability=1, conf_threshold=0.9)
        w.add(make_observation(
            confidence=0.3,
            demographics={"age_group": age},
            attention={"engaged": 0.7},
        ))
        # Demographics should be suppressed due to low confidence
        d = w.compute_demographics()
        assert d is not None and d["suppressed"] is True
        # Attention should still be returned regardless of demographic suppression
        attn = w.compute_attention()
        assert attn is not None
        assert attn["engaged"] == pytest.approx(0.7)
