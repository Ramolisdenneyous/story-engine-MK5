import { RefObject } from "react";
import { SLOT_COLORS, TranscriptEvent, TtsState } from "../../appTypes";

type AdventureLogProps = {
  transcript: TranscriptEvent[];
  transcriptChars: number;
  transcriptRef: RefObject<HTMLDivElement>;
  latestEligibleReply: TranscriptEvent | null;
  ttsState: TtsState;
  ttsAutoPlay: boolean;
  ttsStatusLabels: Record<TtsState, string>;
  ttsError: string;
  onPlayReply: () => void;
  onToggleTtsAutoPlay: () => void;
};

export function AdventureLog({
  transcript,
  transcriptChars,
  transcriptRef,
  latestEligibleReply,
  ttsState,
  ttsAutoPlay,
  ttsStatusLabels,
  ttsError,
  onPlayReply,
  onToggleTtsAutoPlay,
}: AdventureLogProps) {
  const lineClass = (event: TranscriptEvent) => {
    if (event.kind === "objective_updated") return "transcript-line transcript-line--objective";
    if (event.kind === "inventory_gained" || event.kind === "inventory_lost") return "transcript-line transcript-line--inventory";
    return "transcript-line";
  };

  return (
    <article className="card transcript-card transcript-card--flat">
      <div className="card-head">
        <span>Live Session</span>
        <h2>Adventure Log</h2>
        <small>{transcriptChars} chars</small>
        <div className="card-head-actions">
          <span className={`tts-status tts-status--${ttsState}`}>AI Voice: {ttsStatusLabels[ttsState]}</span>
          <button className="btn btn-small" type="button" onClick={onPlayReply} disabled={!latestEligibleReply || ttsState === "loading"}>
            Play
          </button>
          <button
            className={ttsAutoPlay ? "btn btn-small accent-toggle active" : "btn btn-small accent-toggle"}
            type="button"
            onClick={onToggleTtsAutoPlay}
          >
            Auto Play: {ttsAutoPlay ? "On" : "Off"}
          </button>
        </div>
      </div>
      <div ref={transcriptRef} className="transcript-box transcript-box--tall">
        {transcript.map((event) => (
          <div
            key={event.event_id}
            className={lineClass(event)}
            style={{ color: event.role === "agent" && event.agent_slot ? SLOT_COLORS[event.agent_slot] : "var(--text-primary)" }}
          >
            {event.text}
          </div>
        ))}
      </div>
      {ttsError && <p className="inline-guidance">Voice playback error: {ttsError}</p>}
    </article>
  );
}
