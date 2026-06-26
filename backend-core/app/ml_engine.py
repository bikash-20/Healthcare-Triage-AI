"""Rule-based vital-sign anomaly detector.

This module is intentionally conservative — it never asserts a diagnosis, it
just flags parameters that fall outside the WHO/community-health-worker safety
range so the LLM triage step can prioritize review.

Each rule produces an alert string. The overall ``level`` is the worst-case
score across all alerts. Order of severity: green < yellow < red.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("ml_engine")

# ---------------------------------------------------------------------------
# Thresholds (tuned for adult community-health triage in South Asia)
# ---------------------------------------------------------------------------
THRESHOLDS = {
    "spo2_red": 90.0,
    "spo2_yellow": 94.0,
    "temp_f_high_red": 103.0,
    "temp_f_high_yellow": 100.4,
    "temp_f_low_red": 95.0,
    "hr_red_low": 40.0,
    "hr_red_high": 140.0,
    "hr_yellow_low": 50.0,
    "hr_yellow_high": 120.0,
    "glucose_red_low": 50.0,
    "glucose_red_high": 300.0,
    "glucose_yellow_low": 70.0,
    "glucose_yellow_high": 200.0,
    "systolic_red_high": 180.0,
    "systolic_red_low": 90.0,
    "systolic_yellow_high": 140.0,
    "systolic_yellow_low": 100.0,
    "diastolic_red_high": 120.0,
    "diastolic_red_low": 60.0,
}

SEVERITY_RANK = {"green": 0, "yellow": 1, "red": 2, "black": 3}


def _to_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_bp(bp: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    if not bp or "/" not in str(bp):
        return (None, None)
    try:
        sys_v, dia_v = str(bp).split("/", 1)
        return float(sys_v), float(dia_v)
    except (TypeError, ValueError):
        return (None, None)


def _escalate(current: str, candidate: str) -> str:
    if SEVERITY_RANK[candidate] > SEVERITY_RANK[current]:
        return candidate
    return current


def analyze_vitals(vitals: dict) -> dict:
    """Return ``{level, alerts, parsed}`` for the given vitals dict."""
    alerts: list[str] = []
    level = "green"

    spo2 = _to_float(vitals.get("spo2"))
    temp = _to_float(vitals.get("temp"))
    hr = _to_float(vitals.get("hr"))
    glucose = _to_float(vitals.get("glucose"))
    systolic, diastolic = _parse_bp(vitals.get("bp"))

    # SpO₂
    if spo2 is not None:
        if spo2 < THRESHOLDS["spo2_red"]:
            alerts.append(f"Critical low SpO₂ ({spo2}%)")
            level = _escalate(level, "red")
        elif spo2 < THRESHOLDS["spo2_yellow"]:
            alerts.append(f"Low SpO₂ ({spo2}%)")
            level = _escalate(level, "yellow")

    # Temperature (Fahrenheit)
    if temp is not None:
        if temp > THRESHOLDS["temp_f_high_red"]:
            alerts.append(f"High fever ({temp}°F)")
            level = _escalate(level, "red")
        elif temp > THRESHOLDS["temp_f_high_yellow"]:
            alerts.append(f"Fever ({temp}°F)")
            level = _escalate(level, "yellow")
        elif temp < THRESHOLDS["temp_f_low_red"]:
            alerts.append(f"Hypothermia ({temp}°F)")
            level = _escalate(level, "red")

    # Heart rate
    if hr is not None:
        if hr < THRESHOLDS["hr_red_low"] or hr > THRESHOLDS["hr_red_high"]:
            alerts.append(f"Abnormal heart rate ({hr} bpm)")
            level = _escalate(level, "red")
        elif hr < THRESHOLDS["hr_yellow_low"] or hr > THRESHOLDS["hr_yellow_high"]:
            alerts.append(f"Heart rate out of range ({hr} bpm)")
            level = _escalate(level, "yellow")

    # Glucose
    if glucose is not None:
        if (
            glucose < THRESHOLDS["glucose_red_low"]
            or glucose > THRESHOLDS["glucose_red_high"]
        ):
            alerts.append(f"Critical glucose ({glucose} mg/dL)")
            level = _escalate(level, "red")
        elif (
            glucose < THRESHOLDS["glucose_yellow_low"]
            or glucose > THRESHOLDS["glucose_yellow_high"]
        ):
            alerts.append(f"Glucose out of range ({glucose} mg/dL)")
            level = _escalate(level, "yellow")

    # Blood pressure
    if systolic is not None:
        if (
            systolic > THRESHOLDS["systolic_red_high"]
            or systolic < THRESHOLDS["systolic_red_low"]
        ):
            alerts.append(f"Critical BP systolic ({systolic} mmHg)")
            level = _escalate(level, "red")
        elif (
            systolic > THRESHOLDS["systolic_yellow_high"]
            or systolic < THRESHOLDS["systolic_yellow_low"]
        ):
            alerts.append(f"BP systolic elevated/low ({systolic} mmHg)")
            level = _escalate(level, "yellow")
    if diastolic is not None:
        if (
            diastolic > THRESHOLDS["diastolic_red_high"]
            or diastolic < THRESHOLDS["diastolic_red_low"]
        ):
            alerts.append(f"Critical BP diastolic ({diastolic} mmHg)")
            level = _escalate(level, "red")

    return {
        "level": level,
        "alerts": alerts,
        "parsed": {
            "spo2": spo2,
            "temp": temp,
            "hr": hr,
            "glucose": glucose,
            "systolic": systolic,
            "diastolic": diastolic,
        },
    }
