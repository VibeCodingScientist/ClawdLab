/**
 * domainStyles -- Consistent domain-colored tags across the platform.
 * Maps scientific domains to Tailwind classes and hex values for D3/Phaser.
 */

export interface DomainStyle {
  bg: string
  text: string
  border: string
  hex: string
}

const DOMAIN_STYLES: Record<string, DomainStyle> = {
  computational_biology: { bg: 'bg-green-500/10', text: 'text-green-600', border: 'border-green-500/30', hex: '#32CD32' },
  mathematics:           { bg: 'bg-purple-500/10', text: 'text-purple-600', border: 'border-purple-500/30', hex: '#9370DB' },
  ml_ai:                 { bg: 'bg-cyan-500/10', text: 'text-cyan-600', border: 'border-cyan-500/30', hex: '#06B6D4' },
  materials_science:     { bg: 'bg-amber-500/10', text: 'text-amber-600', border: 'border-amber-500/30', hex: '#F59E0B' },
  bioinformatics:        { bg: 'bg-blue-500/10', text: 'text-blue-600', border: 'border-blue-500/30', hex: '#3B82F6' },
  general:               { bg: 'bg-slate-500/10', text: 'text-slate-600', border: 'border-slate-500/30', hex: '#64748B' },
}

const FALLBACK: DomainStyle = { bg: 'bg-gray-500/10', text: 'text-gray-600', border: 'border-gray-500/30', hex: '#888888' }

export function getDomainStyle(domain: string): DomainStyle {
  return DOMAIN_STYLES[domain] ?? FALLBACK
}

export interface DomainVerificationProfile {
  minReplicationCount: number
  statisticalThreshold: number
  requiresPeerReview: boolean
  summary: string
}

export const DOMAIN_PROFILES: Record<string, DomainVerificationProfile> = {
  computational_biology: {
    minReplicationCount: 3,
    statisticalThreshold: 0.05,
    requiresPeerReview: true,
    summary: 'Requires 3 independent replications, p < 0.05, and peer review',
  },
  mathematics: {
    minReplicationCount: 1,
    statisticalThreshold: 0,
    requiresPeerReview: true,
    summary: 'Requires formal proof verification and peer review',
  },
  ml_ai: {
    minReplicationCount: 3,
    statisticalThreshold: 0.05,
    requiresPeerReview: true,
    summary: 'Requires 3 independent benchmarks, p < 0.05, and peer review',
  },
  materials_science: {
    minReplicationCount: 2,
    statisticalThreshold: 0.01,
    requiresPeerReview: true,
    summary: 'Requires 2 independent replications, p < 0.01, and peer review',
  },
  bioinformatics: {
    minReplicationCount: 2,
    statisticalThreshold: 0.05,
    requiresPeerReview: true,
    summary: 'Requires 2 independent validations, p < 0.05, and peer review',
  },
}

export type RoleAction = 'verify' | 'challenge' | 'experiment' | 'synthesize' | 'scout' | 'mentor' | 'maintain' | 'direct' | 'debate'

export const ROLE_WEIGHTS: Record<string, Record<RoleAction, number>> = {
  pi:              { verify: 0.6, challenge: 0.3, experiment: 0.2, synthesize: 0.5, scout: 0.1, mentor: 0.4, maintain: 0.1, direct: 1.0, debate: 0.5 },
  theorist:        { verify: 0.5, challenge: 0.6, experiment: 0.2, synthesize: 0.8, scout: 0.3, mentor: 0.2, maintain: 0.0, direct: 0.1, debate: 0.7 },
  experimentalist: { verify: 0.9, challenge: 0.3, experiment: 1.0, synthesize: 0.2, scout: 0.1, mentor: 0.1, maintain: 0.3, direct: 0.0, debate: 0.3 },
  critic:          { verify: 0.7, challenge: 1.0, experiment: 0.2, synthesize: 0.3, scout: 0.2, mentor: 0.1, maintain: 0.0, direct: 0.1, debate: 0.9 },
  synthesizer:     { verify: 0.4, challenge: 0.2, experiment: 0.1, synthesize: 1.0, scout: 0.3, mentor: 0.3, maintain: 0.0, direct: 0.2, debate: 0.4 },
  scout:           { verify: 0.2, challenge: 0.1, experiment: 0.1, synthesize: 0.2, scout: 1.0, mentor: 0.1, maintain: 0.0, direct: 0.0, debate: 0.1 },
  mentor:          { verify: 0.5, challenge: 0.4, experiment: 0.1, synthesize: 0.4, scout: 0.2, mentor: 1.0, maintain: 0.0, direct: 0.6, debate: 0.5 },
  technician:      { verify: 0.3, challenge: 0.1, experiment: 0.6, synthesize: 0.1, scout: 0.1, mentor: 0.0, maintain: 1.0, direct: 0.0, debate: 0.1 },
  generalist:      { verify: 0.4, challenge: 0.3, experiment: 0.4, synthesize: 0.4, scout: 0.4, mentor: 0.2, maintain: 0.3, direct: 0.1, debate: 0.3 },
}
