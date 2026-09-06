# backend/app/ai/ayurveda/question_bank.py
"""
MediKiosk — Validated Ayurvedic Question Bank
Contains:
1. CCRAS-SF-12 (12-Item Prakriti Assessment Scale)
2. Dashavidha 3-Tier Rapid Scale (Sattva, Satmya, Vyayama Shakti)
Pre-localized for English, Hindi, and regional Indic languages for sub-50ms instant turn response.
"""

from typing import List, Dict, Any

PRAKRITI_QUESTIONS_12: List[Dict[str, Any]] = [
    {
        "id": "prakriti_01",
        "index": 1,
        "pillar": "morphological",
        "trait": "Asthi Bandhana & Upachaya (Body Frame & Weight)",
        "prompt": {
            "en": "Which best describes your natural body build and how your weight behaves?",
            "hi": "आपकी प्राकृतिक शारीरिक बनावट और वजन कैसा रहता है?",
            "mr": "तुमची नैसर्गिक शारीरिक ठेवण आणि वजन कसे राहते?",
            "ta": "உங்கள் இயற்கையான உடல் அமைப்பு மற்றும் எடை எவ்வாறு உள்ளது?",
            "te": "మీ సహజ శరీర నిర్మాణం మరియు బరువు ఎలా ఉంటుంది?"
        },
        "options": [
            {
                "id": "opt_v",
                "anchor": "A",
                "dosha": "Vata",
                "label": {"en": "Thin / Hard to gain weight", "hi": "दुबला / वजन बढ़ना मुश्किल"},
                "spoken": {"en": "Thin or slender frame, hard to gain weight.", "hi": "दुबला-पतला शरीर, आसानी से वजन नहीं बढ़ता।"},
                "value": "A"
            },
            {
                "id": "opt_p",
                "anchor": "B",
                "dosha": "Pitta",
                "label": {"en": "Medium / Proportionate", "hi": "मध्यम / संतुलित वजन"},
                "spoken": {"en": "Medium, athletic build, weight changes predictably.", "hi": "मध्यम और सुडौल शरीर, वजन आसानी से नियंत्रित रहता है।"},
                "value": "B"
            },
            {
                "id": "opt_k",
                "anchor": "C",
                "dosha": "Kapha",
                "label": {"en": "Broad / Gains easily", "hi": "चौड़ा भारी ढांचा / जल्दी वजन बढ़ना"},
                "spoken": {"en": "Broad, heavy solid frame, gains weight very easily.", "hi": "भारी और मजबूत शरीर, वजन बहुत तेजी से बढ़ता है।"},
                "value": "C"
            }
        ]
    },
    {
        "id": "prakriti_02",
        "index": 2,
        "pillar": "morphological",
        "trait": "Sparsha (Skin Texture & Moisture)",
        "prompt": {
            "en": "What is the natural texture and feel of your skin without moisturizer?",
            "hi": "बिना तेल या क्रीम के आपकी त्वचा का प्राकृतिक स्पर्श कैसा होता है?",
            "mr": "क्रीम किंवा तेलाशिवाय तुमच्या त्वचेचा नैसर्गिक स्पर्श कसा असतो?",
            "ta": "எண்ணெய் அல்லது கிரீம் இல்லாமல் உங்கள் தோல் எவ்வாறு உணர்கிறது?",
            "te": "క్రీమ్ లేదా నూనె లేకుండా మీ చర్మం సహజంగా ఎలా ఉంటుంది?"
        },
        "options": [
            {
                "id": "opt_v",
                "anchor": "A",
                "dosha": "Vata",
                "label": {"en": "Dry / Rough / Cool", "hi": "सूखी / खुरदरी / ठंडी"},
                "spoken": {"en": "Dry, rough, easily chapped, and cool to touch.", "hi": "रूखी, सूखी और ठंडी त्वचा।"},
                "value": "A"
            },
            {
                "id": "opt_p",
                "anchor": "B",
                "dosha": "Pitta",
                "label": {"en": "Warm / Sensitive / Redness", "hi": "गर्म / संवेदनशील / लालिमा"},
                "spoken": {"en": "Warm, soft, sensitive, prone to redness or rashes.", "hi": "गर्म, मुलायम, जल्दी लाल होने वाली या दाने निकलने वाली त्वचा।"},
                "value": "B"
            },
            {
                "id": "opt_k",
                "anchor": "C",
                "dosha": "Kapha",
                "label": {"en": "Smooth / Oily / Radiant", "hi": "मुलायम / तैलीय / चमकदार"},
                "spoken": {"en": "Smooth, thick, naturally oily and well-hydrated.", "hi": "चिकनी, चमकदार और प्राकृतिक रूप से तैलीय त्वचा।"},
                "value": "C"
            }
        ]
    },
    {
        "id": "prakriti_03",
        "index": 3,
        "pillar": "morphological",
        "trait": "Kesha Swabhava (Hair Characteristics)",
        "prompt": {
            "en": "What is the natural quality and density of your hair?",
            "hi": "आपके बालों की प्राकृतिक गुणवत्ता और घनत्व कैसा है?",
            "mr": "तुमच्या केसांचा नैसर्गिक पोत आणि घनता कशी आहे?",
            "ta": "உங்கள் முடியின் இயற்கையான தரம் மற்றும் அடர்த்தி எவ்வாறு உள்ளது?",
            "te": "మీ జుట్టు సహజ నాణ్యత మరియు సాంద్రత ఎలా ఉంటుంది?"
        },
        "options": [
            {
                "id": "opt_v",
                "anchor": "A",
                "dosha": "Vata",
                "label": {"en": "Dry / Thin / Frizzy", "hi": "सूखे / पतले / बेजान"},
                "spoken": {"en": "Dry, coarse, thin, or prone to split ends.", "hi": "रूखे, पतले और जल्दी दोमुंहे होने वाले बाल।"},
                "value": "A"
            },
            {
                "id": "opt_p",
                "anchor": "B",
                "dosha": "Pitta",
                "label": {"en": "Fine / Early Graying / Thinning", "hi": "पतले / जल्दी सफेद या झड़ने वाले"},
                "spoken": {"en": "Fine, silky, prone to early thinning or early graying.", "hi": "मुलायम, रेशमी, समय से पहले सफेद होने या झड़ने वाले बाल।"},
                "value": "B"
            },
            {
                "id": "opt_k",
                "anchor": "C",
                "dosha": "Kapha",
                "label": {"en": "Thick / Dense / Lustrous", "hi": "घने / मजबूत / चमकदार"},
                "spoken": {"en": "Thick, dense, lustrous, dark and wavy with strong roots.", "hi": "घने, काले, चमकदार और मजबूत जड़ों वाले बाल।"},
                "value": "C"
            }
        ]
    },
    {
        "id": "prakriti_04",
        "index": 4,
        "pillar": "morphological",
        "trait": "Sandhi Bandhana (Joint Sensation & Articulation)",
        "prompt": {
            "en": "How do your joints feel and sound during everyday movement?",
            "hi": "चलने-फिरने पर आपके जोड़ों में कैसा महसूस या आवाज होती है?",
            "mr": "चालताना किंवा हालचाल करताना तुमच्या सांध्यांमध्ये काय जाणवते?",
            "ta": "நடைபயிற்சியின் போது உங்கள் மூட்டுகளில் சத்தம் அல்லது வலி உள்ளதா?",
            "te": "నడిచేటప్పుడు మీ కీళ్లలో శబ్దం లేదా నొప్పి అనిపిస్తుందా?"
        },
        "options": [
            {
                "id": "opt_v",
                "anchor": "A",
                "dosha": "Vata",
                "label": {"en": "Clicking / Cracking / Stiff", "hi": "चटकने की आवाज / सूखापन"},
                "spoken": {"en": "Prominent bones, joints frequently crack or feel stiff.", "hi": "जोड़ों से कट-कट की आवाज आना या जकड़न महसूस होना।"},
                "value": "A"
            },
            {
                "id": "opt_p",
                "anchor": "B",
                "dosha": "Pitta",
                "label": {"en": "Flexible / Warm / Sensitive", "hi": "लचीले / गर्म / जल्दी थकने वाले"},
                "spoken": {"en": "Moderate flexibility, joints feel warm and prone to strain.", "hi": "लचीले जोड़, लेकिन जल्दी गर्म या दर्द होने वाले।"},
                "value": "B"
            },
            {
                "id": "opt_k",
                "anchor": "C",
                "dosha": "Kapha",
                "label": {"en": "Sturdy / Cushioned / Silent", "hi": "मजबूत / गद्दीदार / आवाज रहित"},
                "spoken": {"en": "Well-padded, sturdy, strong and silent joints.", "hi": "मजबूत, स्थिर और बिना किसी आवाज के सुचारू जोड़।"},
                "value": "C"
            }
        ]
    },
    {
        "id": "prakriti_05",
        "index": 5,
        "pillar": "physiological",
        "trait": "Kshudha / Agni (Appetite & Hunger Consistency)",
        "prompt": {
            "en": "How would you describe your everyday hunger and appetite pattern?",
            "hi": "आपकी रोजाना की भूख और खान-पान की आदत कैसी रहती है?",
            "mr": "तुमची रोजची भूक आणि खाण्याची सवय कशी असते?",
            "ta": "உங்கள் தினசரி பசி மற்றும் உணவு பழக்கம் எப்படி இருக்கும்?",
            "te": "మీ రోజువారీ ఆకలి తీరు ఎలా ఉంటుంది?"
        },
        "options": [
            {
                "id": "opt_v",
                "anchor": "A",
                "dosha": "Vata",
                "label": {"en": "Irregular / Unpredictable", "hi": "अनियमित / कभी ज्यादा कभी कम"},
                "spoken": {"en": "Irregular appetite; can easily skip meals without distress.", "hi": "अनियमित भूख, कभी बहुत ज्यादा तो कभी बिना खाए भी रह सकते हैं।"},
                "value": "A"
            },
            {
                "id": "opt_p",
                "anchor": "B",
                "dosha": "Pitta",
                "label": {"en": "Sharp / Cannot delay meals", "hi": "तेज भूख / भोजन में देरी असहनीय"},
                "spoken": {"en": "Sharp and intense hunger; cannot delay meals without anger.", "hi": "बहुत तेज भूख, समय पर खाना न मिले तो गुस्सा या सिरदर्द होना।"},
                "value": "B"
            },
            {
                "id": "opt_k",
                "anchor": "C",
                "dosha": "Kapha",
                "label": {"en": "Mild / Steady / Can skip easily", "hi": "धीमी / स्थिर भूख"},
                "spoken": {"en": "Slow and steady appetite; can comfortably postpone meals.", "hi": "धीमी और संतुलित भूख, भोजन में देरी होने पर भी कोई परेशानी नहीं।"},
                "value": "C"
            }
        ]
    },
    {
        "id": "prakriti_06",
        "index": 6,
        "pillar": "physiological",
        "trait": "Jarana Shakti (Digestion & Post-Meal Comfort)",
        "prompt": {
            "en": "What is your typical sensation 1 to 2 hours after a normal meal?",
            "hi": "खाना खाने के 1-2 घंटे बाद पेट में आमतौर पर कैसा महसूस होता है?",
            "mr": "जेवणानंतर १-२ तासांनी पोटाची स्थिती कशी असते?",
            "ta": "உணவு சாப்பிட்ட 1-2 மணி நேரம் கழித்து வயிறு எப்படி உணர்கிறது?",
            "te": "భోజనం చేసిన 1-2 గంటల తర్వాత కడుపులో ఎలా అనిపిస్తుంది?"
        },
        "options": [
            {
                "id": "opt_v",
                "anchor": "A",
                "dosha": "Vata",
                "label": {"en": "Gas / Bloating / Rumbling", "hi": "गैस / पेट फूलना / गुड़गुड़ाहट"},
                "spoken": {"en": "Prone to gas, bloating, or unpredictable digestion.", "hi": "पेट में गैस बनना, पेट फूलना या गुड़गुड़ होना।"},
                "value": "A"
            },
            {
                "id": "opt_p",
                "anchor": "B",
                "dosha": "Pitta",
                "label": {"en": "Acidity / Burning / Sour burps", "hi": "एसिडिटी / जलन / खट्टी डकार"},
                "spoken": {"en": "Rapid digestion, prone to burning or sour reflux.", "hi": "जलन, सीने में जलन, एसिडिटी या खट्टी डकारें आना।"},
                "value": "B"
            },
            {
                "id": "opt_k",
                "anchor": "C",
                "dosha": "Kapha",
                "label": {"en": "Heavy / Sluggish / Sleepy", "hi": "भारीपन / सुस्ती / नींद आना"},
                "spoken": {"en": "Slow digestion, feeling heavy, full or sleepy for hours.", "hi": "पेट में भारीपन, आलस या घंटों तक भरा-भरा लगना।"},
                "value": "C"
            }
        ]
    },
    {
        "id": "prakriti_07",
        "index": 7,
        "pillar": "physiological",
        "trait": "Koshtha (Bowel Pattern & Stool Quality)",
        "prompt": {
            "en": "How do your bowel movements naturally behave?",
            "hi": "आपका पेट साफ होने की प्राकृतिक स्थिति कैसी रहती है?",
            "mr": "तुमचे पोट साफ होण्याची नैसर्गिक स्थिती कशी असते?",
            "ta": "உங்கள் மலம் கழிக்கும் பழக்கம் எவ்வாறு உள்ளது?",
            "te": "మీ మలవిసర్జన అలవాటు ఎలా ఉంటుంది?"
        },
        "options": [
            {
                "id": "opt_v",
                "anchor": "A",
                "dosha": "Vata",
                "label": {"en": "Constipated / Hard / Irregular", "hi": "कब्ज / सूखा मल / अनियमित"},
                "spoken": {"en": "Prone to constipation; dry, hard, or irregular stools.", "hi": "कब्ज रहना, सूखा या कड़ा मल आना और पेट साफ होने में कठिनाई।"},
                "value": "A"
            },
            {
                "id": "opt_p",
                "anchor": "B",
                "dosha": "Pitta",
                "label": {"en": "Soft / Frequent (2-3 times)", "hi": "नरम / दिन में 2-3 बार"},
                "spoken": {"en": "Frequent, soft or loose stools; quick evacuation.", "hi": "दिन में 2 से 3 बार, नरम या ढीला मल जल्दी साफ होना।"},
                "value": "B"
            },
            {
                "id": "opt_k",
                "anchor": "C",
                "dosha": "Kapha",
                "label": {"en": "Regular / Solid / Once a day", "hi": "नियमित / बंधा हुआ / दिन में 1 बार"},
                "spoken": {"en": "Regular, once a day, well-formed solid stools.", "hi": "रोजाना दिन में एक बार, बंधा हुआ और आसानी से साफ होना।"},
                "value": "C"
            }
        ]
    },
    {
        "id": "prakriti_08",
        "index": 8,
        "pillar": "physiological",
        "trait": "Sheeta-Ushna (Thermal & Climate Sensitivity)",
        "prompt": {
            "en": "Which weather or temperature makes you feel most uncomfortable?",
            "hi": "किस मौसम या तापमान में आपको सबसे अधिक परेशानी होती है?",
            "mr": "कोणत्या ऋतूत किंवा वातावरणात तुम्हाला जास्त त्रास होतो?",
            "ta": "எந்த வானிலையில் உங்களுக்கு அதிக அசௌகரியம் ஏற்படுகிறது?",
            "te": "ఏ వాతావరణంలో మీకు ఎక్కువ అసౌకర్యంగా ఉంటుంది?"
        },
        "options": [
            {
                "id": "opt_v",
                "anchor": "A",
                "dosha": "Vata",
                "label": {"en": "Cold & Dry / Craves warmth", "hi": "सर्दी और सूखा मौसम असहनीय"},
                "spoken": {"en": "Cold, dry, windy weather; craves warmth and hot tea.", "hi": "ठंड और सूखी हवा असहनीय, गर्म वातावरण और गर्म चीजें पसंद होना।"},
                "value": "A"
            },
            {
                "id": "opt_p",
                "anchor": "B",
                "dosha": "Pitta",
                "label": {"en": "Heat & Sun / Craves AC & Cold", "hi": "गर्मी और धूप असहनीय"},
                "spoken": {"en": "Hot, humid weather; craves AC, shade, and cold drinks.", "hi": "गर्मी और तेज धूप असहनीय, ठंडी हवा और ठंडे पेय पसंद होना।"},
                "value": "B"
            },
            {
                "id": "opt_k",
                "anchor": "C",
                "dosha": "Kapha",
                "label": {"en": "Damp & Rain / Loves warm sun", "hi": "नमी और बारिश असहनीय"},
                "spoken": {"en": "Cold, damp, rainy weather; enjoys warm sunshine.", "hi": "सीलन, नमी और बरसाती मौसम से परेशानी, धूप अच्छी लगना।"},
                "value": "C"
            }
        ]
    },
    {
        "id": "prakriti_09",
        "index": 9,
        "pillar": "physiological",
        "trait": "Sweda (Perspiration & Body Heat)",
        "prompt": {
            "en": "How easily and heavily do you sweat in warm weather or during activity?",
            "hi": "गर्मी में या मेहनत करने पर आपको कितना पसीना आता है?",
            "mr": "उन्हाळ्यात किंवा हालचाली करताना तुम्हाला किती घाम येतो?",
            "ta": "வெயிலில் அல்லது வேலை செய்யும் போது உங்களுக்கு எவ்வளவு வியர்க்கிறது?",
            "te": "ఎండలో లేదా శ్రమించినప్పుడు మీకు ఎంత చెమట పడుతుంది?"
        },
        "options": [
            {
                "id": "opt_v",
                "anchor": "A",
                "dosha": "Vata",
                "label": {"en": "Scanty / Sweats very little", "hi": "बहुत कम पसीना आना"},
                "spoken": {"en": "Sweats very little even in warm weather.", "hi": "गर्मी में भी बहुत कम पसीना आना।"},
                "value": "A"
            },
            {
                "id": "opt_p",
                "anchor": "B",
                "dosha": "Pitta",
                "label": {"en": "Profuse / Sweats heavily & quickly", "hi": "बहुत ज्यादा और जल्दी पसीना आना"},
                "spoken": {"en": "Profuse, sweats easily and copiously in mild warmth.", "hi": "थोड़ी सी गर्मी में भी बहुत ज्यादा पसीना आना।"},
                "value": "B"
            },
            {
                "id": "opt_k",
                "anchor": "C",
                "dosha": "Kapha",
                "label": {"en": "Moderate / Only with heavy exertion", "hi": "मध्यम / केवल भारी मेहनत पर"},
                "spoken": {"en": "Moderate; sweats only after sustained physical exertion.", "hi": "संतुलित पसीना, केवल भारी शारीरिक मेहनत करने पर आना।"},
                "value": "C"
            }
        ]
    },
    {
        "id": "prakriti_10",
        "index": 10,
        "pillar": "physiological",
        "trait": "Nidra (Sleep Quality & Architecture)",
        "prompt": {
            "en": "How would you characterize your typical night's sleep?",
            "hi": "रात में आपकी नींद की गुणवत्ता कैसी रहती है?",
            "mr": "रात्री तुमची झोप कशी असते?",
            "ta": "இரவில் உங்கள் தூக்கத்தின் தரம் எவ்வாறு உள்ளது?",
            "te": "రాత్రి సమయంలో మీ నిద్ర నాణ్యత ఎలా ఉంటుంది?"
        },
        "options": [
            {
                "id": "opt_v",
                "anchor": "A",
                "dosha": "Vata",
                "label": {"en": "Light / Easily broken (5-6 hrs)", "hi": "हल्की / जल्दी खुलने वाली (5-6 घंटे)"},
                "spoken": {"en": "Light sleep, easily disturbed by slight noise, 5 to 6 hours.", "hi": "हल्की नींद, जरा सी आवाज से खुल जाना, 5-6 घंटे सोना।"},
                "value": "A"
            },
            {
                "id": "opt_p",
                "anchor": "B",
                "dosha": "Pitta",
                "label": {"en": "Moderate / Sound / Wakes alert", "hi": "संतुलित / गहरी नींद (6-7 घंटे)"},
                "spoken": {"en": "Moderate, sound sleep; wakes up alert and refreshed.", "hi": "गहरी और संतुलित 6-7 घंटे की नींद, सुबह ताजगी से जागना।"},
                "value": "B"
            },
            {
                "id": "opt_k",
                "anchor": "C",
                "dosha": "Kapha",
                "label": {"en": "Heavy / Deep (8+ hrs) / Hard to wake", "hi": "बहुत गहरी / सुस्ती (8+ घंटे)"},
                "spoken": {"en": "Deep, heavy sleep for 8+ hours, difficult to wake up.", "hi": "बहुत गहरी 8 घंटे से ज्यादा नींद, सुबह उठने में भारीपन।"},
                "value": "C"
            }
        ]
    },
    {
        "id": "prakriti_11",
        "index": 11,
        "pillar": "neuro_cognitive",
        "trait": "Grahana & Smriti (Learning Speed & Memory Retention)",
        "prompt": {
            "en": "How do you naturally absorb and remember new information?",
            "hi": "आप नई बातों को कैसे समझते और याद रखते हैं?",
            "mr": "तुम्ही नवीन गोष्टी कशा समजून घेता आणि लक्षात ठेवता?",
            "ta": "புதிய விஷயங்களை நீங்கள் எவ்வாறு கற்றுக்கொள்கிறீர்கள்?",
            "te": "కొత్త విషయాలను మీరు ఎలా గ్రహిస్తారు మరియు గుర్తుంచుకుంటారు?"
        },
        "options": [
            {
                "id": "opt_v",
                "anchor": "A",
                "dosha": "Vata",
                "label": {"en": "Quick to learn / Forgets quickly", "hi": "जल्दी समझना / जल्दी भूलना"},
                "spoken": {"en": "Grasps concepts very quickly, but forgets details rapidly.", "hi": "जल्दी समझ में आना, लेकिन जल्दी भूल भी जाना।"},
                "value": "A"
            },
            {
                "id": "opt_p",
                "anchor": "B",
                "dosha": "Pitta",
                "label": {"en": "Logical / Precise memory", "hi": "सटीक और तर्कसंगत याददाश्त"},
                "spoken": {"en": "Analytical and logical, remembers facts and sequences clearly.", "hi": "तर्कसंगत और स्पष्ट याददाश्त, तथ्यों को सही याद रखना।"},
                "value": "B"
            },
            {
                "id": "opt_k",
                "anchor": "C",
                "dosha": "Kapha",
                "label": {"en": "Takes time / Never forgets", "hi": "समय लगना / कभी न भूलना"},
                "spoken": {"en": "Takes time to learn initially, but remembers permanently.", "hi": "शुरुआत में समय लगना, लेकिन एक बार याद होने पर कभी न भूलना।"},
                "value": "C"
            }
        ]
    },
    {
        "id": "prakriti_12",
        "index": 12,
        "pillar": "neuro_cognitive",
        "trait": "Manasika (Stress Response & Temperament)",
        "prompt": {
            "en": "What is your dominant emotional reaction when faced with sudden stress or conflict?",
            "hi": "अचानक तनाव या विवाद होने पर आपकी स्वाभाविक प्रतिक्रिया क्या होती है?",
            "mr": "अचानक ताण किंवा वाद निर्माण झाल्यावर तुमची प्रतिक्रिया काय असते?",
            "ta": "திடீர் மன அழுத்தம் ஏற்படும் போது உங்கள் எதிர்வினை என்ன?",
            "te": "అకస్మాత్తుగా ఒత్తిడి వచ్చినప్పుడు మీ స్పందన ఎలా ఉంటుంది?"
        },
        "options": [
            {
                "id": "opt_v",
                "anchor": "A",
                "dosha": "Vata",
                "label": {"en": "Anxiety / Worry / Restlessness", "hi": "चिंता / घबराहट / बेचैनी"},
                "spoken": {"en": "Anxiety, worry, overthinking, and restless agitation.", "hi": "चिंता, घबराहट, अत्यधिक सोचना और बेचैनी होना।"},
                "value": "A"
            },
            {
                "id": "opt_p",
                "anchor": "B",
                "dosha": "Pitta",
                "label": {"en": "Anger / Irritability / Confrontational", "hi": "क्रोध / चिड़चिड़ापन / आक्रामकता"},
                "spoken": {"en": "Irritability, sharp anger, impatience, and confrontation.", "hi": "चिड़चिड़ापन, जल्दी गुस्सा आना या तुरंत विरोध करना।"},
                "value": "B"
            },
            {
                "id": "opt_k",
                "anchor": "C",
                "dosha": "Kapha",
                "label": {"en": "Calm / Patient / Withdraws", "hi": "शांत / धैर्यवान / टालने की प्रवृत्ति"},
                "spoken": {"en": "Calm, patient, slow to agitate; prefers peace and quiet.", "hi": "शांत रहना, धैर्य रखना और विवाद से दूर रहना।"},
                "value": "C"
            }
        ]
    }
]

DASHAVIDHA_QUESTIONS_3: List[Dict[str, Any]] = [
    {
        "id": "dash_sattva",
        "index": 1,
        "domain": "sattva",
        "prompt": {
            "en": "When dealing with physical pain or sudden distress, how do you usually cope?",
            "hi": "शारीरिक दर्द या अचानक तनाव का सामना करते समय आप आमतौर पर कैसे सहन करते हैं?",
            "mr": "शारीरिक वेदना किंवा अचानक तणावाचा सामना करताना तुम्ही कसे सहन करता?",
            "ta": "உடல் வலி அல்லது மன அழுத்தத்தை நீங்கள் எவ்வாறு எதிர்கொள்கிறீர்கள்?",
            "te": "శారీరక నొప్పి లేదా ఒత్తిడిని మీరు ఎలా భరిస్తారు?"
        },
        "options": [
            {
                "id": "sattva_pravara",
                "anchor": "A",
                "tier": "Pravara",
                "label": {"en": "Calm & Self-reliant", "hi": "शांत और धैर्यवान"},
                "spoken": {"en": "I remain calm and endure pain patiently without needing much reassurance.", "hi": "मैं शांत रहकर धैर्य से दर्द सहन कर लेता हूं।"},
                "value": "Pravara"
            },
            {
                "id": "sattva_madhyama",
                "anchor": "B",
                "tier": "Madhyama",
                "label": {"en": "Need Encouragement", "hi": "दूसरों के सहारे से"},
                "spoken": {"en": "I can manage distress, but I need encouragement and support from others.", "hi": "मैं संभाल लेता हूं, लेकिन अपनों के सहारे और दिलासे की जरूरत होती है।"},
                "value": "Madhyama"
            },
            {
                "id": "sattva_avara",
                "anchor": "C",
                "tier": "Avara",
                "label": {"en": "Easily Panicked", "hi": "जल्दी घबरा जाना"},
                "spoken": {"en": "I get easily overwhelmed, anxious, or panicked by pain or bad news.", "hi": "मैं दर्द या बुरी खबर से बहुत जल्दी घबरा और परेशान हो जाता हूं।"},
                "value": "Avara"
            }
        ]
    },
    {
        "id": "dash_satmya",
        "index": 2,
        "domain": "satmya",
        "prompt": {
            "en": "How easily does your body adapt when you change your diet, travel, or face sudden weather changes?",
            "hi": "खान-पान, यात्रा या मौसम बदलने पर आपका शरीर कितनी आसानी से ढल जाता है?",
            "mr": "खानपान किंवा हवामान बदलल्यावर तुमचे शरीर किती लवकर जुळवून घेते?",
            "ta": "உணவு அல்லது வானிலை மாறும் போது உங்கள் உடல் எவ்வளவு எளிதாக மாற்றியமைக்கிறது?",
            "te": "ఆహారం లేదా వాతావరణం మారినప్పుడు మీ శరీరం ఎంత తేలికగా అలవాటుపడుతుంది?"
        },
        "options": [
            {
                "id": "satmya_pravara",
                "anchor": "A",
                "tier": "Pravara",
                "label": {"en": "Highly Adaptable", "hi": "आसानी से ढल जाता है"},
                "spoken": {"en": "Very adaptable; I can easily tolerate diverse foods and climates.", "hi": "बहुत आसानी से, मुझे नया खाना या मौसम बदलने पर कोई परेशानी नहीं होती।"},
                "value": "Pravara"
            },
            {
                "id": "satmya_madhyama",
                "anchor": "B",
                "tier": "Madhyama",
                "label": {"en": "Moderately Adaptable", "hi": "मध्यम अनुकूलता"},
                "spoken": {"en": "Moderately adaptable; I handle normal changes with slight adjustment.", "hi": "मध्यम, थोड़े समय बाद शरीर अभ्यस्त हो जाता है।"},
                "value": "Madhyama"
            },
            {
                "id": "satmya_avara",
                "anchor": "C",
                "tier": "Avara",
                "label": {"en": "Easily Upset / Sick", "hi": "जल्दी बीमार पड़ना"},
                "spoken": {"en": "Poor adaptability; small changes in diet or weather quickly upset my health.", "hi": "कम अनुकूलता, पानी या मौसम बदलते ही जल्दी पेट खराब या जुकाम हो जाता है।"},
                "value": "Avara"
            }
        ]
    },
    {
        "id": "dash_vyayama",
        "index": 3,
        "domain": "vyayama_shakti",
        "prompt": {
            "en": "How does your body handle physical exertion like brisk walking, climbing stairs, or lifting?",
            "hi": "तेज चलने, सीढ़ियां चढ़ने या भारी काम करने पर आपका शरीर कैसा महसूस करता है?",
            "mr": "चालताना किंवा जिने चढताना तुमचे शरीर कसे वाटते?",
            "ta": "படிக்கட்டுகள் ஏறும் போது அல்லது வேலை செய்யும் போது உங்கள் உடல் எப்படி உணர்கிறது?",
            "te": "మెట్లు ఎక్కేటప్పుడు లేదా కష్టపడి పనిచేసేటప్పుడు మీ శరీరానికి ఎలా అనిపిస్తుంది?"
        },
        "options": [
            {
                "id": "vyayama_pravara",
                "anchor": "A",
                "tier": "Pravara",
                "label": {"en": "High Stamina", "hi": "उत्कृष्ट सहनशक्ति"},
                "spoken": {"en": "High stamina; I can do heavy physical work with minimal fatigue.", "hi": "उत्कृष्ट सहनशक्ति, भारी काम करने पर भी जल्दी थकान या सांस नहीं फूलती।"},
                "value": "Pravara"
            },
            {
                "id": "vyayama_madhyama",
                "anchor": "B",
                "tier": "Madhyama",
                "label": {"en": "Moderate Stamina", "hi": "सामान्य सहनशक्ति"},
                "spoken": {"en": "Moderate stamina; I manage daily physical activities comfortably.", "hi": "सामान्य सहनशक्ति, रोजमर्रा के काम आसानी से कर लेता हूं।"},
                "value": "Madhyama"
            },
            {
                "id": "vyayama_avara",
                "anchor": "C",
                "tier": "Avara",
                "label": {"en": "Low Stamina / Breathless", "hi": "जल्दी सांस फूलना / थकान"},
                "spoken": {"en": "Low stamina; even climbing one flight of stairs causes breathlessness.", "hi": "कम सहनशक्ति, एक मंजिल सीढ़ी चढ़ने या थोड़ा तेज चलने पर भी सांस फूलने लगती है।"},
                "value": "Avara"
            }
        ]
    }
]

def get_prakriti_question(index_0_based: int, lang: str = "en") -> Dict[str, Any]:
    """Retrieves localized Prakriti question payload with options."""
    if index_0_based < 0 or index_0_based >= len(PRAKRITI_QUESTIONS_12):
        return {}
    q = PRAKRITI_QUESTIONS_12[index_0_based]
    lang_key = lang.lower().split("-")[0]
    
    prompt_text = q["prompt"].get(lang_key, q["prompt"].get("en", ""))
    options = []
    for opt in q["options"]:
        label_text = opt["label"].get(lang_key, opt["label"].get("en", ""))
        spoken_text = opt["spoken"].get(lang_key, opt["spoken"].get("en", ""))
        options.append({
            "id": f"{q['id']}_{opt['anchor'].lower()}",
            "anchor": opt["anchor"],
            "dosha": opt["dosha"],
            "label": label_text,
            "spoken": spoken_text,
            "value": opt["value"]
        })
    
    return {
        "question_id": q["id"],
        "question_number": q["index"],
        "total_questions": 12,
        "pillar": q["pillar"],
        "trait": q["trait"],
        "text": prompt_text,
        "options": options
    }

def get_dashavidha_question(index_0_based: int, lang: str = "en") -> Dict[str, Any]:
    """Retrieves localized Dashavidha question payload with options."""
    if index_0_based < 0 or index_0_based >= len(DASHAVIDHA_QUESTIONS_3):
        return {}
    q = DASHAVIDHA_QUESTIONS_3[index_0_based]
    lang_key = lang.lower().split("-")[0]
    
    prompt_text = q["prompt"].get(lang_key, q["prompt"].get("en", ""))
    options = []
    for opt in q["options"]:
        label_text = opt["label"].get(lang_key, opt["label"].get("en", ""))
        spoken_text = opt["spoken"].get(lang_key, opt["spoken"].get("en", ""))
        options.append({
            "id": f"{q['id']}_{opt['anchor'].lower()}",
            "anchor": opt["anchor"],
            "tier": opt["tier"],
            "label": label_text,
            "spoken": spoken_text,
            "value": opt["value"]
        })
    
    return {
        "question_id": q["id"],
        "question_number": q["index"],
        "total_questions": 3,
        "domain": q["domain"],
        "text": prompt_text,
        "options": options
    }
