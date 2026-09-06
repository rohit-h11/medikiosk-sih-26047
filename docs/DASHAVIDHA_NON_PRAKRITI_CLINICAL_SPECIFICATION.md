# Dashavidha Pariksha: The 9 Non-Prakriti Parameters
## Comprehensive Clinical Assessment Manual, Diagnostic Algorithms & Engineering Specification

> **Document Type**: Master Clinical-Engineering Specification  
> **Repository Context**: MediKiosk AYUSH Engine (Module A - Ayurveda)  
> **Core Purpose**: Exhaustive clinical knowledge, physiological mechanisms, diagnostic scoring, dialogue questioning sequences, and physician handoff rubrics for the **remaining 9 parameters** of classical Dashavidha Pariksha (*Charaka Samhita, Vimana Sthana 8:94*).  
> **Complementary Asset**: Extends and completes `DASHAVIDHA_PARIKSHA_RESEARCH_AND_SPECIFICATION.md` (which covers Prakriti/CCRAS-PAS).

---

## Executive Summary: The Diagnostic Philosophy of Dashavidha Pariksha

In classical Ayurveda, diagnostic inquiry is governed by a fundamental axiom:
$$\mathbf{Treatment \ Strategy} = f(\mathbf{Rogi \ Bala}, \ \mathbf{Roga \ Bala})$$

Acharya Charaka states (*Vimana Sthana 8:94*):
> *"Parikshyam tu khalu prayojanam roga-bala-pramanam rogi-bala-pramanam cha jnatva..."*  
> *(The primary purpose of clinical examination is to precisely evaluate the strength of the disease [Roga-Bala] versus the vital reserve of the patient [Rogi-Bala] so that neither drastic therapies are administered to weak patients, nor mild, ineffective therapies to robust patients).*

While **Prakriti** determines the lifelong genetic and metabolic baseline, the remaining **9 parameters** determine:
1. **The Acute Pathological Vector**: **Vikriti** (Roga-Bala).
2. **The Vital Functional Reserves**: **Ahara Shakti, Vyayama Shakti, Satmya, Sattva, Vaya** (Kiosk-Assessable Rogi-Bala).
3. **The Deep Structural Integrity**: **Sara, Samhanana, Pramana** (Physician-Examined Rogi-Bala).

```
                      DASHAVIDHA PARIKSHA COMPASS
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
[GENETIC BASELINE]       [ACUTE PATHOLOGY]        [VITAL HOST RESERVE]
  • 1. Prakriti            • 2. Vikriti             • 3. Ahara Shakti
                                                    • 4. Vyayama Shakti
                                                    • 5. Satmya
                                                    • 6. Sattva
                                                    • 7. Vaya
                                                    • 8. Sara
                                                    • 9. Samhanana
                                                    • 10. Pramana
```

---

## Table of Contents
1. [Parameter 2: Vikriti Pariksha (Pathological State & Morbidity Vector)](#1-parameter-2-vikriti-pariksha)
2. [Parameter 3: Ahara Shakti Pariksha (Digestive Power, Agni & Koshtha)](#2-parameter-3-ahara-shakti-pariksha)
3. [Parameter 4: Satmya Pariksha (Epigenetic Tolerance & Adaptability)](#3-parameter-4-satmya-pariksha)
4. [Parameter 5: Sattva Pariksha (Psychic Endurance & Neuro-Coping)](#4-parameter-5-sattva-pariksha)
5. [Parameter 6: Vyayama Shakti Pariksha (Work Capacity & Ardha Shakti)](#5-parameter-6-vyayama-shakti-pariksha)
6. [Parameter 7: Vaya Pariksha (Biological Epochs & Age-Governed Doshic Dynamics)](#6-parameter-7-vaya-pariksha)
7. [Parameter 8: Sara Pariksha (The 8 Tissues of Deep Functional Reserve)](#7-parameter-8-sara-pariksha)
8. [Parameter 9: Samhanana Pariksha (Skeletal-Muscular Compactness)](#8-parameter-9-samhanana-pariksha)
9. [Parameter 10: Pramana Pariksha (Anthropometric Balance & Proportion)](#9-parameter-10-pramana-pariksha)
10. [Unified Clinical Engine: Rogi-Bala vs. Roga-Bala Triage Matrix](#10-unified-clinical-engine-rogi-bala-vs-roga-bala-triage-matrix)
11. [Data Schemas & Dialogue Flow Integration](#11-data-schemas--dialogue-flow-integration)

---

## 1. Parameter 2: Vikriti Pariksha

### 1.1 Classical Definition & Diagnostic Scope
*Vikriti* represents the pathological deviation of doshas and tissues from homeostatic baseline. It assesses:
* **Hetu (Etiology)**: Dietary infractions (*Ahara*), lifestyle errors (*Vihara*), mental stress (*Manasika*), and environmental triggers (*Kala*).
* **Dosha-Dushya Sammurchana**: The interaction of aggravated Doshas with vulnerable bodily tissues (*Dhatus*).
* **Shat Kriya Kala**: The stage of pathogenesis (Accumulation $\rightarrow$ Aggravation $\rightarrow$ Dissemination $\rightarrow$ Localization $\rightarrow$ Manifestation $\rightarrow$ Complication).

### 1.2 Doshic Aggravation Symptom Dictionary (Vriddhi Lakshana)
To enable accurate AI extraction from patient speech, symptoms are mapped to classical markers:

| Dosha Aggravated | Classical Symptom (*Lakshana*) | Biomedical Presentation | Key Probing Vector |
|---|---|---|---|
| **Vata Vriddhi** | *Toda* | Pricking, needle-like shooting pain | Pain character: Sharp, intermittent, migratory |
| | *Stambha* | Stiffness, rigidity, restricted mobility | Morning joint stiffness, muscular spasm |
| | *Kampa* | Tremors, twitching, involuntary spasms | Neuromuscular agitation, fasciculations |
| | *Rukshata* | Severe dryness, cracked skin, rough tongue | Dehydration, xerosis, flaky scalp |
| | *Anaha / Vibandha* | Abdominal distension, gas, hard constipation | Colonic hypomotility, painful hard stools |
| | *Nidranasha* | Broken sleep, insomnia, restless mind | Sleep latency >45 min, early awakenings |
| **Pitta Vriddhi** | *Daha* | Burning sensations (chest, eyes, palms, soles) | GERD, peripheral neuropathy, gastritis |
| | *Paka* | Suppuration, ulceration, aphthous stomatitis | Mucosal erosion, pustules, inflammatory flares |
| | *Raga* | Erythema, redness, flushing | Vasodilation, urticaria, conjunctival injection |
| | *Tikshnagni* | Ravenous hunger, acidic eructation (*Amlodgara*) | Acid hypersecretion, peptic hyperacidity |
| | *Sweda-Daurgandhya* | Excessive foul perspiration, body heat | Hyperhidrosis, metabolic heat generation |
| **Kapha Vriddhi** | *Gaurava* | Heaviness of head, chest, limbs, abdomen | Lethargy, sluggish venous return, fullness |
| | *Tandra* | Excessive somnolence, clouding of consciousness | Daytime drowsiness, postprandial stupor |
| | *Kasa / Shwasa* | Productive cough with thick white mucoid sputum | Bronchial hypersecretion, congestion |
| | *Agnimandya* | Sluggish digestion, feeling full for 6–8 hours | Delayed gastric emptying, hypochlorhydria |
| | *Shotha* | Edema, water retention, puffy eyes/ankles | Fluid stasis, dependent edema |

### 1.3 Constitutional Concordance (Prakriti vs. Vikriti Concordance)
* **Prakriti-Sama-Samaveta (Homologous)**: A Pitta disease occurring in a Pitta-dominant patient (e.g., severe Amlapitta in a Pitta Prakriti). The disease is aggressive and requires cautious management (*Krichhrasadhya*).
* **Vikriti-Vishama-Samaveta (Contradictory)**: A Vata disease occurring in a Kapha-dominant patient (e.g., joint dryness in an oily Kapha person). Readily curable (*Sukhasadhya*) because the baseline tissues resist Vata pathogenesis.

---

## 2. Parameter 3: Ahara Shakti Pariksha

### 2.1 The Two Pillars: Abhyavaharana vs. Jarana Shakti
Charaka divides digestive evaluation into intake capacity versus breakdown power:
1. **Abhyavaharana Shakti** (Meal Volume Capacity): The physical capacity of the stomach to accept food without nausea or distress.
2. **Jarana Shakti** (Metabolic & Digestive Power): The enzymatic efficiency of *Jatharagni* to process, absorb, and transform nutrients into *Rasa Dhatu*.

### 2.2 The 4 Functional States of Agni
The operational efficiency of *Agni* directly correlates to autonomic regulation and gut microbiome health:

```
                            THE 4 STATES OF AGNI
                                     │
      ┌──────────────────┬───────────┴───────────┬──────────────────┐
      ▼                  ▼                       ▼                  ▼
 [SAMAGNI]          [VISHAMAGNI]           [TIKSHNAGNI]        [MANDAGNI]
Balanced Autonomic  Vata-Driven            Pitta-Driven        Kapha-Driven
Transit: Regular    Transit: Irregular     Transit: Rapid      Transit: Delayed
Comfort: High       Gas, Pain, Bloat       Burning, Acid       Heaviness, Mucus
```

1. **Samagni (Optimal / Eudigestion)**:
   * Consumes food at normal intervals. Digestion completes in 3–4 hours without burping, nausea, or sleepiness.
   * Signs of perfect digestion (*Jeerna Ahara Lakshana*): *Udgara Shuddhi* (pure, odorless eructation), *Utsaha* (lightness & energy), *Yathochita Vegotsarga* (proper evacuation of urine and feces).
2. **Vishamagni (Irregular / Vata Agni)**:
   * Unpredictable appetite: Ravenous one day, zero hunger the next.
   * Symptoms: Flatulence, abdominal gurgling (*Atopa*), constipation alternating with loose stools, colicky postprandial cramps. Correlates to Irritable Bowel Syndrome (IBS-M).
3. **Tikshnagni / Atyagni (Hyperactive / Pitta Agni)**:
   * Rapidly burns food. Patient feels hunger within 90 minutes; severe weakness and irritability if meal is delayed.
   * Symptoms: Burning epigastric pain, acid reflux, dry throat, loose yellow burning stools. Correlates to Hyperthyroidism, Gastric Hyperacidity, Peptic Ulcers.
4. **Mandagni (Hypoactive / Kapha Agni)**:
   * Chronic lack of appetite. Small meal creates persistent heaviness (*Gaurava*) in the stomach for 6–8 hours.
   * Symptoms: Sweet/sour regurgitation, excessive salivation (*Praseka*), nausea, white coating on tongue (*Ama*), sticky mucus-laden stools. Correlates to Hypothyroidism, Gastroparesis.

### 2.3 Koshtha Pariksha (Enteric Motility & Laxation Response)
* **Mridu Koshtha (Sensitive / Soft)**: Dominated by Pitta. Evacuates 2–3 times daily. Minimal stimulants (warm milk, fresh grapes, jaggery) cause instant loose stools.
* **Krura Koshtha (Hard / Spastic)**: Dominated by Vata. Hard, dry pellets. Daily defecation requires intense straining; resists moderate laxatives; requires unctuous purgatives (*Castor oil, Trivrit*).
* **Madhyama Koshtha (Normal / Balanced)**: Dominated by Kapha or Sama Doshas. One well-formed stool per day with gentle effort.

---

## 3. Parameter 4: Satmya Pariksha

### 3.1 Classical Concept: Homologation & Epigenetic Adaptation
*Satmya* refers to substances, diets, and climatic exposures that have become biologically compatible (*Upasheya*) through lifelong habitual exposure, promoting tissue longevity without inducing disease (*Charaka Vimana 8:118*).

### 3.2 Classical Dimensions of Satmya
1. **Rasa Satmya (Taste Habituation)**:
   * **Sarva-Rasa Satmya (Pravara)**: The patient comfortably digests and thrives on all six tastes (Sweet, Sour, Salty, Pungent, Bitter, Astringent). Indicates an expansive enzymatic profile and high metabolic flexibility.
   * **Madhyama Satmya**: Habituated to 3–4 tastes, but hypersensitive to extreme pungent, sour, or heavy sweet foods.
   * **Eka-Rasa Satmya (Avara)**: Dependent on only 1 or 2 tastes (e.g., exclusively sweets or only plain bland food). Prone to metabolic and allergic breakdowns.
2. **Desha Satmya (Geographic/Climatic Resilience)**:
   * Adaptability when relocating between *Anupa* (humid/marshy), *Jangala* (arid/desert), and *Sadharana* (temperate) zones.
3. **Ritu Satmya (Seasonal Transition Adaptation)**:
   * Resilience during *Ritusandhi* (the 14-day transition period between seasons when disease outbreaks spike).
4. **Oka Satmya (Conditioned Immunity to Unwholesome Inputs)**:
   * Habitual adaptation to suboptimal foods or toxins (e.g., tolerance to hard water, night shifts, or fermented foods without disease).

### 3.3 Scoring & Clinical Classification

| Satmya Grade | Classical Title | Clinical Presentation | Therapeutic Implication |
|---|---|---|---|
| **Pravara (Score $\ge 80\%$)** | *Sarva-Rasa Satmya* | High nutritional adaptability, travels without illness, minimal dietary allergies | Can tolerate broad pharmacological formulations and rigorous dietary changes |
| **Madhyama (50–79%)** | *Madhyama Satmya* | Tolerates common regional foods; mild transient distress with climatic shifts | Requires gradual substitution (*Padamshika Krama*) of medications/diet |
| **Avara (< 50%)** | *Alpa / Eka-Rasa Satmya* | Narrow dietary tolerance, multiple food sensitivities, frequent travel sickness | Fragile gut; requires strict dietary adherence and gentle, familiar medications |

---

## 4. Parameter 5: Sattva Pariksha

### 4.1 Classical Concept: Manasika Bala (Psychic Resilience)
*Sattva* denotes the purity, endurance, and regulatory power of the mind (*Manas*). It determines how a patient experiences pain, processes clinical diagnosis, and adheres to therapy (*Charaka Vimana 8:119*).

### 4.2 The 3 Tiers of Psychic Endurance

```
                             SATTVA TAXONOMY
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
 [PRAVARA SATTVA]           [MADHYAMA SATTVA]           [AVARA SATTVA]
High Self-Command           Socially Dependent         Psychic Fragility
Pain Tolerated Calmly       Needs Reassurance          Faints / Severe Panic
Disciplined Adherence       Holds Steady with Support  Despair / Amplification
```

1. **Pravara Sattva (High Resilience / Sattva Sara)**:
   * **Characteristics**: Innate tranquility (*Kalyanabhinivesha*), emotional poise, high pain threshold.
   * **Clinical Manifestation**: Even during severe disease, fractures, or painful procedures, remains composed. Adheres strictly to bitter medicines, dietary restrictions, and long treatment regimens without complaining.
2. **Madhyama Sattva (Moderate Resilience / Supportive Coping)**:
   * **Characteristics**: Can endure distress, but draws strength from observing others and requires active empathy and reassurance from healthcare staff (*Paran apekshamana*).
   * **Clinical Manifestation**: Anxious when left alone; becomes stable once the doctor explains the treatment plan and gives reassurance.
3. **Avara Sattva (Low Resilience / Somatic Amplification)**:
   * **Characteristics**: Weak psychological reserve (*Hina Sattva*). Dominated by *Rajas* (hyper-reactivity) and *Tamas* (despair/inertia).
   * **Clinical Manifestation**: Minor discomfort produces extreme distress. Terrified of blood, needles, or medical equipment. Prone to syncope, panic attacks, and non-compliance. Inconsolable despite repeated medical reassurance.

### 4.3 Biomedical Correlates
* Heart Rate Variability (HRV) high-frequency power (parasympathetic vagal brake).
* Prefrontal cortex inhibition over amygdala reactivity.
* Connor-Davidson Resilience Scale (CD-RISC) concordance.

---

## 5. Parameter 6: Vyayama Shakti Pariksha

### 5.1 Work Capacity & Cardiorespiratory Endurance
*Vyayama Shakti* evaluates *Karmashakti* (functional musculoskeletal capacity and aerobic reserve). It dictates whether a patient can endure physical exertion or detoxifying therapies (*Charaka Vimana 8:120*).

### 5.2 The Physiological Endpoint: Ardha Shakti (Half-Capacity)
Ayurveda explicitly warns against exercising to exhaustion. Exercise must halt when the patient reaches **Ardha Shakti** (50% of maximum physiological reserve):

```
                        CARDINAL SIGNS OF ARDHA SHAKTI
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
[Cephalic Perspiration]       [Oral Respiration]             [Dryness & Lightness]
Sweat beads on forehead,      Shift from nasal breathing     *Mukha Shosha* (dry mouth),
nose, temples, and axillae    to deep mouth breathing        followed by muscle tremor
```

*Classical Source (*Ashtanga Hridaya, Sutra Sthana 2:11*):*
> *"Hridi sthana-sthito vayur yadavaktram prapadyate,  
> Vyayamam kurvato jantostadardha-balasya lakshanam."*  
> *(When the air residing in the chest reaches the mouth, forcing oral respiration, that is the sign of half-strength reached).*

### 5.3 Clinical Classification & Scoring

| Grade | Exertion Threshold | Recovery Profile | Clinical Translation |
|---|---|---|---|
| **Pravara** | Sustains heavy physical labor, running, gym workouts $>45$ min | Respiratory recovery $<5$ min; feels energetic | Can tolerate *Shodhana* (Vamana, Virechana), vigorous exercise |
| **Madhyama** | Comfortable with brisk walking (30–45 min), climbing 2–3 flights | Recovery in 15–20 min with mild fatigue | Moderate therapy; gentle daily yoga, brisk walking |
| **Avara** | Breathless on walking 100 meters or climbing 1 flight of stairs | Exhaustion lasts hours; requires prolonged rest | Fragile cardiorespiratory reserve; *Shodhana* contraindicated |

---

## 6. Parameter 7: Vaya Pariksha

### 6.1 Biological Epochs & Doshic Governance
Ayurvedic chronobiology recognizes that age alters baseline physiology and drug pharmacokinetics (*Charaka Vimana 8:122*):

```
+---------------------------------------------------------------------------------------------------------+
| LIFE STAGE          | CHRONOLOGICAL AGE | DOMINANT DOSHA | TISSUE KINETICS        | PHARMACOLOGICAL RULE |
+---------------------+-------------------+----------------+------------------------+----------------------+
| 1. Bala (Childhood) | 0 to 16 years     | Kapha Dominant | *Vivardhamana Dhatu*   | *Mridu* (Mild) drugs,|
|                     |                   |                | Rapid growth, immature | sweet/ghee carriers, |
|                     |                   |                | immune defenses        | avoid harsh purging  |
+---------------------+-------------------+----------------+------------------------+----------------------+
| 2. Madhyama (Adult) | 16 to 60 years    | Pitta Dominant | *Sampoornata / Parihani| Standard therapeutic |
|   • Vriddhi         | (16–30 yrs)       | (Metabolic     | Peak physiological     | dosages; high        |
|   • Yauvana         | (30–40 yrs)       | Vigour)        | reserve and enzyme     | tolerance for all    |
|   • Parihani        | (40–60 yrs)       |                | efficiency             | Panchakarma therapies|
+---------------------+-------------------+----------------+------------------------+----------------------+
| 3. Vriddha (Elderly)| > 60 years        | Vata Dominant  | *Kshayamana Dhatu*     | Titrate dose downward|
|                     |                   |                | Catabolic degeneration,| Rejuvenating Rasayana|
|                     |                   |                | depleted bone/marrow   | Unctuous, non-drying |
+---------------------+-------------------+----------------+------------------------+----------------------+
```

---

## 7. Parameter 8: Sara Pariksha (The 8 Tissue Essences)

### 7.1 Concept of Dhatu Sarata (Deep Vital Reserve)
*Sara* evaluates the qualitative excellence, purity, and functional reserve of each of the seven structural tissues (*Sapta Dhatus*) plus mental essence (*Satva Sara*). It is the definitive indicator of deep immunological stamina (*Vyadhikshamatva*).

### 7.2 The 8 Saras: Clinical Criteria & Physician Observation Rubric

```
                                 THE 8 SARAS
                                      │
     ┌───────────┬───────────┬────────┴──────────┬───────────┬───────────┐
     ▼           ▼           ▼                   ▼           ▼           ▼
[Twak/Rasa]   [Rakta]     [Mamsa]             [Meda]      [Asthi]     [Majja]
 Skin luster  Radiance    Muscular firmness   Lubrication Bone mass   Neuro-ocular
                                                  │
                               ┌──────────────────┴──────────────────┐
                               ▼                                     ▼
                          [Shukra]                              [Satva]
                       Ojas & Vigor                        Mental Fortitude
```

#### 1. Twak Sara / Rasa Sara (Lymph & Plasma Excellence)
* **Physician Inspection**: Skin is soft, smooth, unctuous (*Snigdha*), clear, with fine, delicate, deep-rooted hairs. Nails are lustrous.
* **Psychological Profile**: Cheerful disposition, deep empathy, refined intellect, contentment.
* **Deficiency Sign**: Dry, flaky, cracked skin, dull complexion, pruritus.

#### 2. Rakta Sara (Hemic & Circulatory Excellence)
* **Physician Inspection**: Radiant pinkish-red luster on earlobes, conjunctiva, tongue, lips, palms, soles, and nail beds. Healthy capillary refill ($<2$ seconds).
* **Psychological Profile**: High vitality, emotional warmth, leadership, clarity.
* **Deficiency Sign**: Pallor, cold extremities, fatigue, brittle nails, stomatitis.

#### 3. Mamsa Sara (Muscular Excellence)
* **Physician Inspection**: Firm, symmetrical, well-developed musculature covering bones. Deep unexposed joints. Well-filled temples, cheeks, neck, and calves.
* **Psychological Profile**: Forgiveness, patience, courage, physical endurance, loyalty.
* **Deficiency Sign**: Muscle wasting, visible prominent bony processes, joint laxity.

#### 4. Meda Sara (Adipose & Lipid Excellence)
* **Physician Inspection**: Unctuous, resonant, melodic voice. Oily, lustrous hair, eyes, teeth, and skin. Smooth, effortless joint movement.
* **Psychological Profile**: Affluence, generosity, emotional stability, soft manners.
* **Deficiency Sign**: Joint cracking (*Sandhisphutana*), dry coarse voice, emaciation.

#### 5. Asthi Sara (Skeletal & Bone Mineral Excellence)
* **Physician Inspection**: Broad heels, robust ankles, prominent knees, large teeth, dense skull, strong jawline. High bone density.
* **Psychological Profile**: Tremendous physical endurance, tireless work ethic, unyielding determination.
* **Deficiency Sign**: Dental caries, brittle nails, hair loss, early joint degeneration.

#### 6. Majja Sara (Neuro-Osseous & Marrow Excellence)
* **Physician Inspection**: Thick, strong bones; deep, magnetic, resonant voice; large, clear, expressive eyes; harmonious joint articulations.
* **Psychological Profile**: Profound intellect, artistic mastery, long lifespan, nobility.
* **Deficiency Sign**: Osteoporosis, hollow bone aches, frequent dizziness, neurological tremors.

#### 7. Shukra Sara (Reproductive & Ojas Excellence)
* **Physician Inspection**: Radiant facial glow (*Ojas/Prabha*), bright magnetic eyes, symmetrical teeth, glowing skin, robust libido.
* **Psychological Profile**: Charismatic presence, cheerful vitality, high social appeal, disease resistance.
* **Deficiency Sign**: Sexual debility, chronic fatigue, anxiety, recurring infections.

#### 8. Satva Sara (Psychic Essence)
* **Physician Inspection**: Unshakable memory, dignified posture, clean habits, courageous demeanor under medical crisis.

---

## 8. Parameter 9: Samhanana Pariksha

### 8.1 Skeletal-Muscular Compactness & Structural Symmetry
*Samhanana* evaluates how tightly and symmetrically bones, ligaments, joints, and muscles are bound together (*Charaka Vimana 8:116*).

### 8.2 The 3 Grades of Compactness

```
+-------------------------------------------------------------------------------------------------------+
| GRADE           | STRUCTURAL PHENOTYPE                                | CLINICAL CORRELATE            |
+-----------------+-----------------------------------------------------+-------------------------------+
| 1. Susamhata    | Symmetrical skeletal frame, well-knit joints with   | High trauma resistance,       |
|    (Pravara)    | unexposed bone ends, firm muscular cohesion,        | low incidence of sprains or   |
|                 | upright stable posture                              | spinal disc herniations       |
+-----------------+-----------------------------------------------------+-------------------------------+
| 2. Madhyama     | Average joint articulation, moderate muscle tone,   | Standard physical stability;  |
|    Samhanana    | proportionate skeletal build                        | average injury tolerance      |
+-----------------+-----------------------------------------------------+-------------------------------+
| 3. Hina / Avara | Loose joints, visible hypermobility, asymmetric     | High susceptibility to joint  |
|    Samhanana    | skeletal alignment, prominent superficial veins,    | subluxation, ligament tears,  |
|                 | poor muscular padding over bony prominences         | early osteoarthritis          |
+-----------------+-----------------------------------------------------+-------------------------------+
```

---

## 9. Parameter 10: Pramana Pariksha

### 9.1 Classical Anguli Pramana vs. Modern Biometrics
*Charaka Samhita* defines bodily proportions using **Svena-Angula Pramana** (the patient's own finger-breadth as the standardized unit of measurement):
* **Ideal Height**: 84 *Angulis* ($\approx 3.5$ *Hastas*).
* **Proportional Symmetry**: Height equals arm span (*Ayamaschavistaro yasya samo bhavati*).

### 9.2 Modern Clinical Integration
In the digital kiosk and OPD desk, *Pramana* bridges to objective biometrics:
1. **Height & Weight**: Calibrated load cells and ultrasonic stadiometers.
2. **Body Mass Index (BMI)**:
   * $< 18.5$: *Ati-Karshya* (Severe Emaciation / Vata Aggravation / Rasa Kshaya).
   * $18.5 - 24.9$: *Sama Pramana* (Balanced Constitutional Proportions).
   * $25.0 - 29.9$: *Sthaulya Purvaroopa* (Overweight / Medo Vriddhi).
   * $\ge 30.0$: *Ati-Sthaulya* (Morbid Obesity / Medovaha Srotorodha).
3. **Waist-to-Hip Ratio (WHR)**: Identifies central visceral adiposity (*Udara Sthaulya*).

---

## 10. Unified Clinical Engine: Rogi-Bala vs. Roga-Bala Triage Matrix

The primary diagnostic deliverable of Dashavidha Pariksha is the balance between **Disease Virulence** and **Patient Vitality**:

$$\mathbf{Bala}_{\text{Rogi}} = \sum w_i \cdot \text{Score}_i \quad \text{vs.} \quad \mathbf{Bala}_{\text{Roga}} = \sum v_j \cdot \text{Severity}_j$$

```
                           THE CLINICAL TRIAGE MATRIX
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
[HIGH ROGI + HIGH ROGA]       [LOW ROGI + HIGH ROGA]        [LOW ROGI + LOW ROGA]
Robust Patient / Severe Illness Weak Patient / Severe Illness Weak Patient / Mild Illness
        │                             │                             │
        ▼                             ▼                             ▼
• Indicated: SHODHANA CHIKITSA • SHODHANA IS LETHAL!         • Indicated: GENTLE SHAMANA
  (Full Panchakarma: Vamana,    • Contraindicated for harsh   • Rest, gentle diet,
   Virechana, Basti)             purging or fasting            *Deepana-Pachana* single
• Potent, high-dose classical  • Must prioritize BRIMHANA      herbs, lifestyle tuning
  formulations (Kashayas,        (Nourishing) & supportive     • Gradual convalescence
  Guggulus, Vatis)               care before treating disease
```

---

## 11. Data Schemas & Dialogue Flow Integration

### 11.1 Comprehensive Dashavidha Patient Profile Schema (JSON)

```json
{
  "dashavidha_assessment": {
    "patient_id": "P-98214",
    "timestamp": "2026-09-06T12:00:00Z",
    "parameters": {
      "01_prakriti": {
        "status": "COMPLETED_CCRAS_PAS",
        "scores": { "vata": 22.0, "pitta": 54.0, "kapha": 24.0 },
        "classification": "Pittaja Ekadoshaja"
      },
      "02_vikriti": {
        "dominant_aggravation": "Pitta-Vata",
        "vriddhi_lakshana": ["Daha (burning)", "Tikshnagni (hyperacidity)", "Toda (joint pain)"],
        "dushya_involved": ["Rasa", "Rakta", "Asthi"],
        "severity": "Madhyama"
      },
      "03_ahara_shakti": {
        "abhyavaharana_shakti": "Pravara",
        "jarana_shakti": "Tikshnagni",
        "koshtha": "Mridu",
        "clinical_note": "Acidic regurgitation, hunger every 2 hours"
      },
      "04_satmya": {
        "classification": "Madhyama Satmya",
        "score_pct": 66.7,
        "taste_adaptability": "Tolerates spicy and sour poorly"
      },
      "05_sattva": {
        "classification": "Pravara Sattva",
        "score_pct": 88.9,
        "pain_tolerance": "High",
        "adherence_likelihood": "High"
      },
      "06_vyayama_shakti": {
        "classification": "Madhyama Vyayama Shakti",
        "score_pct": 66.7,
        "fatigue_threshold": "Brisk walk 30 mins"
      },
      "07_vaya": {
        "chronological_age": 34,
        "lifestage": "Madhyama Vaya (Adult - Pitta phase)"
      },
      "08_sara": {
        "status": "PHYSICIAN_EXAMINED",
        "predominant_saras": ["Rakta Sara", "Mamsa Sara"],
        "overall_grade": "Madhyama Sara"
      },
      "09_samhanana": {
        "status": "PHYSICIAN_EXAMINED",
        "compactness_grade": "Susamhata (Pravara)"
      },
      "10_pramana": {
        "height_cm": 172.0,
        "weight_kg": 68.0,
        "bmi": 23.0,
        "classification": "Sama Pramana (Normal Proportionate)"
      }
    },
    "clinical_synthesis": {
      "rogi_bala": "Pravara (High Vital Reserve)",
      "roga_bala": "Madhyama (Moderate Morbidity)",
      "treatment_pathway": "Eligible for standard Panchakarma / Pitta-Shamana therapies without Brimhana pre-conditioning."
    }
  }
}
```

---

## 12. Verification & Reference Citations
* **Charaka Samhita** — *Vimana Sthana*, Chapter 8 (*Rogabhishagjitiya Adhyaya*), Verses 94–122.
* **Sushruta Samhita** — *Sutra Sthana*, Chapter 35 (*Aturopakramaniya Adhyaya*).
* **Ashtanga Hridaya** — *Sutra Sthana*, Chapter 2 (*Dinacharya Adhyaya* — Ardha Shakti definitions).
* **Ministry of AYUSH / CCRAS** — Technical Manual for Clinical Examination in Ayurvedic Hospitals.
