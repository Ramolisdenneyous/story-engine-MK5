import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { api, apiBlob, resolveApiUrl } from "./api";

type SessionState = "DRAFT_TAB1" | "LOCKING" | "ACTIVE" | "SUMMARIZING" | "ENDED" | "NARRATING" | "RESETTING";

type Catalog = {
  preset_id: string;
  preset_name: string;
  map_image_url: string;
  adventure_selection_image_url: string;
  default_image_url: string;
  adventures: Adventure[];
  players: PlayerCatalog[];
  classes: ClassCatalog[];
  monsters: Monster[];
};

type Adventure = {
  adventure_id: string;
  title: string;
  description: string;
  objectives: Array<{ id: string; description: string; status: string }>;
  monsters: string[];
  map_image_url: string;
  locations: AdventureLocation[];
};

type AdventureLocation = {
  id: string;
  number: number;
  title: string;
  description: string;
  x_pct: number;
  y_pct: number;
};

type PlayerCatalog = {
  player_id: string;
  name: string;
  archetype: string;
  gender: string;
  race: string;
  irl_job: string;
  keywords: string[];
  display_text: string;
  image_url: string;
};

type ClassCatalog = {
  class_id: string;
  name: string;
  role: string;
  armor_class: number;
  hp_max: number;
};

type Monster = {
  monster_id: string;
  ac: number;
  hp: number;
  attack_bonus: number;
  attack_text: string;
  image_url: string;
};

type CombatState = {
  in_combat: boolean;
  round: number;
  turn_index: number;
  initiative_order: string[];
  initiative_values: Record<string, number>;
};

type OppositionMonsterInstance = {
  monster_id: string;
  display_name: string;
  current_hp: number;
  hp_max: number;
  is_dead: boolean;
  status_effects: string[];
};

type OppositionState = {
  active: boolean;
  group_id: string;
  initiative_id: string;
  monster_type: string;
  monster_stats: Record<string, unknown>;
  instances: OppositionMonsterInstance[];
};

type PartyMember = {
  slot: number;
  player_id: string;
  player_name: string;
  class_id: string;
  portrait_url: string;
  base_portrait_url: string;
  race: string;
  archetype: string;
  keywords: string[];
  armor_class: number;
  hp_max: number;
  hp_current: number;
  status_effects: string[];
  inventory: string[];
  initiative: number | null;
};

type SessionDetail = {
  session: {
    session_id: string;
    state: SessionState;
    prompt_index: number;
    last_summarized_prompt_index: number;
    tab1_locked: boolean;
    combat_state: CombatState;
    selected_narrative_player_id: string;
    opposition_state?: OppositionState | null;
  };
  tab1: {
    preset_id: string;
    adventure_id: string;
    selected_player_ids: string[];
    class_assignments: Record<number, string>;
    selected_agent_slots: number[];
    agent_names: Record<number, string>;
    tab1_locked: boolean;
    party: PartyMember[];
    active_adventure: Adventure | null;
  };
  events: Array<{
    event_id: string;
    prompt_index: number;
    role: "user" | "agent" | "system";
    kind: string;
    agent_slot: number | null;
    text: string;
    json_payload: Record<string, unknown>;
    created_at: string;
  }>;
  memory_blocks: Array<{
    block_id: string;
    type: string;
    from_prompt_index: number;
    to_prompt_index: number;
    json_payload: Record<string, unknown>;
  }>;
  narrative_drafts: Array<{ draft_id: string; chapter_text: string }>;
  image_state: { image_url: string; prompt_text: string; last_actor_slot: number | null };
  gm_monsters: Monster[];
};

const SLOT_COLORS: Record<number, string> = {
  1: "#f56f7e",
  2: "#ff9e4a",
  3: "#f4cf59",
  4: "#60d48f",
  12: "#69b7ff",
};
const OPPOSITION_SLOT = 12;

const MUSIC_TRACKS = [
  "Citadel of Rusted Banners (1).mp3",
  "Citadel of Rusted Banners.mp3",
  "Cursed Village Menu (1).mp3",
  "Cursed Village Menu.mp3",
  "Gallows of the Forgotten King.mp3",
].map((fileName) => resolveApiUrl(`/music/${encodeURIComponent(fileName)}`));
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
} as const;

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

const MUSIC_VOLUME = 0.1;
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

export function App() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const transcriptRef = useRef<HTMLDivElement | null>(null);
  const speechAudioRef = useRef<HTMLAudioElement | null>(null);
  const speechAudioContextRef = useRef<AudioContext | null>(null);
  const speechGainNodeRef = useRef<GainNode | null>(null);
  const speechSourceNodeRef = useRef<MediaElementAudioSourceNode | null>(null);
  const speechObjectUrlRef = useRef<string | null>(null);
  const speechAbortRef = useRef<AbortController | null>(null);
  const autoPlayBaselineRef = useRef<string | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [sessionId, setSessionId] = useState("");
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [tab, setTab] = useState<1 | 2 | 3>(1);
  const [loading, setLoading] = useState(false);
  const [chapterStarting, setChapterStarting] = useState(false);
  const [chapterLoadingFrame, setChapterLoadingFrame] = useState(0);
  const [imageLoading, setImageLoading] = useState(false);
  const [narrativeBuilding, setNarrativeBuilding] = useState(false);
  const [error, setError] = useState("");
  const [adventurePickerOpen, setAdventurePickerOpen] = useState(false);
  const [trackIndex, setTrackIndex] = useState(0);
  const [musicPlaying, setMusicPlaying] = useState(false);
  const [musicMuted, setMusicMuted] = useState(false);
  const [adventureId, setAdventureId] = useState("");
  const [selectedPlayerIds, setSelectedPlayerIds] = useState<string[]>([]);
  const [classByPlayer, setClassByPlayer] = useState<Record<string, string>>({});
  const [activeAgentSlot, setActiveAgentSlot] = useState(1);
  const [activeMonsterCardIndex, setActiveMonsterCardIndex] = useState(0);
  const [activeLocationId, setActiveLocationId] = useState("");
  const [userPrompt, setUserPrompt] = useState("");
  const [selectedNarrativePlayerId, setSelectedNarrativePlayerId] = useState("");
  const [ttsAutoPlay, setTtsAutoPlay] = useState(false);
  const [ttsState, setTtsState] = useState<"idle" | "loading" | "playing">("idle");
  const [ttsError, setTtsError] = useState("");
  const [travelLoading, setTravelLoading] = useState(false);
  const [longRestLoading, setLongRestLoading] = useState(false);
  const [oppositionQuantity, setOppositionQuantity] = useState(1);
  const [spawnLoading, setSpawnLoading] = useState(false);
  const [dismissLoading, setDismissLoading] = useState(false);

  async function boot() {
    setLoading(true);
    setError("");
    try {
      const [catalogData, created] = await Promise.all([
        api<Catalog>("/catalog"),
        api<{ session_id: string }>("/session", { method: "POST" }),
      ]);
      setCatalog(catalogData);
      setSessionId(created.session_id);
      await refresh(created.session_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function refresh(id = sessionId) {
    const data = await api<SessionDetail>(`/session/${id}`);
    setDetail(data);
    setAdventureId(data.tab1.adventure_id);
    setSelectedPlayerIds(data.tab1.selected_player_ids);
    const byPlayer: Record<string, string> = {};
    data.tab1.party.forEach((member) => {
      byPlayer[member.player_id] = member.class_id;
    });
    setClassByPlayer(byPlayer);
    setSelectedNarrativePlayerId(data.session.selected_narrative_player_id);
    if (!data.tab1.selected_agent_slots.includes(activeAgentSlot)) {
      setActiveAgentSlot(data.tab1.selected_agent_slots[0] ?? 1);
    }
  }

  useEffect(() => {
    void boot();
  }, []);

  const transcript = useMemo(() => {
    if (!detail) return [];
    return detail.events
      .filter((event) => event.kind === "transcript")
      .map((event) => ({ ...event, text: sanitizeVisibleAgentText(event.text) }));
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
    const audio = audioRef.current;
    if (!audio) return;
    audio.load();
    audio.volume = MUSIC_VOLUME;
    audio.muted = musicMuted;
    if (musicPlaying) {
      void audio.play().catch(() => {
        setMusicPlaying(false);
      });
    } else {
      audio.pause();
    }
  }, [trackIndex, musicPlaying, musicMuted]);

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

  async function toggleMusicPlayback() {
    const audio = audioRef.current;
    if (!audio) return;
    if (musicPlaying) {
      audio.pause();
      setMusicPlaying(false);
      return;
    }
    try {
      audio.muted = musicMuted;
      await audio.play();
      setMusicPlaying(true);
    } catch (e) {
      setError((e as Error).message || "Unable to start music playback.");
    }
  }

  function toggleMusicMuted() {
    const audio = audioRef.current;
    const nextMuted = !musicMuted;
    if (audio) {
      audio.muted = nextMuted;
    }
    setMusicMuted(nextMuted);
  }

  const selectedAdventure = useMemo(
    () => catalog?.adventures.find((item) => item.adventure_id === adventureId) ?? null,
    [adventureId, catalog],
  );
  const currentTrack = MUSIC_TRACKS[trackIndex] ?? "";
  const startRequirements = [
    adventureId === "" ? "select an adventure" : null,
    selectedPlayerIds.length < 4 ? "select four players" : null,
    selectedPlayerIds.some((playerId) => !classByPlayer[playerId]) ? "assign a class to each selected player" : null,
  ].filter(Boolean) as string[];
  const startChapterHint = startRequirements.length
    ? `Before you can start the chapter, please ${startRequirements.join(", ")}.`
    : "Ready to begin the adventure.";

  const transcriptChars = transcript.reduce((sum, event) => sum + event.text.length + 1, 0);
  const latestDraft = detail?.narrative_drafts.length ? detail.narrative_drafts[detail.narrative_drafts.length - 1] : null;
  const gmMonsters = detail?.gm_monsters ?? [];
  const activeMonsterCard = gmMonsters[activeMonsterCardIndex] ?? null;
  const oppositionState = detail?.session.opposition_state ?? null;
  const activeOpposition = oppositionState?.active ? oppositionState : null;
  const activeOppositionInstances = activeOpposition?.instances ?? [];
  const adventureLocations = detail?.tab1.active_adventure?.locations ?? [];
  const activeLocation =
    adventureLocations.find((location) => location.id === activeLocationId) ??
    adventureLocations[0] ??
    null;
  const loadingPulse = [".", "..", "..."][chapterLoadingFrame % 3];
  const activeMonsterCardInstances =
    activeOpposition && activeMonsterCard?.monster_id === activeOpposition.monster_type ? activeOppositionInstances : [];

  function displayAdventureTitle(adventure: Adventure | null) {
    if (!adventure) return "";
    return ADVENTURE_TITLE_OVERRIDES[adventure.adventure_id] ?? adventure.title;
  }

  useEffect(() => {
    setActiveMonsterCardIndex(0);
  }, [detail?.tab1.adventure_id]);

  useEffect(() => {
    const firstLocationId = detail?.tab1.active_adventure?.locations?.[0]?.id ?? "";
    setActiveLocationId(firstLocationId);
  }, [detail?.tab1.adventure_id]);

  function stopSpeechPlayback() {
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
    setTtsState("idle");
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

  async function playReply(reply = latestEligibleReply) {
    if (!reply || !reply.text.trim() || !sessionId) return;
    const playerName =
      reply.agent_slot === OPPOSITION_SLOT
        ? "Opposition"
        : reply.agent_slot
          ? playerNameBySlot.get(reply.agent_slot) ?? ""
          : "";
    if (!playerName) return;

    stopSpeechPlayback();
    const controller = new AbortController();
    speechAbortRef.current = controller;
    setTtsError("");
    setTtsState("loading");

    try {
      const blob = await apiBlob(`/session/${sessionId}/tts`, {
        method: "POST",
        body: JSON.stringify({
          text: reply.text,
          player_name: playerName,
        }),
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      const objectUrl = URL.createObjectURL(blob);
      speechObjectUrlRef.current = objectUrl;
      if (!speechAudioRef.current) {
        speechAudioRef.current = new Audio();
      }
      await ensureSpeechGainChain();
      if (speechGainNodeRef.current) {
        speechGainNodeRef.current.gain.value = TTS_PLAYER_GAIN[playerName] ?? 1;
      }
      speechAudioRef.current.volume = 1;
      speechAudioRef.current.src = objectUrl;
      await speechAudioRef.current.play();
      setTtsState("playing");
    } catch (e) {
      if ((e as Error).name === "AbortError") {
        return;
      }
      setTtsError((e as Error).message);
      setTtsState("idle");
    } finally {
      if (speechAbortRef.current === controller) {
        speechAbortRef.current = null;
      }
    }
  }

  useEffect(() => {
    if (!latestEligibleReply?.event_id) return;
    if (!ttsAutoPlay) {
      autoPlayBaselineRef.current = latestEligibleReply.event_id;
      return;
    }
    if (autoPlayBaselineRef.current === null) {
      autoPlayBaselineRef.current = latestEligibleReply.event_id;
      if (ttsState !== "idle") {
        return;
      }
      void playReply(latestEligibleReply);
      return;
    }
    if (latestEligibleReply.event_id === autoPlayBaselineRef.current) {
      return;
    }
    autoPlayBaselineRef.current = latestEligibleReply.event_id;
    if (ttsState !== "idle") {
      return;
    }
    void playReply(latestEligibleReply);
  }, [latestEligibleReply?.event_id, ttsAutoPlay, ttsState]);

  function toggleTtsAutoPlay() {
    setTtsAutoPlay((current) => {
      const next = !current;
      autoPlayBaselineRef.current = next ? latestEligibleReply?.event_id ?? null : latestEligibleReply?.event_id ?? null;
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

  const startReady =
    adventureId !== "" &&
    selectedPlayerIds.length === 4 &&
    selectedPlayerIds.every((playerId) => Boolean(classByPlayer[playerId]));

  async function saveTab1() {
    if (!sessionId) return;
    setLoading(true);
    setError("");
    try {
      const class_assignments = Object.fromEntries(
        selectedPlayerIds.map((playerId, index) => [String(index + 1), classByPlayer[playerId] ?? ""]),
      );
      await api(`/session/${sessionId}/tab1`, {
        method: "PUT",
        body: JSON.stringify({
          preset_id: "valaska",
          adventure_id: adventureId,
          selected_player_ids: selectedPlayerIds,
          class_assignments,
        }),
      });
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function startChapter() {
    setChapterStarting(true);
    await saveTab1();
    setLoading(true);
    try {
      await api(`/session/${sessionId}/lock`, { method: "POST" });
      await refresh();
      setTab(2);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setChapterStarting(false);
      setLoading(false);
    }
  }

  function orderedAgentSlots(): number[] {
    const currentDetail = detail;
    if (!currentDetail) return [1, 2, 3, 4];
    if (currentDetail.session.combat_state.in_combat) {
      return currentDetail.session.combat_state.initiative_order
        .map((item) => {
          if (item === "opp:12") return OPPOSITION_SLOT;
          if (item.startsWith("pc:")) return Number(item.replace("pc:", ""));
          return Number(item);
        })
        .filter((slot) => Number.isFinite(slot));
    }
    return currentDetail.tab1.selected_agent_slots;
  }

  async function submitPrompt(event: FormEvent) {
    event.preventDefault();
    if (!sessionId || !userPrompt.trim()) return;
    setLoading(true);
    setError("");
    try {
      await api(`/session/${sessionId}/prompt`, {
        method: "POST",
        body: JSON.stringify({ agent_slot: activeAgentSlot, user_text: userPrompt }),
      });
      setUserPrompt("");
      await refresh();
      const order = orderedAgentSlots();
      const index = order.indexOf(activeAgentSlot);
      setActiveAgentSlot(order[(index + 1 + order.length) % order.length] ?? order[0] ?? 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
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

  async function rollInitiative() {
    setLoading(true);
    try {
      await api(`/session/${sessionId}/roll-initiative`, { method: "POST" });
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function generateImage() {
    setImageLoading(true);
    setError("");
    try {
      await api(`/session/${sessionId}/generate-image`, { method: "POST" });
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setImageLoading(false);
    }
  }

  async function takeLongRest() {
    if (!sessionId) return;
    setLongRestLoading(true);
    setError("");
    try {
      await api(`/session/${sessionId}/long-rest`, { method: "POST" });
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLongRestLoading(false);
    }
  }

  async function travelToSelectedLocation() {
    if (!sessionId || !activeLocation) return;
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
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setTravelLoading(false);
    }
  }

  async function spawnOpposition() {
    if (!sessionId || !activeMonsterCard) return;
    setSpawnLoading(true);
    setError("");
    try {
      await api(`/session/${sessionId}/spawn-opposition`, {
        method: "POST",
        body: JSON.stringify({
          monster_type: activeMonsterCard.monster_id,
          quantity: oppositionQuantity,
        }),
      });
      await refresh();
      setActiveAgentSlot(OPPOSITION_SLOT);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSpawnLoading(false);
    }
  }

  async function dismissOpposition() {
    if (!sessionId) return;
    setDismissLoading(true);
    setError("");
    try {
      await api(`/session/${sessionId}/dismiss-opposition`, { method: "POST" });
      await refresh();
      if (activeAgentSlot === OPPOSITION_SLOT) {
        setActiveAgentSlot(1);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDismissLoading(false);
    }
  }

  async function saveNarrativeLens() {
    setLoading(true);
    try {
      await api(`/session/${sessionId}/narrative-agent`, {
        method: "PUT",
        body: JSON.stringify({ selected_player_id: selectedNarrativePlayerId }),
      });
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function buildNarrative() {
    await saveNarrativeLens();
    setLoading(true);
    setNarrativeBuilding(true);
    try {
      await api(`/session/${sessionId}/build-narrative`, { method: "POST" });
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setNarrativeBuilding(false);
      setLoading(false);
    }
  }

  async function resetChapter() {
    if (!window.confirm("Reset the current session?")) return;
    setLoading(true);
    try {
      await api(`/session/${sessionId}/reset`, { method: "POST" });
      await refresh();
      setTab(1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function downloadChapter() {
    const chapterText = latestDraft?.chapter_text ?? "";
    const blob = new Blob([chapterText], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `chapter-${sessionId || "mk3"}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  if (!catalog || !detail) {
    return <div className="loading-shell">Loading Story Engine MK3...</div>;
  }

  return (
    <div className="page">
      <audio
        ref={audioRef}
        key={currentTrack}
        preload="metadata"
        src={currentTrack}
        onError={() => setError(`Unable to load music track: ${currentTrack}`)}
        onEnded={() => setTrackIndex((current) => (current + 1) % MUSIC_TRACKS.length)}
      >
        <source src={currentTrack} type="audio/mpeg" />
      </audio>
      <header className="hero">
        <div>
          <div className="eyebrow">Story Engine MK3</div>
          <h1 className="hero-title">Valaska Adventure Console</h1>
          <p className="hero-copy">Guided party preparation, GM-first adventure play, and a cleaner wrap-up flow for first-time users.</p>
        </div>
        <div className="status-strip">
          <div className="status-card"><span>Session</span><strong>{sessionId}</strong></div>
          <div className="status-card"><span>State</span><strong>{detail.session.state}</strong></div>
          <div className="status-card"><span>Round</span><strong>{detail.session.combat_state.in_combat ? detail.session.combat_state.round : "-"}</strong></div>
          <div className="status-card">
            <span>Music</span>
            <strong>{musicPlaying ? "Playing" : "Paused"}</strong>
            <div className="music-controls">
              <button className="btn music-btn" type="button" onClick={() => void toggleMusicPlayback()}>
                {musicPlaying ? "Pause" : "Play"}
              </button>
              <button className="btn music-btn" type="button" onClick={toggleMusicMuted}>
                {musicMuted ? "Unmute" : "Mute"}
              </button>
            </div>
          </div>
        </div>
      </header>

      <nav className="tabs">
        <button className={tab === 1 ? "tab active" : "tab"} onClick={() => setTab(1)}>Preparation</button>
        <button className={tab === 2 ? "tab active" : "tab"} onClick={() => setTab(2)} disabled={!detail.session.tab1_locked}>Adventure</button>
        <button className={tab === 3 ? "tab active" : "tab"} onClick={() => setTab(3)} disabled={!detail.session.tab1_locked}>Wrap Up</button>
      </nav>

      {error && <div className="error-banner">{error}</div>}

      {tab === 1 && (
        <section className="panel">
          <div className="panel-grid panel-grid--tab1">
            <article className="card map-card">
              <div className="card-head"><span>Start Here</span><h2>Setting Map</h2></div>
              <img
                className="media"
                src={resolveApiUrl(adventurePickerOpen ? catalog.adventure_selection_image_url : catalog.map_image_url)}
                alt="Valaska"
              />
              <p className="card-copy">The setting is fixed to Valaska. Moosehearth is the starting town for every session.</p>
            </article>

            <article className="card" onMouseEnter={() => setAdventurePickerOpen(true)} onMouseLeave={() => setAdventurePickerOpen(false)}>
              <div className="card-head"><span>Choose A Mission</span><h2>Adventure Selection</h2></div>
              <div className="adventure-list">
                {catalog.adventures.map((adventure) => (
                  <button
                    key={adventure.adventure_id}
                    className={adventureId === adventure.adventure_id ? "adventure-card selected" : "adventure-card"}
                    onClick={() => setAdventureId(adventure.adventure_id)}
                  >
                    <strong>{displayAdventureTitle(adventure)}</strong>
                    <p>{adventure.description}</p>
                  </button>
                ))}
              </div>
            </article>

            <article className="card">
              <div className="card-head"><span>Build The Party</span><h2>Player Selection</h2></div>
              <div className="player-grid">
                {catalog.players.map((player) => {
                  const selected = selectedPlayerIds.includes(player.player_id);
                  return (
                    <button key={player.player_id} className={selected ? "player-tile selected" : "player-tile"} onClick={() => togglePlayer(player.player_id)}>
                      <img src={resolveApiUrl(player.image_url)} alt={player.name} />
                      <strong>{player.name}</strong>
                      <span>{player.keywords.join(" • ")}</span>
                    </button>
                  );
                })}
              </div>
            </article>

            <article className="card">
              <div className="card-head"><span>Finalize Loadouts</span><h2>Player Class Selection</h2></div>
              <div className="class-grid">
                {selectedPlayerIds.map((playerId, index) => {
                  const player = catalog.players.find((entry) => entry.player_id === playerId)!;
                  const selectedClassId = classByPlayer[playerId] ?? "";
                  const portrait = detail.tab1.party.find((member) => member.player_id === playerId)?.portrait_url ?? player.image_url;
                  return (
                    <div key={playerId} className={selectedClassId ? "class-card selected" : "class-card"}>
                      <img src={resolveApiUrl(selectedClassId ? portrait : player.image_url)} alt={player.name} />
                      <div>
                        <strong>{index + 1}. {player.name}</strong>
                        <p>{player.archetype} • {player.race}</p>
                      </div>
                      <select value={selectedClassId} onChange={(e) => setPlayerClass(playerId, e.target.value)}>
                        <option value="">Choose class</option>
                        {catalog.classes.map((classItem) => <option key={classItem.class_id} value={classItem.class_id}>{classItem.name}</option>)}
                      </select>
                    </div>
                  );
                })}
              </div>
            </article>
          </div>

          {selectedAdventure && (
            <div className="summary-bar">
              <strong>{displayAdventureTitle(selectedAdventure)}</strong>
              <span>{selectedAdventure.objectives.map((objective) => objective.description).join(" | ")}</span>
            </div>
          )}

          <div className="action-row">
            <button className="btn" onClick={() => void saveTab1()} disabled={loading}>Save Page</button>
            {!detail.session.tab1_locked && (
              <span className="button-tooltip-wrap" title={loading || startReady ? "" : startChapterHint}>
                <button className="btn accent" onClick={() => void startChapter()} disabled={loading || !startReady}>Start Chapter</button>
              </span>
            )}
            {detail.session.tab1_locked && <button className="btn danger" onClick={() => void resetChapter()} disabled={loading}>Reset Chapter</button>}
          </div>
          {chapterStarting && <p className="chapter-loading-notice">Adventure Loading{loadingPulse}</p>}
          {!detail.session.tab1_locked && !startReady && <p className="inline-guidance">{startChapterHint}</p>}
        </section>
      )}

      {tab === 2 && (
        <section className="panel">
          <div className="panel-grid panel-grid--top">
            <article className="card transcript-card">
              <div className="card-head">
                <span>Live Session</span>
                <h2>Adventure Log</h2>
                <small>{transcriptChars} chars</small>
                <div className="card-head-actions">
                  <span className={`tts-status tts-status--${ttsState}`}>AI Voice: {TTS_STATUS_LABELS[ttsState]}</span>
                  <button className="btn btn-small" type="button" onClick={() => void playReply()} disabled={!latestEligibleReply || ttsState === "loading"}>
                    Play
                  </button>
                  <button
                    className={ttsAutoPlay ? "btn btn-small accent-toggle active" : "btn btn-small accent-toggle"}
                    type="button"
                    onClick={toggleTtsAutoPlay}
                  >
                    Auto Play: {ttsAutoPlay ? "On" : "Off"}
                  </button>
                </div>
              </div>
              <div ref={transcriptRef} className="transcript-box transcript-box--tall">
                {transcript.map((event) => (
                  <div
                    key={event.event_id}
                    className="transcript-line"
                    style={{ color: event.role === "agent" && event.agent_slot ? SLOT_COLORS[event.agent_slot] : "var(--text-primary)" }}
                  >
                    {event.text}
                  </div>
                ))}
              </div>
              {ttsError && <p className="inline-guidance">Voice playback error: {ttsError}</p>}
            </article>

            <article className="card image-card">
              <div className="card-head"><span>Current Scene</span><h2>Scene Frame</h2></div>
              {imageLoading ? (
                <div className="media media-loading">Loading...</div>
              ) : (
                <img className="media" src={resolveApiUrl(detail.image_state.image_url || catalog.default_image_url)} alt="Current scene" />
              )}
              <p className="card-copy">
                {imageLoading ? "Generating a fresh scene image..." : detail.image_state.prompt_text || "Default scene image loaded."}
              </p>
            </article>
          </div>

          <article className="card prompt-shell" style={{ borderColor: SLOT_COLORS[activeAgentSlot] ?? "var(--border-strong)" }}>
            <div className="card-head"><span>Guide The Party</span><h2>Game Master Prompting</h2></div>
            <div className="agent-tabs">
              {detail.tab1.party.map((member) => (
                <button
                  key={member.slot}
                  className={activeAgentSlot === member.slot ? "agent-chip active" : "agent-chip"}
                  style={{ background: activeAgentSlot === member.slot ? SLOT_COLORS[member.slot] : "transparent", borderColor: SLOT_COLORS[member.slot] }}
                  onClick={() => setActiveAgentSlot(member.slot)}
                >
                  {member.player_name} {member.initiative ? `(${member.initiative})` : ""}
                </button>
              ))}
              {activeOpposition && (
                <button
                  key={OPPOSITION_SLOT}
                  className={activeAgentSlot === OPPOSITION_SLOT ? "agent-chip active" : "agent-chip"}
                  style={{ background: activeAgentSlot === OPPOSITION_SLOT ? SLOT_COLORS[OPPOSITION_SLOT] : "transparent", borderColor: SLOT_COLORS[OPPOSITION_SLOT] }}
                  onClick={() => setActiveAgentSlot(OPPOSITION_SLOT)}
                >
                  Opposition {detail.session.combat_state.initiative_values["opp:12"] ? `(${detail.session.combat_state.initiative_values["opp:12"]})` : ""}
                </button>
              )}
            </div>
            <form onSubmit={submitPrompt} className="prompt-form">
              <textarea value={userPrompt} onChange={(e) => setUserPrompt(e.target.value)} placeholder="GM prompt..." disabled={detail.session.state !== "ACTIVE"} />
              <div className="action-row">
                <button className="btn" type="submit" disabled={loading || detail.session.state !== "ACTIVE"}>Send Prompt</button>
                <button className="btn accent" type="button" onClick={() => void rollInitiative()} disabled={loading}>Roll for Initiative</button>
                <button
                  className="btn accent"
                  type="button"
                  onClick={() => void takeLongRest()}
                  disabled={longRestLoading || Boolean(activeOpposition) || detail.session.state !== "ACTIVE"}
                  title={activeOpposition ? "You cannot take a long rest while monsters are nearby." : ""}
                >
                  {longRestLoading ? "Resting..." : "Long Rest"}
                </button>
                <button className="btn accent" type="button" onClick={() => void generateImage()} disabled={imageLoading}>Generate Image</button>
              </div>
            </form>
          </article>

          <article className="card card-full-width">
              <div className="card-head"><span>Party Overview</span><h2>Player Status</h2></div>
              <div className="status-grid status-grid--row">
                {detail.tab1.party.map((member) => (
                  <div key={member.slot} className="status-card-lg">
                    <img src={resolveApiUrl(member.portrait_url)} alt={member.player_name} />
                    <strong>{member.player_name} the {member.class_id}</strong>
                    <span>AC {member.armor_class} | HP {member.hp_current}/{member.hp_max}</span>
                    <span>{member.status_effects.length ? member.status_effects.join(", ") : "No active status effects"}</span>
                    <p>{member.inventory.join(" • ")}</p>
                  </div>
                ))}
              </div>
              <div className="action-row split-row">
                <button className="btn danger end-button" onClick={() => void endChapter()} disabled={loading || detail.session.state !== "ACTIVE"}>End Chapter</button>
              </div>
          </article>

          <article className="card card-full-width">
              <div className="card-head"><span>Run The Encounter</span><h2>Game Master Screen</h2></div>
              <div className="objective-strip">
                <strong>Adventure Completion Objectives</strong>
                <ul className="objective-list">
                  {(detail.tab1.active_adventure?.objectives ?? []).map((objective) => (
                    <li key={objective.id}>{objective.description}</li>
                  ))}
                </ul>
              </div>
              <div className="gm-screen-layout">
                <div className="gm-map-panel">
                  <div className="gm-screen-label">Adventure Map</div>
                  {detail.tab1.active_adventure ? (
                    <>
                      <div className="gm-map-frame">
                        <img
                          className="gm-map-image"
                          src={resolveApiUrl(detail.tab1.active_adventure.map_image_url)}
                          alt={`${displayAdventureTitle(detail.tab1.active_adventure)} map`}
                        />
                        {adventureLocations.map((location) => (
                          <button
                            key={location.id}
                            type="button"
                            className={activeLocation?.id === location.id ? "gm-map-hotspot active" : "gm-map-hotspot"}
                            style={{ left: `${location.x_pct}%`, top: `${location.y_pct}%` }}
                            onClick={() => setActiveLocationId(location.id)}
                            aria-label={`Location ${location.number}: ${location.title}`}
                          >
                            {location.number}
                          </button>
                        ))}
                      </div>
                      <div className="gm-location-panel">
                        {activeLocation ? (
                          <>
                            <div className="gm-location-header">
                              <div className="gm-location-heading">
                                <span>Location {activeLocation.number}</span>
                                <strong>{activeLocation.title}</strong>
                              </div>
                              <button className="btn accent" type="button" onClick={() => void travelToSelectedLocation()} disabled={travelLoading}>
                                {travelLoading ? "Traveling..." : "Travel"}
                              </button>
                            </div>
                            <p>{activeLocation.description}</p>
                          </>
                        ) : (
                          <p>Select a keyed location on the map.</p>
                        )}
                      </div>
                    </>
                  ) : (
                    <div className="gm-map-empty">Select an adventure to load its map.</div>
                  )}
                </div>
                <div className="gm-monster-panel">
                  <div className="gm-screen-label">Monster Deck</div>
                  {activeMonsterCard ? (
                    <div className="gm-monster-card-viewer">
                      <div className="gm-opposition-controls">
                        <div className="gm-opposition-spawn">
                          <label>
                            Spawn Opposition
                            <select value={oppositionQuantity} onChange={(e) => setOppositionQuantity(Number(e.target.value))}>
                              {[1, 2, 3, 4].map((count) => (
                                <option key={count} value={count}>{count}</option>
                              ))}
                            </select>
                          </label>
                          <button className="btn accent" type="button" onClick={() => void spawnOpposition()} disabled={spawnLoading || Boolean(activeOpposition)}>
                            {spawnLoading ? "Spawning..." : activeOpposition ? "Opposition Active" : `Spawn ${activeMonsterCard.monster_id}`}
                          </button>
                        </div>
                        {activeOpposition && (
                          <button className="btn danger" type="button" onClick={() => void dismissOpposition()} disabled={dismissLoading}>
                            {dismissLoading ? "Dismissing..." : "Dismiss Opposition"}
                          </button>
                        )}
                      </div>
                      <div className="gm-monster-card">
                        <strong>{activeMonsterCard.monster_id}</strong>
                        <img src={resolveApiUrl(activeMonsterCard.image_url)} alt={activeMonsterCard.monster_id} />
                        {activeMonsterCardInstances.length > 0 && (
                          <div className="gm-monster-instance-list">
                            {activeMonsterCardInstances.map((instance) => (
                              <div key={instance.monster_id} className={instance.is_dead ? "gm-monster-instance dead" : "gm-monster-instance"}>
                                {instance.display_name} — {instance.current_hp}/{instance.hp_max} {instance.is_dead ? "DEAD" : ""}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="gm-monster-card-controls">
                        <button
                          className="btn"
                          type="button"
                          onClick={() => setActiveMonsterCardIndex((current) => (current - 1 + gmMonsters.length) % gmMonsters.length)}
                          disabled={gmMonsters.length <= 1}
                        >
                          Previous
                        </button>
                        <span>{activeMonsterCardIndex + 1} / {gmMonsters.length}</span>
                        <button
                          className="btn"
                          type="button"
                          onClick={() => setActiveMonsterCardIndex((current) => (current + 1) % gmMonsters.length)}
                          disabled={gmMonsters.length <= 1}
                        >
                          Next
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="gm-map-empty">No monsters are assigned to this adventure yet.</div>
                  )}
                </div>
              </div>
          </article>
        </section>
      )}

      {tab === 3 && (
        <section className="panel">
          <article className="card">
            <div className="card-head"><span>Choose The Voice</span><h2>Choose a Player to Summarize Your Adventure!</h2></div>
            <div className="lens-grid lens-grid--row">
              {detail.tab1.party.map((member) => (
                <button key={member.player_id} className={selectedNarrativePlayerId === member.player_id ? "lens-card lens-card--compact selected" : "lens-card lens-card--compact"} onClick={() => setSelectedNarrativePlayerId(member.player_id)}>
                  <img src={resolveApiUrl(member.portrait_url)} alt={member.player_name} />
                  <strong>{member.player_name}</strong>
                  <span>{member.archetype}</span>
                </button>
              ))}
            </div>
            <div className="action-row">
              <button className="btn accent" onClick={() => void buildNarrative()} disabled={loading || detail.session.state !== "ENDED" || !selectedNarrativePlayerId}>
                {narrativeBuilding ? "Building..." : "Build Narrative"}
              </button>
            </div>
          </article>

          <article className="card">
            <div className="card-head"><span>Final Chronicle</span><h2>Player Summary of the Adventure</h2></div>
            <pre className="memory-box">{latestDraft?.chapter_text ?? ""}</pre>
            <div className="action-row">
              <button className="btn" onClick={downloadChapter} disabled={!(latestDraft?.chapter_text ?? "").trim()}>Download Chapter</button>
            </div>
          </article>
        </section>
      )}
    </div>
  );
}
