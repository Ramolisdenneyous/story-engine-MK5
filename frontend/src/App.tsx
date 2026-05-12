import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { api, apiBlob, resolveApiUrl } from "./api";
import {
  Adventure,
  AdventureSummary,
  CatalogBoot,
  FeedbackCreateResponse,
  Monster,
  OPPOSITION_SLOT,
  PromptResponse,
  SessionDetail,
  TranscriptEvent,
  TtsState,
} from "./appTypes";
import { AdventureTab } from "./components/AdventureTab";
import { FeedbackTab } from "./components/FeedbackTab";
import { PreparationTab } from "./components/PreparationTab";

type MusicCue = "inn" | "adventure" | "combat" | "victory";

const MUSIC_TRACKS: Record<MusicCue, string[]> = {
  inn: [
    "Citadel of Rusted Banners.mp3",
    "Citadel of Rusted Banners (1).mp3",
  ],
  adventure: ["Cursed Village Menu (1).mp3"],
  combat: ["Cursed Village Menu.mp3"],
  victory: ["Gallows of the Forgotten King.mp3"],
};
const MUSIC_CUE_LABELS: Record<MusicCue, string> = {
  inn: "Inn",
  adventure: "Adventure",
  combat: "Combat",
  victory: "Victory",
};
const MUSIC_TRACK_URLS = Object.fromEntries(
  Object.entries(MUSIC_TRACKS).map(([cue, fileNames]) => [
    cue,
    fileNames.map((fileName) => resolveApiUrl(`/music/${encodeURIComponent(fileName)}`)),
  ]),
) as Record<MusicCue, string[]>;
const VALASKA_INTRO_AUDIO_URL = resolveApiUrl("/audio/valaska-intro.mp3");
const ENCOUNTER_NOTICE_AUDIO: Record<string, string> = {
  "icebane-castle:loc-3": "icebane-castle-loc-3-rolling-stone-boulders.mp3",
  "east-marsh-raid:loc-1": "east-marsh-raid-loc-1-blackwater-approach.mp3",
  "east-marsh-raid:loc-2": "east-marsh-raid-loc-2-watcher-s-rise.mp3",
  "east-marsh-raid:loc-3": "east-marsh-raid-loc-3-outer-camp-ring.mp3",
  "east-marsh-raid:loc-4": "east-marsh-raid-loc-4-supply-cache-pit.mp3",
  "east-marsh-raid:loc-6": "east-marsh-raid-loc-6-fog-choked-escape-channel.mp3",
  "telas-wagons:loc-1": "telas-wagons-loc-1-mud-stuck-wagon.mp3",
  "telas-wagons:loc-6": "telas-wagons-loc-6-glockstead-approach.mp3",
  "old-people-barrow:loc-1": "old-people-barrow-loc-1-rolling-stone-boulders.mp3",
  "old-people-barrow:loc-4": "old-people-barrow-loc-4-puzzle-door.mp3",
  "old-people-barrow:loc-6": "old-people-barrow-loc-6-steep-cliffside.mp3",
  "endless-glacier-undead:loc-1": "endless-glacier-undead-loc-1-everflame-abbey.mp3",
};
const ENCOUNTER_NOTICE_TYPES = new Set(["trap", "hazard", "story"]);
const ENCOUNTER_VISUALS: Record<string, string> = {
  "icebane-castle:loc-3": "Encounter-The-Collapsed-Barracks-TRAP.webp",
  "east-marsh-raid:loc-6": "Encounter-The Fog-Choked Escape Channel-Hazard.webp",
  "telas-wagons:loc-1": "Encounter-The Western Tundra Stretch-Hazard.webp",
  "old-people-barrow:loc-1": "Encounter-The Frost-Cleft Entrance-TRAP.webp",
  "old-people-barrow:loc-6": "Encounter-The Fractured Escape Tunnel-Hazard.webp",
  "endless-glacier-undead:loc-1": "Encounter-Everflame Abbey-NPC.webp",
};

const ADVENTURE_TITLE_OVERRIDES: Record<string, string> = {
  "icebane-castle": "Memories of the Witch King",
  "east-marsh-raid": "Blood at Midnight",
  "telas-wagons": "To Follow the King's Way",
  "old-people-barrow": "The Dead Remember",
  "collecting-taxes": "Collecting What's Owed",
  "endless-glacier-undead": "Nightmares of the Thawed",
};

const TTS_STATUS_LABELS = {
  idle: "Idle",
  loading: "Loading",
  playing: "Playing",
} as const satisfies Record<TtsState, string>;

const MUSIC_VOLUME = 0.014;
const MUSIC_DUCKED_VOLUME = 0.006;
const TTS_REQUEST_TIMEOUT_MS = 25000;
const TTS_PLAYER_GAIN: Record<string, number> = {
  Beau: 1,
  Joe: 1,
  Annie: 1.05,
  Rick: 1.05,
  Sam: 1.05,
  Tom: 1.05,
  Tammey: 1.35,
  Jannet: 1.35,
};

const STARTER_PROMPT = "Party leader, you know this mission, what is your plan?";
const OPPOSITION_STARTER_PROMPT = "The monster gets the drop on the party, and attacks!";
const DEFAULT_TUTORIAL_VIDEO_URL = "https://www.youtube.com/watch?v=eJarez0LH-E";
const TUTORIAL_VIDEO_URL = import.meta.env.VITE_TUTORIAL_VIDEO_URL || DEFAULT_TUTORIAL_VIDEO_URL;
type OnboardingGuideStep = "starter" | "adventure-map" | "location-one" | "travel" | "trigger-encounter" | "start-encounter" | "opposition-prompt" | "complete";
const TTS_QUEUE_LIMIT = 3;

function youtubeEmbedUrl(rawUrl: string) {
  const value = rawUrl.trim();
  if (!value) return "";
  const buildEmbedUrl = (videoId: string) => {
    const embedUrl = new URL(`https://www.youtube-nocookie.com/embed/${videoId}`);
    embedUrl.searchParams.set("controls", "0");
    embedUrl.searchParams.set("rel", "0");
    embedUrl.searchParams.set("playsinline", "1");
    embedUrl.searchParams.set("modestbranding", "1");
    embedUrl.searchParams.set("iv_load_policy", "3");
    return embedUrl.toString();
  };
  try {
    const parsed = new URL(value);
    const host = parsed.hostname.replace(/^www\./, "");
    if (host === "youtu.be") {
      const videoId = parsed.pathname.split("/").filter(Boolean)[0] ?? "";
      return videoId ? buildEmbedUrl(videoId) : "";
    }
    if (host === "youtube.com" || host === "m.youtube.com" || host === "music.youtube.com") {
      if (parsed.pathname.startsWith("/embed/")) {
        const videoId = parsed.pathname.split("/").filter(Boolean)[1] ?? "";
        return videoId ? buildEmbedUrl(videoId) : "";
      }
      const videoId = parsed.searchParams.get("v") ?? "";
      return videoId ? buildEmbedUrl(videoId) : "";
    }
  } catch {
    return "";
  }
  return "";
}

function sanitizeVisibleAgentText(text: string) {
  return text
    .split(/\r?\n/)
    .filter((line) => {
      const trimmed = line.trim();
      if (!trimmed) return true;
      if (/^(TOOL_DICE_ROLL|COMBAT_STATE_CHANGE):/i.test(trimmed)) return false;
      if (/^(resolve_action|update_inventory|update_combat_state|roll_dice|roll_dice_batch)\s*[:(]/i.test(trimmed)) return false;
      if (/^\{.*\}$/.test(trimmed) && /"(target_type|target_id|changes|formula|rolls|actor_id|action_type|ability|actions|results|healing|damage)"/.test(trimmed)) return false;
      return true;
    })
    .join("\n")
    .trim();
}

function orderedAgentSlotsForDetail(detail: SessionDetail | null): number[] {
  if (!detail) return [1, 2, 3, 4];
  if (detail.session.combat_state.in_combat) {
    return detail.session.combat_state.initiative_order
      .map((item) => {
        if (item === "opp:12") return OPPOSITION_SLOT;
        if (item.startsWith("pc:")) return Number(item.replace("pc:", ""));
        return Number(item);
      })
      .filter((slot) => Number.isFinite(slot));
  }
  return detail.tab1.selected_agent_slots;
}

function activeCombatantIdForDetail(detail: SessionDetail): string {
  const combat = detail.session.combat_state;
  const order = combat.initiative_order;
  if (!combat.in_combat || !order.length) return "";
  const livingIds = new Set<string>();
  detail.tab1.party.forEach((member) => {
    if (member.hp_current > 0) livingIds.add(`pc:${member.slot}`);
  });
  if (detail.session.opposition_state?.active) livingIds.add("opp:12");
  if (!livingIds.size) return "";
  const acted = { ...combat.acted_this_round };
  const livingOrder = order.filter((combatantId) => livingIds.has(combatantId));
  if (livingOrder.length && livingOrder.every((combatantId) => acted[combatantId])) {
    Object.keys(acted).forEach((combatantId) => {
      delete acted[combatantId];
    });
  }
  const start = Math.min(combat.turn_index, order.length - 1);
  for (let offset = 0; offset < order.length; offset += 1) {
    const combatantId = order[(start + offset) % order.length];
    if (livingIds.has(combatantId) && !acted[combatantId]) return combatantId;
  }
  return "";
}

function selectableAgentSlotsForDetail(detail: SessionDetail | null): number[] {
  if (!detail) return [1, 2, 3, 4];
  if (detail.session.combat_state.in_combat && detail.session.combat_state.initiative_order.length) {
    const activeCombatant = activeCombatantIdForDetail(detail);
    if (activeCombatant === "opp:12" && detail.session.opposition_state?.active) return [OPPOSITION_SLOT];
    if (activeCombatant?.startsWith("pc:")) {
      const slot = Number(activeCombatant.replace("pc:", ""));
      const member = detail.tab1.party.find((partyMember) => partyMember.slot === slot);
      if (member && member.hp_current > 0) return [slot];
    }
  }
  const playerSlots = detail.tab1.party.filter((member) => member.hp_current > 0).map((member) => member.slot);
  const activeOrder = orderedAgentSlotsForDetail(detail).filter((slot) => slot !== OPPOSITION_SLOT);
  const orderedPlayers = activeOrder.filter((slot) => playerSlots.includes(slot));
  const remainingPlayers = playerSlots.filter((slot) => !orderedPlayers.includes(slot));
  const oppositionSlots = detail.session.opposition_state?.active ? [OPPOSITION_SLOT] : [];
  return [...orderedPlayers, ...remainingPlayers, ...oppositionSlots];
}

function nextSelectableSlot(detail: SessionDetail | null, currentSlot: number): number {
  const slots = selectableAgentSlotsForDetail(detail);
  if (!slots.length) return 1;
  const currentIndex = slots.indexOf(currentSlot);
  if (currentIndex === -1) return slots[0];
  return slots[(currentIndex + 1) % slots.length];
}

function firstMonsterId(monsters: Monster[]) {
  return monsters[0]?.monster_id ?? "";
}

function locationImageSlug(name: string) {
  return name
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u2018\u2019']/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function locationImageUrl(title: string) {
  const slug = locationImageSlug(title);
  return `/assets/Location-${slug}.webp`;
}

function encounterNoticeAudioUrl(adventureId: string, locationId: string) {
  const fileName = ENCOUNTER_NOTICE_AUDIO[`${adventureId}:${locationId}`];
  return fileName ? resolveApiUrl(`/audio/noncombat-encounter-notices/${encodeURIComponent(fileName)}`) : "";
}

function encounterVisualUrl(adventureId: string, locationId: string) {
  const fileName = ENCOUNTER_VISUALS[`${adventureId}:${locationId}`];
  return fileName ? `/assets/${fileName}` : "";
}

function isEncounterNoticeEvent(event: TranscriptEvent) {
  const payload = event.json_payload ?? {};
  const source = typeof payload.source === "string" ? payload.source : "";
  const encounterType = typeof payload.encounter_type === "string" ? payload.encounter_type : "";
  const locationId = typeof payload.location_id === "string" ? payload.location_id : "";
  return event.role === "system" && event.kind === "transcript" && source === "encounter_start" && ENCOUNTER_NOTICE_TYPES.has(encounterType) && Boolean(locationId);
}

export function App() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const introAudioRef = useRef<HTMLAudioElement | null>(null);
  const encounterNoticeAudioRef = useRef<HTMLAudioElement | null>(null);
  const encounterNoticePlayingRef = useRef(false);
  const encounterNoticeBaselineReadyRef = useRef(false);
  const playedEncounterNoticeEventIdsRef = useRef<Set<string>>(new Set());
  const transcriptRef = useRef<HTMLDivElement>(null);
  const speechAudioRef = useRef<HTMLAudioElement | null>(null);
  const speechAudioContextRef = useRef<AudioContext | null>(null);
  const speechGainNodeRef = useRef<GainNode | null>(null);
  const speechSourceNodeRef = useRef<MediaElementAudioSourceNode | null>(null);
  const speechObjectUrlRef = useRef<string | null>(null);
  const speechAbortRef = useRef<AbortController | null>(null);
  const autoPlayBaselineRef = useRef<string | null>(null);
  const ttsQueueRef = useRef<TranscriptEvent[]>([]);
  const ttsQueuedEventIdsRef = useRef<Set<string>>(new Set());
  const ttsPreloadPromisesRef = useRef<Map<string, Promise<string>>>(new Map());
  const ttsPreloadControllersRef = useRef<Map<string, AbortController>>(new Map());
  const ttsPreloadObjectUrlsRef = useRef<Set<string>>(new Set());
  const ttsProcessingRef = useRef(false);
  const narrationPollTokenRef = useRef(0);
  const partyFollowupPollTokenRef = useRef(0);
  const previousMusicCueRef = useRef<MusicCue>("inn");
  const adventureTabTopRef = useRef<HTMLDivElement | null>(null);

  const [catalogBoot, setCatalogBoot] = useState<CatalogBoot | null>(null);
  const [adventureDetailsById, setAdventureDetailsById] = useState<Record<string, Adventure>>({});
  const [sessionId, setSessionId] = useState("");
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [tab, setTab] = useState<1 | 2 | 3>(1);
  const [loading, setLoading] = useState(false);
  const [chapterStarting, setChapterStarting] = useState(false);
  const [chapterLoadingFrame, setChapterLoadingFrame] = useState(0);
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [feedbackSubmittedAt, setFeedbackSubmittedAt] = useState("");
  const [error, setError] = useState("");
  const [musicTrackIndex, setMusicTrackIndex] = useState(0);
  const [musicPlaying, setMusicPlaying] = useState(true);
  const [musicMuted, setMusicMuted] = useState(false);
  const [musicAutoplayBlocked, setMusicAutoplayBlocked] = useState(false);
  const [adventureId, setAdventureId] = useState("");
  const [selectedPlayerIds, setSelectedPlayerIds] = useState<string[]>([]);
  const [classByPlayer, setClassByPlayer] = useState<Record<string, string>>({});
  const [activeAgentSlot, setActiveAgentSlot] = useState(1);
  const [activeLocationId, setActiveLocationId] = useState("");
  const [userPrompt, setUserPrompt] = useState("");
  const [starterPromptDismissed, setStarterPromptDismissed] = useState(false);
  const [ttsAutoPlay, setTtsAutoPlay] = useState(true);
  const [ttsState, setTtsState] = useState<TtsState>("idle");
  const [ttsError, setTtsError] = useState("");
  const [currentTtsReply, setCurrentTtsReply] = useState<TranscriptEvent | null>(null);
  const [encounterNoticeImageUrl, setEncounterNoticeImageUrl] = useState("");
  const [travelLoading, setTravelLoading] = useState(false);
  const [longRestLoading, setLongRestLoading] = useState(false);
  const [encounterModalOpen, setEncounterModalOpen] = useState(false);
  const [encounterMonsterId, setEncounterMonsterId] = useState("");
  const [encounterQuantity, setEncounterQuantity] = useState(1);
  const [spawnLoading, setSpawnLoading] = useState(false);
  const [dismissLoading, setDismissLoading] = useState(false);
  const [feedbackText, setFeedbackText] = useState("");
  const [locationView, setLocationView] = useState<"world" | "adventure" | "encounter">("world");
  const [encounterLocationTitle, setEncounterLocationTitle] = useState("Antlers Rest Inn");
  const [playedAttackEventIds, setPlayedAttackEventIds] = useState<string[]>([]);
  const [animationLocked, setAnimationLocked] = useState(false);
  const [promptNarrationPending, setPromptNarrationPending] = useState(false);
  const [introAudioPlayed, setIntroAudioPlayed] = useState(false);
  const [onboardingGuideStep, setOnboardingGuideStep] = useState<OnboardingGuideStep>("starter");
  const [splashOpen, setSplashOpen] = useState(() => window.localStorage.getItem("story-engine-mk5-splash-seen") !== "true");

  async function refresh(id = sessionId) {
    const data = await api<SessionDetail>(`/session/${id}`);
    setDetail(data);
    if (data.tab1.active_adventure) {
      setAdventureDetailsById((current) => ({
        ...current,
        [data.tab1.active_adventure!.adventure_id]: data.tab1.active_adventure!,
      }));
    }
    setAdventureId(data.tab1.adventure_id);
    setSelectedPlayerIds(data.tab1.selected_player_ids);
    const byPlayer: Record<string, string> = {};
    data.tab1.party.forEach((member) => {
      byPlayer[member.player_id] = member.class_id;
    });
    setClassByPlayer(byPlayer);
    const selectableSlots = selectableAgentSlotsForDetail(data);
    setActiveAgentSlot((current) => (selectableSlots.includes(current) ? current : selectableSlots[0] ?? 1));
    return data;
  }

  function mergePromptEvents(current: SessionDetail | null, response: PromptResponse) {
    if (!current) return current;
    const mergedEvents = [
      ...current.events,
      response.user_event,
      ...(response.agent_event ? [response.agent_event] : []),
      ...response.system_events,
      ...(response.extra_events ?? []),
    ];
    const dedupedEvents = mergedEvents.filter((eventItem, index, all) => (
      all.findIndex((candidate) => candidate.event_id === eventItem.event_id) === index
    ));
    return {
      ...current,
      session: response.session,
      events: dedupedEvents,
    };
  }

  async function waitForPromptNarration(promptIndex: number, agentSlot: number, id = sessionId) {
    const pollToken = narrationPollTokenRef.current + 1;
    narrationPollTokenRef.current = pollToken;
    for (let attempt = 0; attempt < 60; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 500));
      const refreshed = await refresh(id);
      const foundAgentReply = refreshed.events.some((event) => (
        event.prompt_index === promptIndex
        && event.role === "agent"
        && event.agent_slot === agentSlot
        && event.kind === "transcript"
      ));
      if (narrationPollTokenRef.current !== pollToken) {
        return;
      }
      if (foundAgentReply) {
        setPromptNarrationPending(false);
        return;
      }
    }
    if (narrationPollTokenRef.current === pollToken) {
      setPromptNarrationPending(false);
      setError("Agent narration is taking longer than expected. Try refreshing the session state.");
    }
  }

  async function waitForPartyFollowups(promptIndex: number, initialAgentEventId: string | null, expectedAgentEvents: number, id = sessionId) {
    if (!expectedAgentEvents) return;
    const pollToken = partyFollowupPollTokenRef.current + 1;
    partyFollowupPollTokenRef.current = pollToken;
    for (let attempt = 0; attempt < 90; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 400));
      const refreshed = await refresh(id);
      if (partyFollowupPollTokenRef.current !== pollToken) {
        return;
      }
      const followupAgentEvents = refreshed.events.filter((event) => (
        event.prompt_index === promptIndex
        && event.role === "agent"
        && event.kind === "transcript"
        && event.event_id !== initialAgentEventId
      ));
      if (followupAgentEvents.length >= expectedAgentEvents) {
        return;
      }
    }
  }

  async function boot() {
    setLoading(true);
    setError("");
    try {
      const [catalogData, created] = await Promise.all([
        api<CatalogBoot>("/catalog/boot"),
        api<{ session_id: string }>("/session", { method: "POST" }),
      ]);
      setCatalogBoot(catalogData);
      setSessionId(created.session_id);
      setPlayedAttackEventIds([]);
      setStarterPromptDismissed(false);
      setIntroAudioPlayed(false);
      await refresh(created.session_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void boot();
  }, []);

  useEffect(() => {
    if (!adventureId || adventureDetailsById[adventureId]) {
      return;
    }
    let cancelled = false;
    void api<Adventure>(`/catalog/adventures/${adventureId}`)
      .then((adventure) => {
        if (cancelled) return;
        setAdventureDetailsById((current) => ({ ...current, [adventure.adventure_id]: adventure }));
      })
      .catch(() => {
        // Keep the UI usable with summary data if this lazy fetch fails.
      });
    return () => {
      cancelled = true;
    };
  }, [adventureId, adventureDetailsById]);

  const transcript = useMemo(() => {
    if (!detail) return [];
    return detail.events
      .filter((event) => event.kind === "transcript" || event.kind === "objective_updated" || event.kind === "inventory_gained" || event.kind === "inventory_lost" || event.kind === "resource_changed")
      .map((event) => ({ ...event, text: sanitizeVisibleAgentText(event.text) }))
      .filter((event) => event.text.trim());
  }, [detail]);

  const latestEligibleReply = useMemo(() => {
    for (let index = transcript.length - 1; index >= 0; index -= 1) {
      const event = transcript[index];
      if (event.role === "agent") {
        return event;
      }
    }
    return null;
  }, [transcript]);

  const playerNameBySlot = useMemo(
    () => new Map((detail?.tab1.party ?? []).map((member) => [member.slot, member.player_name])),
    [detail],
  );

  useEffect(() => {
    const box = transcriptRef.current;
    if (!box) return;
    box.scrollTop = box.scrollHeight;
  }, [detail?.events.length, detail?.session.prompt_index]);

  useEffect(() => {
    if (!detail) return;
    const eligibleEvents = detail.events.filter(isEncounterNoticeEvent);
    if (!encounterNoticeBaselineReadyRef.current) {
      eligibleEvents.forEach((event) => playedEncounterNoticeEventIdsRef.current.add(event.event_id));
      encounterNoticeBaselineReadyRef.current = true;
      return;
    }

    const nextEvent = eligibleEvents.find((event) => !playedEncounterNoticeEventIdsRef.current.has(event.event_id));
    if (!nextEvent) return;
    playedEncounterNoticeEventIdsRef.current.add(nextEvent.event_id);
    playEncounterNoticeAudio(nextEvent);
  }, [detail?.events.length, adventureId]);

  useEffect(() => {
    const speechAudio = new Audio();
    speechAudioRef.current = speechAudio;
    const onEnded = () => setTtsState("idle");
    const onPause = () => setTtsState((current) => (current === "playing" ? "idle" : current));
    speechAudio.addEventListener("ended", onEnded);
    speechAudio.addEventListener("pause", onPause);
    return () => {
      speechAudio.pause();
      speechAudio.removeEventListener("ended", onEnded);
      speechAudio.removeEventListener("pause", onPause);
      speechSourceNodeRef.current?.disconnect();
      speechGainNodeRef.current?.disconnect();
      void speechAudioContextRef.current?.close();
      speechAbortRef.current?.abort();
      if (speechObjectUrlRef.current) {
        URL.revokeObjectURL(speechObjectUrlRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const introAudio = new Audio(VALASKA_INTRO_AUDIO_URL);
    introAudio.preload = "auto";
    introAudioRef.current = introAudio;
    return () => {
      introAudio.pause();
      introAudioRef.current = null;
    };
  }, []);

  useEffect(() => {
    return () => {
      encounterNoticeAudioRef.current?.pause();
      encounterNoticeAudioRef.current = null;
    };
  }, []);

  useEffect(() => {
    encounterNoticeAudioRef.current?.pause();
    encounterNoticeAudioRef.current = null;
    encounterNoticePlayingRef.current = false;
    setEncounterNoticeImageUrl("");
    encounterNoticeBaselineReadyRef.current = false;
    playedEncounterNoticeEventIdsRef.current.clear();
  }, [sessionId]);

  useEffect(() => {
    if (!chapterStarting) {
      setChapterLoadingFrame(0);
      return;
    }
    const timer = window.setInterval(() => {
      setChapterLoadingFrame((current) => current + 1);
    }, 400);
    return () => window.clearInterval(timer);
  }, [chapterStarting]);

  useEffect(() => {
    setActiveLocationId("");
    setLocationView("world");
    setEncounterLocationTitle("Antlers Rest Inn");
  }, [detail?.tab1.active_adventure?.adventure_id]);

  useEffect(() => {
    setEncounterMonsterId((current) => {
      if (current && detail?.gm_monsters.some((monster) => monster.monster_id === current)) {
        return current;
      }
      return firstMonsterId(detail?.gm_monsters ?? []);
    });
  }, [detail?.gm_monsters]);

  useEffect(() => {
    if (tab !== 2 || splashOpen) return;
    const alignAdventureTop = () => {
      adventureTabTopRef.current?.scrollIntoView({ behavior: "auto", block: "start" });
    };
    const frameId = window.requestAnimationFrame(alignAdventureTop);
    const settleTimerId = window.setTimeout(alignAdventureTop, 600);
    return () => {
      window.cancelAnimationFrame(frameId);
      window.clearTimeout(settleTimerId);
    };
  }, [splashOpen, tab]);

  useEffect(() => {
    if (tab !== 2 || splashOpen || introAudioPlayed || !detail?.session.tab1_locked) return;
    const introAudio = introAudioRef.current;
    if (!introAudio) return;
    introAudio.currentTime = 0;
    introAudio.volume = 1;
    setIntroAudioPlayed(true);
    void introAudio.play().catch(() => undefined);
  }, [detail?.session.tab1_locked, introAudioPlayed, splashOpen, tab]);

  async function enableMusicPlayback() {
    const audio = audioRef.current;
    if (!audio) return;
    try {
      audio.volume = ttsState === "playing" ? MUSIC_DUCKED_VOLUME : MUSIC_VOLUME;
      audio.muted = musicMuted;
      await audio.play();
      setMusicPlaying(true);
      setMusicAutoplayBlocked(false);
    } catch (e) {
      setMusicAutoplayBlocked(true);
    }
  }

  function toggleMusicPlayback() {
    const audio = audioRef.current;
    if (!audio) return;
    if (musicPlaying) {
      audio.pause();
      setMusicPlaying(false);
      setMusicAutoplayBlocked(false);
      return;
    }
    void enableMusicPlayback();
  }

  function toggleMusicMuted() {
    const audio = audioRef.current;
    const nextMuted = !musicMuted;
    if (audio) {
      audio.muted = nextMuted;
    }
    setMusicMuted(nextMuted);
  }

  const selectedAdventureSummary = useMemo(
    () => catalogBoot?.adventures.find((item) => item.adventure_id === adventureId) ?? null,
    [adventureId, catalogBoot],
  );
  const selectedAdventure = detail?.tab1.active_adventure ?? (adventureId ? adventureDetailsById[adventureId] ?? null : null);
  const transcriptChars = transcript.reduce((sum, event) => sum + event.text.length + 1, 0);
  const gmMonsters = detail?.gm_monsters ?? [];
  const oppositionState = detail?.session.opposition_state ?? null;
  const oppositionCleanupPending = Boolean(
    oppositionState?.active
    && oppositionState.instances.length
    && oppositionState.instances.every((instance) => instance.is_dead || instance.current_hp <= 0),
  );
  const activeOpposition = oppositionState?.active && !oppositionCleanupPending ? oppositionState : null;
  const adventureLocations = detail?.tab1.active_adventure?.locations ?? [];
  const activeLocation = adventureLocations.find((location) => location.id === activeLocationId) ?? null;
  const loadingPulse = [".", "..", "..."][chapterLoadingFrame % 3];
  const selectedEncounterMonster = gmMonsters.find((monster) => monster.monster_id === encounterMonsterId) ?? gmMonsters[0] ?? null;
  const encounterMonsterIndex = Math.max(0, gmMonsters.findIndex((monster) => monster.monster_id === encounterMonsterId));
  const encounterState = detail?.session.encounter_state;
  const activeHazardImageUrl =
    encounterState?.encounter_type === "hazard"
    && encounterState.status !== "clear"
    && encounterState.status !== "resolved"
    && encounterState.location_id
      ? encounterVisualUrl(encounterState.adventure_id || detail?.tab1.adventure_id || adventureId, encounterState.location_id)
      : "";
  const encounterLocationImageUrl = encounterNoticeImageUrl || activeHazardImageUrl || locationImageUrl(encounterLocationTitle);
  const objectiveState = detail?.session.mission_objective_state;
  const musicCue: MusicCue = activeOpposition
    ? "combat"
    : objectiveState?.complete && Boolean(objectiveState?.returned_to_moosehearth)
      ? "victory"
      : tab === 2 && Boolean(detail?.session.current_location_id)
        ? "adventure"
        : "inn";
  const currentMusicTracks = MUSIC_TRACK_URLS[musicCue];
  const currentTrack = currentMusicTracks[musicTrackIndex % currentMusicTracks.length] ?? currentMusicTracks[0] ?? "";

  useEffect(() => {
    if (previousMusicCueRef.current === musicCue) return;
    previousMusicCueRef.current = musicCue;
    setMusicTrackIndex(0);
  }, [musicCue]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !currentTrack) return;
    audio.load();
    audio.volume = MUSIC_VOLUME;
    audio.muted = musicMuted;
    if (!musicPlaying) {
      audio.pause();
      return;
    }
    void audio.play()
      .then(() => setMusicAutoplayBlocked(false))
      .catch(() => {
        audio.pause();
        setMusicPlaying(false);
        setMusicAutoplayBlocked(true);
      });
  }, [currentTrack, musicPlaying, musicMuted]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.volume = ttsState === "playing" ? MUSIC_DUCKED_VOLUME : MUSIC_VOLUME;
  }, [ttsState]);
  const allPlayersDown = Boolean(detail?.tab1.party.length) && detail!.tab1.party.every((member) => member.hp_current <= 0);
  const startRequirements = [
    adventureId === "" ? "select an adventure" : null,
    selectedPlayerIds.length < 4 ? "select four players" : null,
    selectedPlayerIds.some((playerId) => !classByPlayer[playerId]) ? "assign a class to each selected player" : null,
  ].filter(Boolean) as string[];
  const startChapterHint = startRequirements.length
    ? `Before you can start the chapter, please ${startRequirements.join(", ")}.`
    : "Ready to begin the adventure.";

  function displayAdventureTitle(adventure: AdventureSummary | Adventure | null) {
    if (!adventure) return "";
    return ADVENTURE_TITLE_OVERRIDES[adventure.adventure_id] ?? adventure.title;
  }

  const headerAdventureTitle = displayAdventureTitle(selectedAdventure ?? selectedAdventureSummary) || "Valaska Adventure Console";

  function clearTtsQueue() {
    ttsQueueRef.current = [];
    ttsQueuedEventIdsRef.current.clear();
    ttsPreloadControllersRef.current.forEach((controller) => controller.abort());
    ttsPreloadControllersRef.current.clear();
    ttsPreloadPromisesRef.current.clear();
    ttsPreloadObjectUrlsRef.current.forEach((objectUrl) => URL.revokeObjectURL(objectUrl));
    ttsPreloadObjectUrlsRef.current.clear();
  }

  function stopSpeechPlayback(clearQueue = false) {
    if (clearQueue) {
      clearTtsQueue();
      ttsProcessingRef.current = false;
    }
    speechAbortRef.current?.abort();
    speechAbortRef.current = null;
    if (speechAudioRef.current) {
      speechAudioRef.current.pause();
      speechAudioRef.current.currentTime = 0;
      speechAudioRef.current.src = "";
    }
    if (speechObjectUrlRef.current) {
      URL.revokeObjectURL(speechObjectUrlRef.current);
      speechObjectUrlRef.current = null;
    }
    setCurrentTtsReply(null);
    setTtsState("idle");
  }

  function stopIntroAudio() {
    const introAudio = introAudioRef.current;
    if (!introAudio) return;
    introAudio.pause();
    introAudio.currentTime = 0;
  }

  function playEncounterNoticeAudio(event: TranscriptEvent) {
    const payload = event.json_payload ?? {};
    const locationId = typeof payload.location_id === "string" ? payload.location_id : "";
    const currentAdventureId = detail?.tab1.adventure_id || adventureId;
    const audioUrl = encounterNoticeAudioUrl(currentAdventureId, locationId);
    if (!audioUrl) return;
    const visualUrl = encounterVisualUrl(currentAdventureId, locationId);

    stopSpeechPlayback(true);
    stopIntroAudio();

    encounterNoticeAudioRef.current?.pause();
    const audio = new Audio(audioUrl);
    audio.preload = "auto";
    audio.volume = 1;
    encounterNoticeAudioRef.current = audio;
    encounterNoticePlayingRef.current = true;
    setEncounterNoticeImageUrl(visualUrl);

    const finish = () => {
      audio.removeEventListener("ended", finish);
      audio.removeEventListener("error", finish);
      audio.removeEventListener("pause", finish);
      if (encounterNoticeAudioRef.current === audio) {
        encounterNoticeAudioRef.current = null;
        setEncounterNoticeImageUrl("");
      }
      encounterNoticePlayingRef.current = false;
      if (ttsAutoPlay && ttsQueueRef.current.length) {
        void drainTtsQueue();
      }
    };

    audio.addEventListener("ended", finish, { once: true });
    audio.addEventListener("error", finish, { once: true });
    audio.addEventListener("pause", finish, { once: true });
    audio.play().catch((e: Error) => {
      setTtsError(e.message);
      finish();
    });
  }

  async function ensureSpeechGainChain() {
    if (!speechAudioRef.current) {
      speechAudioRef.current = new Audio();
    }
    if (!speechAudioContextRef.current) {
      speechAudioContextRef.current = new AudioContext();
    }
    if (!speechGainNodeRef.current) {
      speechGainNodeRef.current = speechAudioContextRef.current.createGain();
      speechGainNodeRef.current.connect(speechAudioContextRef.current.destination);
    }
    if (!speechSourceNodeRef.current) {
      speechSourceNodeRef.current = speechAudioContextRef.current.createMediaElementSource(speechAudioRef.current);
      speechSourceNodeRef.current.connect(speechGainNodeRef.current);
    }
    if (speechAudioContextRef.current.state === "suspended") {
      await speechAudioContextRef.current.resume();
    }
  }

  function playerNameForReply(reply: TranscriptEvent) {
    const playerName =
      reply.agent_slot === OPPOSITION_SLOT
        ? "Opposition"
        : reply.agent_slot
          ? playerNameBySlot.get(reply.agent_slot) ?? ""
          : "";
    return playerName;
  }

  function preloadTtsReply(reply: TranscriptEvent) {
    if (!reply.event_id || !reply.text.trim() || !sessionId) {
      return Promise.resolve("");
    }
    const existing = ttsPreloadPromisesRef.current.get(reply.event_id);
    if (existing) {
      return existing;
    }
    const playerName = playerNameForReply(reply);
    if (!playerName) {
      return Promise.resolve("");
    }
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => {
      controller.abort();
    }, TTS_REQUEST_TIMEOUT_MS);
    ttsPreloadControllersRef.current.set(reply.event_id, controller);
    const promise = (async () => {
      const blob = await apiBlob(`/session/${sessionId}/tts`, {
        method: "POST",
        body: JSON.stringify({
          text: reply.text,
          player_name: playerName,
        }),
        signal: controller.signal,
      });
      const objectUrl = URL.createObjectURL(blob);
      ttsPreloadObjectUrlsRef.current.add(objectUrl);
      return objectUrl;
    })();
    ttsPreloadPromisesRef.current.set(reply.event_id, promise);
    promise.catch((e: Error) => {
      if (e.name !== "AbortError") {
        setTtsError(e.message);
      }
      return "";
    }).finally(() => {
      window.clearTimeout(timeoutId);
      ttsPreloadControllersRef.current.delete(reply.event_id);
    });
    return promise;
  }

  async function playPreparedReply(reply: TranscriptEvent, objectUrl: string) {
    if (!objectUrl) return;
    ttsPreloadObjectUrlsRef.current.delete(objectUrl);
    speechObjectUrlRef.current = objectUrl;
    if (!speechAudioRef.current) {
      speechAudioRef.current = new Audio();
    }
    try {
      await ensureSpeechGainChain();
      if (speechGainNodeRef.current) {
        speechGainNodeRef.current.gain.value = TTS_PLAYER_GAIN[playerNameForReply(reply)] ?? 1;
      }
      speechAudioRef.current.volume = 1;
      speechAudioRef.current.src = objectUrl;
      setCurrentTtsReply(reply);
      const ended = new Promise<void>((resolve) => {
        const audio = speechAudioRef.current;
        if (!audio) {
          resolve();
          return;
        }
        const finish = () => {
          audio.removeEventListener("ended", finish);
          audio.removeEventListener("pause", finish);
          resolve();
        };
        audio.addEventListener("ended", finish, { once: true });
        audio.addEventListener("pause", finish, { once: true });
      });
      await speechAudioRef.current.play();
      stopIntroAudio();
      setTtsState("playing");
      await ended;
    } catch (e) {
      if ((e as Error).name === "AbortError") {
        setTtsState("idle");
        return;
      }
      setTtsError((e as Error).message);
      setTtsState("idle");
    } finally {
      if (reply.event_id) {
        ttsPreloadPromisesRef.current.delete(reply.event_id);
      }
      if (speechObjectUrlRef.current === objectUrl) {
        URL.revokeObjectURL(objectUrl);
        speechObjectUrlRef.current = null;
      }
      setCurrentTtsReply((current) => (current?.event_id === reply.event_id ? null : current));
      setTtsState("idle");
    }
  }

  async function playReply(reply = latestEligibleReply, interrupt = true) {
    if (!reply || !reply.text.trim() || !sessionId || !playerNameForReply(reply)) return;
    if (interrupt) {
      stopSpeechPlayback(true);
    }
    setTtsError("");
    setTtsState("loading");
    try {
      const objectUrl = await preloadTtsReply(reply);
      await playPreparedReply(reply, objectUrl);
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setTtsError((e as Error).message);
      }
      setTtsState("idle");
    }
  }

  async function drainTtsQueue() {
    if (ttsProcessingRef.current || !ttsAutoPlay || encounterNoticePlayingRef.current) return;
    ttsProcessingRef.current = true;
    try {
      while (ttsAutoPlay && !encounterNoticePlayingRef.current && ttsQueueRef.current.length) {
        const next = ttsQueueRef.current.shift();
        if (!next) break;
        try {
          setTtsState("loading");
          const objectUrl = await preloadTtsReply(next);
          await playPreparedReply(next, objectUrl);
        } catch (e) {
          if ((e as Error).name !== "AbortError") {
            setTtsError((e as Error).message);
          }
        }
      }
    } finally {
      ttsProcessingRef.current = false;
      if (ttsAutoPlay && !encounterNoticePlayingRef.current && ttsQueueRef.current.length) {
        void drainTtsQueue();
      }
    }
  }

  function enqueueTtsReplies(replies: TranscriptEvent[]) {
    replies.forEach((reply) => {
      if (!reply.event_id || ttsQueuedEventIdsRef.current.has(reply.event_id)) return;
      if (ttsQueueRef.current.length >= TTS_QUEUE_LIMIT) return;
      ttsQueuedEventIdsRef.current.add(reply.event_id);
      ttsQueueRef.current.push(reply);
      void preloadTtsReply(reply);
    });
    void drainTtsQueue();
  }

  useEffect(() => {
    if (!latestEligibleReply?.event_id) return;
    if (!ttsAutoPlay) {
      autoPlayBaselineRef.current = latestEligibleReply.event_id;
      return;
    }
    if (autoPlayBaselineRef.current === null) {
      autoPlayBaselineRef.current = latestEligibleReply.event_id;
      enqueueTtsReplies([latestEligibleReply]);
      return;
    }
    const baselineIndex = transcript.findIndex((event) => event.event_id === autoPlayBaselineRef.current);
    const newReplies = transcript
      .slice(baselineIndex >= 0 ? baselineIndex + 1 : 0)
      .filter((event) => event.role === "agent" && event.text.trim())
      .slice(0, 2);
    if (!newReplies.length) {
      return;
    }
    autoPlayBaselineRef.current = latestEligibleReply.event_id;
    enqueueTtsReplies(newReplies);
  }, [latestEligibleReply?.event_id, transcript.length, ttsAutoPlay]);

  function toggleTtsAutoPlay() {
    setTtsAutoPlay((current) => {
      const next = !current;
      autoPlayBaselineRef.current = latestEligibleReply?.event_id ?? null;
      if (!next) {
        stopSpeechPlayback(true);
      }
      return next;
    });
  }

  function togglePlayer(playerId: string) {
    setSelectedPlayerIds((current) => {
      if (current.includes(playerId)) {
        const next = current.filter((item) => item !== playerId);
        setClassByPlayer((map) => {
          const copy = { ...map };
          delete copy[playerId];
          return copy;
        });
        return next;
      }
      if (current.length >= 4) return current;
      return [...current, playerId];
    });
  }

  function setPlayerClass(playerId: string, classId: string) {
    setClassByPlayer((current) => ({ ...current, [playerId]: classId }));
  }

  function applyRecommendedParty() {
    setSelectedPlayerIds(["Joe", "Annie", "Tammey", "Rick"]);
    setClassByPlayer({
      Joe: "Fighter",
      Annie: "Rogue",
      Tammey: "Cleric",
      Rick: "Ranger",
    });
  }

  const startReady =
    adventureId !== "" &&
    selectedPlayerIds.length === 4 &&
    selectedPlayerIds.every((playerId) => Boolean(classByPlayer[playerId]));

  async function saveTab1(showSpinner = true) {
    if (!sessionId) return null;
    if (showSpinner) {
      setLoading(true);
    }
    setError("");
    try {
      const classAssignments = Object.fromEntries(
        selectedPlayerIds.map((playerId, index) => [String(index + 1), classByPlayer[playerId] ?? ""]),
      );
      const tab1Data = await api<SessionDetail["tab1"]>(`/session/${sessionId}/tab1`, {
        method: "PUT",
        body: JSON.stringify({
          preset_id: "valaska",
          adventure_id: adventureId,
          selected_player_ids: selectedPlayerIds,
          class_assignments: classAssignments,
        }),
      });
      if (tab1Data.active_adventure) {
        setAdventureDetailsById((current) => ({
          ...current,
          [tab1Data.active_adventure!.adventure_id]: tab1Data.active_adventure!,
        }));
      }
      setDetail((current) => (current ? { ...current, tab1: tab1Data } : current));
      return tab1Data;
    } catch (e) {
      setError((e as Error).message);
      return null;
    } finally {
      if (showSpinner) {
        setLoading(false);
      }
    }
  }

  async function startChapter() {
    if (!sessionId) return;
    setChapterStarting(true);
    setLoading(true);
    setError("");
    try {
      const tab1Data = await saveTab1(false);
      if (!tab1Data) {
        return;
      }
      const sessionSummary = await api<SessionDetail["session"]>(`/session/${sessionId}/lock`, { method: "POST" });
      setDetail((current) => (current ? { ...current, session: sessionSummary, tab1: tab1Data } : current));
      setTab(2);
      setPlayedAttackEventIds([]);
      setStarterPromptDismissed(false);
      setIntroAudioPlayed(false);
      void refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setChapterStarting(false);
      setLoading(false);
    }
  }

  async function sendPromptToAgent(agentSlot: number, text: string) {
    if (!sessionId || !text.trim() || !detail || promptNarrationPending) return;
    if (!selectableAgentSlotsForDetail(detail).includes(agentSlot)) return;
    setLoading(true);
    setError("");
    try {
      const response = await api<PromptResponse>(`/session/${sessionId}/prompt`, {
        method: "POST",
        body: JSON.stringify({ agent_slot: agentSlot, user_text: text.trim() }),
      });
      const nextDetail = mergePromptEvents(detail, response);
      setDetail(nextDetail);
      setUserPrompt("");
      setStarterPromptDismissed(true);
      if (nextDetail) {
        setActiveAgentSlot(nextSelectableSlot(nextDetail, agentSlot));
      }
      if (response.narration_pending) {
        setPromptNarrationPending(true);
        void waitForPromptNarration(response.user_event.prompt_index, agentSlot, sessionId).catch((pollError: Error) => {
          setPromptNarrationPending(false);
          setError(pollError.message);
        });
      } else {
        setPromptNarrationPending(false);
      }
      if (response.followup_pending) {
        void waitForPartyFollowups(
          response.user_event.prompt_index,
          response.agent_event?.event_id ?? null,
          response.followup_expected_agent_events ?? 0,
          sessionId,
        ).catch((pollError: Error) => {
          setError(pollError.message);
        });
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function submitPrompt(event: FormEvent) {
    event.preventDefault();
    await sendPromptToAgent(activeAgentSlot, userPrompt);
  }

  async function submitStarterPrompt() {
    if (!detail) return;
    if (onboardingGuideStep === "opposition-prompt") {
      setActiveAgentSlot(OPPOSITION_SLOT);
      setOnboardingGuideStep("complete");
      await sendPromptToAgent(OPPOSITION_SLOT, OPPOSITION_STARTER_PROMPT);
      return;
    }
    const firstPlayerSlot = detail.tab1.selected_agent_slots.find((slot) => slot !== OPPOSITION_SLOT) ?? detail.tab1.party[0]?.slot ?? 1;
    setActiveAgentSlot(firstPlayerSlot);
    setStarterPromptDismissed(true);
    setOnboardingGuideStep((current) => (current === "starter" ? "adventure-map" : current));
    await sendPromptToAgent(firstPlayerSlot, STARTER_PROMPT);
  }

  function dismissOnboardingGuide() {
    setOnboardingGuideStep("complete");
  }

  function setGuidedLocationView(view: "world" | "adventure" | "encounter") {
    setLocationView(view);
    setOnboardingGuideStep((current) => (current === "adventure-map" && view === "adventure" ? "location-one" : current));
  }

  function setGuidedActiveLocationId(locationId: string) {
    setActiveLocationId(locationId);
    setOnboardingGuideStep((current) => {
      if (current !== "location-one") return current;
      const selectedLocationNumber = adventureLocations.find((location) => location.id === locationId)?.number;
      return selectedLocationNumber === 1 ? "travel" : "complete";
    });
  }

  async function endChapter() {
    setLoading(true);
    try {
      await api(`/session/${sessionId}/end`, { method: "POST" });
      await refresh();
      setTab(3);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function takeLongRest() {
    if (!sessionId) return;
    setLongRestLoading(true);
    setError("");
    try {
      const refreshed = await api(`/session/${sessionId}/long-rest`, { method: "POST" });
      await refresh();
      return refreshed;
    } catch (e) {
      setError((e as Error).message);
      return null;
    } finally {
      setLongRestLoading(false);
    }
  }

  async function travelToSelectedLocation() {
    if (!sessionId || !activeLocation) return;
    const traveledLocationTitle = activeLocation.title;
    setOnboardingGuideStep((current) => {
      if (current === "travel" && activeLocation.number === 1) return "trigger-encounter";
      if (current !== "complete") return "complete";
      return current;
    });
    setTravelLoading(true);
    setError("");
    try {
      await api(`/session/${sessionId}/travel`, {
        method: "POST",
        body: JSON.stringify({
          location_id: activeLocation.id,
          location_name: activeLocation.title,
          location_description: activeLocation.description,
        }),
      });
      await refresh();
      setEncounterLocationTitle(traveledLocationTitle);
      setLocationView("encounter");
      setActiveLocationId("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setTravelLoading(false);
    }
  }

  async function returnToMoosehearth() {
    if (!sessionId) return;
    setTravelLoading(true);
    setError("");
    try {
      const sessionSummary = await api<SessionDetail["session"]>(`/session/${sessionId}/return-to-moosehearth`, { method: "POST" });
      setDetail((current) => (current ? { ...current, session: sessionSummary } : current));
      await refresh();
      setEncounterLocationTitle("EndGame Antlers Rest Inn");
      setLocationView("encounter");
      setActiveLocationId("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setTravelLoading(false);
    }
  }

  function cycleEncounterMonster(direction: "previous" | "next") {
    if (!gmMonsters.length) return;
    const currentIndex = gmMonsters.findIndex((monster) => monster.monster_id === encounterMonsterId);
    const safeIndex = currentIndex >= 0 ? currentIndex : 0;
    const offset = direction === "next" ? 1 : -1;
    const nextIndex = (safeIndex + offset + gmMonsters.length) % gmMonsters.length;
    setEncounterMonsterId(gmMonsters[nextIndex].monster_id);
  }

  async function triggerEncounter() {
    if (!sessionId || !selectedEncounterMonster) return;
    const continueGuideToOppositionPrompt = onboardingGuideStep === "start-encounter";
    setSpawnLoading(true);
    setError("");
    try {
      await api(`/session/${sessionId}/spawn-opposition`, {
        method: "POST",
        body: JSON.stringify({
          monster_type: selectedEncounterMonster.monster_id,
          quantity: encounterQuantity,
        }),
      });
      const refreshed = await refresh();
      setEncounterModalOpen(false);
      setLocationView("encounter");
      setActiveAgentSlot(activeOpposition?.active ? activeAgentSlot : (refreshed.session.opposition_state?.active ? OPPOSITION_SLOT : activeAgentSlot));
      setOnboardingGuideStep((current) => (
        continueGuideToOppositionPrompt && current === "start-encounter" && refreshed.session.opposition_state?.active
          ? "opposition-prompt"
          : "complete"
      ));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSpawnLoading(false);
    }
  }

  async function fleeEncounter() {
    if (!sessionId) return;
    setDismissLoading(true);
    setError("");
    try {
      await api(`/session/${sessionId}/dismiss-opposition`, { method: "POST" });
      const refreshed = await refresh();
      if (activeAgentSlot === OPPOSITION_SLOT) {
        setActiveAgentSlot(selectableAgentSlotsForDetail(refreshed)[0] ?? 1);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDismissLoading(false);
    }
  }

  async function searchLocation() {
    if (!sessionId) return;
    setLoading(true);
    setError("");
    try {
      const sessionSummary = await api<SessionDetail["session"]>(`/session/${sessionId}/search`, {
        method: "POST",
        body: JSON.stringify({ agent_slot: activeAgentSlot, skill: "Perception" }),
      });
      setDetail((current) => (current ? { ...current, session: sessionSummary } : current));
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function useSelectedItem(itemName: string, targetId = "") {
    if (!sessionId || !itemName) return;
    setLoading(true);
    setError("");
    try {
      const sessionSummary = await api<SessionDetail["session"]>(`/session/${sessionId}/use-item`, {
        method: "POST",
        body: JSON.stringify({ agent_slot: activeAgentSlot, item_name: itemName, target_id: targetId || `pc:${activeAgentSlot}` }),
      });
      setDetail((current) => (current ? { ...current, session: sessionSummary } : current));
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function submitFeedback() {
    if (!sessionId || !feedbackText.trim()) return;
    setFeedbackSubmitting(true);
    setError("");
    try {
      const response = await api<FeedbackCreateResponse>(`/session/${sessionId}/feedback`, {
        method: "POST",
        body: JSON.stringify({ feedback_text: feedbackText.trim() }),
      });
      setFeedbackSubmittedAt(response.created_at);
      setFeedbackText("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setFeedbackSubmitting(false);
    }
  }

  async function resetChapter() {
    if (!window.confirm("Reset the current session?")) return;
    setLoading(true);
    try {
      await api(`/session/${sessionId}/reset`, { method: "POST" });
      setPlayedAttackEventIds([]);
      setStarterPromptDismissed(false);
      setIntroAudioPlayed(false);
      setOnboardingGuideStep("starter");
      await refresh();
      setTab(1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function startOver() {
    window.location.reload();
  }

  function enterApp() {
    window.localStorage.setItem("story-engine-mk5-splash-seen", "true");
    setSplashOpen(false);
  }

  function replaySplash() {
    setSplashOpen(true);
  }

  if (!catalogBoot || !detail) {
    return <div className="loading-shell">Loading Story Engine MK5...</div>;
  }

  const tutorialEmbedUrl = youtubeEmbedUrl(TUTORIAL_VIDEO_URL);
  const showStarterPrompt = Boolean(
    detail.session.state === "ACTIVE"
    && detail.session.prompt_index === 0
    && !userPrompt.trim()
    && !promptNarrationPending
    && !starterPromptDismissed,
  );
  const showOppositionStarterPrompt = Boolean(
    detail.session.state === "ACTIVE"
    && onboardingGuideStep === "opposition-prompt"
    && activeOpposition?.active
    && activeAgentSlot === OPPOSITION_SLOT
    && !userPrompt.trim()
    && !promptNarrationPending,
  );
  const activeOnboardingGuideStep = showStarterPrompt || showOppositionStarterPrompt || onboardingGuideStep !== "starter" ? onboardingGuideStep : "complete";
  const starterPromptText = showOppositionStarterPrompt
    ? OPPOSITION_STARTER_PROMPT
    : (showStarterPrompt ? STARTER_PROMPT : "");

  return (
    <div className="page">
      {splashOpen && (
        <div className="splash-overlay" role="dialog" aria-modal="true" aria-label="Story Engine tutorial">
          <div className="splash-card splash-card--tutorial">
            <div className="splash-copy">
              <div className="eyebrow">Story Engine MK5</div>
              <h1>Welcome to Valaska</h1>
              <p>Watch the quick tutorial, then enter the adventure console to choose a mission, build the party, and begin play.</p>
            </div>
            <div className="tutorial-video-frame">
              {tutorialEmbedUrl ? (
                <iframe
                  src={tutorialEmbedUrl}
                  title="Story Engine MK5 tutorial video"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                  allowFullScreen
                />
              ) : (
                <div className="tutorial-video-placeholder">
                  <strong>Tutorial video not configured</strong>
                  <span>Set VITE_TUTORIAL_VIDEO_URL to a YouTube link and rebuild the frontend container.</span>
                </div>
              )}
            </div>
            <div className="splash-legal-placeholder">
              Legal and advertising notices will live here before public release.
            </div>
            <div className="action-row">
              <button className="btn accent" type="button" onClick={enterApp}>Enter Story Engine</button>
            </div>
          </div>
        </div>
      )}

      <audio
        ref={audioRef}
        key={currentTrack}
        preload="metadata"
        src={currentTrack}
        loop={currentMusicTracks.length === 1}
        onError={() => setError(`Unable to load music track: ${currentTrack}`)}
        onEnded={() => setMusicTrackIndex((current) => (current + 1) % currentMusicTracks.length)}
      >
        <source src={currentTrack} type="audio/mpeg" />
      </audio>

      <header className="hero hero--phase1">
        <div>
          <div className="eyebrow">Story Engine MK5</div>
          <h1 className="hero-title">{headerAdventureTitle}</h1>
          <p className="hero-copy">Preparation, adventure play, and feedback now follow a simpler phase-by-phase layout built around the mission map, location cell, and GM prompting.</p>
        </div>
        <div className="status-strip status-strip--compact">
          <div className="status-card">
            <span>Music</span>
            <strong>{musicAutoplayBlocked ? "Enable Music" : `${musicPlaying ? "Playing" : "Paused"} - ${MUSIC_CUE_LABELS[musicCue]}`}</strong>
            <div className="music-controls">
              <button className="btn music-btn" type="button" onClick={() => void toggleMusicPlayback()}>
                {musicAutoplayBlocked ? "Enable Music" : musicPlaying ? "Pause" : "Play"}
              </button>
              <button className="btn music-btn" type="button" onClick={toggleMusicMuted}>
                {musicMuted ? "Unmute" : "Mute"}
              </button>
              <button className="btn music-btn" type="button" onClick={replaySplash}>
                Tutorial
              </button>
            </div>
            <div className="mobile-tts-controls">
              <span className={`tts-status tts-status--${ttsState}`}>AI Voice: {TTS_STATUS_LABELS[ttsState]}</span>
              <button className="btn music-btn" type="button" onClick={() => void playReply()} disabled={!latestEligibleReply || ttsState === "loading"}>
                Play
              </button>
              <button
                className={ttsAutoPlay ? "btn music-btn accent-toggle active" : "btn music-btn accent-toggle"}
                type="button"
                onClick={toggleTtsAutoPlay}
              >
                Auto: {ttsAutoPlay ? "On" : "Off"}
              </button>
            </div>
          </div>
        </div>
      </header>

      <nav className="tabs">
        <button className={tab === 1 ? "tab active" : "tab"} onClick={() => setTab(1)}>Preparation</button>
        <button className={tab === 2 ? "tab active" : "tab"} onClick={() => setTab(2)} disabled={!detail.session.tab1_locked}>Adventure</button>
        <button className={tab === 3 ? "tab active" : "tab"} onClick={() => setTab(3)} disabled={!detail.session.tab1_locked}>Feedback</button>
      </nav>

      {error && <div className="error-banner">{error}</div>}

      {tab === 1 && (
        <PreparationTab
          catalogBoot={catalogBoot}
          detail={detail}
          adventureId={adventureId}
          setAdventureId={setAdventureId}
          selectedPlayerIds={selectedPlayerIds}
          classByPlayer={classByPlayer}
          selectedAdventureSummary={selectedAdventureSummary}
          selectedAdventure={selectedAdventure}
          loading={loading}
          chapterStarting={chapterStarting}
          startReady={startReady}
          startChapterHint={startChapterHint}
          loadingPulse={loadingPulse}
          onTogglePlayer={togglePlayer}
          onSetPlayerClass={setPlayerClass}
          onApplyRecommendedParty={applyRecommendedParty}
          onStartChapter={() => void startChapter()}
          onResetChapter={() => void resetChapter()}
          displayAdventureTitle={displayAdventureTitle}
        />
      )}

      {tab === 2 && (
        <div ref={adventureTabTopRef}>
          <AdventureTab
            detail={detail}
            transcript={transcript}
            transcriptChars={transcriptChars}
            transcriptRef={transcriptRef}
            latestEligibleReply={latestEligibleReply}
            currentTtsReply={currentTtsReply}
            ttsState={ttsState}
            ttsAutoPlay={ttsAutoPlay}
            ttsStatusLabels={TTS_STATUS_LABELS}
            ttsError={ttsError}
            userPrompt={userPrompt}
            activeAgentSlot={activeAgentSlot}
            activeOpposition={activeOpposition}
            locationOppositionState={oppositionState}
            activeLocation={activeLocation}
            adventureLocations={adventureLocations}
            gmMonsters={gmMonsters}
            encounterModalOpen={encounterModalOpen}
            encounterMonsterId={encounterMonsterId}
            encounterMonsterIndex={encounterMonsterIndex}
            encounterQuantity={encounterQuantity}
            selectedEncounterMonster={selectedEncounterMonster}
            loading={loading || spawnLoading || dismissLoading || promptNarrationPending}
            longRestLoading={longRestLoading}
            travelLoading={travelLoading}
            allPlayersDown={allPlayersDown}
            worldMapImageUrl={catalogBoot.map_image_url}
            encounterImageUrl={encounterLocationImageUrl}
            encounterLocationTitle={encounterLocationTitle}
            locationView={locationView}
            onboardingGuideStep={activeOnboardingGuideStep}
            playedAttackEventIds={playedAttackEventIds}
            animationLocked={animationLocked}
            onPlayReply={() => void playReply()}
            onAnimationStateChange={setAnimationLocked}
            onAnimationSettled={refresh}
            onMarkAttackAnimationPlayed={(eventId) => {
              setPlayedAttackEventIds((current) => (
                current.includes(eventId) ? current : [...current, eventId]
              ));
            }}
            onToggleTtsAutoPlay={toggleTtsAutoPlay}
            onSubmitPrompt={submitPrompt}
            onSetUserPrompt={setUserPrompt}
            starterPromptText={starterPromptText}
            onSubmitStarterPrompt={() => void submitStarterPrompt()}
            onDismissStarterPrompt={() => {
              setStarterPromptDismissed(true);
              dismissOnboardingGuide();
            }}
            onSetActiveAgentSlot={setActiveAgentSlot}
            onTakeLongRest={() => void takeLongRest()}
            onEndChapter={() => void endChapter()}
            onSetLocationView={setGuidedLocationView}
            onSetActiveLocationId={setGuidedActiveLocationId}
            onTravelToSelectedLocation={() => void travelToSelectedLocation()}
            onReturnToMoosehearth={() => void returnToMoosehearth()}
            onOpenEncounterModal={() => {
              setEncounterModalOpen(true);
              setOnboardingGuideStep((current) => (current === "trigger-encounter" ? "start-encounter" : "complete"));
            }}
            onCloseEncounterModal={() => setEncounterModalOpen(false)}
            onSetEncounterMonsterId={setEncounterMonsterId}
            onCycleEncounterMonster={cycleEncounterMonster}
            onSetEncounterQuantity={setEncounterQuantity}
            onTriggerEncounter={() => void triggerEncounter()}
            onFleeEncounter={() => void fleeEncounter()}
            onSearchLocation={() => void searchLocation()}
            onUseItem={(itemName, targetId) => void useSelectedItem(itemName, targetId)}
            onStartOver={startOver}
            displayAdventureTitle={displayAdventureTitle}
          />
        </div>
      )}

      {tab === 3 && (
        <FeedbackTab
          detail={detail}
          feedbackText={feedbackText}
          feedbackSubmitting={feedbackSubmitting}
          feedbackSubmittedAt={feedbackSubmittedAt}
          selectedAdventure={selectedAdventure}
          selectedAdventureSummary={selectedAdventureSummary}
          onSetFeedbackText={setFeedbackText}
          onSubmitFeedback={() => void submitFeedback()}
          displayAdventureTitle={displayAdventureTitle}
        />
      )}
    </div>
  );
}
