import base64
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.orm import Session

from .config import settings
from .game_data import MONSTER_CATALOG, NARRATIVE_BASE_PROMPT, PLAYER_NARRATIVE_LENSES, VALASKA_SYSTEM_PROMPT
from .models import LLMArtifact
from .prompt_loader import load_system_prompt

logger = logging.getLogger("uvicorn.error")
PSEUDO_TOOL_CALL_RE = re.compile(
    r"(?:functions\.)?(?:resolve_action|update_inventory|roll_dice|roll_dice_batch|update_combat_state)\s*(?:\(|:)",
    re.IGNORECASE,
)
UNRESOLVED_COMBAT_ACTION_RE = re.compile(
    r"(\*rolls?\*|attack lands|lands with a total of|deals?\s+\d+\s+(?:points?\s+of\s+)?damage|heals?\s+\d+\s*(?:hp|hit points)|\b(?:misses|hits|strikes|slashes|swings|charges|gore(?:s)?|bites?|slams?|casts?)\b)",
    re.IGNORECASE,
)
DECLARED_BUT_UNROLLED_ACTION_RE = re.compile(
    r"("
    r"\b(?:roll|rolling)\s+for\s+(?:an?\s+)?(?:attack|damage|healing?|initiative|check|save)\b|"
    r"\b(?:roll|rolling)\s+for\s+(?:a\s+|an\s+)?(?:[a-z]+(?:\s+[a-z]+){0,2}\s+check)\b|"
    r"\bi\s+(?:roll|am\s+rolling)\s+to\s+(?:attack|hit|damage|heal)\b|"
    r"\bi(?:'ll| will)\s+roll\s+(?:for\s+)?(?:a\s+|an\s+)?(?:[a-z]+(?:\s+[a-z]+){0,2}\s+check|attack|damage|healing?|initiative|save)\b|"
    r"\bi(?:'ll| will)\s+(?:make|take|attempt|use|cast)?\s*(?:my\s+)?(?:attack|swing|shot|heal|spell|skill check)\b|"
    r"\bi(?:['’]ll| will)\s+cast\s+[a-z][a-z\s'-]{1,40}\b|"
    r"\bi attack\b|"
    r"\bi(?:'m| am)\s+going to attack\b|"
    r"\bi\s+(?:swing|strike|slash|shoot|fire|cast)\b|"
    r"\bi\s+draw\s+back\s+(?:my\s+)?(?:bow|string|arrow|arrows)\b|"
    r"\bi\s+(?:loose|release|let\s+loose)\s+(?:an?\s+)?(?:arrow|arrows|shot)\b|"
    r"\bhere goes nothing\b|"
    r"\blet'?s see if i can hit\b"
    r")",
    re.IGNORECASE,
)
ATTACK_RESOLUTION_RE = re.compile(
    r"(attack lands|lands with a total of|go(?:es)? wide|fly wide|flies wide|sail(?:s)? wide|aim (?:is|was) off|"
    r"\b(?:misses|hits|strikes|slashes|swings|shoots?|fires?|looses?|releases?|charges|gore(?:s)?|bites?|slams?)\b)",
    re.IGNORECASE,
)
MISS_RESOLUTION_RE = re.compile(
    r"(\bmiss(?:es|ed)?\b|go(?:es)? wide|fly wide|flies wide|sail(?:s)? wide|aim (?:is|was) off|does\s+not\s+(?:hit|land)|fails?\s+to\s+hit|fails?\s+to\s+land|connects?\s+with\s+empty\s+air)",
    re.IGNORECASE,
)
STATE_RESOLUTION_RE = re.compile(
    r"(deals?\s+\d+\s+(?:points?\s+of\s+)?damage|dealing\s+\d+\s+(?:points?\s+of\s+)?damage|"
    r"heals?\s+\d+\s*(?:hp|hit points)|healing\s+\d+\s*(?:hp|hit points)|"
    r"takes\s+\d+\s+(?:points?\s+of\s+)?damage|recovers?\s+\d+\s*(?:hp|hit points)|"
    r"bringing\s+\w+['’]s?\s+(?:current\s+)?hp\s+down\s+to\s+\d+)",
    re.IGNORECASE,
)
PROCESS_LEAK_RE = re.compile(
    r"(now,\s+i\s+will\s+update|i\s+will\s+update\s+\w+['’]s?\s+combat\s+state|update\s+\w+['’]s?\s+combat\s+state)",
    re.IGNORECASE,
)
FAKE_TOOL_PROCESS_RE = re.compile(
    r"(now,\s+i(?:['’]ll| will)\s+resolve|calling\s+for\s+[a-z][a-z\s'-]{1,40})",
    re.IGNORECASE,
)
ATTACK_RESOLUTION_MARKER_PREFIX = "ATTACK_RESOLUTION:"


@dataclass
class GenerationResult:
    content: str
    pending_state_changes: list[dict[str, Any]]
    pending_roll_results: list[dict[str, Any]]
    pending_action_results: list[dict[str, Any]]
    party_requests: list[dict[str, Any]] | None = None
    continuation: dict[str, Any] | None = None

    @property
    def narration_pending(self) -> bool:
        return self.continuation is not None


def _has_effective_state_change(pending_state_changes: list[dict[str, Any]]) -> bool:
    for payload in pending_state_changes:
        for target in payload.get("targets", []):
            for change in target.get("changes", []):
                kind = change.get("kind")
                amount = int(change.get("amount", 0) or 0)
                value = change.get("value", "")
                if kind in {"damage", "healing"} and amount > 0:
                    return True
                if kind in {"status_add", "status_remove", "inventory_add", "inventory_remove"} and value:
                    return True
    return False

CHARACTER_SYSTEM_PROMPT = load_system_prompt("player_base.md")
SUMMARY_SYSTEM_PROMPT = load_system_prompt("summary_agent.md")
AGENT0_SYSTEM_PROMPT = f"{load_system_prompt('world_lock_agent.md')}\n\n{VALASKA_SYSTEM_PROMPT}"
IMAGE_SYSTEM_PROMPT = load_system_prompt("image_agent.md")
OPPOSITION_SYSTEM_PROMPT = load_system_prompt("opposition_agent.md")

TTS_PLAYER_VOICE_ALIASES = {
    "Jannet": "lumen",
    "Tammey": "lumen",
    "Annie": "lumen",
    "Sam": "verse",
    "Joe": "sol",
    "Rick": "sol",
    "Tom": "sol",
    "Beau": "nova",
}

# Preserve the requested MK3 voice identities while resolving unsupported aliases
# to current OpenAI TTS voice names under the hood.
TTS_OPENAI_VOICE_MAP = {
    "verse": "verse",
    "nova": "nova",
    "lumen": "sage",
    "ember": "coral",
    "sol": "ash",
    "alloy": "alloy",
}


class LLMProvider:
    provider_name = "base"

    def generate(self, agent_id: str, model: str, payload: dict) -> str:
        raise NotImplementedError

    def generate_action_response(self, agent_id: str, model: str, payload: dict) -> GenerationResult:
        return GenerationResult(
            content=self.generate(agent_id, model, payload),
            pending_state_changes=[],
            pending_roll_results=[],
            pending_action_results=[],
            party_requests=[],
        )

    def continue_generation(self, continuation: dict[str, Any]) -> str:
        return str(continuation.get("content", "") or "")

    def generate_image(self, prompt_text: str, reference_image_bytes: bytes | None = None) -> str:
        raise NotImplementedError

    def generate_speech(self, text: str, voice_alias: str) -> bytes:
        raise NotImplementedError


class MockLLMProvider(LLMProvider):
    provider_name = "mock"

    def generate(self, agent_id: str, model: str, payload: dict) -> str:
        if agent_id == "agent0":
            return f"Valaska mission lock created for {payload.get('adventure', {}).get('title', 'unknown mission')}."
        if agent_id == "agent8":
            return f"Turn delta summary for prompts {payload.get('from_prompt_index')}-{payload.get('to_prompt_index')}."
        if agent_id == "agent9":
            return "Narrative draft generated from the selected player lens, structured memory, and transcript."
        if agent_id == "agent13":
            return "[Verse]\nThe party came home through the frost and the flame,\nWith hard-won scars and a tale to proclaim.\n\n[Chorus]\nRaise up the cup, let Moosehearth sing,\nFor brave hearts return with the dawn on their wings.\n\n[Outro]\nSo pay the bard and remember the night,\nWhen Valaska's heroes came back from the fight."
        if agent_id == "agent10":
            party = payload.get("recent_context", [])
            moment = party[-1]["text"] if party else "the party presses into the cold Valaskan dusk"
            return f"Dark fantasy illustration of {moment[:160]}"
        if agent_id == "agent12":
            living = [item for item in payload.get("monster_group_state", {}).get("instances", []) if not item.get("is_dead")]
            if not living:
                return "The opposition hesitates, with no living monsters left to act."
            return "\n\n".join(
                f"{monster.get('display_name', 'Monster')} lashes out according to its default hostile behavior."
                for monster in living
            )
        slot = payload.get("agent_identity", {}).get("slot")
        user_prompt = payload.get("user_prompt", "")
        return f"I answer as slot {slot}: {user_prompt[:180]}"

    def generate_action_response(self, agent_id: str, model: str, payload: dict) -> GenerationResult:
        return GenerationResult(
            content=self.generate(agent_id, model, payload),
            pending_state_changes=[],
            pending_roll_results=[],
            pending_action_results=[],
            party_requests=[],
        )

    def generate_image(self, prompt_text: str, reference_image_bytes: bytes | None = None) -> str:
        return "mock://generated-image"

    def generate_speech(self, text: str, voice_alias: str) -> bytes:
        raise RuntimeError("TTS is unavailable when using the mock provider")

    def continue_generation(self, continuation: dict[str, Any]) -> str:
        messages = continuation.get("messages", [])
        if messages:
            return "The action resolves as described."
        return ""


class OpenAIProvider(LLMProvider):
    provider_name = "openai"

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def generate(self, agent_id: str, model: str, payload: dict) -> str:
        system_prompt = self._system_prompt(agent_id, payload)
        messages = self._messages(agent_id, payload)
        tools = self._tools(agent_id, payload)
        return self._chat(model, messages, system_prompt, tools, payload).content

    def generate_action_response(self, agent_id: str, model: str, payload: dict) -> GenerationResult:
        system_prompt = self._system_prompt(agent_id, payload)
        messages = self._messages(agent_id, payload)
        tools = self._tools(agent_id, payload)
        return self._chat(model, messages, system_prompt, tools, payload)

    def generate_image(self, prompt_text: str, reference_image_bytes: bytes | None = None) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        with httpx.Client(timeout=180.0) as client:
            if reference_image_bytes:
                response = client.post(
                    f"{self.base_url}/images/edits",
                    headers=headers,
                    data={"model": "gpt-image-1-mini", "prompt": prompt_text, "size": "1024x1024"},
                    files={"image": ("reference.png", reference_image_bytes, "image/png")},
                )
            else:
                response = client.post(
                    f"{self.base_url}/images/generations",
                    headers={**headers, "Content-Type": "application/json"},
                    json={"model": "gpt-image-1-mini", "prompt": prompt_text, "size": "1024x1024"},
                )
            response.raise_for_status()
            data = response.json()
            item = data["data"][0]
            if "b64_json" in item:
                return f"data:image/png;base64,{item['b64_json']}"
            return item.get("url", "")

    def generate_speech(self, text: str, voice_alias: str) -> bytes:
        resolved_voice = TTS_OPENAI_VOICE_MAP.get(voice_alias, "alloy")
        started_at = time.perf_counter()
        with httpx.Client(timeout=180.0) as client:
            try:
                response = client.post(
                    f"{self.base_url}/audio/speech",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.llm_model_tts,
                        "voice": resolved_voice,
                        "input": text,
                        "format": "mp3",
                    },
                )
                response.raise_for_status()
                elapsed = time.perf_counter() - started_at
                logger.info(
                    "TTS upstream completed in %.2fs model=%s voice_alias=%s resolved_voice=%s text_chars=%s bytes=%s",
                    elapsed,
                    settings.llm_model_tts,
                    voice_alias,
                    resolved_voice,
                    len(text),
                    len(response.content),
                )
                return response.content
            except Exception:
                elapsed = time.perf_counter() - started_at
                logger.exception(
                    "TTS upstream failed after %.2fs model=%s voice_alias=%s resolved_voice=%s text_chars=%s",
                    elapsed,
                    settings.llm_model_tts,
                    voice_alias,
                    resolved_voice,
                    len(text),
                )
                raise

    def _chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]] | None,
        payload_context: dict[str, Any],
    ) -> GenerationResult:
        chat_messages = [{"role": "system", "content": system_prompt}, *messages]
        force_finalize = False
        pending_state_changes: list[dict[str, Any]] = []
        pending_roll_results: list[dict[str, Any]] = []
        pending_action_results: list[dict[str, Any]] = []
        party_requests: list[dict[str, Any]] = []
        used_action_tool = False
        used_inventory_tool = False
        with httpx.Client(timeout=90.0) as client:
            for _ in range(4):
                payload: dict[str, Any] = {
                    "model": model,
                    "messages": chat_messages,
                    "temperature": 0.4,
                }
                if tools:
                    payload["tools"] = tools
                    payload["tool_choice"] = "none" if force_finalize else "auto"
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if response.status_code == 429:
                    if _ < 3:
                        time.sleep(1.5 * (_ + 1))
                        continue
                response.raise_for_status()
                data = response.json()
                message = data["choices"][0]["message"]
                tool_calls = message.get("tool_calls") or []
                if tool_calls:
                    chat_messages.append(message)
                    retry_required = False
                    gameplay_tool_called = False
                    for call in tool_calls:
                        args = json.loads(call["function"]["arguments"])
                        if call["function"]["name"] == "resolve_action":
                            result = resolve_action_tool(payload_context, args)
                            used_action_tool = True
                            gameplay_tool_called = True
                            if result.get("retry_required"):
                                retry_required = True
                            else:
                                pending_action_results.extend(result.get("results", []))
                                pending_roll_results.extend(result.get("rolls", []))
                                pending_state_changes.extend(result.get("state_changes", []))
                        elif call["function"]["name"] == "update_inventory":
                            result = update_inventory_tool(args)
                            pending_state_changes.append(result)
                            used_inventory_tool = True
                            gameplay_tool_called = True
                        elif call["function"]["name"] == "request_party_response":
                            result = request_party_response_tool(payload_context, args)
                            if result.get("accepted"):
                                party_requests.append(result)
                        else:
                            continue
                        chat_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call["id"],
                                "content": json.dumps(result, ensure_ascii=True),
                            }
                        )
                    if retry_required:
                        chat_messages.append(
                            {
                                "role": "system",
                                "content": (
                                    "Your last resolve_action call used an invalid actor or target reference. "
                                    "Read the tool error carefully, choose only from the provided viable_targets list, "
                                    "and call resolve_action again now using the exact target_id values returned by the backend. "
                                    "Do not narrate yet."
                                ),
                            }
                        )
                        force_finalize = False
                        continue
                    if party_requests and not gameplay_tool_called:
                        chat_messages.append(
                            {
                                "role": "system",
                                "content": (
                                    "Your request for another party member to respond has been recorded. "
                                    "Now finish your own visible reply to the GM in character. Do not call another tool."
                                ),
                            }
                        )
                        force_finalize = True
                        continue
                    continuation_messages = [
                        *chat_messages,
                        {
                            "role": "system",
                            "content": (
                                "Use the tool result you just received and answer the GM now. Call additional tools only if another separate roll or state update is still required. "
                                "For SEARCH, PERCEPTION, or INVESTIGATION results, treat any found_loot field as authoritative: name those exact items and do not invent an ornate box, chest, relic, clue, or extra treasure. "
                                "If the result says no loot or failure, do not describe finding treasure."
                            ),
                        },
                    ]
                    return GenerationResult(
                        content="",
                        pending_state_changes=pending_state_changes,
                        pending_roll_results=pending_roll_results,
                        pending_action_results=pending_action_results,
                        party_requests=party_requests,
                        continuation={"model": model, "messages": continuation_messages},
                    )
                content = (message.get("content") or "").strip()
                if tools and PSEUDO_TOOL_CALL_RE.search(content):
                    logger.warning("Model emitted pseudo tool syntax instead of a real tool call; retrying with correction.")
                    pending_state_changes = []
                    pending_roll_results = []
                    pending_action_results = []
                    party_requests = []
                    used_action_tool = False
                    used_inventory_tool = False
                    chat_messages.append(message)
                    chat_messages.append(
                        {
                            "role": "system",
                            "content": (
                                "Do not print function calls, pseudo-code, or tool syntax in your reply. "
                                "If a tool is needed, call the actual tool through the tool interface. "
                                "Then answer the GM in plain text only."
                            ),
                        }
                    )
                    force_finalize = False
                    continue
                missing_action_tool = (DECLARED_BUT_UNROLLED_ACTION_RE.search(content) or ATTACK_RESOLUTION_RE.search(content)) and not used_action_tool
                missing_state_tool = STATE_RESOLUTION_RE.search(content) and not _has_effective_state_change(pending_state_changes)
                process_leak = PROCESS_LEAK_RE.search(content) or FAKE_TOOL_PROCESS_RE.search(content)
                impossible_miss_state = MISS_RESOLUTION_RE.search(content) and _has_effective_state_change(pending_state_changes)
                if tools and (missing_action_tool or missing_state_tool or process_leak or impossible_miss_state):
                    logger.warning("Model described combat or healing resolution without using required tools; retrying with correction.")
                    pending_state_changes = []
                    pending_roll_results = []
                    pending_action_results = []
                    party_requests = []
                    used_action_tool = False
                    used_inventory_tool = False
                    chat_messages.append(message)
                    chat_messages.append(
                        {
                            "role": "system",
                            "content": (
                                "Your last reply described an attack, damage, healing, or a roll without completing the required tool workflow. "
                                "If you attack, cast a spell, or attempt a skill check, use resolve_action first and wait for the backend resolution. "
                                "Do not roll dice yourself, determine hit or miss yourself, or apply HP changes yourself. "
                                "If the result changes inventory only, then use update_inventory. "
                                "If the attack misses, do not apply any damage or status changes. A miss must never produce a combat-state update for damage. "
                                "Do not say that you roll, hit, miss, deal damage, or heal unless those outcomes came from a real resolve_action result, and do not apply inventory changes without update_inventory. "
                                "Do not mention that you are about to update combat state or talk about the tool process in the visible reply. "
                                "Retry now using the proper tools and then answer in plain text."
                            ),
                        }
                    )
                    force_finalize = False
                    continue
                return GenerationResult(
                    content=content,
                    pending_state_changes=pending_state_changes,
                    pending_roll_results=pending_roll_results,
                    pending_action_results=pending_action_results,
                    party_requests=party_requests,
                )
        return GenerationResult(
            content="I report the roll result and wait for the GM to resolve the outcome.",
            pending_state_changes=pending_state_changes,
            pending_roll_results=pending_roll_results,
            pending_action_results=pending_action_results,
            party_requests=party_requests,
        )

    def continue_generation(self, continuation: dict[str, Any]) -> str:
        model = str(continuation.get("model", "") or "")
        messages = continuation.get("messages", [])
        if not model or not isinstance(messages, list) or not messages:
            return ""
        with httpx.Client(timeout=90.0) as client:
            for _ in range(3):
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": 0.4,
                    },
                )
                if response.status_code == 429 and _ < 2:
                    time.sleep(1.5 * (_ + 1))
                    continue
                response.raise_for_status()
                data = response.json()
                message = data["choices"][0]["message"]
                content = (message.get("content") or "").strip()
                if content:
                    return content
        return ""

    def _system_prompt(self, agent_id: str, payload: dict) -> str:
        if agent_id == "agent0":
            return AGENT0_SYSTEM_PROMPT
        if agent_id == "agent8":
            return SUMMARY_SYSTEM_PROMPT
        if agent_id == "agent9":
            selected_player_id = payload["selected_player_id"]
            return (
                f"{NARRATIVE_BASE_PROMPT}\n\nSelected player lens:\n{PLAYER_NARRATIVE_LENSES[selected_player_id]}"
            )
        if agent_id == "agent13":
            return (
                "You are a bardic lyricist for Story Engine MK5. Write original, singable fantasy tavern-ballad lyrics "
                "from the provided completed adventure context. Do not quote or closely imitate any existing song. "
                "Return only lyrics with simple section labels."
            )
        if agent_id == "agent10":
            return IMAGE_SYSTEM_PROMPT
        if agent_id == "agent12":
            return OPPOSITION_SYSTEM_PROMPT
        return CHARACTER_SYSTEM_PROMPT

    def _messages(self, agent_id: str, payload: dict) -> list[dict[str, Any]]:
        if agent_id in {"agent0", "agent8", "agent10", "agent12", "agent13"}:
            return [{"role": "user", "content": json.dumps(payload, ensure_ascii=True)}]
        if agent_id == "agent9":
            return [{"role": "user", "content": json.dumps(payload, ensure_ascii=True)}]
        return [{"role": "user", "content": self._character_prompt(payload)}]

    def _character_prompt(self, payload: dict) -> str:
        identity = payload["agent_identity"]
        class_sheet = payload["class_sheet"]
        memory = payload["structured_memory"]
        recent = payload["recent_context"]
        opposition_state = payload.get("opposition_state", {})
        mechanical_hint = payload.get("mechanical_resolution_hint", {})
        mission_objective = payload.get("mission_objective", {})
        current_encounter = payload.get("current_encounter", {})
        current_location = payload.get("current_location", "")
        party_roster = payload.get("party_roster", [])
        party_prompt_mode = payload.get("party_prompt_mode", "")
        starter_party_prompt_required = bool(payload.get("starter_party_prompt_required"))
        user_prompt = payload["user_prompt"]
        lines = []
        for event in recent:
            if event.get("role") == "user":
                lines.append(f"GM: {event['text']}")
            elif event.get("role") == "agent":
                lines.append(f"{event.get('agent_name') or 'Agent'}: {event['text']}")
            else:
                lines.append(f"system: {event['text']}")
        return (
            "[Player Identity]\n"
            f"{json.dumps(identity, ensure_ascii=True)}\n\n"
            "[GM chosen class for you to play]\n"
            f"{json.dumps(class_sheet, ensure_ascii=True)}\n\n"
            "[Structured Memory]\n"
            f"{json.dumps(memory, ensure_ascii=True)}\n\n"
            "[Mechanical Resolution Hint]\n"
            f"{json.dumps(mechanical_hint, ensure_ascii=True)}\n\n"
            "[Current Location]\n"
            f"{current_location}\n\n"
            "[Mission Objective]\n"
            f"{json.dumps(mission_objective, ensure_ascii=True)}\n\n"
            "[Current Encounter]\n"
            f"{json.dumps(current_encounter, ensure_ascii=True)}\n\n"
            "[Opposition State]\n"
            f"{json.dumps(opposition_state, ensure_ascii=True)}\n\n"
            "[Party Roster]\n"
            f"{json.dumps(party_roster, ensure_ascii=True)}\n\n"
            "[Party Prompt Mode]\n"
            f"{party_prompt_mode or 'direct GM prompt'}\n\n"
            "[Party Prompt Guidance]\n"
            f"{json.dumps({'allowed': bool(payload.get('allow_party_prompt')), 'starter_party_prompt_required': starter_party_prompt_required, 'instruction': 'For the exact starter prompt, answer with your plan and call request_party_response to ask exactly one other player agent a question.' if starter_party_prompt_required else ''}, ensure_ascii=True)}\n\n"
            "[Recent Context]\n"
            f"{chr(10).join(lines)}\n\n"
            "[User Prompt]\n"
            f"{user_prompt}"
        )

    def _tools(self, agent_id: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]] | None:
        if agent_id not in {"agent_character", "agent12"}:
            return None
        payload = payload or {}
        if payload.get("party_prompt_mode"):
            return None
        supported_abilities = [
            "RAPIER",
            "LONGSWORD",
            "GREATSWORD",
            "DAGGER",
            "MACE",
            "HANDAXE",
            "LONGBOW",
            "SHORTBOW",
            "SHORTSWORD",
            "JAVELIN",
            "SCIMITAR",
            "QUARTERSTAFF",
            "MAGIC_MISSILE",
            "CURE_WOUNDS",
            "CLEAVE",
            "RAGE",
            "DOUBLE_NOCK",
            "SMITE",
            "LAY_ON_HANDS",
            "BLESS",
            "THUNDERWAVE",
            "FIREBOLT",
            "BURNING_HANDS",
            "ATHLETICS",
            "PERCEPTION",
            "INVESTIGATION",
            "SEARCH",
            "POTION_OF_HEALING",
            "POTION_OF_SPELL_RESTORE",
            "FIREBALL_SCROLL",
        ]
        supported_abilities.extend(
            re.sub(r"[^A-Z0-9]+", "_", name.strip().upper()).strip("_")
            for name in MONSTER_CATALOG.keys()
        )
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "resolve_action",
                    "description": "Request one or more gameplay actions. The backend will resolve all mechanics, update HP, and return the authoritative results. For named multiattack features, send CLEAVE exactly once or DOUBLE_NOCK exactly once; the backend expands the named feature into its allowed attacks.",
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "actions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "actor_id": {"type": "string"},
                                        "action_type": {"type": "string", "enum": ["ATTACK", "SPELL", "SKILL", "USE_ITEM"]},
                                        "ability": {"type": "string", "enum": supported_abilities},
                                        "target_id": {"type": "string"},
                                    },
                                    "required": ["actor_id", "action_type", "ability", "target_id"],
                                },
                            }
                        },
                        "required": ["actions"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "update_inventory",
                    "description": "Record authoritative inventory changes only. Do not use this for HP, healing, conditions, combat resolution, or consuming a healing item; healing items must use resolve_action.",
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "targets": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "target_type": {"type": "string", "enum": ["player"]},
                                        "target_slot": {"type": "integer"},
                                        "target_id": {"type": "string"},
                                        "changes": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "additionalProperties": False,
                                                "properties": {
                                                    "kind": {
                                                        "type": "string",
                                                        "enum": ["inventory_add", "inventory_remove"],
                                                    },
                                                    "amount": {"type": "integer"},
                                                    "value": {"type": "string"},
                                                },
                                                "required": ["kind", "value"],
                                            },
                                        },
                                    },
                                    "required": ["target_type", "changes"],
                                },
                            },
                        },
                        "required": ["targets"],
                    },
                },
            },
        ]
        if (
            agent_id == "agent_character"
            and payload.get("allow_party_prompt")
            and not payload.get("party_prompt_mode")
        ):
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": "request_party_response",
                        "description": (
                            "Outside combat only: ask or address one other player agent. "
                            "Use this only when a brief character-to-character reply would help the scene. "
                            "The backend will route a bounded response chain; do not use it during combat."
                        ),
                        "parameters": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "target_slot": {"type": "integer", "enum": [1, 2, 3, 4]},
                                "message": {"type": "string"},
                                "mode": {"type": "string", "enum": ["statement", "question"]},
                            },
                            "required": ["target_slot", "message", "mode"],
                        },
                    },
                }
            )
        return tools


def resolve_action_tool(payload_context: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    from .services import resolve_actions_for_payload

    return resolve_actions_for_payload(payload_context, args)


def request_party_response_tool(payload_context: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    source_slot = int(payload_context.get("agent_identity", {}).get("slot", 0) or 0)
    target_slot = int(args.get("target_slot", 0) or 0)
    mode = str(args.get("mode", "") or "").lower()
    message = str(args.get("message", "") or "").strip()
    party = payload_context.get("party_roster", []) or []
    valid_slots = {int(member.get("slot", 0) or 0) for member in party}
    in_combat = bool(payload_context.get("mechanical_resolution_hint", {}).get("in_combat"))
    if in_combat:
        return {"accepted": False, "reason": "Party response requests are not allowed during combat."}
    if mode not in {"statement", "question"}:
        return {"accepted": False, "reason": "mode must be statement or question."}
    if not message:
        return {"accepted": False, "reason": "message is required."}
    if target_slot not in valid_slots or target_slot == source_slot:
        return {"accepted": False, "reason": "target_slot must be another selected player agent."}
    name_by_slot = {int(member.get("slot", 0) or 0): str(member.get("name", "") or "") for member in party}
    return {
        "accepted": True,
        "source_slot": source_slot,
        "source_name": name_by_slot.get(source_slot, f"Agent {source_slot}"),
        "target_slot": target_slot,
        "target_name": name_by_slot.get(target_slot, f"Agent {target_slot}"),
        "mode": mode,
        "message": message[:1000],
    }


def update_inventory_tool(args: dict[str, Any]) -> dict[str, Any]:
    targets = args.get("targets", [])
    if not targets:
        targets = []
    normalized_targets = []
    for target in targets:
        normalized_changes = []
        for change in target.get("changes", []):
            kind = change.get("kind", "")
            if kind not in {"inventory_add", "inventory_remove"}:
                continue
            normalized_changes.append(
                {
                    "kind": kind,
                    "amount": int(change.get("amount", 0)) if change.get("amount") is not None else 0,
                    "value": change.get("value", ""),
                }
            )
        if not normalized_changes:
            continue
        normalized_targets.append(
            {
                "target_type": "player",
                "target_slot": int(target.get("target_slot", 0)) if target.get("target_slot") is not None else 0,
                "target_id": target.get("target_id", ""),
                "changes": normalized_changes,
            }
        )
    return {"targets": normalized_targets, "source": "tool"}


def tts_voice_alias_for_player(player_name: str) -> str:
    return TTS_PLAYER_VOICE_ALIASES.get(player_name, "alloy")


def get_provider() -> LLMProvider:
    if settings.llm_provider == "openai":
        if not settings.llm_external_enabled:
            raise RuntimeError("LLM provider is openai but LLM_EXTERNAL_ENABLED is false")
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return OpenAIProvider(settings.openai_api_key, settings.openai_base_url)
    return MockLLMProvider()


def log_artifact(db: Session, session_id: str, agent_id: str, model: str, payload: dict, output: str, provider_name: str) -> None:
    payload_text = json.dumps(payload, sort_keys=True)
    artifact = LLMArtifact(
        session_id=session_id,
        agent_id=agent_id,
        provider=provider_name,
        model=model,
        input_hash=hashlib.sha256(payload_text.encode("utf-8")).hexdigest(),
        token_counts={"input_chars": len(payload_text), "output_chars": len(output)},
        raw_input_ref=payload_text,
        raw_output_ref=output,
    )
    db.add(artifact)


def decode_data_image(data_url: str) -> bytes | None:
    if not data_url.startswith("data:image"):
        return None
    _, encoded = data_url.split(",", 1)
    return base64.b64decode(encoded)
