"""Citation registry: the published source behind every method in the package.

The project promises to be upfront about its methods and sources. This module
is the single machine-readable place where each computational method maps to
its original publication or standard. Agents reach it through the
``get_citations`` MCP tool and the ``lcf://citations`` resource, and the
human-readable equivalent is docs/PHYSICS_REVIEW.pdf.

Entries state the method, the citation, and where honesty requires it, a
status note (for example that ASTM E739 was withdrawn, or that a method's
validation is implementation-grade rather than benchmarked).
"""

from __future__ import annotations

__all__ = ["CITATIONS", "get_citations"]

CITATIONS: dict[str, dict[str, str]] = {
    "true_stress_strain": {
        "method": "Engineering to true stress-strain conversion",
        "citation": "Standard relations, e.g. Dowling, Mechanical Behavior "
                    "of Materials, Pearson, 4th ed., 2013, ch. 4",
    },
    "ramberg_osgood": {
        "method": "Ramberg-Osgood stress-strain curve",
        "citation": "Ramberg and Osgood, NACA Technical Note 902, 1943",
    },
    "basquin": {
        "method": "Basquin elastic strain-life (stress-life) relation",
        "citation": "Basquin, Proc. ASTM 10 (1910) 625-630",
    },
    "coffin_manson": {
        "method": "Coffin-Manson plastic strain-life relation",
        "citation": "Coffin, Trans. ASME 76 (1954) 931-950, and Manson, "
                    "NACA Technical Note 2933, 1953",
    },
    "morrow_mean_stress": {
        "method": "Morrow mean-stress correction",
        "citation": "Morrow, in Fatigue Design Handbook, SAE, 1968",
    },
    "swt": {
        "method": "Smith-Watson-Topper damage parameter and life relation",
        "citation": "Smith, Watson, and Topper, Journal of Materials 5 "
                    "(1970) 767-778",
    },
    "walker": {
        "method": "Walker mean-stress correction",
        "citation": "Walker, ASTM STP 462 (1970) 1-14. The gamma-from-"
                    "ultimate-strength estimate for steels follows Dowling, "
                    "SAE 2004-01-2227, and Dowling, Calhoun, and Arcari, "
                    "Fatigue Fract. Eng. Mater. Struct. 32 (2009) 163-179",
    },
    "rainflow": {
        "method": "Three-point rainflow cycle counting",
        "citation": "ASTM E1049-85 (reapproved 2017), Standard Practices "
                    "for Cycle Counting in Fatigue Analysis. Origin: "
                    "Matsuishi and Endo, JSME, 1968",
    },
    "level_crossing_counting": {
        "method": "Level-crossing counting",
        "citation": "ASTM E1049-85 (reapproved 2017), section 5.2",
    },
    "peak_counting": {
        "method": "Peak counting",
        "citation": "ASTM E1049-85 (reapproved 2017), section 5.3",
    },
    "racetrack_filter": {
        "method": "Racetrack (gate) filter for history condensation",
        "citation": "Fuchs, Nelson, Burke, and Toomay, SAE paper 730565, "
                    "1973",
    },
    "miner": {
        "method": "Palmgren-Miner linear damage rule",
        "citation": "Palmgren, VDI-Zeitschrift 68 (1924) 339-341, and "
                    "Miner, J. Appl. Mech. 12 (1945) A159-A164",
    },
    "sn_knee_haibach": {
        "method": "Woehler line below the knee, Haibach fictitious slope "
                  "2k-1, and the elementary variant",
        "citation": "Haibach, LBF Report TM 50/70, 1970, described in "
                    "Haibach, Betriebsfestigkeit, Springer, 3rd ed., 2006",
    },
    "dldr": {
        "method": "Double linear damage rule",
        "citation": "Manson and Halford, Int. J. Fracture 17 (1981) 169-192",
    },
    "corten_dolan": {
        "method": "Corten-Dolan cumulative damage",
        "citation": "Corten and Dolan, Proc. Int. Conf. on Fatigue of "
                    "Metals, IMechE, 1956, 235-246",
    },
    "neuber": {
        "method": "Neuber notch rule",
        "citation": "Neuber, J. Appl. Mech. 28 (1961) 544-550",
    },
    "glinka": {
        "method": "Glinka equivalent strain energy density notch rule",
        "citation": "Molski and Glinka, Mater. Sci. Eng. 50 (1981) 93-100",
    },
    "kf_peterson": {
        "method": "Peterson fatigue notch factor",
        "citation": "Peterson, in Sines and Waisman (eds.), Metal Fatigue, "
                    "McGraw-Hill, 1959",
    },
    "kf_neuber": {
        "method": "Neuber fatigue notch factor",
        "citation": "Neuber, Theory of Notch Stresses, 2nd ed., 1958",
    },
    "log_life_regression": {
        "method": "Linearized log-life regression with confidence and "
                  "prediction intervals",
        "citation": "ASTM E739 (withdrawn January 2024 with no replacement, "
                    "cited as historical practice). Modern treatment: Meeker "
                    "et al., Statistical Science 41 (2026) 1-27, also "
                    "available as arXiv:2212.04550",
        "note": "E739 excludes runouts, use the censored maximum-likelihood "
                "fit when runouts exist",
    },
    "censored_mle": {
        "method": "Maximum-likelihood life fit with right-censored runouts",
        "citation": "Spindel and Haibach, Int. J. Fatigue 1 (1979), and "
                    "Ling and Pan, Int. J. Fatigue 19 (1997) 415-419",
    },
    "owen_design_curve": {
        "method": "One-sided tolerance (reliability-confidence) design "
                  "curves via the Owen factor",
        "citation": "Owen, Technometrics 10 (1968) 445-478. The tolerance-"
                    "limit design-curve approach is also standardized in "
                    "ISO 12107:2012",
    },
    "grubbs_test": {
        "method": "Grubbs single-outlier test",
        "citation": "Grubbs, Technometrics 11 (1969) 1-21, and NIST/SEMATECH "
                    "e-Handbook of Statistical Methods, section 1.3.5.17.1",
    },
    "generalized_esd": {
        "method": "Generalized extreme studentized deviate outlier test",
        "citation": "Rosner, Technometrics 25 (1983) 165-172, and "
                    "NIST/SEMATECH e-Handbook, section 1.3.5.17.3",
    },
    "cooks_distance": {
        "method": "Cook's distance and studentized-residual influence "
                  "diagnostics",
        "citation": "Cook, Technometrics 19 (1977) 15-18",
    },
    "frequency_modified_coffin_manson": {
        "method": "Frequency-modified Coffin-Manson law, coefficient form",
        "citation": "Coffin's frequency-modified law in the coefficient form "
                    "used by Engelmaier, IEEE Trans. Components, Hybrids, "
                    "and Manufacturing Technology 6 (1983) 232-237",
    },
    "creep_fatigue_time_fraction": {
        "method": "Time-fraction creep-fatigue damage with a bilinear "
                  "interaction diagram",
        "citation": "Robinson, Trans. ASME 74 (1952) 777-781, and the "
                    "damage-envelope approach of ASME Boiler and Pressure "
                    "Vessel Code, Section III, Division 5",
    },
    "fatemi_socie": {
        "method": "Fatemi-Socie critical-plane parameter",
        "citation": "Fatemi and Socie, Fatigue Fract. Eng. Mater. Struct. "
                    "11 (1988) 149-165",
        "note": "evaluated either from caller-supplied plane quantities or "
                "through the tensor plane search (lcf.criticalplane), which "
                "resolves one cycle's path, per-plane rainflow of long "
                "histories is not implemented",
    },
    "brown_miller": {
        "method": "Brown-Miller critical-plane parameter",
        "citation": "Brown and Miller, Proc. IMechE 187 (1973) 745-755",
        "note": "evaluated either from caller-supplied plane quantities or "
                "through the tensor plane search (lcf.criticalplane), which "
                "resolves one cycle's path, per-plane rainflow of long "
                "histories is not implemented",
    },
    "estimate_medians": {
        "method": "Medians method for strain-life constant estimation",
        "citation": "Meggiolaro and Castro, Int. J. Fatigue 26 (2004) "
                    "463-476",
    },
    "estimate_uniform_material_law": {
        "method": "Uniform Material Law for strain-life constant estimation",
        "citation": "Baeumel and Seeger, Materials Data for Cyclic Loading, "
                    "Supplement 1, Elsevier, 1990",
    },
    "estimate_universal_slopes": {
        "method": "Universal slopes strain-life constant estimation",
        "citation": "Manson, Experimental Mechanics 5 (1965) 193-226",
    },
    "estimate_modified_universal_slopes": {
        "method": "Modified universal slopes strain-life constant estimation",
        "citation": "Muralidharan and Manson, J. Eng. Mater. Technol. 110 "
                    "(1988) 55-58",
    },
    "estimate_hardness": {
        "method": "Hardness-based strain-life constant estimation for steels",
        "citation": "Roessle and Fatemi, Int. J. Fatigue 22 (2000) 495-511",
    },
    "e606_reporting": {
        "method": "Strain-controlled test specimen and reporting metadata "
                  "schema (SpecimenMetadata)",
        "citation": "ASTM E606/E606M-21, Standard Test Method for "
                    "Strain-Controlled Fatigue Testing",
    },
    "staircase_dixon_mood": {
        "method": "Staircase (up-and-down) fatigue-limit estimation, "
                  "Dixon-Mood method",
        "citation": "Dixon and Mood, J. Amer. Statist. Assoc. 43 (1948) "
                    "109-126, and ISO 12107:2012. Validated against "
                    "Ekaputra, Dewa, Haryadi, and Kim, Open Engineering 10 "
                    "(2020) 394-400",
        "note": "below the 0.3 variability bound the standard deviation is "
                "the approximate 0.53*step fallback and is flagged",
    },
    "basis_values": {
        "method": "A-basis and B-basis one-sided tolerance bounds",
        "citation": "Owen, Factors for One-Sided Tolerance Limits and for "
                    "Variables Sampling Plans, Sandia monograph SCR-607, "
                    "1963. Basis definitions (99/95 and 90/95) follow "
                    "MMPDS practice",
    },
    "lack_of_fit_f_test": {
        "method": "Lack-of-fit F test for the linearized life regression",
        "citation": "ASTM E739-10(2015) (withdrawn 2024, de facto "
                    "reference), standard partition of residual error into "
                    "pure error and lack of fit",
    },
    "random_fatigue_limit": {
        "method": "Random fatigue limit model, normal-normal form, "
                  "maximum likelihood with runouts",
        "citation": "Pascual and Meeker, Estimating Fatigue Curves With "
                    "the Random Fatigue-Limit Model, Technometrics 41 "
                    "(1999) 277-290. Modern context: Meeker et al., "
                    "Statistical Science 41 (2026) 1-27",
        "note": "implementation validated by likelihood cross-check and "
                "simulated parameter recovery, not yet benchmarked against "
                "the published laminate-panel fit, its raw data are not "
                "openly published",
    },
    "mean_stress_relaxation": {
        "method": "Cycle-dependent mean stress relaxation power law "
                  "(strain-controlled asymmetric cycling)",
        "citation": "Jhansale and Topper, ASTM STP 519 (1973) 246-270, and "
                    "Morrow and Sinclair, ASTM STP 237 (1958) 83-109",
        "note": "reconstructed from collaborator notes (2026-07-08) matching "
                "the standard published power law, pending confirmation the "
                "formulation is the intended one",
    },
    "ratcheting": {
        "method": "Ratcheting strain accumulation power law and its "
                  "ductility-exhaustion life penalty (stress-controlled "
                  "asymmetric cycling)",
        "citation": "Xia, Kujawski and Ellyin, Int. J. Fatigue 18 (1996) "
                    "335-341, and Kapoor, Fatigue Fract. Eng. Mater. Struct. "
                    "17 (1994) 201-219",
        "note": "reconstructed from collaborator notes (2026-07-08) matching "
                "the standard published forms, pending confirmation the "
                "formulation is the intended one",
    },
    "fkm_roughness": {
        "method": "FKM surface roughness factor K_R",
        "citation": "FKM guideline, Rechnerischer Festigkeitsnachweis fuer "
                    "Maschinenbauteile (Analytical Strength Assessment). "
                    "Formula and material-group constants as tabulated in "
                    "open engineering references (quadco.engineering, "
                    "accessed 2026-07-11), validated against the published "
                    "worked example K_R=0.79 for steel, Rm 600 MPa, Rz 100",
        "note": "applies to stress-based fatigue strengths",
    },
    "fkm_size_factor": {
        "method": "FKM technological size factor K_d,m for tensile strength",
        "citation": "FKM guideline, Rechnerischer Festigkeitsnachweis fuer "
                    "Maschinenbauteile. Logarithmic formula with the 0.7686 "
                    "coefficient verified against two independent open "
                    "sources (accessed 2026-07-11)",
        "note": "only the formula is implemented, the per-material constant "
                "tables are copyrighted FKM data and are not bundled, the "
                "caller supplies a_dm and d_eff_N from a licensed guideline",
    },
    "va_local_strain_simulation": {
        "method": "Variable-amplitude local strain simulation with material "
                  "memory (Masing branches, rainflow-consistent closure)",
        "citation": "Masing, Proc. 2nd Int. Congress for Applied Mechanics, "
                    "Zurich, 1926 (doubled branch). Dowling, Mechanical "
                    "Behavior of Materials, Pearson, 4th ed., 2013, ch. 14 "
                    "(local strain approach). ASTM E1049-85 (memory rule)",
        "note": "internally consistent with the constant-amplitude solvers "
                "and rainflow counting. Compared against the Conle SAE "
                "smooth-specimen dataset (Conle, MSc thesis, U. Waterloo, "
                "1974, data via fde.uwaterloo.ca): within 2x on two of "
                "three histories, about 3x non-conservative on the third. "
                "Mean stress relaxation and ratcheting are not modeled",
    },
}


def get_citations(topic: str | None = None) -> dict[str, dict[str, str]]:
    """Return the citation registry, optionally filtered by a topic substring.

    The filter matches case-insensitively against the key, the method name,
    and the citation text.
    """
    if topic is None:
        return dict(CITATIONS)
    t = topic.lower()
    return {
        key: entry for key, entry in CITATIONS.items()
        if t in key.lower()
        or t in entry["method"].lower()
        or t in entry["citation"].lower()
    }
