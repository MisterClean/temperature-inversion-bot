from __future__ import annotations

from temp_inversion_bot.domain import CombinedAnalysis, InversionStatus

_MAX_POST_LENGTH = 280


def _c_to_f_delta(delta_c: float) -> float:
    return delta_c * 9.0 / 5.0


def _emoji(status: InversionStatus, max_delta_c: float | None) -> str:
    if status == InversionStatus.UNCERTAIN:
        return "🤷"
    if status == InversionStatus.NO_INVERSION:
        return "❌"
    if status == InversionStatus.LOCALIZED:
        return "⚠️"
    if max_delta_c is not None and max_delta_c < 2.0:
        return "⚠️"
    return "✅"


def _build_inversion_text(
    analysis: CombinedAnalysis,
    include_mix_out: bool,
    include_station_note: bool,
    include_fahrenheit: bool,
) -> str:
    emoji = _emoji(analysis.status, analysis.max_delta_c)
    header = f"Chicagoland inversion {emoji}"

    delta_text = "unknown"
    if analysis.max_delta_c is not None:
        delta_text = f"~{analysis.max_delta_c:.1f}°C"
        if include_fahrenheit:
            delta_f = _c_to_f_delta(analysis.max_delta_c)
            delta_text = f"{delta_text} (~{delta_f:.1f}°F)"

    depth_text = "in the lower atmosphere"
    if analysis.inversion_top_m is not None:
        depth_text = f"from surface to ~{analysis.inversion_top_m:.0f} m"
    elif analysis.inversion_depth_m is not None:
        depth_text = f"in lowest ~{analysis.inversion_depth_m:.0f} m"

    strength_text = analysis.strength.value
    line_two = f"{delta_text} warming {depth_text} ({strength_text}). {analysis.impact_text}"

    extras: list[str] = []
    if include_mix_out and analysis.mix_out_hint:
        extras.append(analysis.mix_out_hint)
    if include_station_note and analysis.cross_station_note:
        extras.append(analysis.cross_station_note)

    if extras:
        line_two = f"{line_two} {' '.join(extras)}"

    return f"{header}\n{line_two}"


def _build_no_inversion_text(analysis: CombinedAnalysis, include_station_note: bool) -> str:
    header = "Chicagoland inversion ❌"
    if analysis.max_delta_c is not None:
        body = (
            f"No meaningful near-surface inversion in today’s profile "
            f"(max warming ~{analysis.max_delta_c:.1f}°C). Mixing looks decent."
        )
    else:
        body = "No meaningful near-surface inversion in today’s profile. Mixing looks decent."
    if include_station_note and analysis.cross_station_note:
        body = f"{body} {analysis.cross_station_note}"
    return f"{header}\n{body}"


def _build_uncertain_text(analysis: CombinedAnalysis) -> str:
    header = "Chicagoland inversion: uncertain 🤷"
    reason = analysis.reasoning or "Data incomplete today (METAR/forecast profile missing). Will retry later."
    return f"{header}\n{reason}"


def compose_post(analysis: CombinedAnalysis, max_length: int = _MAX_POST_LENGTH) -> str:
    if analysis.status == InversionStatus.UNCERTAIN:
        message = _build_uncertain_text(analysis)
        return message[:max_length]

    if analysis.status == InversionStatus.NO_INVERSION:
        candidate = _build_no_inversion_text(analysis, include_station_note=True)
        if len(candidate) <= max_length:
            return candidate

        candidate = _build_no_inversion_text(analysis, include_station_note=False)
        return candidate[:max_length]

    versions = [
        (True, True, True),
        (False, True, True),
        (False, False, True),
        (False, False, False),
    ]
    for include_mix_out, include_station_note, include_fahrenheit in versions:
        candidate = _build_inversion_text(
            analysis,
            include_mix_out=include_mix_out,
            include_station_note=include_station_note,
            include_fahrenheit=include_fahrenheit,
        )
        if len(candidate) <= max_length:
            return candidate

    fallback = _build_inversion_text(
        analysis,
        include_mix_out=False,
        include_station_note=False,
        include_fahrenheit=False,
    )
    return fallback[:max_length]
