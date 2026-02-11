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
}

const FALLBACK: DomainStyle = { bg: 'bg-gray-500/10', text: 'text-gray-600', border: 'border-gray-500/30', hex: '#888888' }

export function getDomainStyle(domain: string): DomainStyle {
  return DOMAIN_STYLES[domain] ?? FALLBACK
}
