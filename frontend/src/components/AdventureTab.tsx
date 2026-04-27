import { FormEvent, RefObject } from "react";
import {
  Adventure,
  AdventureLocation,
  Monster,
  OppositionState,
  SessionDetail,
  TranscriptEvent,
  TtsState,
} from "../appTypes";
import { AdventureLog } from "./adventure/AdventureLog";
import { GmPromptPanel } from "./adventure/GmPromptPanel";
import { LocationCell } from "./adventure/LocationCell";

type LocationView = "world" | "adventure" | "encounter";

type AdventureTabProps = {
  detail: SessionDetail;
  transcript: TranscriptEvent[];
  transcriptChars: number;
  transcriptRef: RefObject<HTMLDivElement>;
  latestEligibleReply: TranscriptEvent | null;
  ttsState: TtsState;
  ttsAutoPlay: boolean;
  ttsStatusLabels: Record<TtsState, string>;
  ttsError: string;
  userPrompt: string;
  activeAgentSlot: number;
  activeOpposition: OppositionState | null;
  locationOppositionState: OppositionState | null;
  activeLocation: AdventureLocation | null;
  adventureLocations: AdventureLocation[];
  gmMonsters: Monster[];
  encounterModalOpen: boolean;
  encounterMonsterId: string;
  encounterMonsterIndex: number;
  encounterQuantity: number;
  selectedEncounterMonster: Monster | null;
  loading: boolean;
  longRestLoading: boolean;
  travelLoading: boolean;
  allPlayersDown: boolean;
  worldMapImageUrl: string;
  encounterImageUrl: string;
  encounterLocationTitle: string;
  locationView: LocationView;
  playedAttackEventIds: string[];
  animationLocked: boolean;
  onPlayReply: () => void;
  onAnimationStateChange: (locked: boolean) => void;
  onAnimationSettled: () => Promise<SessionDetail>;
  onMarkAttackAnimationPlayed: (eventId: string) => void;
  onToggleTtsAutoPlay: () => void;
  onSubmitPrompt: (event: FormEvent) => void;
  onSetUserPrompt: (value: string) => void;
  onSetActiveAgentSlot: (slot: number) => void;
  onTakeLongRest: () => void;
  onEndChapter: () => void;
  onSetLocationView: (view: LocationView) => void;
  onSetActiveLocationId: (locationId: string) => void;
  onTravelToSelectedLocation: () => void;
  onReturnToMoosehearth: () => void;
  onOpenEncounterModal: () => void;
  onCloseEncounterModal: () => void;
  onSetEncounterMonsterId: (monsterId: string) => void;
  onCycleEncounterMonster: (direction: "previous" | "next") => void;
  onSetEncounterQuantity: (quantity: number) => void;
  onTriggerEncounter: () => void;
  onFleeEncounter: () => void;
  onStartOver: () => void;
  displayAdventureTitle: (adventure: Adventure | null) => string;
};

export function AdventureTab(props: AdventureTabProps) {
  return (
    <section className="panel panel--adventure-phase1">
      <LocationCell
        detail={props.detail}
        worldMapImageUrl={props.worldMapImageUrl}
        encounterImageUrl={props.encounterImageUrl}
        activeAgentSlot={props.activeAgentSlot}
        activeLocation={props.activeLocation}
        adventureLocations={props.adventureLocations}
        gmMonsters={props.gmMonsters}
        activeOpposition={props.locationOppositionState}
        travelLoading={props.travelLoading}
        locationView={props.locationView}
        onSetActiveLocationId={props.onSetActiveLocationId}
        onSetLocationView={props.onSetLocationView}
        onTravelToSelectedLocation={props.onTravelToSelectedLocation}
        onReturnToMoosehearth={props.onReturnToMoosehearth}
        displayAdventureTitle={props.displayAdventureTitle}
        encounterLocationTitle={props.encounterLocationTitle}
        playedAttackEventIds={props.playedAttackEventIds}
        onAnimationStateChange={props.onAnimationStateChange}
        onAnimationSettled={props.onAnimationSettled}
        onMarkAttackAnimationPlayed={props.onMarkAttackAnimationPlayed}
      />

      <AdventureLog
        transcript={props.transcript}
        transcriptChars={props.transcriptChars}
        transcriptRef={props.transcriptRef}
        latestEligibleReply={props.latestEligibleReply}
        ttsState={props.ttsState}
        ttsAutoPlay={props.ttsAutoPlay}
        ttsStatusLabels={props.ttsStatusLabels}
        ttsError={props.ttsError}
        onPlayReply={props.onPlayReply}
        onToggleTtsAutoPlay={props.onToggleTtsAutoPlay}
      />

      <GmPromptPanel
        detail={props.detail}
        activeAgentSlot={props.activeAgentSlot}
        activeOpposition={props.activeOpposition}
        userPrompt={props.userPrompt}
        loading={props.loading}
        animationLocked={props.animationLocked}
        longRestLoading={props.longRestLoading}
        encounterModalOpen={props.encounterModalOpen}
        encounterMonsterId={props.encounterMonsterId}
        encounterMonsterIndex={props.encounterMonsterIndex}
        encounterQuantity={props.encounterQuantity}
        selectedEncounterMonster={props.selectedEncounterMonster}
        gmMonsters={props.gmMonsters}
        onSetActiveAgentSlot={props.onSetActiveAgentSlot}
        onSubmitPrompt={props.onSubmitPrompt}
        onSetUserPrompt={props.onSetUserPrompt}
        onTakeLongRest={props.onTakeLongRest}
        onOpenEncounterModal={props.onOpenEncounterModal}
        onCloseEncounterModal={props.onCloseEncounterModal}
        onSetEncounterMonsterId={props.onSetEncounterMonsterId}
        onCycleEncounterMonster={props.onCycleEncounterMonster}
        onSetEncounterQuantity={props.onSetEncounterQuantity}
        onTriggerEncounter={props.onTriggerEncounter}
        onFleeEncounter={props.onFleeEncounter}
        onEndChapter={props.onEndChapter}
        gameOver={props.allPlayersDown}
        onStartOver={props.onStartOver}
      />
    </section>
  );
}
