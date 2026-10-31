# Anatomical and histological scope — verification record

**Status: PROPOSALS AND EVIDENCE ONLY. Nothing here is approved eligibility criteria.**
D008 remains the operative outcome definition. The subsite and histology rules below are recorded
so the verification work is not lost, and so the reviewer can decide **P014–P022** with the
evidence in front of them. No screening or extraction may apply these rules until they are adopted.

Each claim is tagged **VERIFIED** (read from a source listed below), **INTERPRETATION** (my
inference from those sources), or **INACCESSIBLE** (the primary source could not be consulted).

## Sources consulted

| ID | Source | Edition / version | Original or reproduction | Accessed |
|---|---|---|---|---|
| **S1** | ICD-10-CM code list and per-code inclusion terms, C00–C14, via `icd10data.com` | **ICD-10-CM FY2027** | **Secondary reproduction** of the **US clinical modification** | 2026-10-30 |
| **S2** | NCI SEER, *Site Recode ICD-O-3/WHO 2008 Definition* | ICD-O-3 / WHO 2008 recode | Original (SEER's own table) | 2026-10-30 |
| **S3** | NCI SEER Training Modules, *Head and Neck — Morphology & Grade* | current web edition | Original (NCI training resource) | 2026-10-30 |
| **S4** | NCI SEER Training Modules, ***Anatomy of the Head & Neck*** | current web edition | Original | 2026-10-30 |
| **S5** | NCI Thesaurus via EVS REST API (`ICD-O-3_Code` property) | current release | Original controlled terminology | 2026-10-30 |

### Sources that could NOT be consulted — gaps, not omissions

| Source | What happened |
|---|---|
| **WHO ICD-10 browser** (`icd.who.int/browse10/2019`) | Page shell loads but the content pane never populates; four direct calls to its own endpoints all returned `TypeError: Failed to fetch`. The app's AJAX is blocked in this environment. **WHO ICD-10's own four-character subdivisions are unverified.** S1 is a clinical modification of it, and S1 itself states *"other international versions of ICD-10 … may differ."* |
| **ICD-O-3 manual** (3rd ed., rev. 1/2) | Licensed IARC/WHO publication; IARC host returned "navigation denied". Reached only **indirectly**: topography via S2's ranges, morphology via S5's code properties. **The manual was never read.** |
| **WHO Classification of Head and Neck Tumours, 5th ed. (2022)** | `tumourclassification.iarc.who.int` returned a page with **zero extractable text**; paywalled. **Not consulted.** This is the authority on which entities are formal SCC *variants*, so **P021 and P022 cannot be settled without it.** |
| **AJCC Cancer Staging Manual, 8th ed.** | Paywalled, not attempted. The TNM convention below reaches this document only through S4's description of it. |

## Verified anatomical facts

**S4 verbatim:** *"The oral cavity extends from the vermilion (red) border of the lips to the
junction of the hard and soft palates in the roof of the mouth, and to the circumvallate papillae
on the tongue. The oral cavity consists of the lips, commissures, all surfaces (anterior 2/3 or
oral, dorsal, ventral, border) of the tongue **except the base of tongue, lingual tonsil**, gums
(alveolar ridge), floor of mouth, hard palate, buccal mucosa, and retromolar trigone."*

**S4 verbatim:** *"For purposes of TNM staging, the pharynx includes the following: Oropharynx —
Tonsillar fossae, tonsillar pillars (faucial arch), vallecula, lateral and posterior walls of
oropharynx, **the base of tongue, soft palate, uvula**, and branchial cleft as a site of neoplasm."*

**S4 verbatim:** *"Minor salivary glands are located in many oral cavity structures, including the
oral mucosa, palate, uvul[a]…"* — and **S2** restricts its "Salivary Gland" group to **C079–C089**,
i.e. major glands only. So minor glands are coded to their **anatomical site**, not to a salivary
topography. **VERIFIED.**

**A documented conflict.** S4 places the **soft palate and uvula in the oropharynx for TNM
staging**; NCIt (S5, C12231) describes the soft palate as *"the muscular extension of the hard
palate which **comprises the posterior of the oral cavity**"*; and both ICD-10-CM (S1) and SEER's
recode (S2) place all of C05 within oral groupings. **The assignment is convention-dependent, not
an anatomical absolute** — INTERPRETATION. A protocol must state which convention it adopts
(**P016**) rather than assert a fact.

## Subsite table

Codes are **ICD-10-CM FY2027 (S1)**. They are **not interchangeable with ICD-O-3**: base of tongue
is **C01** in ICD-10-CM but **C01.9** in ICD-O-3 topography (S1 vs S2) — VERIFIED.

### The governing principle

An unspecified or overlapping code is anatomically indeterminate **only if its parent category
straddles the oral-cavity/oropharynx boundary**. Straddling: **C02** (oral tongue vs C02.4 lingual
tonsil) and **C05** (C05.0 hard palate vs C05.1/C05.2 soft palate and uvula). Wholly oral cavity:
**C00, C03, C04, C06**.

| Code | Description (S1) | Type | Compartment identifiable? | Proposed | Inclusion terms (S1) |
|---|---|---|---|---|---|
| C00.0 | External upper lip | specific | yes — external | *P015* | "lipstick area of upper lip; upper lip NOS; vermilion border of upper lip" |
| C00.1 | External lower lip | specific | yes — external | *P015* | "lower lip NOS; lipstick area; vermilion border of lower lip" |
| C00.2 | External lip, unspecified | unspecified within external lip | yes — external | *P015* | "vermilion border of lip NOS" |
| C00.3 | Upper lip, inner aspect | specific | yes — mucosal | *P015* | "buccal aspect; frenulum; mucosa; oral aspect of upper lip" |
| C00.4 | Lower lip, inner aspect | specific | yes — mucosal | *P015* | "buccal aspect; frenulum; mucosa; oral aspect of lower lip" |
| C00.5 | Lip, unspecified, inner aspect | unspecified within mucosal lip | yes — mucosal | *P015* | "buccal aspect; frenulum; mucosa; oral aspect of lip, unspecified" |
| C00.6 | Commissure of lip | specific site, aspect unstated | yes — oral cavity; **external/mucosal not resolvable** | *P015* | none |
| C00.8 | Overlapping sites of lip | overlapping within lip | yes — oral cavity; aspect not resolvable | *P015* | none |
| C00.9 | Lip, unspecified | unspecified within lip | yes — oral cavity; aspect not resolvable | *P015* | none |
| C02.0 | Dorsal surface of tongue | specific | **yes — oral cavity** | **include** | "**anterior two-thirds of tongue**, dorsal surface" + a Type 2 Excludes note (text truncated in capture) |
| C02.1 | Border of tongue | specific | yes — oral | **include** | "tip of tongue" |
| C02.2 | Ventral surface of tongue | specific | yes — oral | **include** | "**anterior two-thirds of tongue**, ventral surface; frenulum linguae" |
| C02.3 | Anterior two-thirds, part unspecified | unspecified within oral tongue | yes — oral | **include** | "middle third of tongue NOS; **mobile part of tongue** NOS" |
| **C02.4** | **Lingual tonsil** | specific | **yes — oropharynx** | **exclude** | capture contains an Excludes fragment sending "tonsil NOS / faucial / palatine" to C09.9, i.e. C02.4 is the *lingual* tonsil |
| **C02.8** | Overlapping sites of tongue | overlapping **across the boundary** | **NO** | *P017* | "**two or more contiguous sites of tongue**" — "tongue" includes base of tongue (C01) |
| **C02.9** | Tongue, unspecified | unspecified **across the boundary** | **NO** | *P017* | none |
| C03.0 | Upper gum | specific | yes — oral | **include** | none |
| C03.1 | Lower gum | specific | yes — oral | **include** | none |
| **C03.9** | **Gum, unspecified** | unspecified within gum | **yes — oral cavity** | **include** | none. Only *which* gum is unknown; there is no oropharyngeal gum |
| C04.0 | Anterior floor of mouth | specific | yes — oral | **include** | "anterior to the premolar-canine junction" |
| C04.1 | Lateral floor of mouth | specific | yes — oral | **include** | none |
| **C04.8** | **Overlapping sites of floor of mouth** | overlapping within floor of mouth | **yes — oral cavity** | **include** | none |
| **C04.9** | **Floor of mouth, unspecified** | unspecified within floor of mouth | **yes — oral cavity** | **include** | none |
| **C05.0** | **Hard palate** | specific | **yes — oral cavity** | **include** | none |
| **C05.1** | **Soft palate** | specific | oropharynx **under TNM** (S4); posterior oral cavity per NCIt (S5) | *P016* | Excludes fragment sends the *nasopharyngeal surface* of soft palate to C11.3 |
| **C05.2** | **Uvula** | specific | oropharynx **under TNM** (S4) | *P016* | none |
| **C05.8** | Overlapping sites of palate | overlapping **across the boundary** | **NO** | *P017* | none |
| **C05.9** | Palate, unspecified | unspecified **across the boundary** | **NO** | *P017* | "**roof of mouth**" — covers hard *and* soft palate |
| C06.0 | Cheek mucosa | specific | yes — oral | **include** | "**buccal mucosa** NOS; internal cheek" |
| C06.1 | Vestibule of mouth | specific | yes — oral | **include** | "buccal sulcus (upper)(lower); labial sulcus (upper)(lower)" |
| C06.2 | Retromolar area | specific | yes — oral | **include** | none |
| C06.80 | Overlapping sites of **unspecified** parts of mouth | overlapping, parts unspecified | probably oral cavity — INTERPRETATION | *P017* | none. **WHO ICD-10 carries a note at C06.8 about origin not classifiable to C00–C06.2 that I could NOT verify**; if it exists it could admit C02.4 |
| C06.89 | Overlapping sites of **other** parts of mouth | overlapping within oral cavity | **yes — oral cavity** | **include** | "**'book leaf' neoplasm [ventral surface of tongue and floor of mouth]**" — both components oral |
| **C06.9** | **Mouth, unspecified** | unspecified within mouth | **yes — oral cavity by name** | **include**, with caveat | "**minor salivary gland, unspecified site**; **oral cavity NOS**" |
| C07, C08.0, C08.1, C08.9 | Major salivary glands | specific | major salivary — separate group (S2) | **exclude** | — |

**Lip is part of the oral cavity** under the standard definition (S4). Excluding it would be an
**aetiological choice, not an anatomical correction** — an earlier framing of mine implied
otherwise and is corrected here.

### Registry groupings cross the boundary (S2) — VERIFIED

| SEER group | ICD-O-3 codes | Mixes |
|---|---|---|
| **Tongue** | C019–C029 | oral tongue (eligible) **+ base of tongue + lingual tonsil** |
| **Gum and Other Mouth** | C030–C039, C050–C059, C060–C069 | gingiva, buccal, retromolar, hard palate **+ soft palate + uvula** |
| **Lip** | C000–C009 | external **+** inner lip undivided |
| Salivary Gland | C079–C089 | major glands only — clean |

Consequence (INTERPRETATION): a strict subsite definition will exclude many registry-based studies
not because their substance is ineligible but because they cannot report at that granularity.
That trade-off is **P018**.

## Histology table

Morphology codes from **S5 (NCIt `ICD-O-3_Code` property)** — an authoritative NCI reproduction,
**not the ICD-O-3 manual**. **S3** states: *"The majority of head and neck malignancies (90-95%)
are squamous cell cancers (M-807_3)."*

| Entity | NCIt term and code | Morphology | What the sources support | Under D008 as written | Needs the Blue Book |
|---|---|---|---|---|---|
| Conventional SCC | Squamous Cell Carcinoma, C2929 | **8070/3** | SCC (S3, S5) | **eligible** | no |
| Verrucous carcinoma | Verrucous Carcinoma, C3781 | **8051/3** | NCIt's definition does **not** state it is squamous | **ambiguous** | **yes** — is it a formal SCC variant? |
| Basaloid SCC | Basaloid Squamous Cell Carcinoma, C54244 | **8083/3** | name and definition explicitly squamous | arguably eligible | **yes** |
| Papillary SCC | Papillary Squamous Cell Carcinoma, C4102 | **8052/3** | *"A well differentiated squamous cell carcinoma…"* | arguably eligible | **yes** |
| Spindle-cell SCC | **Spindle Cell Squamous Carcinoma, C27084** | **8074/3** | name squamous; 807x family | arguably eligible | **yes** |
| Sarcomatoid carcinoma NOS | Sarcomatoid Carcinoma, C27004 | **8032/3, 8033/3** | **not squamous-specific**; a **distinct entity** from C27084 | not eligible | partly |
| Adenosquamous carcinoma | Adenosquamous Carcinoma, C3727 | **8560/3** | *"malignant glandular cells **and** malignant squamous cells"* — distinct entity | not eligible | **yes** |
| Minor salivary gland SCC | — | squamous morphology at an oral topography | minor glands coded to site (S2, S4); C06.9 admits "minor salivary gland, unspecified site" (S1) | **eligible as written** — possibly unintended | **yes** |
| Mucoepidermoid carcinoma | C3772 | **8430/1, 8430/3** | non-squamous salivary (S3) | not eligible | no |
| Adenoid cystic carcinoma | C2970 | **8200/3** | non-squamous salivary (S3) | not eligible | no |
| Acinic cell carcinoma | NCIt label **"Acinar Cell Carcinoma"**, C3768 | **8550/3** | non-squamous salivary (S3); NCIt's concept is generic, so the **salivary-specific entity was not verified** | not eligible | yes |

**Correction on record:** spindle-cell *squamous* carcinoma (8074/3, C27084) and sarcomatoid
carcinoma NOS (8032/3, 8033/3, C27004) are **different entities** and must not be merged. An
earlier note of mine conflated them.

**S3** also defines leukoplakia as *"A white patch on the mucosa of the oral cavity that does not
rub off and cannot be characterized as any other disease"* — i.e. not itself a carcinoma, so oral
potentially malignant disorders without invasive carcinoma are out.

## Two gaps D008 does not currently address — INTERPRETATION

1. **No site-purity rule.** D008 sets a ≥90% threshold for *histology* but none for *anatomy*. A
   study of "oral cavity cancer" containing 15% base-of-tongue cases is not addressed. **P019.**
2. **"Separately reported" is ambiguous.** D008 says eligible "unless an oral-cavity-specific
   **estimate** is reported separately". Separable *case counts* are not the same as a separable
   *effect estimate*. **P020.**

**Site contamination differs from histological contamination** in a way that matters: histological
contamination mixes cell types sharing one exposure route and usually dilutes toward the null;
**site contamination mixes different exposure–outcome relationships** — HPV-driven oropharyngeal
disease, UV-driven external lip disease — so its direction is not predictable.

## Guidance to consult before deciding

ICD-O-3 directly · **WHO Classification of Head and Neck Tumours 5th ed.** (decides P021, P022) ·
AJCC 8th ed. (the TNM convention first-hand) · **INHANCE consortium** subsite groupings, the de
facto standard in this exact literature · IARC Monographs Vol. 100E · SEER Head and Neck Solid
Tumor Rules.
