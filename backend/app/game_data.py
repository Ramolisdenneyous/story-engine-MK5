from .prompt_loader import load_narrative_lens, load_player_persona, load_system_prompt

VALASKA_PRESET_ID = "valaska"

VALASKA_SYSTEM_PROMPT = load_system_prompt("valaska_setting.md")

DEFAULT_IMAGE_FILE = "default-image.jpg"
MAP_IMAGE_FILE = "Valaska-Map.png"
ADVENTURE_SELECTION_IMAGE_FILE = "Adventure-selection.png"

PLAYER_ORDER = ["Joe", "Annie", "Tammey", "Rick", "Beau", "Sam", "Tom", "Jannet"]
CLASS_ORDER = ["Fighter", "Barbarian", "Rogue", "Ranger", "Paladin", "Cleric", "Druid", "Wizard"]

PLAYERS = {
    "Joe": {
        "player_id": "Joe",
        "name": "Joe",
        "archetype": "Orphan",
        "gender": "Male",
        "race": "Dwarf",
        "irl_job": "Social worker",
        "keywords": ["Protective", "Cautious", "Compassionate"],
        "display_text": load_player_persona("Joe"),
    },
    "Annie": {
        "player_id": "Annie",
        "name": "Annie",
        "archetype": "Hero",
        "gender": "Female",
        "race": "Elf",
        "irl_job": "Retail",
        "keywords": ["Bold", "Inspiring", "Dramatic"],
        "display_text": load_player_persona("Annie"),
    },
    "Tammey": {
        "player_id": "Tammey",
        "name": "Tammey",
        "archetype": "Caregiver",
        "gender": "Female",
        "race": "Half-Elf",
        "irl_job": "Nurse",
        "keywords": ["Supportive", "Steady", "Empathetic"],
        "display_text": load_player_persona("Tammey"),
    },
    "Rick": {
        "player_id": "Rick",
        "name": "Rick",
        "archetype": "Explorer",
        "gender": "Male",
        "race": "Human",
        "irl_job": "Park Ranger",
        "keywords": ["Curious", "Practical", "Observant"],
        "display_text": load_player_persona("Rick"),
    },
    "Beau": {
        "player_id": "Beau",
        "name": "Beau",
        "archetype": "Rebel",
        "gender": "non-binary",
        "race": "Elf",
        "irl_job": "Human Resources",
        "keywords": ["Defiant", "Clever", "Disruptive"],
        "display_text": load_player_persona("Beau"),
    },
    "Sam": {
        "player_id": "Sam",
        "name": "Sam",
        "archetype": "Jester",
        "gender": "Male",
        "race": "Gnome",
        "irl_job": "Customer Service",
        "keywords": ["Playful", "Expressive", "Unpredictable"],
        "display_text": load_player_persona("Sam"),
    },
    "Tom": {
        "player_id": "Tom",
        "name": "Tom",
        "archetype": "Magician",
        "gender": "Male",
        "race": "Human",
        "irl_job": "Engineer",
        "keywords": ["Analytical", "Strategic", "Precise"],
        "display_text": load_player_persona("Tom"),
    },
    "Jannet": {
        "player_id": "Jannet",
        "name": "Jannet",
        "archetype": "Ruler",
        "gender": "Female",
        "race": "Human",
        "irl_job": "School Principle",
        "keywords": ["Decisive", "Organized", "Authoritative"],
        "display_text": load_player_persona("Jannet"),
    },
}

CLASSES = {
    "Fighter": {
        "class_id": "Fighter",
        "name": "Fighter",
        "role": "Frontline combat specialist focused on weapon mastery, battlefield control, and durability.",
        "ability_scores": {"STR": 16, "DEX": 13, "CON": 15, "INT": 11, "WIS": 13, "CHA": 9},
        "hp_max": 12,
        "armor_class": 18,
        "speed": 30,
        "features": ["Fighting Style - Protection", "Second Wind"],
        "weapons": ["Longsword", "Handaxe"],
        "attack_profiles": [
            {"name": "Longsword", "attack_formula": "1d20+5", "damage_formula": "1d8+3", "damage_type": "slashing", "range": "melee"},
            {"name": "Handaxe", "attack_formula": "1d20+5", "damage_formula": "1d6+3", "damage_type": "slashing", "range": "melee or thrown"},
        ],
        "inventory": ["Chain mail", "Shield", "Longsword", "Handaxe x2", "Explorer's pack"],
        "doctrine": [
            "Hold the frontline.",
            "Protect weaker allies.",
            "Maintain control of enemy positioning.",
            "Sustain through longer fights.",
        ],
    },
    "Barbarian": {
        "class_id": "Barbarian",
        "name": "Barbarian",
        "role": "Shock trooper who absorbs damage and delivers devastating melee attacks.",
        "ability_scores": {"STR": 16, "DEX": 14, "CON": 15, "INT": 9, "WIS": 13, "CHA": 11},
        "hp_max": 15,
        "armor_class": 15,
        "speed": 30,
        "features": ["Rage", "Unarmored Defense"],
        "weapons": ["Greataxe", "Handaxes"],
        "attack_profiles": [
            {"name": "Greataxe", "attack_formula": "1d20+5", "damage_formula": "1d12+3", "damage_type": "slashing", "range": "melee"},
            {"name": "Handaxe", "attack_formula": "1d20+5", "damage_formula": "1d6+3", "damage_type": "slashing", "range": "melee or thrown"},
        ],
        "inventory": ["Greataxe", "Handaxe x2", "Explorer's pack", "Javelins x4"],
        "doctrine": ["Charge dangerous enemies.", "Draw enemy attention.", "Break enemy lines through aggression."],
    },
    "Rogue": {
        "class_id": "Rogue",
        "name": "Rogue",
        "role": "Precision striker specializing in stealth, positioning, and exploiting enemy vulnerabilities.",
        "ability_scores": {"STR": 9, "DEX": 16, "CON": 13, "INT": 15, "WIS": 11, "CHA": 14},
        "hp_max": 9,
        "armor_class": 15,
        "speed": 30,
        "features": ["Sneak Attack", "Expertise", "Thieves' Cant"],
        "weapons": ["Rapier", "Shortbow"],
        "attack_profiles": [
            {"name": "Rapier", "attack_formula": "1d20+5", "damage_formula": "1d8+3", "damage_type": "piercing", "range": "melee"},
            {"name": "Shortbow", "attack_formula": "1d20+5", "damage_formula": "1d6+3", "damage_type": "piercing", "range": "ranged"},
        ],
        "inventory": ["Leather armor", "Rapier", "Shortbow", "Arrows x20", "Thieves' tools", "Burglar pack"],
        "doctrine": ["Avoid direct confrontation.", "Strike distracted enemies.", "Exploit positioning."],
    },
    "Ranger": {
        "class_id": "Ranger",
        "name": "Ranger",
        "role": "Mobile tracker and ranged skirmisher who controls space through awareness and mobility.",
        "ability_scores": {"STR": 13, "DEX": 16, "CON": 14, "INT": 11, "WIS": 15, "CHA": 9},
        "hp_max": 12,
        "armor_class": 15,
        "speed": 30,
        "features": ["Favored Enemy", "Natural Explorer"],
        "weapons": ["Longbow", "Shortswords"],
        "attack_profiles": [
            {"name": "Longbow", "attack_formula": "1d20+5", "damage_formula": "1d8+3", "damage_type": "piercing", "range": "ranged"},
            {"name": "Shortsword", "attack_formula": "1d20+5", "damage_formula": "1d6+3", "damage_type": "piercing", "range": "melee"},
        ],
        "inventory": ["Scale mail", "Longbow", "Arrows x20", "Shortswords x2", "Explorer's pack"],
        "doctrine": ["Fight at range when possible.", "Use terrain advantage.", "Track enemies and scout."],
    },
    "Paladin": {
        "class_id": "Paladin",
        "name": "Paladin",
        "role": "Armored champion who protects allies and destroys powerful enemies through divine strength.",
        "ability_scores": {"STR": 16, "DEX": 11, "CON": 15, "INT": 9, "WIS": 13, "CHA": 14},
        "hp_max": 12,
        "armor_class": 18,
        "speed": 30,
        "features": ["Divine Sense", "Lay on Hands"],
        "weapons": ["Longsword", "Javelins"],
        "attack_profiles": [
            {"name": "Longsword", "attack_formula": "1d20+5", "damage_formula": "1d8+3", "damage_type": "slashing", "range": "melee"},
            {"name": "Javelin", "attack_formula": "1d20+5", "damage_formula": "1d6+3", "damage_type": "piercing", "range": "melee or thrown"},
        ],
        "inventory": ["Chain mail", "Shield", "Longsword", "Javelins x5", "Explorer's pack", "Holy symbol"],
        "doctrine": ["Stand beside the fighter in melee.", "Protect allies.", "Deliver decisive blows."],
    },
    "Cleric": {
        "class_id": "Cleric",
        "name": "Cleric",
        "role": "Divine support who heals allies, enhances party capability, and maintains battlefield stability.",
        "class_prompt_guidance": [
            "Use healing magic with restraint and purpose.",
            "As a default tactical rule, only use healing spells on allies who are below half of their maximum HP, unless the GM gives a specific reason to heal someone else.",
        ],
        "ability_scores": {"STR": 13, "DEX": 11, "CON": 14, "INT": 10, "WIS": 16, "CHA": 15},
        "hp_max": 10,
        "armor_class": 18,
        "speed": 30,
        "features": ["Spellcasting", "Divine Domain"],
        "weapons": ["Mace"],
        "attack_profiles": [
            {"name": "Mace", "attack_formula": "1d20+3", "damage_formula": "1d6+1", "damage_type": "bludgeoning", "range": "melee"},
        ],
        "inventory": ["Chain mail", "Shield", "Mace", "Holy symbol", "Priest pack"],
        "doctrine": ["Sustain the party.", "Heal injured allies.", "Maintain buffs."],
    },
    "Druid": {
        "class_id": "Druid",
        "name": "Druid",
        "role": "Nature caster who controls terrain and adapts between support, control, and offense.",
        "class_prompt_guidance": [
            "Use healing magic with restraint and purpose.",
            "As a default tactical rule, only use healing spells on allies who are below half of their maximum HP, unless the GM gives a specific reason to heal someone else.",
        ],
        "ability_scores": {"STR": 11, "DEX": 13, "CON": 14, "INT": 10, "WIS": 16, "CHA": 15},
        "hp_max": 10,
        "armor_class": 14,
        "speed": 30,
        "features": ["Spellcasting", "Druidic"],
        "weapons": ["Scimitar", "Quarterstaff"],
        "attack_profiles": [
            {"name": "Scimitar", "attack_formula": "1d20+3", "damage_formula": "1d6+1", "damage_type": "slashing", "range": "melee"},
            {"name": "Quarterstaff", "attack_formula": "1d20+2", "damage_formula": "1d6", "damage_type": "bludgeoning", "range": "melee"},
        ],
        "inventory": ["Hide armor", "Scimitar", "Druidic focus", "Explorer's pack"],
        "doctrine": ["Control battlefield space.", "Support allies.", "Disrupt enemy movement."],
    },
    "Wizard": {
        "class_id": "Wizard",
        "name": "Wizard",
        "role": "Arcane strategist who manipulates the battlefield through versatile spells and tactical control.",
        "ability_scores": {"STR": 9, "DEX": 14, "CON": 13, "INT": 16, "WIS": 12, "CHA": 11},
        "hp_max": 8,
        "armor_class": 12,
        "speed": 30,
        "features": ["Spellcasting", "Arcane Recovery"],
        "weapons": ["Quarterstaff"],
        "attack_profiles": [
            {"name": "Quarterstaff", "attack_formula": "1d20+1", "damage_formula": "1d6-1", "damage_type": "bludgeoning", "range": "melee"},
        ],
        "inventory": ["Spellbook", "Quarterstaff", "Component pouch", "Scholar pack"],
        "doctrine": ["Avoid direct melee combat.", "Control the battlefield.", "Use spells strategically."],
    },
}

MONSTERS = {
    "Animated Armor": {"monster_id": "Animated Armor", "ac": 18, "hp": 33, "attack_bonus": 4, "attack_text": "Slam 1d6+2"},
    "Bandit": {"monster_id": "Bandit", "ac": 12, "hp": 11, "attack_bonus": 3, "attack_text": "Scimitar 1d6+1 or Light Crossbow 1d8+1"},
    "Bandit Captain": {"monster_id": "Bandit Captain", "ac": 15, "hp": 65, "attack_bonus": 5, "attack_text": "Scimitar 1d6+3 (multiattack)"},
    "Berserker": {"monster_id": "Berserker", "ac": 13, "hp": 67, "attack_bonus": 5, "attack_text": "Greataxe 1d12+3"},
    "Ghast": {"monster_id": "Ghast", "ac": 13, "hp": 36, "attack_bonus": 5, "attack_text": "Bite 2d8+3, Claws 2d6+3 + paralysis"},
    "Giant Boar": {"monster_id": "Giant Boar", "ac": 12, "hp": 42, "attack_bonus": 5, "attack_text": "Tusk 2d6+3"},
    "Gibbering Mouther": {"monster_id": "Gibbering Mouther", "ac": 9, "hp": 67, "attack_bonus": 2, "attack_text": "Bite 5d6"},
    "Gray Ooze": {"monster_id": "Gray Ooze", "ac": 8, "hp": 22, "attack_bonus": 3, "attack_text": "Pseudopod 1d6+1 + acid"},
    "Guard": {"monster_id": "Guard", "ac": 16, "hp": 11, "attack_bonus": 3, "attack_text": "Spear 1d6+1"},
    "Mastiff": {"monster_id": "Mastiff", "ac": 12, "hp": 5, "attack_bonus": 3, "attack_text": "Bite 1d6+1 + knock prone"},
    "Minotaur Skeleton": {"monster_id": "Minotaur Skeleton", "ac": 12, "hp": 67, "attack_bonus": 6, "attack_text": "Greataxe 2d12+4"},
    "Orc": {"monster_id": "Orc", "ac": 13, "hp": 15, "attack_bonus": 5, "attack_text": "Greataxe 1d12+3"},
    "Priest": {"monster_id": "Priest", "ac": 13, "hp": 27, "attack_bonus": 2, "attack_text": "Mace 1d6 | Spellcaster"},
    "Scout": {"monster_id": "Scout", "ac": 13, "hp": 16, "attack_bonus": 4, "attack_text": "Shortsword 1d6+2 or Longbow 1d8+2"},
    "Shadow": {"monster_id": "Shadow", "ac": 12, "hp": 16, "attack_bonus": 4, "attack_text": "Strength Drain 2d6"},
    "Skeleton": {"monster_id": "Skeleton", "ac": 13, "hp": 13, "attack_bonus": 4, "attack_text": "Shortsword 1d6+2 or Shortbow 1d6+2"},
    "Swarm of Insects": {"monster_id": "Swarm of Insects", "ac": 12, "hp": 22, "attack_bonus": 3, "attack_text": "Swarm Bite 4d4"},
    "Thug": {"monster_id": "Thug", "ac": 11, "hp": 32, "attack_bonus": 4, "attack_text": "Mace 1d6+2 (multiattack)"},
    "Warhorse": {"monster_id": "Warhorse", "ac": 11, "hp": 19, "attack_bonus": 6, "attack_text": "Hooves 2d6+4"},
    "Warhorse Skeleton": {"monster_id": "Warhorse Skeleton", "ac": 13, "hp": 22, "attack_bonus": 6, "attack_text": "Hooves 2d6+4"},
    "Zombie": {"monster_id": "Zombie", "ac": 8, "hp": 22, "attack_bonus": 3, "attack_text": "Slam 1d6+1"},
}

MONSTER_CATALOG = {monster_id: {**monster} for monster_id, monster in MONSTERS.items()}

ADVENTURE_MAP_FILES = {
    "icebane-castle": "Adventure-icebane-castle.png",
    "east-marsh-raid": "Adventure-east-marsh-raid.png",
    "telas-wagons": "Adventure-telas-wagons.jpg",
    "old-people-barrow": "Adventure-old-people-barrow.png",
    "collecting-taxes": "Adventure-collecting-taxes.jpg",
    "endless-glacier-undead": "Adventure-endless-glacier-undead.png",
}

ADVENTURE_LOCATIONS = {
    "icebane-castle": [
        {
            "id": "loc-1",
            "number": 1,
            "title": "The Thaw Gate",
            "description": "The southern wall of Icebane Castle has partially collapsed, leaving a jagged breach where stone and ice have sheared apart. Meltwater drips steadily from exposed beams, forming slick patches across the uneven ground. The remnants of a heavy portcullis lie twisted nearby, half-frozen into the earth. Faint drafts of cold air still flow outward from deeper within, carrying the scent of ancient stone and something long sealed.",
            "x_pct": 26.0,
            "y_pct": 18.0,
        },
        {
            "id": "loc-2",
            "number": 2,
            "title": "The Frost-Choked Hall",
            "description": "A long corridor stretches inward, its vaulted ceiling fractured but still standing. Thick veins of ice crawl along the walls, preserving old banners that hang stiff and colorless. Sections of the floor remain frozen solid, while others have thawed into shallow pools. Sound carries strangely here, each step echoes too far, as if the hall remembers movement.",
            "x_pct": 51.0,
            "y_pct": 40.0,
        },
        {
            "id": "loc-3",
            "number": 3,
            "title": "The Collapsed Barracks",
            "description": "This chamber was once a soldiers' quarters, now partially caved in. Wooden bunks lie splintered beneath fallen stone, and rusted weapons are scattered among the debris. One section of the ceiling has opened to the sky, allowing pale light to filter in. Snow has drifted into the room, forming uneven mounds across the wreckage.",
            "x_pct": 21.0,
            "y_pct": 56.0,
        },
        {
            "id": "loc-4",
            "number": 4,
            "title": "The Melted Armory Vault",
            "description": "A reinforced stone chamber sits behind a warped iron door that hangs ajar. Inside, racks of weapons and armor are fused together by ice and time. Some sections have thawed just enough to reveal workable gear, while others remain encased. The air here is colder than outside, as if the room resists the thaw.",
            "x_pct": 77.0,
            "y_pct": 58.0,
        },
        {
            "id": "loc-5",
            "number": 5,
            "title": "The Subterranean Reliquary",
            "description": "A narrow stairwell descends into a partially exposed lower chamber. The room below is circular, lined with alcoves that once held relics or offerings. Many have been disturbed, some empty, others cracked open. Meltwater drips from above, forming a shallow reflective pool at the center. The space feels older than the rest of the castle.",
            "x_pct": 48.0,
            "y_pct": 62.0,
        },
        {
            "id": "loc-6",
            "number": 6,
            "title": "The Fractured Throne Room",
            "description": "At the heart of the ruins lies a grand hall split by a massive fissure running through the floor. The throne itself remains on a raised dais, partially intact but coated in frost. One side of the room has sunk slightly, creating a dangerous slope toward the crack. Light filters in through broken high windows, illuminating drifting ice particles in the air.",
            "x_pct": 76.0,
            "y_pct": 16.0,
        },
    ],
    "east-marsh-raid": [
        {
            "id": "loc-1",
            "number": 1,
            "title": "The Blackwater Approach",
            "description": "A stretch of ankle-deep marshwater choked with reeds and black mud. The ground shifts underfoot, and faint ripples betray movement long before sound carries. Rotting tree stumps jut like broken teeth from the water.",
            "x_pct": 17.0,
            "y_pct": 21.0,
        },
        {
            "id": "loc-2",
            "number": 2,
            "title": "The Watcher's Rise",
            "description": "A small mound of firmer ground rises above the marsh, topped with a crude wooden platform lashed together with rope and bone charms.",
            "x_pct": 44.0,
            "y_pct": 19.0,
        },
        {
            "id": "loc-3",
            "number": 3,
            "title": "The Outer Camp Ring",
            "description": "A loose ring of tents, drying racks, and tethered animals surrounds the main encampment. Mud paths connect everything in uneven loops.",
            "x_pct": 75.0,
            "y_pct": 29.0,
        },
        {
            "id": "loc-4",
            "number": 4,
            "title": "The Supply Cache Pit",
            "description": "A partially dug-out pit reinforced with timber and covered by stretched hides. Inside are crates, barrels, and bundled goods taken from raids.",
            "x_pct": 35.0,
            "y_pct": 46.0,
        },
        {
            "id": "loc-5",
            "number": 5,
            "title": "The War Leader's Tent",
            "description": "A larger, reinforced tent marked with trophies, bones, shields, and banners taken from prior victims. The ground here is more stable, deliberately chosen.",
            "x_pct": 80.0,
            "y_pct": 67.0,
        },
        {
            "id": "loc-6",
            "number": 6,
            "title": "The Fog-Choked Escape Channel",
            "description": "A narrow waterway cutting through the marsh, partially concealed by thick rolling fog. Small boats or makeshift rafts are hidden nearby.",
            "x_pct": 41.0,
            "y_pct": 83.0,
        },
    ],
    "telas-wagons": [
        {
            "id": "loc-1",
            "number": 1,
            "title": "The Western Tundra Stretch",
            "description": "Beyond the river, the land opens into a wide, wind-scoured tundra where the road fades into faint tracks. Sparse black pines dot the horizon, and the sky stretches endlessly overhead. Wind carries loose snow across the ground, making distance hard to judge and movement feel smaller than it is. There is no cover and nowhere to hide. The convoy is fully visible, and anything watching from afar would see it long before being seen in return.",
            "x_pct": 63.0,
            "y_pct": 56.0,
        },
        {
            "id": "loc-2",
            "number": 2,
            "title": "The Barrow Approach",
            "description": "The road skirts the Old People's Barrow, a low mound of ancient stone half-buried in frost. Faded carvings line its exposed slabs, and a thin fog clings to the ground around it. Sound dulls unnaturally here, and even the animals grow uneasy as the convoy passes. The presence of the barrow presses in from the side, making the road feel tighter and heavier, as if something beneath the earth is aware of passing movement.",
            "x_pct": 55.0,
            "y_pct": 39.0,
        },
        {
            "id": "loc-3",
            "number": 3,
            "title": "The Narrow Pass",
            "description": "The King's Way compresses between two rising ridgelines, forcing the wagons into a tight formation. Loose rock and uneven ground make footing uncertain, while brush and stone along the slopes provide intermittent cover. The sky narrows overhead, and sound echoes unpredictably between the walls. It is a natural choke point, movement is controlled, visibility is limited, and any disruption quickly affects the entire convoy.",
            "x_pct": 52.0,
            "y_pct": 31.0,
        },
        {
            "id": "loc-4",
            "number": 4,
            "title": "The Whiteout Flats",
            "description": "The land flattens into a featureless expanse where snow and sky blur together, erasing the road entirely. When the wind rises, visibility collapses to only a few paces, and direction becomes uncertain. Wagons slow as wheels grind against hidden ice beneath the snow. Progress here is difficult to maintain, cohesion can break easily, and even small delays compound quickly in the storm.",
            "x_pct": 46.0,
            "y_pct": 22.0,
        },
        {
            "id": "loc-5",
            "number": 5,
            "title": "Silverrun Crossing",
            "description": "The King's Way narrows at the Silverrun River, where a frost-rimed wooden bridge spans dark, fast-moving water. One side of the road has collapsed into a slushy rut, forcing wagons to pass single file over unstable ground. Ice chunks scrape beneath the bridge supports, and every creak of wood echoes sharply in the cold air. The crossing feels exposed and precarious, movement is slow, footing is unreliable, and a single mistake could delay the entire convoy or damage a wagon.",
            "x_pct": 41.0,
            "y_pct": 16.0,
        },
        {
            "id": "loc-6",
            "number": 6,
            "title": "The Glockstead Approach",
            "description": "The road descends toward Glockstead, its wooden walls and watchtowers just visible in the distance. The terrain becomes more stable, with boundary markers and fencing appearing along the roadside. Smoke rises from within the settlement, signaling safety that is close but not yet secured. The final stretch feels tense despite the proximity, open ground still leaves the convoy vulnerable, and any last disruption could jeopardize the delivery before reaching the gates.",
            "x_pct": 14.0,
            "y_pct": 11.0,
        },
    ],
    "old-people-barrow": [
        {
            "id": "loc-1",
            "number": 1,
            "title": "The Frost-Cleft Entrance",
            "description": "A collapsed section of the burial mound reveals a narrow, sloping passage descending into darkness. Stone blocks jut at odd angles where the structure has shifted, and thin ice clings to the walls. Faint carvings, worn nearly smooth, line the entry, depicting figures in procession. Cold air seeps outward from below, carrying a dry, ancient stillness that feels undisturbed for generations.",
            "x_pct": 30.0,
            "y_pct": 15.0,
        },
        {
            "id": "loc-2",
            "number": 2,
            "title": "The Hall of Echoes",
            "description": "A long, rectangular chamber stretches ahead, supported by squat stone pillars. The floor is uneven, with cracked flagstones and shallow depressions filled with frost. Every sound carries unnaturally far, repeating in soft, delayed echoes. The silence between sounds feels heavier than the echoes themselves, as if the chamber listens as much as it reflects.",
            "x_pct": 22.0,
            "y_pct": 40.0,
        },
        {
            "id": "loc-3",
            "number": 3,
            "title": "The Ancestral Gallery",
            "description": "Stone alcoves line the walls, each holding skeletal remains wrapped in decayed burial cloth. Some are intact, others collapsed into dust. Offerings, rusted weapons, cracked pottery, and fragments of jewelry rest beside them. A faint, lingering presence hangs here, as though the dead are aware of intrusion but have not yet decided how to respond.",
            "x_pct": 15.0,
            "y_pct": 62.0,
        },
        {
            "id": "loc-4",
            "number": 4,
            "title": "The Sealed Door",
            "description": "A heavy stone door blocks the path forward, its surface carved with interlocking symbols worn by time. The seams are tight, but hairline cracks suggest the seal has weakened. Frost gathers thickest here, creeping outward from the edges. The air beyond the door feels colder still, sharper, older, and more dangerous than the chambers behind.",
            "x_pct": 53.0,
            "y_pct": 26.0,
        },
        {
            "id": "loc-5",
            "number": 5,
            "title": "The Burial Vault",
            "description": "A circular chamber lies beyond, dominated by a central stone sarcophagus raised on a low platform. The walls are etched with spiraling carvings that converge toward the tomb, telling a story too eroded to fully read. Scattered relics lie around the base, some intact, others broken. This is the heart of the barrow, and the weight of its purpose is unmistakable.",
            "x_pct": 55.0,
            "y_pct": 49.0,
        },
        {
            "id": "loc-6",
            "number": 6,
            "title": "The Fractured Escape Tunnel",
            "description": "A narrow, partially collapsed passage branches away from the vault, slanting upward toward faint light. Loose stone and packed earth choke parts of the tunnel, forcing careful movement. Cold air flows unevenly through it, suggesting unstable openings above. The path offers escape but not safety, and the barrow does not easily release what enters it.",
            "x_pct": 52.0,
            "y_pct": 75.0,
        },
    ],
    "endless-glacier-undead": [
        {
            "id": "loc-1",
            "number": 1,
            "title": "Everflame Abbey",
            "description": "The abbey stands as a rare bastion of warmth against the glacier's edge, its ever-burning brazier casting flickering orange light across frost-covered stone. Priests move quietly, their voices low, their eyes drawn often toward the ice fields beyond. Father Balgart receives the party with urgency but restraint. Reports speak of shapes moving across the glacier at night, too many, too coordinated. Whatever stirs the dead is not recent, and not mindless.",
            "x_pct": 48.0,
            "y_pct": 72.0,
        },
        {
            "id": "loc-2",
            "number": 2,
            "title": "The Frozen Pilgrim's Path",
            "description": "A narrow, half-buried trail winds from the abbey onto the glacier, marked by old stone cairns barely visible beneath layers of snow. The wind howls across open ice, carrying whispers that almost sound like distant voices. Scattered along the path are frozen remains, pilgrims, travelers, or perhaps earlier attempts to investigate the disturbance. Some lie undisturbed. Others show signs of movement. The path is exposed and silent, offering no cover and no certainty of what lies ahead.",
            "x_pct": 37.0,
            "y_pct": 59.0,
        },
        {
            "id": "loc-3",
            "number": 3,
            "title": "The Shattered Ice Field",
            "description": "The glacier fractures into a maze of jagged ice ridges and deep crevasses, forcing careful movement between unstable ground. Cracks echo beneath each step, and distant collapses send tremors through the ice. Here, the dead begin to appear more frequently, some half-trapped in the ice, others wandering freely between the ridges. Their movements are slow, but purposeful. The terrain itself becomes a threat, turning every step into a risk as the boundary between solid ground and deadly fall blurs.",
            "x_pct": 47.0,
            "y_pct": 39.0,
        },
        {
            "id": "loc-4",
            "number": 4,
            "title": "The Burial Drift",
            "description": "A wide depression in the glacier where snow has collected into deep, wind-packed drifts. Beneath the surface, shapes can be seen, dozens of bodies frozen just below the ice. The air here is unnaturally still. Sound seems dampened, as if the snow itself absorbs it. Occasionally, the surface shifts. This place feels less like a battlefield and more like a mass grave waiting to wake.",
            "x_pct": 63.0,
            "y_pct": 47.0,
        },
        {
            "id": "loc-5",
            "number": 5,
            "title": "The Black Ice Scar",
            "description": "A long, unnatural fissure cuts across the glacier, its surface dark and glass-like rather than white. The ice here reflects distorted shapes, and movement within it suggests something beneath the surface. The undead are more aggressive here, drawn toward the fissure as if responding to a silent call. There is a sense of convergence, this is not random wandering. The dead are gathering.",
            "x_pct": 76.0,
            "y_pct": 66.0,
        },
        {
            "id": "loc-6",
            "number": 6,
            "title": "The Heart of the Glacier",
            "description": "At the far reach of the disturbance lies a partially exposed ruin, buried deep within the ice. Ancient stone protrudes through frozen layers, marked with symbols worn nearly smooth by time. The cold here is sharper, biting deeper, unnatural. This is the source. Whether it is a buried battlefield, a forgotten ritual site, or something older, it exerts a pull over the dead, binding them, directing them, refusing to let them rest. To end the disturbance, something here must be confronted, broken, or put to rest.",
            "x_pct": 88.0,
            "y_pct": 18.0,
        },
    ],
    "collecting-taxes": [
        {
            "id": "loc-1",
            "number": 1,
            "title": "Narrow Bridge Over the Silverrun",
            "description": "The King's Way crosses the Silverrun River over a weathered stone bridge just wide enough for a single wagon at a time. Moss clings to the stones, and the water below churns fast and cold, making any fall potentially lethal. The surrounding terrain rises slightly on both sides, with broken rock and sparse pine offering excellent cover for hidden attackers. This is a perfect choke point. A single blocked wagon halts all traffic, forcing caravans to negotiate or panic. The party can demand payment under threat of cutting the lead horse loose or tipping cargo into the river. Violence here is quick and decisive, but risky. If things go wrong, enemies can be driven into the river or the players can.",
            "x_pct": 38.0,
            "y_pct": 18.0,
        },
        {
            "id": "loc-2",
            "number": 2,
            "title": "The Burned-Out Waystation",
            "description": "A half-collapsed roadside shelter sits just off the King's Way, its roof charred and walls blackened from an old fire. Travelers still stop here out of habit, drawn by the illusion of safety and the presence of a well that still produces clean water. The surrounding tree line is dense enough to conceal multiple attackers. This location favors deception. The party can pose as survivors, guards, or fellow travelers before springing the trap. Negotiation is easier here, but so is betrayal. If handled well, the party can extract coin or goods without a fight. If mishandled, the confined space turns into a chaotic skirmish with limited escape routes.",
            "x_pct": 53.0,
            "y_pct": 26.0,
        },
        {
            "id": "loc-3",
            "number": 3,
            "title": "The Fog-Choked Low Road",
            "description": "A low stretch of the King's Way dips into marshy ground where cold air settles and thick fog lingers even during the day. Visibility drops to a few yards, and the road becomes soft and uneven, slowing wagons and separating caravan elements as they struggle through the muck. Ambushes here are disorienting and psychological. Voices echo strangely, shapes move in the mist, and it's easy to isolate targets. The party can strike from multiple directions, creating the illusion of a larger force. This is an ideal place to pressure caravans into surrender if the party plays it right.",
            "x_pct": 69.0,
            "y_pct": 46.0,
        },
        {
            "id": "loc-4",
            "number": 4,
            "title": "The High Ridge Overlook",
            "description": "The King's Way winds along the base of a rocky ridge, with a steep incline leading up to a natural overlook above the road. From this vantage point, the entire stretch below is visible, and loose stones and debris can be easily dislodged. This is a control point rather than a trap. The party can halt caravans from above, using height and threat instead of immediate violence. A rockslide or even the suggestion of one can force compliance. However, ranged retaliation becomes a real threat here, and once the party commits, there's little cover on the ridge itself.",
            "x_pct": 27.0,
            "y_pct": 47.0,
        },
        {
            "id": "loc-5",
            "number": 5,
            "title": "The Wagon Bottleneck at King's Valley Pass",
            "description": "The road narrows sharply as it enters King's Valley Pass, where sheer cliffs press in from both sides. Wagons must slow to navigate the tight turns, often bunching together as drivers wait their turn to pass through the narrowest sections. This is the most traditional ambush site, tight quarters, limited movement, and nowhere to run. The party can strike the middle of a convoy, trapping both front and rear. It's an ideal place for a decisive, forceful extraction of goods. But it's also the most dangerous. If resistance forms, the party risks being pinned in the same choke point they created.",
            "x_pct": 71.0,
            "y_pct": 82.0,
        },
        {
            "id": "loc-6",
            "number": 6,
            "title": "The Open Road Near Flames' Rest Inn",
            "description": "A short distance from the Flames' Rest Inn, the King's Way opens into a relatively safe and well-traveled stretch. Smoke from the inn's hearth is often visible in the distance, and caravans tend to relax as they approach, believing danger has passed. This location tests restraint. Attacking here risks drawing attention from the inn or other travelers, potentially escalating consequences beyond the immediate encounter. However, it's also where caravans are least guarded. The party can attempt a fast, clean interception or manipulate travelers into voluntary payment under the guise of protection.",
            "x_pct": 86.0,
            "y_pct": 17.0,
        },
    ],
}

ADVENTURES = {
    "icebane-castle": {
        "adventure_id": "icebane-castle",
        "title": "Treasure Hunting the Ruins of Icebane Castle",
        "description": (
            "The long-frozen fortress of Icebane Castle has begun to thaw along its southern face, revealing "
            "collapsed vaults and exposed relic chambers long sealed by ice. Local rumors speak of ancestral "
            "artifacts and forgotten war spoils buried beneath centuries of frost and ruin. Competing interests may "
            "already be moving toward the site. Discretion and speed are advised."
        ),
        "objectives": [
            {"id": "obj-1", "description": "Locate and recover at least one significant artifact or treasure from within the castle ruins.", "status": "pending"},
            {"id": "obj-2", "description": "Survive environmental hazards and any hostile forces occupying the site.", "status": "pending"},
            {"id": "obj-3", "description": "Exit the ruins with proof of recovery.", "status": "pending"},
        ],
        "monsters": ["Gray Ooze", "Orc", "Scout", "Shadow", "Thug", "Swarm of Insects"],
    },
    "east-marsh-raid": {
        "adventure_id": "east-marsh-raid",
        "title": "Midnight Raid of the East Marsh Orcs",
        "description": (
            "Scouting reports confirm that a band of orcs has established a temporary encampment in the East Marsh, "
            "staging raids against nearby trade routes. A covert nighttime strike could disrupt their operations and "
            "weaken future assaults. Stealth and coordination will determine success."
        ),
        "objectives": [
            {"id": "obj-1", "description": "Infiltrate or approach the orc encampment under cover of darkness.", "status": "pending"},
            {"id": "obj-2", "description": "Neutralize the war leader, supply cache, or primary threat source.", "status": "pending"},
            {"id": "obj-3", "description": "Withdraw before dawn with minimal civilian casualties or collateral damage.", "status": "pending"},
        ],
        "monsters": ["Orc", "Scout", "Thug", "Bandit Captain", "Giant Boar"],
    },
    "telas-wagons": {
        "adventure_id": "telas-wagons",
        "title": "Escort of the Telos Supply Wagons along the King's Way",
        "description": (
            "A caravan carrying critical provisions for the frontier settlement of Moosehearth must travel the King's "
            "Way to Glockstead, a route increasingly plagued by bandits and winter storms. The wagons are slow, "
            "vulnerable, and essential. Reliable escorts are needed to ensure safe delivery."
        ),
        "objectives": [
            {"id": "obj-1", "description": "Protect the supply wagons from hostile attacks or sabotage during transit.", "status": "pending"},
            {"id": "obj-2", "description": "Resolve at least one major complication during the journey.", "status": "pending"},
            {"id": "obj-3", "description": "Deliver the majority of supplies safely from Moosehearth to Glockstead.", "status": "pending"},
        ],
        "monsters": ["Scout", "Thug", "Bandit", "Bandit Captain", "Berserker"],
    },
    "old-people-barrow": {
        "adventure_id": "old-people-barrow",
        "title": "Tombrobbing the Old-People's Barrow",
        "description": (
            "An ancient burial mound known as the Old-People's Barrow has been partially unearthed by shifting frost. "
            "Local superstition warns against disturbing it, yet scholars and collectors believe it may contain relics "
            "from a pre-kingdom civilization. Enter at your own risk."
        ),
        "objectives": [
            {"id": "obj-1", "description": "Successfully enter and navigate the interior chambers of the barrow.", "status": "pending"},
            {"id": "obj-2", "description": "Recover at least one relic of historical or monetary value.", "status": "pending"},
            {"id": "obj-3", "description": "Escape the barrow alive, resolving any awakened guardians or curses.", "status": "pending"},
        ],
        "monsters": ["Zombie", "Shadow", "Animated Armor", "Skeleton", "Gibbering Mouther"],
    },
    "collecting-taxes": {
        "adventure_id": "collecting-taxes",
        "title": "Collecting 'Taxes' Along the King's Road",
        "description": (
            "Comely triads men pass along The King's Way road without paying their proper taxes to the local baron. "
            "Your mission is to make sure those taxes get paid, and who is to say if the gold really finds its way to "
            "the local baron or not."
        ),
        "objectives": [
            {"id": "obj-1", "description": "Engage with at least three trade convoys along The King's Way.", "status": "pending"},
            {"id": "obj-2", "description": "Secure agreed tribute in coin, goods, or binding contracts.", "status": "pending"},
            {"id": "obj-3", "description": "Maintain enough order that trade along the road continues without collapse.", "status": "pending"},
        ],
        "monsters": ["Bandit", "Guard", "Mastiff", "Warhorse", "Priest"],
    },
    "endless-glacier-undead": {
        "adventure_id": "endless-glacier-undead",
        "title": "Putting to Rest the Undead Along the Endless Glacier",
        "description": (
            "Travelers report restless dead wandering the ice fields of the Endless Glacier, drawn perhaps by "
            "forgotten battlefields beneath the snow. These undead threaten caravans and isolated outposts. A "
            "cleansing expedition is required to end the disturbance and restore safe passage."
        ),
        "objectives": [
            {"id": "obj-1", "description": "Report to Father Balgart at the Everflame Abbey.", "status": "pending"},
            {"id": "obj-2", "description": "Defeat or lay to rest the primary undead threat.", "status": "pending"},
            {"id": "obj-3", "description": "Ensure the glacier region is safe for travel.", "status": "pending"},
        ],
        "monsters": ["Warhorse Skeleton", "Zombie", "Skeleton", "Minotaur Skeleton", "Ghast"],
    },
}

PLAYER_NARRATIVE_LENSES = {
    "Joe": load_narrative_lens("Joe"),
    "Annie": load_narrative_lens("Annie"),
    "Tammey": load_narrative_lens("Tammey"),
    "Rick": load_narrative_lens("Rick"),
    "Beau": load_narrative_lens("Beau"),
    "Sam": load_narrative_lens("Sam"),
    "Tom": load_narrative_lens("Tom"),
    "Jannet": load_narrative_lens("Jannet"),
}

NARRATIVE_BASE_PROMPT = load_system_prompt("narrative_base.md")

for monster_id, monster in MONSTERS.items():
    monster["image_file"] = f"Monster-{monster_id}.webp"
    MONSTER_CATALOG[monster_id]["image_file"] = monster["image_file"]

for adventure_id, filename in ADVENTURE_MAP_FILES.items():
    ADVENTURES[adventure_id]["map_image_file"] = filename
    ADVENTURES[adventure_id]["locations"] = ADVENTURE_LOCATIONS[adventure_id]
