# Lab State & Purpose-Driven Narrative — Implementation Plan

Two connected changes that transform the lab view from a transport log into a research story.

---

## 1 — Lab State: Expanded View with Research Journey

### The Problem

The Lab State panel currently shows a compact list of items with status, score, and a one-line summary. When a visitor clicks to expand an item, they see the evidence entries — but these are flat metadata records (type, description, agent). There's no narrative synthesis. You can't follow the intellectual thread from hypothesis to current state.

### The Target

Expanded view shows a synthesized research journey as chronological bullets. Each bullet names the agent, describes what they did, and states the outcome or implication. It reads like a research logbook.

**Collapsed (no change needed)**:
```
✅ β-sheet folding pathway in prion proteins            0.94  14 refs
   Verified via AlphaFold2 and independently replicated with ESMFold.
```

**Expanded (new)**:
```
✅ β-sheet folding pathway in prion proteins            0.94  14 refs
   computational biology · Protein Folding Dynamics Lab

   Verified via AlphaFold2 and independently replicated with ESMFold.
   14 downstream results reference this pathway.

   Research journey:
   • Dr. Folding proposed investigating β-sheet folding pathways in 
     prion proteins as a potential mechanism for misfolding propagation.
   • PaperHound-9 found 7 relevant papers including Marchetti et al.'s 
     2024 cryo-EM study showing β-sheet intermediates.
   • LabRunner-12 ran AlphaFold2 structure predictions on 50 independent 
     trajectories — pLDDT 0.94, consistent with the proposed pathway.
   • Skepticus-5 challenged: "Single method prediction insufficient. 
     Need independent structural validation."
   • BenchBot-8 replicated with ESMFold — pLDDT 0.91, confirming 
     the AlphaFold2 result with an independent method.
   • Verification passed: reproducibility engine confirmed across 3 
     independent runs. Score: 0.94.
```

For items still in progress:

```
🔬 Membrane protein stability hypothesis                      investigating

   ESMFold predictions complete. Awaiting MACE-MP simulations and 
   roundtable review before verification can proceed.

   Progress so far:
   • DeepThink-3 hypothesized that membrane-associated prion proteins 
     exhibit different folding stability than soluble forms.
   • PaperHound-9 identified conflicting evidence: 3 papers support 
     the hypothesis, 2 suggest no significant difference.
   • LabRunner-12 completed ESMFold predictions on membrane-bound 
     conformations — initial pLDDT varies widely (0.45–0.88).
   • Waiting: MACE-MP simulations queued to assess energetic stability.
```

### Data Model Changes

The `lab_state_items.evidence` JSONB column already exists. Extend the entry structure:

```typescript
interface EvidenceEntry {
  type: 'hypothesis' | 'literature' | 'experiment' | 'result' 
      | 'challenge' | 'verification' | 'replication' | 'decision';
  summary: string;        // "LabRunner-12 ran AlphaFold2 predictions on 50 trajectories — pLDDT 0.94"
  agent_id: string;
  timestamp: string;      // ISO datetime
  day_label?: string;     // "Day 1", "Day 3" — relative timeline for readability
  outcome?: string;       // "below target" / "confirmed" / "inconclusive"
}
```

Each entry represents a *meaningful state change* — not every workspace event, but the moments that advanced, redirected, or contested the research. The rule: if removing this bullet would leave a gap in the story, it belongs. If removing it changes nothing, it doesn't.

Add a `current_summary` text column to `lab_state_items` if not already present. This holds 1–2 sentences synthesizing where the item stands right now. It's shown in the collapsed view and as the opening paragraph of the expanded view. Regenerate it whenever a new evidence entry is appended.

```sql
alter table lab_state_items add column if not exists 
  current_summary text;
```

### Mock Data

This is the most labor-intensive part. Each lab needs 4–6 state items, each with 3–8 evidence bullets that tell a coherent story. Author these manually — they can't be procedurally generated because the research journey needs to make scientific sense.

**Structure for mock data** (add to `mockData.ts`):

Write evidence chains for all three labs. Each chain should include at least: one hypothesis entry, one literature entry, one experiment entry, and one outcome (verification, challenge, or "waiting"). For `established` items, the chain ends with verification. For `under_investigation`, it ends with a "waiting" entry. For `contested`, it ends with a challenge.

Example for Quantum Error Correction Lab:

```typescript
{
  id: 'qec-ls-001',
  title: 'Surface code threshold improved to 1.1%',
  status: 'established',
  verificationScore: 0.91,
  currentSummary: 'Monte Carlo simulations on corrected lattice sizes confirmed 1.1% threshold, above the 1.0% target. Verified via 3 independent runs.',
  evidence: [
    { type: 'hypothesis', summary: 'Qubit-Prime proposed investigating surface code thresholds as an alternative to concatenated approaches.', agent_id: 'qubit-prime', day_label: 'Day 1' },
    { type: 'literature', summary: "ArXivBot-3 found 4 relevant papers including Chen et al.'s noise-adapted compilation framework.", agent_id: 'arxivbot-3', day_label: 'Day 2' },
    { type: 'experiment', summary: 'QSimulator-4 ran initial Monte Carlo simulations — first results showed 0.8% threshold, below target.', agent_id: 'qsimulator-4', day_label: 'Day 3', outcome: 'below target' },
    { type: 'challenge', summary: 'ErrorCheck-1 challenged the simulation parameters: insufficient lattice sizes biased the result downward.', agent_id: 'errorcheck-1', day_label: 'Day 4' },
    { type: 'experiment', summary: 'QSimulator-4 re-ran with corrected parameters (L=12,16,20,24) — threshold improved to 1.1%.', agent_id: 'qsimulator-4', day_label: 'Day 5', outcome: 'above target' },
    { type: 'verification', summary: 'Verification passed: reproducibility engine confirmed across 3 independent runs. Score: 0.91.', agent_id: 'system', day_label: 'Day 6' },
  ],
}
```

### Frontend Component Changes

In `LabStatePanel.tsx`:

- Collapsed row: status icon, title, score (colored), reference count, `currentSummary` as gray subtext. No change from current.
- Click handler: toggles `expandedItemId` state.
- Expanded section renders:
  - Domain tag + lab name
  - `currentSummary` as opening paragraph
  - "Research journey:" or "Progress so far:" header (use "Research journey" for `established`, "Progress so far" for `under_investigation`/`contested`, "Proposed" for `proposed`/`next`)
  - Evidence bullets as an ordered list. Each bullet: agent name in bold or accent color, then the summary text. Outcome annotations (if present) as a subtle tag: `below target`, `confirmed`, etc.
  - For items with status `under_investigation`: final bullet prefixed with "Waiting:" in amber to show what's blocking progress.

### Backend Integration (Production)

When workspace events cause significant state transitions (claim submitted, verification completed, challenge filed, experiment finished), the backend appends an evidence entry to the corresponding `lab_state_items` row and regenerates `current_summary`. This can be done in the `WorkspaceService` that already translates Kafka events into workspace state.

---

## 2 — Purpose-Driven Agent Narrative

### The Problem

The current NarrativePanel generates text like:

```
Qubit-Prime is moved to presentation in the presentation.
ErrorCheck-1 is moved to roundtable in the roundtable.
```

This describes motion, not purpose. A visitor watches agents walk between zones but has no idea why. The narrative is disconnected from the Lab State, so activity can't be understood in the context of the research.

### The Target

Every narrative entry connects an agent's action to the Lab State item they're working on:

```
● Dr. Folding reviews ESMFold predictions for membrane protein 
  stability hypothesis at the bench.

● Skepticus-5 challenges the methodology behind entropic 
  contribution to folding free energy at the roundtable.

● PaperHound-9 scouts recent literature on prion conformational 
  dynamics for the allosteric effects study.

● DeepThink-3 shifts focus to membrane protein stability 
  hypothesis — beginning theoretical framework.
```

The research item name (italic or accent-colored) is a clickable link. Clicking it scrolls to and highlights the corresponding item in the Lab State panel above.

### Template System

Templates keyed by `zone:status:archetype` with a fallback chain. More specific = better prose.

```typescript
export const NARRATIVE_TEMPLATES_V3: Record<string, string[]> = {
  // Tier 1: zone + status + archetype (most specific)
  'roundtable:debating:critic': [
    '{name} challenges the methodology behind *{task_title}*.',
    '{name} presents counter-evidence against *{task_title}* findings.',
    '{name} questions the statistical significance of *{task_title}*.',
  ],
  'roundtable:debating:theorist': [
    '{name} defends the theoretical basis of *{task_title}*.',
    '{name} proposes a reformulation of *{task_title}*.',
  ],
  'bench:experimenting:experimentalist': [
    '{name} runs {task_description} for *{task_title}*.',
    '{name} launches a new experiment batch for *{task_title}*.',
    '{name} calibrates simulation parameters for *{task_title}*.',
  ],
  'library:scanning:scout': [
    '{name} scouts recent literature on *{task_title}*.',
    '{name} identifies new preprints relevant to *{task_title}*.',
    '{name} cross-references claims against *{task_title}* evidence.',
  ],
  'ideation:brainstorming:pi': [
    '{name} outlines next steps for *{task_title}*.',
    '{name} coordinates the team approach to *{task_title}*.',
    '{name} re-evaluates priorities after *{task_title}* progress.',
  ],
  'ideation:brainstorming:synthesizer': [
    '{name} connects *{task_title}* findings with related work.',
    '{name} synthesizes results across experiments for *{task_title}*.',
  ],
  'whiteboard:theorizing:theorist': [
    '{name} formalizes the framework for *{task_title}*.',
    '{name} sketches a proof strategy for *{task_title}*.',
  ],
  'verification:verifying:technician': [
    '{name} submits *{task_title}* for computational verification.',
    '{name} monitors verification pipeline for *{task_title}*.',
  ],

  // Tier 2: zone + status (no archetype match)
  'roundtable:debating': [
    '{name} weighs in on *{task_title}* at the roundtable.',
  ],
  'bench:experimenting': [
    '{name} works on *{task_title}* at the bench.',
  ],
  'library:scanning': [
    '{name} reviews literature for *{task_title}*.',
  ],

  // Tier 3: zone only (no task assigned)
  'roundtable': ['{name} joins the roundtable discussion.'],
  'bench': ['{name} begins work at the lab bench.'],
  'library': ['{name} browses the library.'],
  'ideation': ['{name} brainstorms in the ideation space.'],
  'whiteboard': ['{name} reviews the whiteboard.'],
  'verification': ['{name} checks the verification chamber.'],
  'presentation': ['{name} prepares findings for presentation.'],
  'entrance': ['{name} enters the lab.'],
}
```

**Special templates for task changes** (when an agent switches `currentTaskId`):

```typescript
export const TASK_CHANGE_TEMPLATES: string[] = [
  '{name} shifts focus to *{task_title}* — {task_description}.',
  '{name} picks up *{task_title}* — {task_description}.',
  '{name} turns attention to *{task_title}*.',
];
```

### Template Resolution Logic

New utility function `resolveNarrative(agent, event, labState)`:

```
1. Get agent's currentTaskId from agent_state
2. Resolve to lab_state_item → extract task_title
3. Get agent's task_description
4. Build template key: `${zone}:${status}:${archetype}`
5. Try key at Tier 1 → pick random template from array
6. If no match, try Tier 2: `${zone}:${status}`
7. If no match, try Tier 3: `${zone}`
8. Replace placeholders:
   - {name} → agent display name
   - {task_title} → lab state item title (rendered as clickable link)
   - {task_description} → agent_state.task_description (optional, omit if absent)
9. Return rendered string
```

### When to Emit Narrative Entries

Not on every tick. Only on meaningful state changes:

- **Agent changes zone** → narrative entry (they moved for a reason)
- **Agent changes `currentTaskId`** → narrative entry using `TASK_CHANGE_TEMPLATES` (shift of focus)
- **Agent status changes within same zone** → narrative entry (new phase of work)

Bubble text does NOT generate narrative entries — bubbles are their own channel.

### Mock Event Engine Changes

Update `MockEventEngine` (or `mockEventEngine.ts`):

- On agent creation: assign a `currentTaskId` from the lab's state items. Weight by archetype: experimentalists → `under_investigation` items, critics → `contested` items, scouts → any active item, PIs → highest-priority item.
- Every ~30 seconds (simulated): 20% chance an agent changes task. Emit a task-change event that triggers a `TASK_CHANGE_TEMPLATES` narrative entry.
- On zone change: resolve the narrative using `resolveNarrative()` instead of the current flat template.
- Track each agent's `currentTaskId` and `taskDescription` in the mock engine state.

### Clickable Research Item Links

In the NarrativePanel component, render `*{task_title}*` segments as clickable spans. On click:

1. Scroll the Lab State panel into view if needed.
2. Set `highlightedItemId` state on the Lab State panel.
3. The Lab State panel applies a brief highlight animation (background pulse, 1.5s) on the matching row.
4. If the item is collapsed, expand it.

This requires a shared state or event bus between NarrativePanel and LabStatePanel. Use the existing `GameBridge` EventEmitter or React context.

---

## Implementation Steps

### Step 1 — Data Model + Types (half day)

- Add `current_summary` column to `lab_state_items` if not present
- Update `EvidenceEntry` TypeScript interface with `day_label` and `outcome` fields
- Update `AgentState` type to ensure `currentTaskId` and `taskDescription` are present
- Create `NARRATIVE_TEMPLATES_V3` and `TASK_CHANGE_TEMPLATES` in a new file `narrativeTemplates.ts`

### Step 2 — Mock Data Authoring (1 day)

- Write evidence chains for all lab state items across all 3 labs. Each `established` item needs 4–8 bullets telling a complete story. Each `under_investigation` item needs 2–5 bullets ending with a "waiting" entry. Each `contested` item needs the challenge as the final bullet.
- Write `currentSummary` for every lab state item.
- Assign `currentTaskId` and `taskDescription` to every mock agent.
- Write 3–5 templates per `zone:status:archetype` combination for the narrative system.

This is the most time-intensive step because the stories need to make scientific sense within each domain. Budget a full day.

### Step 3 — Expanded Lab State UI (half day)

- Add expand/collapse toggle to each row in `LabStatePanel.tsx`
- Expanded section: render domain + lab, `currentSummary` paragraph, evidence bullets with agent name highlighting and outcome tags
- Style: bullets as an ordered timeline with subtle left-border line connecting them
- "Waiting:" prefix in amber for the final bullet of `under_investigation` items

### Step 4 — Narrative Engine (1 day)

- Create `resolveNarrative(agent, event, labState)` utility function with the 3-tier fallback chain
- Replace current narrative generation in `MockEventEngine` or `NarrativePanel` with the new resolver
- Add task-change event handling: when `currentTaskId` changes, emit a narrative entry using `TASK_CHANGE_TEMPLATES`
- Update `MockEventEngine` to track agent tasks and occasionally reassign them
- Filter: only emit narrative on zone change, task change, or status change — not on every tick

### Step 5 — Cross-Panel Linking (half day)

- Make `*{task_title}*` in NarrativePanel clickable
- On click: emit a `highlight_state_item` event through GameBridge or React context
- LabStatePanel listens: scrolls into view, sets `highlightedItemId`, expands if collapsed, applies 1.5s background pulse animation
- Clear highlight after animation completes

### Step 6 — Polish and QA (half day)

- Verify narrative entries read naturally across all three labs
- Check that evidence chains tell coherent stories when expanded
- Confirm cross-panel links work (click task name in activity → Lab State highlights)
- Test edge cases: agent with no task assigned, lab state item with empty evidence
- Mobile: verify Lab State collapses properly, narrative entries don't overflow

**Total: ~4 days**
