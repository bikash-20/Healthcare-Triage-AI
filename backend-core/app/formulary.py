"""Rural Bangladesh primary-care formulary.

A deterministic, hand-curated dataset of the WHO Model List of Essential
Medicines plus Bangladesh national essential medicines, scoped to the
~80 generic drugs a community health worker (CHW) will actually see in
the field. The point of this module is to replace the LLM-first dose
calculation with a vetted lookup that cannot hallucinate. The LLM is
still available, but only as a *post-hoc explanation* of the formula
result, never as the source of truth.

Each entry encodes the standard pediatric / adult dose used in WHO and
Bangladesh primary-care protocols, with safety rails (max single dose,
max daily dose, minimum age, route) and bilingual (English / Bangla)
display strings.

Disclaimer: This module is decision-support, not a prescription. Any
dose returned here must be reviewed by a qualified clinician before
administration. The free-text warnings are clinical cautions, not
substitutes for medical advice.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data shape
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DoseRule:
    """How to compute a single dose for one drug.

    All numeric values are in the units stated in the field name (mg for
    fixed-dose drugs, mg/kg for weight-banded drugs). ``freq_per_day``
    is how many doses in 24 hours. ``min_age_months`` is the youngest
    patient the rule applies to; very high values mean adult-only.
    """

    mg_per_kg_per_dose: Optional[float] = None
    fixed_mg_per_dose: Optional[float] = None
    max_single_mg: Optional[float] = None
    max_daily_mg_per_kg: Optional[float] = None
    max_daily_mg: Optional[float] = None
    freq_per_day: int = 1
    min_age_months: int = 0
    route: str = "Oral"
    interval_hours: Optional[int] = None
    warnings_en: Tuple[str, ...] = field(default_factory=tuple)
    warnings_bn: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DrugEntry:
    """One drug in the formulary."""

    key: str  # canonical English lookup key, lowercase, no spaces
    display_en: str
    display_bn: str
    category: str  # e.g. "antibiotic", "antipyretic"
    adult_rule: Optional[DoseRule] = None
    pediatric_rule: Optional[DoseRule] = None
    notes_en: str = ""
    notes_bn: str = ""
    aliases: Tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

def _ped(
    mg_per_kg: float,
    *,
    max_single: float,
    max_daily_per_kg: Optional[float] = None,
    freq: int = 4,
    interval: Optional[int] = None,
    min_age_months: int = 1,
    route: str = "Oral",
    warnings_en: Tuple[str, ...] = (),
    warnings_bn: Tuple[str, ...] = (),
) -> DoseRule:
    return DoseRule(
        mg_per_kg_per_dose=mg_per_kg,
        max_single_mg=max_single,
        max_daily_mg_per_kg=max_daily_per_kg or (mg_per_kg * freq),
        freq_per_day=freq,
        interval_hours=interval or (24 // max(freq, 1)),
        min_age_months=min_age_months,
        route=route,
        warnings_en=warnings_en,
        warnings_bn=warnings_bn,
    )


def _adult(
    fixed_mg: float,
    *,
    max_daily: float,
    freq: int = 4,
    interval: Optional[int] = None,
    route: str = "Oral",
    warnings_en: Tuple[str, ...] = (),
    warnings_bn: Tuple[str, ...] = (),
) -> DoseRule:
    return DoseRule(
        fixed_mg_per_dose=fixed_mg,
        max_single_mg=fixed_mg,
        max_daily_mg=max_daily,
        freq_per_day=freq,
        interval_hours=interval or (24 // max(freq, 1)),
        min_age_months=12 * 12,  # 12 years — pediatric rule wins below this
        route=route,
        warnings_en=warnings_en,
        warnings_bn=warnings_bn,
    )


# ---------------------------------------------------------------------------
# Formulary entries (alphabetized by category, then by display_en)
# ---------------------------------------------------------------------------

_FORMULARY: Dict[str, DrugEntry] = {}


def _add(entry: DrugEntry) -> None:
    _FORMULARY[entry.key] = entry
    for alias in entry.aliases:
        _FORMULARY.setdefault(alias.lower(), entry)


def _unique_entries() -> Dict[str, DrugEntry]:
    """Return canonical entries keyed by their stable drug key."""
    return {entry.key: entry for entry in _FORMULARY.values()}


# ---------- Analgesics / antipyretics ---------------------------------------

_add(DrugEntry(
    key="paracetamol",
    display_en="Paracetamol (Acetaminophen)",
    display_bn="প্যারাসিটামল",
    category="analgesic",
    pediatric_rule=_ped(15, max_single=1000, freq=4, interval=6,
                        min_age_months=1,
                        warnings_en=("Do not exceed 4 doses in 24 hours.",
                                     "Avoid in severe liver disease."),
                        warnings_bn=("২৪ ঘণ্টায় ৪ ডোজের বেশি দেবেন না।",
                                     "গুরুতর লিভারের রোগে এড়িয়ে চলুন।")),
    adult_rule=_adult(500, max_daily=4000, freq=4, interval=6),
    notes_en="First-line for fever and mild-moderate pain in all ages.",
    notes_bn="সব বয়সে জ্বর ও হালকা-মাঝারি ব্যথার প্রথম পছন্দ।",
    aliases=("acetaminophen", "tylenol"),
))

_add(DrugEntry(
    key="ibuprofen",
    display_en="Ibuprofen",
    display_bn="আইবুপ্রোফেন",
    category="nsaid",
    pediatric_rule=_ped(10, max_single=400, freq=3, interval=8,
                        min_age_months=6,
                        warnings_en=("Give with food.",
                                     "Avoid in asthma, dehydration, or renal impairment."),
                        warnings_bn=("খাবারের সাথে দিন।",
                                     "হাঁপানি, পানিশূন্যতা বা কিডনি সমস্যায় এড়িয়ে চলুন।")),
    adult_rule=_adult(400, max_daily=2400, freq=3, interval=8),
    notes_en="NSAID for pain, fever, inflammation.",
    notes_bn="ব্যথা, জ্বর, প্রদাহের জন্য NSAID।",
))

_add(DrugEntry(
    key="aspirin",
    display_en="Aspirin (Acetylsalicylic acid)",
    display_bn="অ্যাসপিরিন",
    category="nsaid_antiplatelet",
    adult_rule=_adult(75, max_daily=150, freq=1, route="Oral",
                      warnings_en=("Low-dose only for cardiovascular prevention.",
                                   "Do not give to children under 18 (Reye syndrome risk)."),
                      warnings_bn=("শুধুমাত্র হৃদরোগ প্রতিরোধে কম ডোজ।",
                                   "১৮ বছরের কম বয়সীদের দেবেন না (রেই সিন্ড্রোমের ঝুঁকি)।")),
    notes_en="Analgesic use is largely replaced by paracetamol/ibuprofen in Bangladesh.",
    notes_bn="বাংলাদেশে ব্যথানাশক হিসেবে ব্যবহার কমেছে।",
    aliases=("acetylsalicylic acid", "asa"),
))

_add(DrugEntry(
    key="tramadol",
    display_en="Tramadol",
    display_bn="ট্রামাডল",
    category="opioid",
    adult_rule=_adult(50, max_daily=400, freq=4, interval=6,
                      warnings_en=("Schedule H. Risk of dependence.",
                                   "Avoid with MAO inhibitors and SSRIs."),
                      warnings_bn=("নিয়ন্ত্রিত ওষুধ। আসক্তির ঝুঁকি আছে।",
                                   "MAO এবং SSRI ওষুধের সাথে এড়িয়ে চলুন।")),
    notes_en="For moderate-severe pain not responding to step-1 analgesics.",
    notes_bn="হালকা ওষুধে না কমা মাঝারি-তীব্র ব্যথায়।",
))

_add(DrugEntry(
    key="morphine",
    display_en="Morphine",
    display_bn="মরফিন",
    category="opioid",
    adult_rule=_adult(10, max_daily=200, freq=4, interval=6, route="Oral",
                      warnings_en=("Schedule X. Respiratory depression risk.",
                                   "Use only under clinical supervision."),
                      warnings_bn=("নিয়ন্ত্রিত ওষুধ। শ্বাসকষ্টের ঝুঁকি।",
                                   "শুধুমাত্র চিকিৎসকের তত্ত্বাবধানে।")),
    notes_en="Severe pain, palliative care. Injectable forms also available.",
    notes_bn="তীব্র ব্যথা ও প্যালিয়েটিভ কেয়ারে।",
))


# ---------- Antibiotics -----------------------------------------------------

_add(DrugEntry(
    key="amoxicillin",
    display_en="Amoxicillin",
    display_bn="অ্যামোক্সিসিলিন",
    category="antibiotic_penicillin",
    pediatric_rule=_ped(25, max_single=500, freq=2, interval=12,
                        min_age_months=1,
                        warnings_en=("Complete the full course.",
                                     "Stop if rash or anaphylaxis — penicillin allergy."),
                        warnings_bn=("সম্পূর্ণ কোর্স শেষ করুন।",
                                     "অ্যালার্জি দেখা দিলে বন্ধ করুন।")),
    adult_rule=_adult(500, max_daily=3000, freq=3, interval=8),
    notes_en="First-line for otitis, sinusitis, pneumonia, UTI.",
    notes_bn="কান, সাইনাস, নিউমোনিয়া ও প্রস্রাবের সংক্রমণে প্রথম পছন্দ।",
))

_add(DrugEntry(
    key="amoxicillin_clavulanate",
    display_en="Amoxicillin + Clavulanic acid",
    display_bn="অ্যামোক্সিসিলিন + ক্লাভুলানিক অ্যাসিড",
    category="antibiotic_penicillin",
    pediatric_rule=_ped(25, max_single=500, freq=2, interval=12,
                        min_age_months=3,
                        warnings_en=("Higher diarrhea risk than amoxicillin alone.",
                                     "Take with food."),
                        warnings_bn=("শুধু অ্যামোক্সিসিলিনের চেয়ে ডায়রিয়ার ঝুঁকি বেশি।",
                                     "খাবারের সাথে নিন।")),
    adult_rule=_adult(625, max_daily=1875, freq=2, interval=12),
    notes_en="For resistant infections. Dose expressed as amoxicillin component.",
    notes_bn="প্রতিরোধী সংক্রমণে। অ্যামোক্সিসিলিনের ডোজ হিসাবে গণনা।",
    aliases=("amoxicillin/clavulanic acid", "co-amoxiclav", "augmentin"),
))

_add(DrugEntry(
    key="benzylpenicillin",
    display_en="Benzylpenicillin (Penicillin G)",
    display_bn="বেনজিলপেনিসিলিন",
    category="antibiotic_penicillin",
    adult_rule=DoseRule(fixed_mg_per_dose=2000000, max_single_mg=5000000,
                        freq_per_day=4, interval_hours=6,
                        min_age_months=12 * 12, route="IM/IV",
                        warnings_en=("Test dose for hypersensitivity if history of allergy.",
                                     "Injectable only — refer to facility."),
                        warnings_bn=("অ্যালার্জির ইতিহাস থাকলে পরীক্ষামূলক ডোজ দিন।",
                                     "ইনজেকশনই শুধু — স্বাস্থ্যকেন্দ্রে পাঠান।")),
    notes_en="Severe infections: pneumonia, meningitis, syphilis.",
    notes_bn="গুরুতর সংক্রমণে: নিউমোনিয়া, মেনিনজাইটিস, সিফিলিস।",
    aliases=("penicillin g",),
))

_add(DrugEntry(
    key="phenoxymethylpenicillin",
    display_en="Phenoxymethylpenicillin (Penicillin V)",
    display_bn="ফেনক্সিমিথাইলপেনিসিলিন",
    category="antibiotic_penicillin",
    pediatric_rule=_ped(12.5, max_single=500, freq=2, interval=12, min_age_months=12),
    adult_rule=_adult(500, max_daily=2000, freq=2, interval=12),
    notes_en="Oral step-down after benzylpenicillin; strep pharyngitis.",
    notes_bn="বেনজিলপেনিসিলিনের পরে মুখে খাওয়ার ওষুধ।",
    aliases=("penicillin v", "phenoxymethyl penicillin"),
))

_add(DrugEntry(
    key="benzathine_benzylpenicillin",
    display_en="Benzathine benzylpenicillin",
    display_bn="বেনজাথিন বেনজিলপেনিসিলিন",
    category="antibiotic_penicillin",
    adult_rule=DoseRule(fixed_mg_per_dose=2400000, max_single_mg=2400000,
                        freq_per_day=1, interval_hours=0,
                        min_age_months=12 * 12, route="IM",
                        warnings_en=("Single-dose IM injection. Refer to facility.",
                                     "Never give IV — risk of cardiac arrest."),
                        warnings_bn=("একক ডোজ ইনজেকশন। স্বাস্থ্যকেন্দ্রে।",
                                     "আইভি দেবেন না — হৃদরোগ বন্ধের ঝুঁকি।")),
    notes_en="Syphilis (single-dose), rheumatic fever prophylaxis.",
    notes_bn="সিফিলিস (একক ডোজ), বাতজ্বর প্রতিরোধ।",
))

_add(DrugEntry(
    key="cefalexin",
    display_en="Cefalexin (Cephalexin)",
    display_bn="সেফালেক্সিন",
    category="antibiotic_cephalosporin",
    pediatric_rule=_ped(25, max_single=1000, freq=2, interval=12, min_age_months=1),
    adult_rule=_adult(500, max_daily=4000, freq=2, interval=12),
    notes_en="Skin, soft-tissue, UTI.",
    notes_bn="চামড়া, নরম টিস্যু ও প্রস্রাবের সংক্রমণে।",
    aliases=("cephalexin",),
))

_add(DrugEntry(
    key="ceftriaxone",
    display_en="Ceftriaxone",
    display_bn="সেফট্রিয়াক্সোন",
    category="antibiotic_cephalosporin",
    adult_rule=DoseRule(fixed_mg_per_dose=1000, max_single_mg=2000,
                        freq_per_day=1, interval_hours=24,
                        min_age_months=12 * 12, route="IM/IV",
                        warnings_en=("Injectable — refer to facility.",
                                     "Caution in neonates with hyperbilirubinemia."),
                        warnings_bn=("ইনজেকশন — স্বাস্থ্যকেন্দ্রে।",
                                     "নবজাতকের জন্ডিসে সতর্কতা।")),
    notes_en="Severe infections: pneumonia, meningitis, sepsis, gonorrhea.",
    notes_bn="গুরুতর সংক্রমণ: নিউমোনিয়া, মেনিনজাইটিস, সেপসিস।",
))

_add(DrugEntry(
    key="cefotaxime",
    display_en="Cefotaxime",
    display_bn="সেফোট্যাক্সিম",
    category="antibiotic_cephalosporin",
    adult_rule=DoseRule(fixed_mg_per_dose=1000, max_single_mg=2000,
                        freq_per_day=3, interval_hours=8,
                        min_age_months=12 * 12, route="IM/IV"),
    notes_en="Severe infections including neonatal sepsis.",
    notes_bn="নবজাতকসহ গুরুতর সংক্রমণে।",
))

_add(DrugEntry(
    key="cefixime",
    display_en="Cefixime",
    display_bn="সেফিক্সিম",
    category="antibiotic_cephalosporin",
    pediatric_rule=_ped(8, max_single=400, freq=1, interval=24, min_age_months=6),
    adult_rule=_adult(400, max_daily=400, freq=1, interval=24),
    notes_en="Typhoid, UTI, gonorrhea (single-dose 800mg).",
    notes_bn="টাইফয়েড, প্রস্রাবের সংক্রমণ, গনোরিয়ায়।",
))

_add(DrugEntry(
    key="cefuroxime",
    display_en="Cefuroxime",
    display_bn="সেফুরোক্সিম",
    category="antibiotic_cephalosporin",
    adult_rule=_adult(500, max_daily=1000, freq=2, interval=12),
    notes_en="Upper and lower respiratory infections.",
    notes_bn="উপরের ও নিচের শ্বাসতন্ত্রের সংক্রমণে।",
))

_add(DrugEntry(
    key="ciprofloxacin",
    display_en="Ciprofloxacin",
    display_bn="সিপ্রোফ্লক্সাসিন",
    category="antibiotic_fluoroquinolone",
    pediatric_rule=_ped(10, max_single=500, freq=2, interval=12,
                        min_age_months=12,
                        warnings_en=("Avoid in pregnancy and under 12y unless no alternative.",
                                     "Avoid dairy/antacids within 2 hours."),
                        warnings_bn=("গর্ভাবস্থায় ও ১২ বছরের কম বয়সে এড়িয়ে চলুন।",
                                     "দুধ/অ্যান্টাসিড থেকে ২ ঘণ্টা ব্যবধান রাখুন।")),
    adult_rule=_adult(500, max_daily=1500, freq=2, interval=12),
    notes_en="Typhoid, UTI, diarrheal disease. Growing resistance in Bangladesh.",
    notes_bn="টাইফয়েড, প্রস্রাবের সংক্রমণ, ডায়রিয়ায়।",
))

_add(DrugEntry(
    key="azithromycin",
    display_en="Azithromycin",
    display_bn="অ্যাজিথ্রোমাইসিন",
    category="antibiotic_macrolide",
    pediatric_rule=_ped(10, max_single=500, freq=1, interval=24,
                        min_age_months=6),
    adult_rule=_adult(500, max_daily=500, freq=1, interval=24),
    notes_en="3-day course. Atypical pneumonia, strep, chlamydia.",
    notes_bn="৩ দিনের কোর্স। অ্যাটিপিক্যাল নিউমোনিয়া, ক্ল্যামাইডিয়ায়।",
    aliases=("azithro",),
))

_add(DrugEntry(
    key="metronidazole",
    display_en="Metronidazole",
    display_bn="মেট্রোনিডাজল",
    category="antibiotic_nitroimidazole",
    pediatric_rule=_ped(7.5, max_single=500, freq=3, interval=8, min_age_months=1,
                        warnings_en=("Avoid alcohol during and 48h after treatment.",
                                     "Metallic taste is common."),
                        warnings_bn=("চিকিৎসার সময় ও ৪৮ ঘণ্টা পরে মদ্যপান এড়িয়ে চলুন।",
                                     "মুখে ধাতব স্বাদ হতে পারে।")),
    adult_rule=_adult(500, max_daily=1500, freq=3, interval=8),
    notes_en="Anaerobic infections, amoebiasis, giardia, bacterial vaginosis.",
    notes_bn="অ্যানারোবিক সংক্রমণ, অ্যামিবিয়াসিস, জিয়ার্ডিয়ায়।",
))

_add(DrugEntry(
    key="doxycycline",
    display_en="Doxycycline",
    display_bn="ডক্সিসাইক্লিন",
    category="antibiotic_tetracycline",
    adult_rule=_adult(100, max_daily=200, freq=2, interval=12,
                      warnings_en=("Avoid in pregnancy and under 8y — teeth staining.",
                                   "Take with plenty of water, sit upright."),
                      warnings_bn=("গর্ভাবস্থায় ও ৮ বছরের কম বয়সে নিষেধ — দাঁতের ক্ষতি।",
                                   "প্রচুর পানির সাথে, বসে খান।")),
    notes_en="Rickettsial disease, cholera, malaria prophylaxis.",
    notes_bn="রিকেটসিয়া, কলেরা ও ম্যালেরিয়া প্রতিরোধে।",
))

_add(DrugEntry(
    key="gentamicin",
    display_en="Gentamicin",
    display_bn="জেন্টামাইসিন",
    category="antibiotic_aminoglycoside",
    adult_rule=DoseRule(fixed_mg_per_dose=120, max_single_mg=160,
                        freq_per_day=1, interval_hours=24,
                        min_age_months=12 * 12, route="IM/IV",
                        warnings_en=("Nephrotoxic and ototoxic.",
                                     "Monitor renal function."),
                        warnings_bn=("কিডনি ও কানের ক্ষতি করতে পারে।",
                                     "কিডনি পরীক্ষা করুন।")),
    notes_en="Severe Gram-negative infections.",
    notes_bn="গুরুতর গ্রাম-নেগেটিভ সংক্রমণে।",
))

_add(DrugEntry(
    key="amikacin",
    display_en="Amikacin",
    display_bn="অ্যামিকাসিন",
    category="antibiotic_aminoglycoside",
    adult_rule=DoseRule(fixed_mg_per_dose=500, max_single_mg=750,
                        freq_per_day=1, interval_hours=24,
                        min_age_months=12 * 12, route="IM/IV"),
    notes_en="Multi-drug resistant TB, severe sepsis.",
    notes_bn="এমডিআর যক্ষ্মা ও গুরুতর সেপসিসে।",
))

_add(DrugEntry(
    key="clindamycin",
    display_en="Clindamycin",
    display_bn="ক্লিন্ডামাইসিন",
    category="antibiotic_lincosamide",
    adult_rule=_adult(300, max_daily=1800, freq=4, interval=6,
                      warnings_en=("Risk of C. difficile colitis.",
                                   "Discontinue if severe diarrhea."),
                      warnings_bn=("C. difficile কোলাইটিসের ঝুঁকি।",
                                   "তীব্র ডায়রিয়া হলে বন্ধ করুন।")),
    notes_en="Skin/soft tissue, anaerobic, dental infections.",
    notes_bn="চামড়া, অ্যানারোবিক ও দাঁতের সংক্রমণে।",
))

_add(DrugEntry(
    key="vancomycin",
    display_en="Vancomycin",
    display_bn="ভ্যানকোমাইসিন",
    category="antibiotic_glycopeptide",
    adult_rule=DoseRule(fixed_mg_per_dose=1000, max_single_mg=2000,
                        freq_per_day=2, interval_hours=12,
                        min_age_months=12 * 12, route="IV",
                        warnings_en=("Nephrotoxic. Trough levels required.",
                                     "Red-man syndrome if infused fast."),
                        warnings_bn=("কিডনির ক্ষতি। রক্তের মাত্রা পরীক্ষা করুন।",
                                     "দ্রুত দিলে লালচে ত্বক।")),
    notes_en="MRSA, severe C. difficile colitis.",
    notes_bn="MRSA ও গুরুতর C. difficile সংক্রমণে।",
))

_add(DrugEntry(
    key="nitrofurantoin",
    display_en="Nitrofurantoin",
    display_bn="নাইট্রোফিউরান্টোইন",
    category="antibiotic_urine",
    pediatric_rule=_ped(1.5, max_single=100, freq=2, interval=12, min_age_months=3,
                        warnings_en=("Avoid in infants under 1 month.",
                                     "Discolors urine — harmless."),
                        warnings_bn=("১ মাসের কম বয়সে নিষেধ।",
                                     "প্রস্রাবের রঙ বদলায় — ক্ষতিকর নয়।")),
    adult_rule=_adult(100, max_daily=400, freq=2, interval=12),
    notes_en="Uncomplicated UTI only — does not reach kidneys.",
    notes_bn="শুধু সাধারণ প্রস্রাবের সংক্রমণে।",
))

_add(DrugEntry(
    key="co_trimoxazole",
    display_en="Trimethoprim/Sulfamethoxazole (Co-trimoxazole)",
    display_bn="ট্রাইমেথোপ্রিম/সালফামেথক্সাজল",
    category="antibiotic_sulfonamide",
    pediatric_rule=_ped(4, max_single=160, freq=2, interval=12, min_age_months=1,
                        warnings_en=("Avoid under 6 weeks (kernicterus risk).",
                                     "Stop if rash, sulfa allergy."),
                        warnings_bn=("৬ সপ্তাহের কম বয়সে নিষেধ।",
                                     "অ্যালার্জি দেখলে বন্ধ করুন।")),
    adult_rule=_adult(960, max_daily=1920, freq=2, interval=12),
    notes_en="UTI, PCP prophylaxis, traveler's diarrhea.",
    notes_bn="প্রস্রাবের সংক্রমণ, PCP প্রতিরোধ, ভ্রমণকারীর ডায়রিয়ায়।",
    aliases=("cotrimoxazole", "septran", "bactrim"),
))

_add(DrugEntry(
    key="paracetamol_codeine",
    display_en="Paracetamol + Codeine combination",
    display_bn="প্যারাসিটামল + কোডিন সংমিশ্রণ",
    category="analgesic_opioid",
    adult_rule=DoseRule(fixed_mg_per_dose=500, max_single_mg=1000,
                        freq_per_day=4, interval_hours=6,
                        min_age_months=12 * 12, route="Oral",
                        warnings_en=("Schedule-controlled. Codeine dependence risk.",
                                     "Avoid in pregnancy and lactation."),
                        warnings_bn=("নিয়ন্ত্রিত ওষুধ। আসক্তির ঝুঁকি।",
                                     "গর্ভাবস্থায় ও স্তন্যদানকালে এড়িয়ে চলুন।")),
    notes_en="Fixed-dose combo (e.g. 500mg paracetamol + 8-30mg codeine).",
    notes_bn="একত্রিত ডোজ (৫০০ মিগ্রা প্যারাসিটামল + ৮-৩০ মিগ্রা কোডিন)।",
))


# ---------- Antifungals -----------------------------------------------------

_add(DrugEntry(
    key="clotrimazole",
    display_en="Clotrimazole",
    display_bn="ক্লোট্রিমাজল",
    category="antifungal",
    adult_rule=DoseRule(freq_per_day=2, interval_hours=12, min_age_months=12 * 12,
                        route="Topical",
                        warnings_en=("External use only.",
                                     "Continue for 2 weeks after symptoms clear."),
                        warnings_bn=("শুধু বাইরে ব্যবহার।",
                                     "লক্ষণ কমার ২ সপ্তাহ পর পর্যন্ত ব্যবহার।")),
    notes_en="Vaginal candidiasis pessary 500mg single dose; topical cream.",
    notes_bn="যোনি ক্যান্ডিডিয়াসিস ৫০০ মিগ্রা একক ডোজ।",
))

_add(DrugEntry(
    key="fluconazole",
    display_en="Fluconazole",
    display_bn="ফ্লুকোনাজল",
    category="antifungal",
    pediatric_rule=_ped(6, max_single=400, freq=1, interval=24,
                        min_age_months=1),
    adult_rule=_adult(150, max_daily=400, freq=1, interval=24),
    notes_en="Single 150mg dose for vaginal candidiasis. Cryptococcal meningitis.",
    notes_bn="যোনি ক্যান্ডিডিয়াসিসে একক ১৫০ মিগ্রা ডোজ।",
))

_add(DrugEntry(
    key="nystatin",
    display_en="Nystatin",
    display_bn="নিস্ট্যাটিন",
    category="antifungal",
    pediatric_rule=DoseRule(fixed_mg_per_dose=500000, max_single_mg=1000000,
                            freq_per_day=4, interval_hours=6,
                            min_age_months=1, route="Oral suspension",
                            warnings_en=("Continue 48h after symptoms clear.",
                                         "Shake bottle before use."),
                            warnings_bn=("লক্ষণ কমার ৪৮ ঘণ্টা পর পর্যন্ত ব্যবহার।",
                                         "ব্যবহারের আগে শিশি ঝাঁকান।")),
    notes_en="Oral thrush, mild intestinal candidiasis.",
    notes_bn="মুখের ছত্রাক ও হালকা অন্ত্রের ক্যান্ডিডিয়াসিস।",
))


# ---------- Antiparasitics / anthelmintics ----------------------------------

_add(DrugEntry(
    key="ivermectin",
    display_en="Ivermectin",
    display_bn="আইভারমেকটিন",
    category="antiparasitic",
    adult_rule=DoseRule(fixed_mg_per_dose=12, max_single_mg=12,
                        freq_per_day=1, interval_hours=0,
                        min_age_months=60,
                        route="Oral",
                        warnings_en=("Avoid in children under 5y or under 15kg.",
                                     "Take on empty stomach."),
                        warnings_bn=("৫ বছরের কম বা ১৫ কেজির কম শিশুদের নিষেধ।",
                                     "খালি পেটে নিন।")),
    notes_en="Onchocerciasis, strongyloidiasis, scabies.",
    notes_bn="অনকোসার্কিয়াসিস, স্ট্রংগাইলয়ড, স্ক্যাবিস।",
))

_add(DrugEntry(
    key="albendazole",
    display_en="Albendazole",
    display_bn="অ্যালবেনডাজল",
    category="anthelmintic",
    pediatric_rule=DoseRule(fixed_mg_per_dose=400, max_single_mg=400,
                            freq_per_day=1, interval_hours=0,
                            min_age_months=12, route="Oral"),
    adult_rule=DoseRule(fixed_mg_per_dose=400, max_single_mg=400,
                        freq_per_day=1, interval_hours=0,
                        min_age_months=12 * 12, route="Oral"),
    notes_en="Single dose 400mg for soil-transmitted helminths.",
    notes_bn="কৃমিতে একক ৪০০ মিগ্রা ডোজ।",
))

_add(DrugEntry(
    key="praziquantel",
    display_en="Praziquantel",
    display_bn="প্রাজিকোয়ান্টেল",
    category="anthelmintic",
    adult_rule=DoseRule(fixed_mg_per_dose=600, max_single_mg=2400,
                        freq_per_day=3, interval_hours=4,
                        min_age_months=48, route="Oral"),
    notes_en="Schistosomiasis. Take with food.",
    notes_bn="সিস্টোসোমিয়াসিস। খাবারের সাথে নিন।",
))

_add(DrugEntry(
    key="niclosamide",
    display_en="Niclosamide",
    display_bn="নিক্লোসামাইড",
    category="anthelmintic",
    adult_rule=DoseRule(fixed_mg_per_dose=1000, max_single_mg=2000,
                        freq_per_day=1, interval_hours=0,
                        min_age_months=24, route="Oral"),
    notes_en="Tapeworm infections. Chew tablets well.",
    notes_bn="ফিতাকৃমিতে। ভালো করে চিবিয়ে খান।",
))


# ---------- GI / rehydration ------------------------------------------------

_add(DrugEntry(
    key="ors",
    display_en="Oral Rehydration Salts (ORS)",
    display_bn="ওরস (মুখে খাওয়ার স্যালাইন)",
    category="rehydration",
    pediatric_rule=DoseRule(freq_per_day=99, min_age_months=0, route="Oral",
                            warnings_en=("Dissolve one sachet in 1 litre of clean water.",
                                         "Continue normal feeding."),
                            warnings_bn=("এক প্যাকেট ১ লিটার পরিষ্কার পানিতে গুলান।",
                                         "স্বাভাবিক খাবার চালিয়ে যান।")),
    adult_rule=DoseRule(freq_per_day=99, min_age_months=12 * 12, route="Oral"),
    notes_en="Standard WHO-ORS: 75 mEq/L sodium, 75 mmol/L glucose.",
    notes_bn="WHO স্ট্যান্ডার্ড ORS।",
    aliases=("oral rehydration salts", "nirdhan"),
))

_add(DrugEntry(
    key="zinc_sulfate",
    display_en="Zinc Sulfate",
    display_bn="জিংক সালফেট",
    category="supplement",
    pediatric_rule=DoseRule(fixed_mg_per_dose=20, max_single_mg=20,
                            freq_per_day=1, interval_hours=24,
                            min_age_months=6, route="Oral"),
    adult_rule=DoseRule(fixed_mg_per_dose=50, max_single_mg=50,
                        freq_per_day=1, interval_hours=24,
                        min_age_months=12 * 12, route="Oral"),
    notes_en="10-14 days with ORS for acute diarrhea in children.",
    notes_bn="শিশুদের তীব্র ডায়রিয়ায় ORS-এর সাথে ১০-১৪ দিন।",
))

_add(DrugEntry(
    key="ranitidine",
    display_en="Ranitidine",
    display_bn="র‍্যানিটিডিন",
    category="antacid",
    adult_rule=_adult(150, max_daily=300, freq=2, interval=12,
                      warnings_en=("Take with or without food.",
                                   "Withdrawn in some countries — supply uncertain."),
                      warnings_bn=("খাবারের সাথে বা আলাদা নেওয়া যায়।",
                                   "কিছু দেশে প্রত্যাহার — সরবরাহ সীমিত।")),
    notes_en="Acid reduction, peptic ulcer.",
    notes_bn="অ্যাসিড কমায়, আলসারে।",
))

_add(DrugEntry(
    key="omeprazole",
    display_en="Omeprazole",
    display_bn="ওমিপ্রাজল",
    category="ppi",
    adult_rule=_adult(20, max_daily=40, freq=1, interval=24,
                      warnings_en=("Take 30 min before breakfast.",
                                   "Long-term use: monitor magnesium and B12."),
                      warnings_bn=("সকালের খাবারের ৩০ মিনিট আগে নিন।",
                                   "দীর্ঘমেয়াদী ব্যবহারে ম্যাগনেসিয়াম ও B12 পরীক্ষা করুন।")),
    notes_en="GERD, peptic ulcer, H. pylori eradication.",
    notes_bn="গ্যাস্ট্রাইটিস, আলসারে।",
))

_add(DrugEntry(
    key="ondansetron",
    display_en="Ondansetron",
    display_bn="অনড্যানসেট্রন",
    category="antiemetic",
    pediatric_rule=_ped(0.15, max_single=8, freq=3, interval=8, min_age_months=1,
                        warnings_en=("Single dose per episode of vomiting preferred.",
                                     "QT prolongation risk at high doses."),
                        warnings_bn=("বমির প্রতি পর্বে একক ডোজ।",
                                     "উচ্চ ডোজে QT ঝুঁকি।")),
    adult_rule=_adult(4, max_daily=24, freq=3, interval=8),
    notes_en="Vomiting. Avoid in cholera (paradoxical diarrhea).",
    notes_bn="বমিতে। কলেরায় এড়িয়ে চলুন।",
))

_add(DrugEntry(
    key="metoclopramide",
    display_en="Metoclopramide",
    display_bn="মেটোক্লোপ্রামাইড",
    category="antiemetic",
    adult_rule=_adult(10, max_daily=30, freq=3, interval=8,
                      warnings_en=("Extrapyramidal reactions possible.",
                                   "Avoid in young adults and pregnancy."),
                      warnings_bn=("বিরল পার্শ্বপ্রতিক্রিয়া সম্ভব।",
                                   "অল্প বয়সী ও গর্ভাবস্থায় এড়িয়ে চলুন।")),
    notes_en="Vomiting, gastroparesis.",
    notes_bn="বমি ও গ্যাস্ট্রোপ্যারেসিসে।",
))

_add(DrugEntry(
    key="loperamide",
    display_en="Loperamide",
    display_bn="লোপেরামাইড",
    category="antidiarrheal",
    adult_rule=_adult(4, max_daily=16, freq=4, interval=6,
                      warnings_en=("Avoid in bloody diarrhea or in children under 6y.",
                                   "Stop if no improvement in 48h."),
                      warnings_bn=("রক্তমিশ্রিত ডায়রিয়া বা ৬ বছরের কমে নিষেধ।",
                                   "৪৮ ঘণ্টায় উন্নতি না হলে বন্ধ।")),
    notes_en="Acute non-specific diarrhea.",
    notes_bn="তীব্র সাধারণ ডায়রিয়ায়।",
))


# ---------- Respiratory ----------------------------------------------------

_add(DrugEntry(
    key="salbutamol",
    display_en="Salbutamol (Albuterol)",
    display_bn="সালবিউটামল",
    category="bronchodilator",
    pediatric_rule=DoseRule(freq_per_day=4, min_age_months=12, route="Inhaled",
                            warnings_en=("Metered-dose inhaler with spacer for children.",
                                         "Tremor and tachycardia are common."),
                            warnings_bn=("শিশুদের জন্য স্পেসারসহ ইনহেলার।",
                                         "হাত কাঁপা ও হৃদস্পন্দন সাধারণ।")),
    adult_rule=DoseRule(freq_per_day=4, min_age_months=12 * 12, route="Inhaled"),
    notes_en="Asthma, COPD. 100mcg/puff, 1-2 puffs q4-6h.",
    notes_bn="হাঁপানি ও COPD-তে।",
    aliases=("albuterol", "salbutamol inhaler"),
))

_add(DrugEntry(
    key="ipratropium_bromide",
    display_en="Ipratropium Bromide",
    display_bn="আইপ্রাট্রোপিয়াম ব্রোমাইড",
    category="bronchodilator",
    adult_rule=DoseRule(freq_per_day=4, min_age_months=12 * 12, route="Inhaled"),
    notes_en="Nebulized 500mcq + salbutamol in acute asthma.",
    notes_bn="তীব্র হাঁপানিতে সালবিউটামলের সাথে।",
))

_add(DrugEntry(
    key="beclometasone",
    display_en="Beclometasone (Inhaled)",
    display_bn="বেক্লোমেটাসন (ইনহেলার)",
    category="inhaled_steroid",
    pediatric_rule=DoseRule(fixed_mg_per_dose=0.1, max_single_mg=0.2,
                            freq_per_day=2, interval_hours=12, min_age_months=24,
                            route="Inhaled"),
    adult_rule=DoseRule(fixed_mg_per_dose=0.2, max_single_mg=0.4,
                        freq_per_day=2, interval_hours=12,
                        min_age_months=12 * 12, route="Inhaled"),
    notes_en="Asthma prophylaxis. Rinse mouth after use.",
    notes_bn="হাঁপানি প্রতিরোধ। ব্যবহারের পর মুখ ধুয়ে নিন।",
    aliases=("beclomethasone",),
))


# ---------- Steroids / anti-inflammatory -----------------------------------

_add(DrugEntry(
    key="prednisolone",
    display_en="Prednisolone",
    display_bn="প্রেডনিসোলন",
    category="steroid",
    pediatric_rule=_ped(1, max_single=40, freq=2, interval=12, min_age_months=12),
    adult_rule=_adult(20, max_daily=60, freq=1, interval=24,
                      warnings_en=("Take with food.",
                                   "Taper if used more than 2 weeks."),
                      warnings_bn=("খাবারের সাথে নিন।",
                                   "২ সপ্তাহের বেশি ব্যবহারে ধীরে কমান।")),
    notes_en="Asthma exacerbation, allergic reactions, autoimmune disease.",
    notes_bn="হাঁপানি, অ্যালার্জি ও অটোইমিউন রোগে।",
    aliases=("prednisone",),
))

_add(DrugEntry(
    key="dexamethasone",
    display_en="Dexamethasone",
    display_bn="ডেক্সামেথাসন",
    category="steroid",
    pediatric_rule=_ped(0.15, max_single=8, freq=1, interval=24, min_age_months=1),
    adult_rule=_adult(6, max_daily=16, freq=1, interval=24),
    notes_en="Severe croup, cerebral edema, COVID-19 oxygen need.",
    notes_bn="গুরুতর ক্রুপ, মস্তিষ্কের ফোলা, COVID-তে।",
))

_add(DrugEntry(
    key="hydrocortisone",
    display_en="Hydrocortisone",
    display_bn="হাইড্রোকর্টিসন",
    category="steroid",
    adult_rule=DoseRule(fixed_mg_per_dose=100, max_single_mg=200,
                        freq_per_day=2, interval_hours=12,
                        min_age_months=12 * 12, route="IV/IM"),
    notes_en="Anaphylaxis, adrenal insufficiency, severe asthma.",
    notes_bn="অ্যানাফিল্যাক্সিস ও গুরুতর হাঁপানিতে।",
))


# ---------- Allergy / antihistamines ---------------------------------------

_add(DrugEntry(
    key="chlorphenamine",
    display_en="Chlorphenamine (Chlorpheniramine)",
    display_bn="ক্লোরফেনিরামিন",
    category="antihistamine",
    pediatric_rule=_ped(0.1, max_single=4, freq=4, interval=6,
                        min_age_months=12,
                        warnings_en=("Causes drowsiness — caution with driving.",),
                        warnings_bn=("ঘুম ঘুম ভাব — গাড়ি চালানোর সময় সতর্ক।",)),
    adult_rule=_adult(4, max_daily=24, freq=4, interval=6),
    notes_en="Allergic rhinitis, urticaria, common cold.",
    notes_bn="অ্যালার্জি, চুলকানি ও সর্দিতে।",
    aliases=("chlorpheniramine", "avil", "piriton"),
))

_add(DrugEntry(
    key="loratadine",
    display_en="Loratadine",
    display_bn="লোরাটাডিন",
    category="antihistamine_nondrowsy",
    adult_rule=_adult(10, max_daily=10, freq=1, interval=24),
    notes_en="Non-drowsy alternative to chlorphenamine.",
    notes_bn="ক্লোরফেনিরামিনের বিকল্প, ঘুম কম আসে।",
))


# ---------- Emergency / anaesthesia ----------------------------------------

_add(DrugEntry(
    key="epinephrine",
    display_en="Epinephrine (Adrenaline)",
    display_bn="এপিনেফ্রিন (অ্যাড্রেনালিন)",
    category="emergency",
    adult_rule=DoseRule(fixed_mg_per_dose=0.5, max_single_mg=0.5,
                        freq_per_day=1, interval_hours=0,
                        min_age_months=12 * 12, route="IM",
                        warnings_en=("Anaphylaxis: 0.5mg IM mid-anterolateral thigh.",
                                     "Repeat every 5-15 min if needed."),
                        warnings_bn=("অ্যানাফিল্যাক্সিসে উরুর বাইরের দিকে ০.৫ মিগ্রা।",
                                     "প্রয়োজনে ৫-১৫ মিনিটে পুনরাবৃত্তি।")),
    notes_en="Anaphylaxis, cardiac arrest. 1:1000 (1mg/mL) IM for anaphylaxis.",
    notes_bn="অ্যানাফিল্যাক্সিস ও হৃদরোগ বন্ধে।",
    aliases=("adrenaline",),
))

_add(DrugEntry(
    key="diazepam",
    display_en="Diazepam",
    display_bn="ডায়াজেপাম",
    category="benzodiazepine",
    adult_rule=_adult(5, max_daily=30, freq=3, interval=8,
                      warnings_en=("Drowsiness and dependence.",
                                   "Avoid in pregnancy (1st trimester)."),
                      warnings_bn=("ঘুম ঘুম ভাব ও আসক্তি।",
                                   "গর্ভাবস্থার প্রথম তিন মাসে নিষেধ।")),
    notes_en="Seizures (rectal 10mg), anxiety, alcohol withdrawal.",
    notes_bn="খিঁচুনি, উদ্বেগ ও মদ্যপ বিরতিতে।",
))

_add(DrugEntry(
    key="lorazepam",
    display_en="Lorazepam",
    display_bn="লোরাজেপাম",
    category="benzodiazepine",
    adult_rule=_adult(2, max_daily=6, freq=3, interval=8),
    notes_en="Status epilepticus 4mg IV over 2 min.",
    notes_bn="মারাত্মক খিঁচুনিতে ৪ মিগ্রা শিরায়।",
))

_add(DrugEntry(
    key="lidocaine",
    display_en="Lidocaine (Lignocaine)",
    display_bn="লিডোকেইন",
    category="local_anesthetic",
    adult_rule=DoseRule(fixed_mg_per_dose=20, max_single_mg=200,
                        freq_per_day=1, interval_hours=0,
                        min_age_months=12 * 12, route="Infiltration",
                        warnings_en=("Maximum 4.5 mg/kg without adrenaline, 7 mg/kg with.",
                                     "Avoid intravascular injection."),
                        warnings_bn=("অ্যাড্রেনালিন ছাড়া সর্বোচ্চ ৪.৫ মিগ্রা/কেজি।",
                                     "শিরায় যেন না যায়।")),
    notes_en="Local anesthesia, 1-2% solution.",
    notes_bn="স্থানীয় অবশ করায়, ১-২% দ্রবণ।",
    aliases=("lignocaine", "xylocaine"),
))

_add(DrugEntry(
    key="bupivacaine",
    display_en="Bupivacaine",
    display_bn="বুপিভাকেইন",
    category="local_anesthetic",
    adult_rule=DoseRule(fixed_mg_per_dose=50, max_single_mg=150,
                        freq_per_day=1, interval_hours=0,
                        min_age_months=12 * 12, route="Infiltration/Nerve block"),
    notes_en="Longer acting than lidocaine. 0.25-0.5% solution.",
    notes_bn="লিডোকেইনের চেয়ে দীর্ঘস্থায়ী। ০.২৫-০.৫% দ্রবণ।",
))

_add(DrugEntry(
    key="lidocaine_adrenaline",
    display_en="Lidocaine with Adrenaline",
    display_bn="লিডোকেইন + অ্যাড্রেনালিন",
    category="local_anesthetic",
    adult_rule=DoseRule(fixed_mg_per_dose=20, max_single_mg=500,
                        freq_per_day=1, interval_hours=0,
                        min_age_months=12 * 12, route="Infiltration",
                        warnings_en=("Avoid in fingers, toes, nose, ears — vasoconstriction risk.",
                                     "Never use in pregnancy."),
                        warnings_bn=("আঙুলে ব্যবহার এড়িয়ে চলুন।",
                                     "গর্ভাবস্থায় নিষেধ।")),
    notes_en="Maximum 7 mg/kg lidocaine with adrenaline 1:100,000.",
    notes_bn="অ্যাড্রেনালিনসহ সর্বোচ্চ ৭ মিগ্রা/কেজি লিডোকেইন।",
    aliases=("lignocaine_adrenaline",),
))


# ---------- Cardiovascular --------------------------------------------------

_add(DrugEntry(
    key="atenolol",
    display_en="Atenolol",
    display_bn="অ্যাটেনোলল",
    category="beta_blocker",
    adult_rule=_adult(50, max_daily=100, freq=1, interval=24,
                      warnings_en=("Do not stop abruptly.",
                                   "Caution in asthma, heart block."),
                      warnings_bn=("হঠাৎ বন্ধ করবেন না।",
                                   "হাঁপানি ও হৃদযন্ত্রের ব্লকে সতর্ক।")),
    notes_en="Hypertension, angina.",
    notes_bn="উচ্চ রক্তচাপ ও বুকে ব্যথায়।",
))

_add(DrugEntry(
    key="propranolol",
    display_en="Propranolol",
    display_bn="প্রোপ্রানোলল",
    category="beta_blocker",
    adult_rule=_adult(40, max_daily=160, freq=2, interval=12,
                      warnings_en=("Non-selective — caution in asthma.",),
                      warnings_bn=("নন-সিলেক্টিভ — হাঁপানিতে সতর্ক।",)),
    notes_en="Hypertension, portal hypertension, migraine prophylaxis.",
    notes_bn="উচ্চ রক্তচাপ ও মাইগ্রেন প্রতিরোধে।",
))

_add(DrugEntry(
    key="amlodipine",
    display_en="Amlodipine",
    display_bn="অ্যামলোডিপিন",
    category="calcium_channel_blocker",
    adult_rule=_adult(5, max_daily=10, freq=1, interval=24,
                      warnings_en=("Peripheral edema common.",
                                   "Take same time daily."),
                      warnings_bn=("পায়ে ফোলা সাধারণ।",
                                   "প্রতিদিন একই সময়ে নিন।")),
    notes_en="First-line for hypertension in Bangladesh NEML.",
    notes_bn="বাংলাদেশে উচ্চ রক্তচাপের প্রথম পছন্দ।",
))

_add(DrugEntry(
    key="enalapril",
    display_en="Enalapril",
    display_bn="এনালাপ্রিল",
    category="ace_inhibitor",
    adult_rule=_adult(10, max_daily=40, freq=1, interval=24,
                      warnings_en=("Dry cough — switch to losartan if intolerable.",
                                   "Avoid in pregnancy."),
                      warnings_bn=("শুকনো কাশি — অসহ্য হলে লোসার্টানে বদলান।",
                                   "গর্ভাবস্থায় নিষেধ।")),
    notes_en="Hypertension, heart failure, diabetic nephropathy.",
    notes_bn="উচ্চ রক্তচাপ, হৃদযন্ত্র ও কিডনি রক্ষায়।",
))

_add(DrugEntry(
    key="losartan",
    display_en="Losartan",
    display_bn="লোসার্টান",
    category="arb",
    adult_rule=_adult(50, max_daily=100, freq=1, interval=24,
                      warnings_en=("Avoid in pregnancy.",
                                   "Monitor potassium."),
                      warnings_bn=("গর্ভাবস্থায় নিষেধ।",
                                   "পটাসিয়াম পরীক্ষা করুন।")),
    notes_en="Cough-free alternative to ACE inhibitors.",
    notes_bn="এনালাপ্রিলের বিকল্প, কাশি হয় না।",
))

_add(DrugEntry(
    key="hydrochlorothiazide",
    display_en="Hydrochlorothiazide",
    display_bn="হাইড্রোক্লোরোথায়াজাইড",
    category="thiazide",
    adult_rule=_adult(25, max_daily=50, freq=1, interval=24,
                      warnings_en=("Take in morning to avoid nocturia.",
                                   "Monitor sodium and potassium."),
                      warnings_bn=("সকালে নিন — রাতে প্রস্রাব এড়াতে।",
                                   "সোডিয়াম ও পটাসিয়াম পরীক্ষা।")),
    notes_en="Hypertension, mild edema.",
    notes_bn="উচ্চ রক্তচাপ ও হালকা ফোলায়।",
))

_add(DrugEntry(
    key="furosemide",
    display_en="Furosemide",
    display_bn="ফুরোসেমাইড",
    category="loop_diuretic",
    adult_rule=_adult(40, max_daily=160, freq=2, interval=12,
                      warnings_en=("Monitor potassium and renal function.",
                                   "Take in morning and early afternoon."),
                      warnings_bn=("পটাসিয়াম ও কিডনি পরীক্ষা।",
                                   "সকাল ও দুপুরে নিন।")),
    notes_en="Heart failure, severe edema, pulmonary edema.",
    notes_bn="হৃদযন্ত্রের ব্যর্থতা ও ফুসফুসের ফোলায়।",
))

_add(DrugEntry(
    key="atorvastatin",
    display_en="Atorvastatin",
    display_bn="অ্যাটোরভাস্ট্যাটিন",
    category="statin",
    adult_rule=_adult(20, max_daily=80, freq=1, interval=24,
                      warnings_en=("Avoid in pregnancy and active liver disease.",
                                   "Monitor liver enzymes."),
                      warnings_bn=("গর্ভাবস্থায় ও লিভারের রোগে নিষেধ।",
                                   "লিভারের এনজাইম পরীক্ষা।")),
    notes_en="Hyperlipidemia, cardiovascular prevention.",
    notes_bn="উচ্চ কোলেস্টেরল ও হৃদরোগ প্রতিরোধে।",
))

_add(DrugEntry(
    key="simvastatin",
    display_en="Simvastatin",
    display_bn="সিমভাস্ট্যাটিন",
    category="statin",
    adult_rule=_adult(20, max_daily=40, freq=1, interval=24,
                      warnings_en=("Avoid grapefruit juice.",
                                   "Evening dosing preferred."),
                      warnings_bn=("আঙুরের রস এড়িয়ে চলুন।",
                                   "সন্ধ্যায় নেওয়া ভালো।")),
    notes_en="Hyperlipidemia.",
    notes_bn="উচ্চ কোলেস্টেরলে।",
))

_add(DrugEntry(
    key="warfarin",
    display_en="Warfarin",
    display_bn="ওয়ারফারিন",
    category="anticoagulant",
    adult_rule=_adult(5, max_daily=10, freq=1, interval=24,
                      warnings_en=("INR monitoring essential.",
                                   "Vitamin K rich foods (green leafy) affect dose."),
                      warnings_bn=("INR পরীক্ষা অত্যাবশ্যক।",
                                   "সবুজ শাকসবজি ডোজ পরিবর্তন করে।")),
    notes_en="Anticoagulation. Target INR 2-3.",
    notes_bn="রক্ত জমাট বাঁধা প্রতিরোধে। INR লক্ষ্য ২-৩।",
))

_add(DrugEntry(
    key="enoxaparin",
    display_en="Enoxaparin (LMWH)",
    display_bn="এনক্সাপারিন",
    category="anticoagulant",
    adult_rule=DoseRule(fixed_mg_per_dose=40, max_single_mg=80,
                        freq_per_day=1, interval_hours=24,
                        min_age_months=12 * 12, route="SC",
                        warnings_en=("Adjust dose in renal impairment.",
                                     "Monitor anti-Xa if available."),
                        warnings_bn=("কিডনি সমস্যায় ডোজ কমান।",
                                     "Anti-Xa পরীক্ষা করান।")),
    notes_en="DVT prophylaxis and treatment.",
    notes_bn="গভীর শিরায় রক্ত জমাট প্রতিরোধ ও চিকিৎসায়।",
))

_add(DrugEntry(
    key="tranexamic_acid",
    display_en="Tranexamic Acid",
    display_bn="ট্রানেক্সামিক অ্যাসিড",
    category="antifibrinolytic",
    adult_rule=_adult(1000, max_daily=3000, freq=3, interval=8,
                      warnings_en=("Avoid in active thromboembolic disease.",
                                   "First dose within 3h of bleeding onset."),
                      warnings_bn=("সক্রিয় রক্ত জমাটে নিষেধ।",
                                   "রক্তপাতের ৩ ঘণ্টার মধ্যে প্রথম ডোজ।")),
    notes_en="Post-partum hemorrhage, trauma bleeding.",
    notes_bn="প্রসব-পরবর্তী রক্তপাত, আঘাতজনিত রক্তপাতে।",
))

_add(DrugEntry(
    key="nifedipine",
    display_en="Nifedipine",
    display_bn="নিফেডিপিন",
    category="calcium_channel_blocker",
    adult_rule=_adult(20, max_daily=60, freq=3, interval=8,
                      warnings_en=("Sublingual short-acting not recommended.",
                                   "Avoid in cardiogenic shock."),
                      warnings_bn=("জিহ্বার নিচে দেওয়া সুপারিশ নয়।",
                                   "হৃদযন্ত্রের শকে এড়িয়ে চলুন।")),
    notes_en="Hypertension, angina, tocolysis.",
    notes_bn="উচ্চ রক্তচাপ ও বুকে ব্যথায়।",
))


# ---------- Maternal / reproductive -----------------------------------------

_add(DrugEntry(
    key="oxytocin",
    display_en="Oxytocin",
    display_bn="অক্সিটোসিন",
    category="uterotonic",
    adult_rule=DoseRule(fixed_mg_per_dose=10, max_single_mg=20,
                        freq_per_day=1, interval_hours=0,
                        min_age_months=12 * 12, route="IV/IM",
                        warnings_en=("Active management of third stage of labor: 10 IU IM.",
                                     "Never give IV bolus — risk of hypotension."),
                        warnings_bn=("প্রসবের তৃতীয় পর্যায়ে ১০ আইইউ ইনজেকশন।",
                                     "আইভি বোলাস দেবেন না।")),
    notes_en="Postpartum hemorrhage, labor induction.",
    notes_bn="প্রসব-পরবর্তী রক্তপাত ও প্রসব প্ররোচনায়।",
))

_add(DrugEntry(
    key="ergometrine",
    display_en="Ergometrine (Ergonovine)",
    display_bn="এর্গোমেট্রিন",
    category="uterotonic",
    adult_rule=DoseRule(fixed_mg_per_dose=0.2, max_single_mg=0.2,
                        freq_per_day=3, interval_hours=4,
                        min_age_months=12 * 12, route="IM",
                        warnings_en=("Avoid in hypertension and preeclampsia.",
                                     "Do not give IV bolus."),
                        warnings_bn=("উচ্চ রক্তচাপে নিষেধ।",
                                     "আইভি বোলাস নিষেধ।")),
    notes_en="Postpartum hemorrhage. Refrigerate ampoules.",
    notes_bn="প্রসব-পরবর্তী রক্তপাতে।",
    aliases=("ergonovine", "methylergometrine"),
))

_add(DrugEntry(
    key="misoprostol",
    display_en="Misoprostol",
    display_bn="মিসোপ্রস্টল",
    category="uterotonic",
    adult_rule=DoseRule(fixed_mg_per_dose=200, max_single_mg=800,
                        freq_per_day=4, interval_hours=6,
                        min_age_months=12 * 12, route="Oral/Per-rectal",
                        warnings_en=("Off-label for PPH in many settings.",
                                     "Avoid in pregnancy (unless termination)."),
                        warnings_bn=("গর্ভাবস্থায় নিষেধ (গর্ভপাত ছাড়া)।",
                                     "প্রসব-পরবর্তী রক্তপাতে অফ-লেবেল।")),
    notes_en="PPH prevention where oxytocin not available.",
    notes_bn="অক্সিটোসিন না থাকলে PPH প্রতিরোধে।",
))

_add(DrugEntry(
    key="levonorgestrel",
    display_en="Levonorgestrel (Emergency Contraception)",
    display_bn="লেভোনরজেস্ট্রেল",
    category="contraceptive",
    adult_rule=DoseRule(fixed_mg_per_dose=1.5, max_single_mg=1.5,
                        freq_per_day=1, interval_hours=0,
                        min_age_months=12 * 12, route="Oral"),
    notes_en="Single dose within 72h of unprotected intercourse.",
    notes_bn="অরক্ষিত যৌন সম্পর্কের ৭২ ঘণ্টার মধ্যে একক ডোজ।",
))

_add(DrugEntry(
    key="medroxyprogesterone",
    display_en="Medroxyprogesterone (DMPA)",
    display_bn="মেড্রক্সিপ্রোজেস্টেরন",
    category="contraceptive",
    adult_rule=DoseRule(fixed_mg_per_dose=150, max_single_mg=150,
                        freq_per_day=1, interval_hours=0,
                        min_age_months=12 * 12, route="IM"),
    notes_en="Every 3 months IM injection.",
    notes_bn="প্রতি ৩ মাসে ইনজেকশন।",
))

_add(DrugEntry(
    key="combined_oral_contraceptive",
    display_en="Combined Oral Contraceptive",
    display_bn="সমন্বিত জন্মনিরোধক বড়ি",
    category="contraceptive",
    adult_rule=DoseRule(freq_per_day=1, interval_hours=24,
                        min_age_months=12 * 12, route="Oral"),
    notes_en="21 active + 7 placebo. Take same time daily.",
    notes_bn="২১ দিন সক্রিয় + ৭ দিন ভুয়া। প্রতিদিন একই সময়ে।",
    aliases=("coc", "oral contraceptive", "pill"),
))


# ---------- Diabetes / metabolic --------------------------------------------

_add(DrugEntry(
    key="insulin_regular",
    display_en="Insulin (Regular)",
    display_bn="ইনসুলিন (নিয়মিত)",
    category="antidiabetic",
    adult_rule=DoseRule(freq_per_day=3, interval_hours=8,
                        min_age_months=12 * 12, route="SC",
                        warnings_en=("Dose individualized by blood glucose log.",
                                     "Hypoglycemia education required."),
                        warnings_bn=("রক্তের গ্লুকোজ অনুযায়ী ডোজ।",
                                     "হাইপোগ্লাইসেমিয়া সম্পর্কে শিক্ষা দিন।")),
    notes_en="Short-acting, given before meals.",
    notes_bn="খাবারের আগে দ্রুত-কার্যকর ইনসুলিন।",
    aliases=("insulin", "soluble insulin"),
))

_add(DrugEntry(
    key="insulin_nph",
    display_en="Insulin (Intermediate / NPH)",
    display_bn="ইনসুলিন (মধ্যম-মেয়াদী)",
    category="antidiabetic",
    adult_rule=DoseRule(freq_per_day=2, interval_hours=12,
                        min_age_months=12 * 12, route="SC"),
    notes_en="Cloudy suspension. Roll gently before drawing up.",
    notes_bn="মেঘলা দ্রবণ। আঁকানোর আগে আলতো করে গড়িয়ে নিন।",
    aliases=("nph", "isophane insulin"),
))

_add(DrugEntry(
    key="metformin",
    display_en="Metformin",
    display_bn="মেটফরমিন",
    category="antidiabetic",
    pediatric_rule=_ped(10, max_single=1000, freq=2, interval=12, min_age_months=120),
    adult_rule=_adult(500, max_daily=2000, freq=2, interval=12,
                      warnings_en=("Take with meals.",
                                   "Hold if eGFR < 30.",
                                   "Risk of lactic acidosis in renal failure."),
                      warnings_bn=("খাবারের সাথে নিন।",
                                   "কিডনি সমস্যায় বন্ধ।",
                                   "ল্যাকটিক অ্যাসিডোসিসের ঝুঁকি।")),
    notes_en="First-line oral hypoglycemic for type 2 diabetes.",
    notes_bn="টাইপ-২ ডায়াবেটিসের প্রথম পছন্দ।",
))

_add(DrugEntry(
    key="glibenclamide",
    display_en="Glibenclamide (Glyburide)",
    display_bn="গ্লাইবেনক্লামাইড",
    category="sulfonylurea",
    adult_rule=_adult(5, max_daily=20, freq=2, interval=12,
                      warnings_en=("Take 30 min before meals.",
                                   "Risk of hypoglycemia, especially in elderly."),
                      warnings_bn=("খাবারের ৩০ মিনিট আগে।",
                                   "বয়স্কদের মধ্যে হাইপোগ্লাইসেমিয়া ঝুঁকি।")),
    notes_en="Type 2 diabetes.",
    notes_bn="টাইপ-২ ডায়াবেটিসে।",
    aliases=("glyburide",),
))


# ---------- Vitamins / supplements ------------------------------------------

_add(DrugEntry(
    key="ferrous_sulfate",
    display_en="Ferrous Sulfate (Iron)",
    display_bn="আয়রন সালফেট",
    category="supplement",
    pediatric_rule=_ped(3, max_single=200, freq=2, interval=12, min_age_months=6,
                        warnings_en=("Take on empty stomach with vitamin C.",
                                     "Stool darkens — harmless.",
                                     "Keep away from children — overdose fatal."),
                        warnings_bn=("খালি পেটে ভিটামিন সি-এর সাথে।",
                                     "মলের রঙ কালো হয় — ক্ষতিকর নয়।",
                                     "শিশুদের নাগালের বাইরে রাখুন।")),
    adult_rule=_adult(200, max_daily=400, freq=2, interval=12),
    notes_en="Iron-deficiency anemia. Elemental iron 60-65mg per 200mg tab.",
    notes_bn="রক্তস্বল্পতায়। প্রতি ২০০ মিগ্রা ট্যাবলেটে ৬০-৬৫ মিগ্রা আয়রন।",
))

_add(DrugEntry(
    key="folic_acid",
    display_en="Folic Acid",
    display_bn="ফলিক অ্যাসিড",
    category="supplement",
    adult_rule=_adult(5, max_daily=5, freq=1, interval=24,
                      warnings_en=("Pregnancy: 400-500 mcg/day for neural tube prevention.",
                                   "Higher dose in anemia."),
                      warnings_bn=("গর্ভাবস্থায় ৪০০-৫০০ মাইক্রোগ্রাম।",
                                   "রক্তস্বল্পতায় উচ্চ মাত্রা।")),
    notes_en="Pregnancy, megaloblastic anemia.",
    notes_bn="গর্ভাবস্থা ও মেগালোব্লাস্টিক অ্যানিমিয়ায়।",
))

_add(DrugEntry(
    key="vitamin_a",
    display_en="Vitamin A (Retinol)",
    display_bn="ভিটামিন এ",
    category="supplement",
    pediatric_rule=DoseRule(fixed_mg_per_dose=200000, max_single_mg=200000,
                            freq_per_day=1, interval_hours=0,
                            min_age_months=12, route="Oral"),
    adult_rule=DoseRule(fixed_mg_per_dose=200000, max_single_mg=200000,
                        freq_per_day=1, interval_hours=0,
                        min_age_months=12 * 12, route="Oral"),
    notes_en="WHO supplementation schedule for children 6-59 months.",
    notes_bn="WHO সিডিউল অনুযায়ী ৬-৫৯ মাস বয়সী শিশুদের।",
))

_add(DrugEntry(
    key="multivitamin",
    display_en="Multivitamin preparation",
    display_bn="মাল্টিভিটামিন",
    category="supplement",
    adult_rule=DoseRule(freq_per_day=1, interval_hours=24,
                        min_age_months=12 * 12, route="Oral"),
    notes_en="Supportive supplementation. Not a substitute for diet.",
    notes_bn="সহায়ক সাপ্লিমেন্ট। খাবারের বিকল্প নয়।",
    aliases=("multivitamins",),
))

_add(DrugEntry(
    key="vitamin_b12",
    display_en="Vitamin B12 (Cyanocobalamin / Mecobalamin)",
    display_bn="ভিটামিন বি১২",
    category="supplement",
    adult_rule=DoseRule(fixed_mg_per_dose=1, max_single_mg=1,
                        freq_per_day=1, interval_hours=24,
                        min_age_months=12 * 12, route="IM/Oral"),
    notes_en="Megaloblastic anemia, neuropathy.",
    notes_bn="মেগালোব্লাস্টিক অ্যানিমিয়া ও স্নায়ুর সমস্যায়।",
    aliases=("cyanocobalamin", "mecobalamin"),
))

_add(DrugEntry(
    key="calcium_carbonate",
    display_en="Calcium Carbonate",
    display_bn="ক্যালসিয়াম কার্বোনেট",
    category="supplement",
    adult_rule=_adult(500, max_daily=1500, freq=3, interval=8,
                      warnings_en=("Take with food.",
                                   "Separate from tetracyclines / quinolones by 2h."),
                      warnings_bn=("খাবারের সাথে নিন।",
                                   "টেট্রাসাইক্লিন/কুইনোলোন থেকে ২ ঘণ্টা ব্যবধান।")),
    notes_en="Calcium supplementation, antacid.",
    notes_bn="ক্যালসিয়াম সরবরাহ ও অ্যান্টাসিড।",
    aliases=("calcium",),
))

_add(DrugEntry(
    key="vitamin_d3",
    display_en="Vitamin D3 (Cholecalciferol)",
    display_bn="ভিটামিন ডি৩",
    category="supplement",
    adult_rule=DoseRule(fixed_mg_per_dose=0.025, max_single_mg=0.125,
                        freq_per_day=1, interval_hours=24,
                        min_age_months=12 * 12, route="Oral"),
    notes_en="1000 IU = 0.025 mg. Loading dose 60,000 IU weekly x 8-12 weeks in deficiency.",
    notes_bn="১০০০ আইইউ = ০.০২৫ মিগ্রা।",
    aliases=("cholecalciferol", "vitamin d"),
))

_add(DrugEntry(
    key="tetanus_toxoid",
    display_en="Tetanus Toxoid (Vaccine)",
    display_bn="টিটেনাস টক্সয়েড (টিকা)",
    category="vaccine",
    adult_rule=DoseRule(fixed_mg_per_dose=0.5, max_single_mg=0.5,
                        freq_per_day=1, interval_hours=0,
                        min_age_months=1, route="IM"),
    notes_en="Maternal: 2 doses in pregnancy. Childhood: DPT schedule.",
    notes_bn="গর্ভবতী: ২ ডোজ। শিশু: DPT সিডিউল।",
    aliases=("tt", "tt_vaccine"),
))


# ---------- Antiseptics -----------------------------------------------------

_add(DrugEntry(
    key="chlorhexidine",
    display_en="Chlorhexidine",
    display_bn="ক্লোরহেক্সিডিন",
    category="antiseptic",
    adult_rule=DoseRule(freq_per_day=99, min_age_months=0, route="Topical"),
    notes_en="Umbilical cord care (4% chlorhexidine). Skin antiseptic 0.5% w/v in 70% alcohol.",
    notes_bn="নাভির যত্নে ৪% ক্লোরহেক্সিডিন।",
))

_add(DrugEntry(
    key="povidone_iodine",
    display_en="Povidone-Iodine",
    display_bn="পোভিডন-আয়োডিন",
    category="antiseptic",
    adult_rule=DoseRule(freq_per_day=99, min_age_months=0, route="Topical",
                        warnings_en=("Avoid in pregnancy (2nd/3rd trimester) and infants.",
                                     "Avoid in thyroid disease."),
                        warnings_bn=("গর্ভাবস্থায় ও শিশুদের ক্ষেত্রে সতর্ক।",
                                     "থাইরয়েডের সমস্যায় এড়িয়ে চলুন।")),
    notes_en="Skin antiseptic 10% solution.",
    notes_bn="চামড়ার জীবাণুনাশক ১০% দ্রবণ।",
))


# ---------- Electrolytes / emergency ----------------------------------------

_add(DrugEntry(
    key="calcium_gluconate",
    display_en="Calcium Gluconate",
    display_bn="ক্যালসিয়াম গ্লুকোনেট",
    category="electrolyte",
    adult_rule=DoseRule(fixed_mg_per_dose=1000, max_single_mg=3000,
                        freq_per_day=1, interval_hours=0,
                        min_age_months=12 * 12, route="IV",
                        warnings_en=("Slow IV push for hyperkalemia or calcium channel blocker overdose.",
                                     "Extravasation causes tissue necrosis."),
                        warnings_bn=("ধীরে শিরায় দিন।",
                                     "টিস্যু ক্ষতির ঝুঁকি।")),
    notes_en="Hyperkalemia, hypocalcemia, calcium channel blocker toxicity.",
    notes_bn="হাইপারক্যালেমিয়া ও হাইপোক্যালসেমিয়ায়।",
))

_add(DrugEntry(
    key="magnesium_sulfate",
    display_en="Magnesium Sulfate",
    display_bn="ম্যাগনেসিয়াম সালফেট",
    category="emergency",
    adult_rule=DoseRule(fixed_mg_per_dose=4000, max_single_mg=4000,
                        freq_per_day=1, interval_hours=4,
                        min_age_months=12 * 12, route="IV/IM",
                        warnings_en=("Eclampsia: 4g IV over 20 min, then 1g/hr.",
                                     "Monitor knee jerk reflex and respiratory rate."),
                        warnings_bn=("এক্লাম্পসিয়ায় ৪ গ্রাম ২০ মিনিটে।",
                                     "হাঁটুর রিফ্লেক্স ও শ্বাসের হার পরীক্ষা।")),
    notes_en="Eclampsia prophylaxis and treatment. Severe asthma.",
    notes_bn="এক্লাম্পসিয়া প্রতিরোধ ও চিকিৎসায়।",
    aliases=("mgso4", "epsom salt"),
))

_add(DrugEntry(
    key="potassium_chloride",
    display_en="Potassium Chloride",
    display_bn="পটাসিয়াম ক্লোরাইড",
    category="electrolyte",
    adult_rule=_adult(600, max_daily=2400, freq=3, interval=8,
                      warnings_en=("Take with food and water.",
                                   "Never give IV push — risk of cardiac arrest."),
                      warnings_bn=("খাবার ও পানির সাথে নিন।",
                                   "আইভি বোলাস নিষেধ।")),
    notes_en="Hypokalemia.",
    notes_bn="হাইপোক্যালেমিয়ায়।",
))

_add(DrugEntry(
    key="sodium_bicarbonate",
    display_en="Sodium Bicarbonate",
    display_bn="সোডিয়াম বাইকার্বোনেট",
    category="alkalinizer",
    adult_rule=DoseRule(fixed_mg_per_dose=2000, max_single_mg=4000,
                        freq_per_day=3, interval_hours=8,
                        min_age_months=12 * 12, route="Oral",
                        warnings_en=("Avoid long-term use.",
                                     "Caution in CHF, hypertension."),
                        warnings_bn=("দীর্ঘমেয়াদী ব্যবহার এড়িয়ে চলুন।",
                                     "হৃদযন্ত্র ও উচ্চ রক্তচাপে সতর্ক।")),
    notes_en="Metabolic acidosis, urinary alkalinization.",
    notes_bn="বিপাকীয় অ্যাসিডোসিস ও প্রস্রাব ক্ষারীয় করতে।",
))

_add(DrugEntry(
    key="ors_zinc",
    display_en="ORS + Zinc (Co-pack)",
    display_bn="ওরস + জিংক (একত্রে)",
    category="rehydration",
    pediatric_rule=DoseRule(freq_per_day=99, min_age_months=6, route="Oral",
                            warnings_en=("ORS as needed; zinc 20mg/day for 10-14 days.",
                                         "Continue normal feeding."),
                            warnings_bn=("ORS প্রয়োজনমতো; জিংক ১০-১৪ দিন ২০ মিগ্রা।",
                                         "স্বাভাবিক খাবার চালিয়ে যান।")),
    adult_rule=DoseRule(freq_per_day=99, min_age_months=12 * 12, route="Oral"),
    notes_en="Bangladesh IMCI standard co-pack for childhood diarrhea.",
    notes_bn="বাংলাদেশের IMCI স্ট্যান্ডার্ড।",
    aliases=("oral rehydration solution with zinc", "ors and zinc"),
))


# ---------- Neurology / psychiatry ------------------------------------------

_add(DrugEntry(
    key="carbamazepine",
    display_en="Carbamazepine",
    display_bn="কার্বামাজেপিন",
    category="anticonvulsant",
    adult_rule=_adult(200, max_daily=1200, freq=2, interval=12,
                      warnings_en=("Start low and titrate slowly.",
                                   "Monitor CBC and liver function."),
                      warnings_bn=("কম ডোজে শুরু করে ধীরে বাড়ান।",
                                   "রক্ত ও লিভার পরীক্ষা।")),
    notes_en="Epilepsy, trigeminal neuralgia, bipolar disorder.",
    notes_bn="মৃগীরোগ ও ট্রাইজেমিনাল নিউরালজিয়ায়।",
))

_add(DrugEntry(
    key="valproic_acid",
    display_en="Sodium Valproate",
    display_bn="সোডিয়াম ভ্যালপ্রোয়েট",
    category="anticonvulsant",
    adult_rule=_adult(400, max_daily=2400, freq=2, interval=12,
                      warnings_en=("Avoid in pregnancy — neural tube defects.",
                                   "Monitor liver function."),
                      warnings_bn=("গর্ভাবস্থায় নিষেধ — স্নায়ুর নালী ত্রুটি।",
                                   "লিভার পরীক্ষা করুন।")),
    notes_en="Broad-spectrum anticonvulsant.",
    notes_bn="বিস্তৃত-স্পেকট্রাম খিঁচুনির ওষুধ।",
    aliases=("sodium valproate", "valproate"),
))

_add(DrugEntry(
    key="phenytoin",
    display_en="Phenytoin",
    display_bn="ফেনিটোইন",
    category="anticonvulsant",
    adult_rule=_adult(100, max_daily=600, freq=3, interval=8,
                      warnings_en=("Narrow therapeutic window.",
                                   "Gingival hyperplasia with long-term use."),
                      warnings_bn=("সরু থেরাপিউটিক পরিসর।",
                                   "দীর্ঘমেয়াদে মাড়ি ফুলতে পারে।")),
    notes_en="Tonic-clonic and focal seizures.",
    notes_bn="টনিক-ক্লোনিক ও ফোকাল খিঁচুনিতে।",
))

_add(DrugEntry(
    key="levetiracetam",
    display_en="Levetiracetam",
    display_bn="লেভেটিরাসিটাম",
    category="anticonvulsant",
    adult_rule=_adult(500, max_daily=3000, freq=2, interval=12,
                      warnings_en=("Behavioral side effects possible.",
                                   "Renal dose adjustment required."),
                      warnings_bn=("আচরণগত পার্শ্বপ্রতিক্রিয়া সম্ভব।",
                                   "কিডনি সমস্যায় ডোজ কমান।")),
    notes_en="Broad-spectrum, fewer drug interactions than older agents.",
    notes_bn="কম ওষুধের মিথস্ক্রিয়া।",
))


# ---------- Immunosuppressants ----------------------------------------------

_add(DrugEntry(
    key="azathioprine",
    display_en="Azathioprine",
    display_bn="অ্যাজাথায়োপ্রিন",
    category="immunosuppressant",
    adult_rule=DoseRule(fixed_mg_per_dose=50, max_single_mg=150,
                        freq_per_day=1, interval_hours=24,
                        min_age_months=12 * 12, route="Oral",
                        warnings_en=("Monitor CBC and LFT.",
                                     "Avoid with allopurinol — severe toxicity."),
                        warnings_bn=("রক্ত ও লিভার পরীক্ষা।",
                                     "অ্যালোপিউরিনলের সাথে নিষেধ।")),
    notes_en="Autoimmune disease, transplant rejection prevention.",
    notes_bn="অটোইমিউন রোগ ও প্রতিস্থাপন প্রতিরোধে।",
))

_add(DrugEntry(
    key="methotrexate",
    display_en="Methotrexate",
    display_bn="মেথোট্রেক্সেট",
    category="immunosuppressant",
    adult_rule=DoseRule(fixed_mg_per_dose=7.5, max_single_mg=25,
                        freq_per_day=1, interval_hours=168,
                        min_age_months=12 * 12, route="Oral/IM",
                        warnings_en=("Weekly (not daily) dosing for autoimmune disease.",
                                     "Folate supplementation recommended."),
                        warnings_bn=("সাপ্তাহিক (দৈনিক নয়) ডোজ।",
                                     "ফলেট সাপ্লিমেন্ট।")),
    notes_en="Rheumatoid arthritis, psoriasis, some cancers.",
    notes_bn="রিউমাটয়েড আর্থ্রাইটিস ও সোরিয়াসিসে।",
))


# ---------- Public API -----------------------------------------------------

def drug_count() -> int:
    """Number of drugs in the formulary."""
    return len(_unique_entries())


def list_drugs() -> list[dict[str, str]]:
    """Return [{key, display_en, display_bn, category}, ...] sorted by display_en."""
    items = sorted(_unique_entries().values(), key=lambda d: d.display_en.lower())
    return [
        {
            "key": d.key,
            "display_en": d.display_en,
            "display_bn": d.display_bn,
            "category": d.category,
        }
        for d in items
    ]


def list_categories() -> list[str]:
    """Return unique sorted categories present in the formulary."""
    return sorted({d.category for d in _unique_entries().values()})


def _normalize(name: str) -> str:
    """Lowercase, strip, collapse whitespace, drop common punctuation."""
    s = (name or "").lower().strip()
    s = " ".join(s.split())
    for ch in "-_/.,()[]":
        s = s.replace(ch, " ")
    s = " ".join(s.split())
    return s


def lookup(medication_name: str) -> Optional[DrugEntry]:
    """Find a drug by exact key, display name, or alias (case-insensitive).

    Returns None if not found.
    """
    if not medication_name:
        return None
    needle = _normalize(medication_name)
    # 1) exact key
    if medication_name in _FORMULARY:
        return _FORMULARY[medication_name]
    # 2) normalized key
    for k, v in _FORMULARY.items():
        if _normalize(k) == needle:
            return v
    # 3) display names
    for v in _FORMULARY.values():
        if _normalize(v.display_en) == needle or _normalize(v.display_bn) == needle:
            return v
    # 4) aliases
    for v in _FORMULARY.values():
        for alias in v.aliases:
            if _normalize(alias) == needle:
                return v
    # 5) substring fallback: needle contained in any key/display
    for k, v in _FORMULARY.items():
        if needle and needle in _normalize(k):
            return v
    for v in _FORMULARY.values():
        if needle and needle in _normalize(v.display_en):
            return v
    return None


def _pick_rule(entry: DrugEntry, age_months: float) -> Optional[DoseRule]:
    """Pick pediatric or adult rule based on age_months."""
    # Pediatric rule applies when present AND age below adult threshold (12y=144mo)
    if entry.pediatric_rule is not None and age_months < 144:
        return entry.pediatric_rule
    return entry.adult_rule


def _format_dose_text(dose_mg: float, unit_pref: str = "mg") -> str:
    """Render mg nicely — if dose is fractional and small, show as fraction string."""
    if unit_pref != "mg":
        return f"{dose_mg:g} {unit_pref}"
    rounded = round(dose_mg, 2)
    if abs(rounded - round(rounded)) < 0.005:
        return f"{int(round(rounded))} mg"
    return f"{rounded:g} mg"


def calculate_dose(
    medication_name: str,
    age_years: float,
    weight_kg: float,
    lang: str = "en",
) -> Optional[dict]:
    """Return deterministic dose for a medication, or None if not in formulary.

    Returns dict with: matched_key, display_en, display_bn, category, age_rule_used,
    dose_mg_per_dose, freq_per_day, interval_hours, max_daily_mg, route,
    warnings (list[str]), is_dangerous (bool), source ("formulary"),
    formatted_dose_en, formatted_dose_bn.

    Safety rails:
    - Younger than min_age_months → is_dangerous=True with warning.
    - Computed mg/kg dose exceeds max_single_mg → clamp + is_dangerous=True.
    - Computed daily dose exceeds max_daily_mg → is_dangerous=True.
    - Unknown drug → returns None (caller falls back to LLM).
    """
    entry = lookup(medication_name)
    if entry is None:
        return None

    age_months = age_years * 12.0
    rule = _pick_rule(entry, age_months)
    if rule is None:
        return None

    warnings: list[str] = []
    is_dangerous = False

    # Age guardrail
    if rule.min_age_months and age_months < rule.min_age_months:
        is_dangerous = True
        msg = (
            f"Patient age ({age_years:g} years) is below the minimum age "
            f"({rule.min_age_months / 12:g} years) for {entry.display_en}."
            if lang == "en" else
            f"রোগীর বয়স ({age_years:g} বছর) — {entry.display_bn} এর সর্বনিম্ন বয়স "
            f"({rule.min_age_months / 12:g} বছর) এর কম।"
        )
        warnings.append(msg)

    # Compute mg per dose
    if rule.mg_per_kg_per_dose is not None and weight_kg > 0:
        dose_mg = rule.mg_per_kg_per_dose * weight_kg
        computed_via = "mg/kg"
    elif rule.fixed_mg_per_dose is not None:
        dose_mg = rule.fixed_mg_per_dose
        computed_via = "fixed"
    else:
        dose_mg = 0.0
        computed_via = "none"

    # Clamp to max_single_mg
    if rule.max_single_mg and dose_mg > rule.max_single_mg:
        clamped = dose_mg
        dose_mg = rule.max_single_mg
        is_dangerous = True
        msg = (
            f"Calculated dose ({clamped:g} mg) exceeds single-dose maximum "
            f"({rule.max_single_mg:g} mg). Clamped."
            if lang == "en" else
            f"গণনাকৃত ডোজ ({clamped:g} মিগ্রা) একক-ডোজ সর্বোচ্চ ({rule.max_single_mg:g} মিগ্রা) ছাড়িয়েছে।"
        )
        warnings.append(msg)

    # Daily dose check
    daily_mg = dose_mg * rule.freq_per_day if rule.freq_per_day else 0.0
    if rule.max_daily_mg and daily_mg > rule.max_daily_mg:
        is_dangerous = True
        msg = (
            f"Total daily dose ({daily_mg:g} mg) exceeds maximum "
            f"({rule.max_daily_mg:g} mg/day). Verify with prescriber."
            if lang == "en" else
            f"মোট দৈনিক ডোজ ({daily_mg:g} মিগ্রা) সর্বোচ্চ ({rule.max_daily_mg:g} মিগ্রা/দিন) ছাড়িয়েছে।"
        )
        warnings.append(msg)

    # Append rule warnings
    rule_warnings = rule.warnings_en if lang == "en" else rule.warnings_bn
    warnings.extend(rule_warnings)

    notes = entry.notes_en if lang == "en" else entry.notes_bn
    display = entry.display_en if lang == "en" else entry.display_bn

    age_rule_used = "pediatric" if (entry.pediatric_rule is rule) else "adult"

    formatted_dose = _format_dose_text(dose_mg)

    return {
        "matched_key": entry.key,
        "display_en": entry.display_en,
        "display_bn": entry.display_bn,
        "category": entry.category,
        "age_rule_used": age_rule_used,
        "dose_mg_per_dose": round(dose_mg, 3),
        "freq_per_day": rule.freq_per_day,
        "interval_hours": rule.interval_hours,
        "max_daily_mg": rule.max_daily_mg,
        "route": rule.route,
        "warnings": warnings,
        "notes": notes,
        "computed_via": computed_via,
        "is_dangerous": is_dangerous,
        "source": "formulary",
        "formatted_dose_en": formatted_dose,
        "formatted_dose_bn": _format_dose_text(dose_mg),
        "display_name_used": display,
    }
