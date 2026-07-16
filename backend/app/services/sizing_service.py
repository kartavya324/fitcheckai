"""
Size & Fit advisor.

Estimates body measurements from height/weight/sex, then recommends a size per
category (tops/bottoms) using standard size charts — adjusted for the user's fit
preference and for brands that run small or large. This is the single biggest
lever on fashion returns (size/fit uncertainty drives ~40% of them).

Measurements are transparent estimates, not exact — the API labels them as such.
Photo-based build refinement is a planned enhancement (see recommend()).
"""
from __future__ import annotations

SIZES = ["XS", "S", "M", "L", "XL", "XXL"]

# Size charts: ordered (label, low_cm, high_cm) by the driving measurement.
CHARTS: dict[str, dict[str, list[tuple[str, float, float]]]] = {
    "male": {
        "tops": [  # by chest circumference (cm)
            ("XS", 0, 86), ("S", 86, 92), ("M", 92, 98),
            ("L", 98, 104), ("XL", 104, 112), ("XXL", 112, 999),
        ],
        "bottoms": [  # by waist circumference (cm)
            ("XS", 0, 72), ("S", 72, 78), ("M", 78, 84),
            ("L", 84, 92), ("XL", 92, 100), ("XXL", 100, 999),
        ],
    },
    "female": {
        "tops": [  # by bust circumference (cm)
            ("XS", 0, 82), ("S", 82, 87), ("M", 87, 92),
            ("L", 92, 98), ("XL", 98, 105), ("XXL", 105, 999),
        ],
        "bottoms": [  # by waist circumference (cm)
            ("XS", 0, 64), ("S", 64, 69), ("M", 69, 74),
            ("L", 74, 80), ("XL", 80, 88), ("XXL", 88, 999),
        ],
    },
}

# How a brand runs, in size steps: +1 = runs small (size up), -1 = runs large.
BRAND_OFFSETS: dict[str, int] = {
    "zara": 1,
    "h&m": 1,
    "uniqlo": 0,
    "nike": 0,
    "adidas": 0,
    "levi's": 0,
    "roadster": 0,
    "u.s. polo assn.": 0,
    "allen solly": 0,
    "generic": 0,
}

FIT_OFFSETS = {"fitted": -1, "regular": 0, "relaxed": 1}


def estimate_measurements(
    height_cm: float, weight_kg: float, sex: str, build_factor: float = 0.0
) -> dict:
    """
    Transparent estimates of chest/bust and waist circumference (cm) from
    height, weight and sex. `build_factor` (-1 slim … +1 broad, e.g. from a
    photo) nudges the chest estimate. Calibrated to anchor personas; clearly
    an estimate, not a measurement.
    """
    sex = "female" if sex.lower().startswith("f") else "male"

    # Linear anchors: (weight, height) -> circumference, tuned so an average
    # build (BMI ~22-24) lands on M in the charts below.
    chest = 0.45 * weight_kg + 0.20 * height_cm + 27.0
    waist = 0.6125 * weight_kg + 0.15 * height_cm + 9.5

    if sex == "female":
        chest -= 3.0   # bust vs chest baseline
        waist -= 7.0   # women typically carry less at the natural waist

    chest += build_factor * 3.0  # broader/narrower frame

    bmi = weight_kg / ((height_cm / 100.0) ** 2) if height_cm else 0.0
    return {
        "chest_cm": round(chest, 1),
        "waist_cm": round(waist, 1),
        "bmi": round(bmi, 1),
    }


def _base_size(value: float, chart: list[tuple[str, float, float]]) -> str:
    for label, lo, hi in chart:
        if lo <= value < hi:
            return label
    return chart[-1][0]


def _shift(label: str, steps: int) -> str:
    idx = max(0, min(len(SIZES) - 1, SIZES.index(label) + steps))
    return SIZES[idx]


def recommend(
    *,
    height_cm: float,
    weight_kg: float,
    sex: str,
    fit_preference: str = "regular",
    brand: str | None = None,
    categories: list[str] | None = None,
    build_factor: float = 0.0,
) -> dict:
    """
    Return a size recommendation per category with the estimated measurements
    and the chart range for the recommended size.

    Future enhancement: derive `build_factor` from the user's full-body photo
    (shoulder-width / height ratio off the silhouette) to refine chest sizing.
    """
    sex_key = "female" if sex.lower().startswith("f") else "male"
    categories = categories or ["tops", "bottoms"]
    fit_offset = FIT_OFFSETS.get(fit_preference.lower(), 0)
    brand_key = (brand or "generic").strip().lower()
    brand_offset = BRAND_OFFSETS.get(brand_key, 0)

    measurements = estimate_measurements(height_cm, weight_kg, sex_key, build_factor)
    driver = {"tops": measurements["chest_cm"], "bottoms": measurements["waist_cm"]}

    recs = []
    for cat in categories:
        if cat not in ("tops", "bottoms"):
            continue
        chart = CHARTS[sex_key][cat]
        base = _base_size(driver[cat], chart)
        final = _shift(base, brand_offset + fit_offset)
        lo, hi = next((lo, hi) for lbl, lo, hi in chart if lbl == final)

        # "Between sizes" hint: within 1.5cm of the recommended size's boundary
        value = driver[cat]
        between = None
        if value - lo < 1.5 and SIZES.index(final) > 0:
            between = _shift(final, -1)
        elif hi < 999 and hi - value < 1.5:
            between = _shift(final, 1)

        recs.append(
            {
                "category": cat,
                "size": final,
                "base_size": base,
                "driver_cm": driver[cat],
                "range_cm": [lo, None if hi >= 999 else hi],
                "adjusted": final != base,
                "between_size": between,  # user is borderline; consider this too
            }
        )

    notes = []
    if brand_offset > 0:
        notes.append(f"{brand} tends to run small — we sized you up.")
    elif brand_offset < 0:
        notes.append(f"{brand} tends to run large — we sized you down.")
    if fit_offset:
        notes.append(
            f"Adjusted for your {fit_preference} fit preference."
        )
    if build_factor:
        notes.append("Refined using your photo's build.")

    return {
        "sex": sex_key,
        "brand": brand or "generic",
        "fit_preference": fit_preference,
        "measurements": measurements,
        "recommendations": recs,
        "notes": notes,
        "disclaimer": (
            "Measurements are estimates from height and weight. For the best fit, "
            "compare the size range against a garment you already own that fits well."
        ),
    }
