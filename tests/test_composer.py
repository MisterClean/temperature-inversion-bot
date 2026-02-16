from __future__ import annotations

from temp_inversion_bot.composer import compose_post
from temp_inversion_bot.domain import CombinedAnalysis, InversionStatus, InversionStrength


def test_compose_inversion_snapshot() -> None:
    analysis = CombinedAnalysis(
        primary_station="KORD",
        secondary_station="KMDW",
        status=InversionStatus.INVERSION,
        strength=InversionStrength.MODERATE,
        confidence=0.8,
        max_delta_c=3.5,
        inversion_top_m=450,
        inversion_depth_m=450,
        impact_text="Likely traps pollution/smoke and can keep haze around.",
        mix_out_hint="May persist into afternoon.",
        cross_station_note="KORD/KMDW agree.",
        source="synthetic",
    )

    post = compose_post(analysis)

    expected = (
        "Chicagoland inversion ✅\n"
        "~3.5°C (~6.3°F) warming from surface to ~450 m (moderate). "
        "Likely traps pollution/smoke and can keep haze around. "
        "May persist into afternoon. KORD/KMDW agree."
    )
    assert post == expected
    assert len(post) < 280


def test_compose_no_inversion() -> None:
    analysis = CombinedAnalysis(
        primary_station="KORD",
        secondary_station="KMDW",
        status=InversionStatus.NO_INVERSION,
        strength=InversionStrength.NONE,
        confidence=0.9,
        max_delta_c=0.4,
        inversion_top_m=None,
        inversion_depth_m=None,
        impact_text="Mixing looks decent.",
        source="synthetic",
    )

    post = compose_post(analysis)

    assert "Chicagoland inversion ❌" in post
    assert "Mixing looks decent" in post
    assert len(post) < 280


def test_compose_uncertain() -> None:
    analysis = CombinedAnalysis(
        primary_station="KORD",
        secondary_station="KMDW",
        status=InversionStatus.UNCERTAIN,
        strength=InversionStrength.NONE,
        confidence=0.2,
        max_delta_c=None,
        inversion_top_m=None,
        inversion_depth_m=None,
        impact_text="Data incomplete today.",
        reasoning="Data incomplete today (METAR/forecast profile missing). Will retry later.",
        source="synthetic",
    )

    post = compose_post(analysis)

    assert post.startswith("Chicagoland inversion: uncertain 🤷")
    assert "Data incomplete today" in post
    assert len(post) < 280


def test_character_budget_drops_optional_sections_in_order() -> None:
    analysis = CombinedAnalysis(
        primary_station="KORD",
        secondary_station="KMDW",
        status=InversionStatus.INVERSION,
        strength=InversionStrength.STRONG,
        confidence=0.8,
        max_delta_c=4.8,
        inversion_top_m=900,
        inversion_depth_m=900,
        impact_text=(
            "Likely traps pollution/smoke and can keep haze around while reducing near-surface mixing "
            "through much of the morning period in Chicagoland."
        ),
        mix_out_hint="May persist into afternoon due to light winds.",
        cross_station_note="KORD/KMDW differ today.",
        source="synthetic",
    )

    post = compose_post(analysis, max_length=160)

    assert len(post) <= 160
    assert "May persist into afternoon" not in post
    assert "KORD/KMDW differ today" not in post
    assert "°F" not in post
