/**
 * archetypes -- Agent archetype definitions: colors, texture keys, and display labels.
 * No external dependencies.
 */
export interface ArchetypeConfig {
  key: string
  color: string
  label: string
  icon: string
  skinTone: string
  hairColor: string
  eyeColor: string
}

export type RoleArchetype =
  | 'pi'
  | 'theorist'
  | 'experimentalist'
  | 'critic'
  | 'synthesizer'
  | 'scout'
  | 'mentor'
  | 'technician'
  | 'generalist'

export const ARCHETYPE_CONFIGS: Record<RoleArchetype, ArchetypeConfig> = {
  pi:              { key: 'agent-pi',              color: '#F5C542', label: 'PI',              icon: 'crown',     skinTone: '#F5D0A9', hairColor: '#2a1a0a', eyeColor: '#4466AA' },
  theorist:        { key: 'agent-theorist',        color: '#5B8DEF', label: 'Theorist',        icon: 'lightbulb', skinTone: '#E8B88A', hairColor: '#5a3010', eyeColor: '#338844' },
  experimentalist: { key: 'agent-experimentalist', color: '#4ADE80', label: 'Experimentalist', icon: 'flask',     skinTone: '#D4956B', hairColor: '#8a6030', eyeColor: '#885522' },
  critic:          { key: 'agent-critic',           color: '#EF6461', label: 'Critic',          icon: 'shield',   skinTone: '#C47A50', hairColor: '#d44020', eyeColor: '#224488' },
  synthesizer:     { key: 'agent-synthesizer',     color: '#A78BFA', label: 'Synthesizer',     icon: 'merge',     skinTone: '#F5D0A9', hairColor: '#1a1a2a', eyeColor: '#7744AA' },
  scout:           { key: 'agent-scout',           color: '#22D3EE', label: 'Scout',           icon: 'compass',   skinTone: '#E8B88A', hairColor: '#c4a050', eyeColor: '#44AACC' },
  mentor:          { key: 'agent-mentor',          color: '#C2956B', label: 'Mentor',          icon: 'book',      skinTone: '#8B5E3C', hairColor: '#2a1a0a', eyeColor: '#336644' },
  technician:      { key: 'agent-technician',      color: '#D97706', label: 'Technician',      icon: 'wrench',    skinTone: '#C47A50', hairColor: '#5a3010', eyeColor: '#886622' },
  generalist:      { key: 'agent-generalist',      color: '#2DD4BF', label: 'Generalist',      icon: 'star',      skinTone: '#D4956B', hairColor: '#8a6030', eyeColor: '#448888' },
}

export const ARCHETYPE_LIST: RoleArchetype[] = [
  'pi', 'theorist', 'experimentalist', 'critic', 'synthesizer',
  'scout', 'mentor', 'technician', 'generalist',
]
