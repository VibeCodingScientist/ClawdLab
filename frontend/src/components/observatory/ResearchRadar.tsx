/**
 * ResearchRadar -- D3 force-directed graph visualization of lab clusters and connections.
 * Depends on: d3, @tanstack/react-query, workspace/feed APIs
 */
import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import * as d3 from 'd3'
import { getLabs } from '@/api/workspace'
import { getClusters } from '@/api/feed'

interface ResearchRadarProps {
  onLabSelect: (slug: string) => void
}

interface NodeDatum extends d3.SimulationNodeDatum {
  id: string
  slug: string
  name: string
  memberCount: number
  domains: string[]
  primaryDomain: string
}

interface LinkDatum extends d3.SimulationLinkDatum<NodeDatum> {
  citationCount: number
}

const DOMAIN_COLORS: Record<string, string> = {
  computational_biology: '#32CD32',
  ml_ai: '#4169E1',
  mathematics: '#FFD700',
  materials_science: '#FF6347',
  bioinformatics: '#9370DB',
}

export function ResearchRadar({ onLabSelect }: ResearchRadarProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [tooltip, setTooltip] = useState<{
    visible: boolean
    x: number
    y: number
    lab: NodeDatum | null
  }>({ visible: false, x: 0, y: 0, lab: null })

  const { data: labs } = useQuery({
    queryKey: ['labs'],
    queryFn: getLabs,
  })

  const { data: clusters } = useQuery({
    queryKey: ['clusters'],
    queryFn: getClusters,
  })

  useEffect(() => {
    if (!svgRef.current || !labs || !clusters) return

    const svg = d3.select(svgRef.current)
    const width = svgRef.current.clientWidth || 600
    const height = svgRef.current.clientHeight || 400

    svg.selectAll('*').remove()

    // Build nodes
    const nodes: NodeDatum[] = labs.map(lab => ({
      id: lab.slug,
      slug: lab.slug,
      name: lab.name,
      memberCount: lab.memberCount,
      domains: lab.domains,
      primaryDomain: lab.domains[0] || 'ml_ai',
    }))

    // Build links from clusters (deduplicate pairs across clusters)
    const links: LinkDatum[] = []
    const linkKeys = new Set<string>()
    for (const cluster of clusters) {
      for (let i = 0; i < cluster.labs.length; i++) {
        for (let j = i + 1; j < cluster.labs.length; j++) {
          const source = cluster.labs[i]
          const target = cluster.labs[j]
          const key = source < target ? `${source}|${target}` : `${target}|${source}`
          if (linkKeys.has(key)) continue
          if (nodes.find(n => n.id === source) && nodes.find(n => n.id === target)) {
            linkKeys.add(key)
            links.push({
              source,
              target,
              citationCount: cluster.citation_count,
            })
          }
        }
      }
    }

    // Force simulation
    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink<NodeDatum, LinkDatum>(links).id(d => d.id).distance(150))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(d => (d as NodeDatum).memberCount * 2 + 30))

    // Defs for glow
    const defs = svg.append('defs')
    const filter = defs.append('filter').attr('id', 'glow')
    filter.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'coloredBlur')
    const feMerge = filter.append('feMerge')
    feMerge.append('feMergeNode').attr('in', 'coloredBlur')
    feMerge.append('feMergeNode').attr('in', 'SourceGraphic')

    // Links
    const link = svg.append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', '#4a4a6a')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', d => Math.max(1, d.citationCount / 10))

    // Nodes
    const nodeGroup = svg.append('g')
      .selectAll('g')
      .data(nodes)
      .join('g')
      .style('cursor', 'pointer')
    // Apply drag behavior
    const dragBehavior = d3.drag<SVGGElement, NodeDatum>()
      .on('start', (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart()
        d.fx = d.x
        d.fy = d.y
      })
      .on('drag', (event, d) => {
        d.fx = event.x
        d.fy = event.y
      })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0)
        d.fx = null
        d.fy = null
      })

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    nodeGroup.call(dragBehavior as any)

    // Node circles
    nodeGroup.append('circle')
      .attr('r', d => d.memberCount * 2 + 15)
      .attr('fill', d => DOMAIN_COLORS[d.primaryDomain] || '#888')
      .attr('fill-opacity', 0.15)
      .attr('stroke', d => DOMAIN_COLORS[d.primaryDomain] || '#888')
      .attr('stroke-width', 2)
      .attr('filter', 'url(#glow)')

    // Inner circle
    nodeGroup.append('circle')
      .attr('r', d => d.memberCount + 8)
      .attr('fill', d => DOMAIN_COLORS[d.primaryDomain] || '#888')
      .attr('fill-opacity', 0.5)

    // Labels
    nodeGroup.append('text')
      .text(d => d.name.split(' ').slice(0, 2).join(' '))
      .attr('text-anchor', 'middle')
      .attr('dy', d => d.memberCount * 2 + 28)
      .attr('fill', '#aaaacc')
      .attr('font-size', '11px')
      .attr('font-family', 'monospace')

    // Member count
    nodeGroup.append('text')
      .text(d => d.memberCount.toString())
      .attr('text-anchor', 'middle')
      .attr('dy', '4px')
      .attr('fill', '#ffffff')
      .attr('font-size', '12px')
      .attr('font-weight', 'bold')
      .attr('font-family', 'monospace')

    // Hover events
    nodeGroup
      .on('mouseover', (event, d) => {
        if (!svgRef.current) return
        const rect = svgRef.current.getBoundingClientRect()
        setTooltip({
          visible: true,
          x: event.clientX - rect.left,
          y: event.clientY - rect.top,
          lab: d,
        })
      })
      .on('mouseout', () => {
        setTooltip(prev => ({ ...prev, visible: false }))
      })
      .on('click', (_event, d) => {
        onLabSelect(d.slug)
      })

    // Tick
    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as NodeDatum).x!)
        .attr('y1', d => (d.source as NodeDatum).y!)
        .attr('x2', d => (d.target as NodeDatum).x!)
        .attr('y2', d => (d.target as NodeDatum).y!)

      nodeGroup.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    return () => {
      simulation.stop()
      svg.selectAll('*').remove()
      setTooltip(prev => ({ ...prev, visible: false }))
    }
  }, [labs, clusters, onLabSelect])

  return (
    <div className="relative w-full h-full min-h-[400px]">
      <svg
        ref={svgRef}
        className="w-full h-full"
        style={{ minHeight: 400 }}
      />
      {tooltip.visible && tooltip.lab && (
        <div
          className="absolute z-50 pointer-events-none bg-card border rounded-lg shadow-lg p-3"
          style={{ left: tooltip.x + 12, top: tooltip.y - 8 }}
        >
          <p className="font-semibold text-sm">{tooltip.lab.name}</p>
          <p className="text-xs text-muted-foreground mt-1">
            {tooltip.lab.memberCount} members
          </p>
          <div className="flex gap-1 mt-1">
            {tooltip.lab.domains.map(d => (
              <span
                key={d}
                className="text-xs px-1.5 py-0.5 rounded"
                style={{
                  backgroundColor: (DOMAIN_COLORS[d] || '#888') + '20',
                  color: DOMAIN_COLORS[d] || '#888',
                }}
              >
                {d.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
          <p className="text-xs text-muted-foreground mt-1">Click to view details</p>
        </div>
      )}
    </div>
  )
}
