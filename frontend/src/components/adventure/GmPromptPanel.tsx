import { FormEvent } from "react";
import { resolveApiUrl } from "../../api";
import { Monster, OPPOSITION_SLOT, OppositionState, SessionDetail, SLOT_COLORS } from "../../appTypes";

type OnboardingGuideStep = "starter" | "adventure-map" | "location-one" | "travel" | "trigger-encounter" | "start-encounter" | "opposition-prompt" | "complete";

type GmPromptPanelProps = {
  detail: SessionDetail;
  activeAgentSlot: number;
  activeOpposition: OppositionState | null;
  userPrompt: string;
  loading: boolean;
  animationLocked: boolean;
  longRestLoading: boolean;
  encounterModalOpen: boolean;
  encounterMonsterId: string;
  encounterMonsterIndex: number;
  encounterQuantity: number;
  selectedEncounterMonster: Monster | null;
  gmMonsters: Monster[];
  onSetActiveAgentSlot: (slot: number) => void;
  onSubmitPrompt: (event: FormEvent) => void;
  onSetUserPrompt: (value: string) => void;
  starterPromptText: string;
  onboardingGuideStep: OnboardingGuideStep;
  onSubmitStarterPrompt: () => void;
  onDismissStarterPrompt: () => void;
  onTakeLongRest: () => void;
  onOpenEncounterModal: () => void;
  onCloseEncounterModal: () => void;
  onSetEncounterMonsterId: (monsterId: string) => void;
  onCycleEncounterMonster: (direction: "previous" | "next") => void;
  onSetEncounterQuantity: (quantity: number) => void;
  onTriggerEncounter: () => void;
  onFleeEncounter: () => void;
  onSearchLocation: () => void;
  onUseItem: (itemName: string) => void;
  onEndChapter: () => void;
  gameOver: boolean;
  onStartOver: () => void;
};

function agentTooltip(member: SessionDetail["tab1"]["party"][number]) {
  const inventory = member.inventory.length ? member.inventory.join(", ") : "No listed inventory";
  return `HP ${member.hp_current}/${member.hp_max} | Inventory: ${inventory}`;
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

export function GmPromptPanel({
  detail,
  activeAgentSlot,
  activeOpposition,
  userPrompt,
  loading,
  animationLocked,
  longRestLoading,
  encounterModalOpen,
  encounterMonsterId,
  encounterMonsterIndex,
  encounterQuantity,
  selectedEncounterMonster,
  gmMonsters,
  onSetActiveAgentSlot,
  onSubmitPrompt,
  onSetUserPrompt,
  starterPromptText,
  onboardingGuideStep,
  onSubmitStarterPrompt,
  onDismissStarterPrompt,
  onTakeLongRest,
  onOpenEncounterModal,
  onCloseEncounterModal,
  onSetEncounterMonsterId,
  onCycleEncounterMonster,
  onSetEncounterQuantity,
  onTriggerEncounter,
  onFleeEncounter,
  onSearchLocation,
  onUseItem,
  onEndChapter,
  gameOver,
  onStartOver,
}: GmPromptPanelProps) {
  const selectedMember = detail.tab1.party.find((member) => member.slot === activeAgentSlot) ?? null;
  const activeMemberIsDown = selectedMember ? selectedMember.hp_current <= 0 : false;
  const combatActive = detail.session.combat_state.in_combat && detail.session.combat_state.initiative_order.length > 0;
  const activeCombatantId = combatActive ? activeCombatantIdForDetail(detail) : "";
  const activeCombatSlot = activeCombatantId === "opp:12"
    ? OPPOSITION_SLOT
    : activeCombatantId.startsWith("pc:")
      ? Number(activeCombatantId.replace("pc:", ""))
      : 0;
  const selectedAgentHasCombatTurn = !combatActive || activeCombatSlot === activeAgentSlot;
  const canEditPrompt = detail.session.state === "ACTIVE" && !activeMemberIsDown && selectedAgentHasCombatTurn;
  const canPrompt = detail.session.state === "ACTIVE"
    && !activeMemberIsDown
    && !animationLocked
    && selectedAgentHasCombatTurn
    && (activeAgentSlot !== OPPOSITION_SLOT || Boolean(activeOpposition?.active));
  const encounterButtonLabel = activeOpposition?.active ? "Flee Encounter" : "Trigger Encounter";
  const showStarterPrompt = Boolean(starterPromptText && canPrompt && !userPrompt.trim() && !loading);
  const triggerEncounterGuideActive = onboardingGuideStep === "trigger-encounter" && !activeOpposition?.active;
  const startEncounterGuideActive = onboardingGuideStep === "start-encounter";
  const encounterState = detail.session.encounter_state ?? {};
  const searchState = encounterState.search ?? {};
  const usableItems = selectedMember?.inventory.filter((item) => {
    const lowered = item.toLowerCase();
    return lowered.includes("healing") || lowered.includes("spell restore") || lowered.includes("fireball scroll");
  }) ?? [];

  return (
    <>
      <article
        className="card prompt-shell"
        style={{ borderColor: SLOT_COLORS[activeAgentSlot] ?? "var(--border-strong)" }}
        onClick={showStarterPrompt ? onDismissStarterPrompt : undefined}
      >
        <div className="card-head">
          <span>Guide the Party</span>
          <h2>Game Master Prompting</h2>
        </div>
        <div className={activeOpposition?.active ? "agent-tabs agent-tabs--combat" : "agent-tabs"}>
          {detail.tab1.party.map((member) => {
            const waitingForTurn = combatActive && activeCombatSlot !== member.slot;
            const disabled = member.hp_current <= 0 || animationLocked || waitingForTurn;
            return (
              <button
                key={member.slot}
                className={activeAgentSlot === member.slot ? "agent-chip active" : "agent-chip"}
              style={{ background: activeAgentSlot === member.slot ? SLOT_COLORS[member.slot] : "transparent", borderColor: SLOT_COLORS[member.slot] }}
              onClick={() => onSetActiveAgentSlot(member.slot)}
              disabled={disabled}
                title={waitingForTurn ? "Waiting for this agent's initiative turn." : agentTooltip(member)}
              >
                {member.player_name} {member.initiative ? `(${member.initiative})` : ""}
              </button>
            );
          })}
          {activeOpposition?.active && (
            <button
              className={activeAgentSlot === OPPOSITION_SLOT ? "agent-chip active" : "agent-chip"}
              style={{ background: activeAgentSlot === OPPOSITION_SLOT ? SLOT_COLORS[OPPOSITION_SLOT] : "transparent", borderColor: SLOT_COLORS[OPPOSITION_SLOT] }}
              onClick={() => onSetActiveAgentSlot(OPPOSITION_SLOT)}
              disabled={animationLocked || (combatActive && activeCombatSlot !== OPPOSITION_SLOT)}
              title={combatActive && activeCombatSlot !== OPPOSITION_SLOT ? "Waiting for the Opposition initiative turn." : activeOpposition.instances.map((instance) => `${instance.display_name}: ${instance.current_hp}/${instance.hp_max}`).join(" | ")}
            >
              Opposition {detail.session.combat_state.initiative_values["opp:12"] ? `(${detail.session.combat_state.initiative_values["opp:12"]})` : ""}
            </button>
          )}
        </div>
        <form onSubmit={onSubmitPrompt} className="prompt-form">
          <div className="prompt-textarea-shell">
            <textarea
              value={userPrompt}
              onFocus={showStarterPrompt ? onDismissStarterPrompt : undefined}
              onChange={(event) => onSetUserPrompt(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  if (canPrompt && userPrompt.trim() && !loading) {
                    event.currentTarget.form?.requestSubmit();
                  }
                }
              }}
              placeholder="GM prompt..."
              disabled={!canEditPrompt}
            />
            {showStarterPrompt && (
              <button
                className={["starter-prompt-bubble", onboardingGuideStep === "starter" || onboardingGuideStep === "opposition-prompt" ? "onboarding-guide-pulse" : ""].filter(Boolean).join(" ")}
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  onSubmitStarterPrompt();
                }}
              >
                {starterPromptText}
              </button>
            )}
          </div>
          {activeMemberIsDown && <p className="inline-guidance">That agent is at 0 HP and cannot be prompted until they are healed.</p>}
          {!selectedAgentHasCombatTurn && <p className="inline-guidance">Waiting for the current initiative turn.</p>}
          {animationLocked && <p className="inline-guidance">Resolving combat animation...</p>}
          {encounterState.encounter_type && encounterState.encounter_type !== "none" && (
            <div className="encounter-status-strip">
              <strong>{encounterState.encounter_name}</strong>
              <span>{encounterState.encounter_type} | {encounterState.status}</span>
            </div>
          )}
          <details className="mobile-party-details">
            <summary>Party Status</summary>
            <div className="party-summary-list">
              {detail.tab1.party.map((member) => (
                <div key={member.slot} className={member.hp_current <= 0 ? "party-summary-chip disabled" : "party-summary-chip"}>
                  <strong>{member.player_name}</strong>
                  <span>HP {member.hp_current}/{member.hp_max}</span>
                  <span>{member.inventory.length ? member.inventory.join(", ") : "No listed inventory"}</span>
                </div>
              ))}
            </div>
          </details>
          <div className="action-row">
            <button className="btn" type="submit" disabled={loading || !canPrompt}>Send Prompt</button>
            <button
              className={[
                activeOpposition?.active ? "btn danger" : "btn accent",
                triggerEncounterGuideActive ? "onboarding-guide-pulse" : "",
              ].filter(Boolean).join(" ")}
              type="button"
              onClick={activeOpposition?.active ? onFleeEncounter : onOpenEncounterModal}
              disabled={loading || animationLocked || (!activeOpposition?.active && gmMonsters.length === 0)}
            >
              {encounterButtonLabel}
            </button>
            <button
              className="btn accent"
              type="button"
              onClick={onTakeLongRest}
              disabled={longRestLoading || animationLocked || Boolean(activeOpposition?.active) || detail.session.state !== "ACTIVE"}
              title={activeOpposition?.active ? "You cannot take a long rest while monsters are nearby." : ""}
            >
              {longRestLoading ? "Resting..." : "Long Rest"}
            </button>
            {searchState.available && !searchState.found && (
              <button className="btn accent" type="button" onClick={onSearchLocation} disabled={loading || animationLocked || !canPrompt}>
                Search Location
              </button>
            )}
            {usableItems.length > 0 && (
              <select
                className="item-use-select"
                value=""
                onChange={(event) => {
                  if (event.target.value) onUseItem(event.target.value);
                }}
                disabled={loading || animationLocked || !canPrompt}
                title="Use item"
              >
                <option value="">Use item...</option>
                {usableItems.map((item, index) => (
                  <option key={`${item}-${index}`} value={item}>{item}</option>
                ))}
              </select>
            )}
            <button className="btn" type="button" onClick={onEndChapter} disabled={loading || animationLocked || detail.session.state !== "ACTIVE"}>End Chapter</button>
          </div>
        </form>
      </article>

      {encounterModalOpen && (
        <div className="overlay-backdrop" role="presentation" onClick={onCloseEncounterModal}>
          <div className="overlay-card" role="dialog" aria-modal="true" aria-label="Trigger Encounter" onClick={(event) => event.stopPropagation()}>
            <div className="card-head">
              <span>Encounter</span>
              <h2>Trigger Encounter</h2>
            </div>
            <p className="card-copy">Choose one of the creatures already assigned to this adventure. A maximum of four creatures can be spawned, and initiative begins immediately.</p>
            {selectedEncounterMonster && (
              <>
                <div className="encounter-card-stack">
                  <button className="btn" type="button" onClick={() => onCycleEncounterMonster("previous")} disabled={gmMonsters.length <= 1}>
                    Previous
                  </button>
                  <div className="encounter-stack-frame">
                    <div className="encounter-stack-card encounter-stack-card--back" aria-hidden="true" />
                    <div className="encounter-stack-card encounter-stack-card--mid" aria-hidden="true" />
                    <div className="encounter-stack-card encounter-stack-card--front">
                      <img src={resolveApiUrl(selectedEncounterMonster.image_url)} alt={selectedEncounterMonster.monster_id} />
                      <div className="encounter-stack-copy">
                        <strong>{selectedEncounterMonster.monster_id}</strong>
                        <span>Card {encounterMonsterIndex + 1} of {gmMonsters.length}</span>
                        <span>AC {selectedEncounterMonster.ac} | HP {selectedEncounterMonster.hp} | Attack +{selectedEncounterMonster.attack_bonus}</span>
                        <span>{selectedEncounterMonster.attack_text}</span>
                      </div>
                    </div>
                  </div>
                  <button className="btn" type="button" onClick={() => onCycleEncounterMonster("next")} disabled={gmMonsters.length <= 1}>
                    Next
                  </button>
                </div>
                <label className="field-stack">
                  <span>Creature</span>
                  <select value={encounterMonsterId} onChange={(event) => onSetEncounterMonsterId(event.target.value)}>
                    {gmMonsters.map((monster) => (
                      <option key={monster.monster_id} value={monster.monster_id}>
                        {monster.monster_id}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field-stack">
                  <span>Quantity</span>
                  <select value={encounterQuantity} onChange={(event) => onSetEncounterQuantity(Number(event.target.value))}>
                    {[1, 2, 3, 4].map((count) => (
                      <option key={count} value={count}>{count}</option>
                    ))}
                  </select>
                </label>
              </>
            )}
            <div className="action-row">
              <button className="btn" type="button" onClick={onCloseEncounterModal}>Cancel</button>
              <button
                className={startEncounterGuideActive ? "btn accent onboarding-guide-pulse" : "btn accent"}
                type="button"
                onClick={onTriggerEncounter}
                disabled={!selectedEncounterMonster || loading}
              >
                Start Encounter
              </button>
            </div>
          </div>
        </div>
      )}

      {gameOver && (
        <div className="overlay-backdrop">
          <div className="overlay-card overlay-card--compact" role="dialog" aria-modal="true" aria-label="Game Over">
            <div className="card-head">
              <span>Game Over</span>
              <h2>The Entire Party Is Down</h2>
            </div>
            <p className="card-copy">Start over to create a fresh session and begin again from the preparation screen.</p>
            <div className="action-row">
              <button className="btn danger" type="button" onClick={onStartOver}>Start Over</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
