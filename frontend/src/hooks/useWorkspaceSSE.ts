/**
 * useWorkspaceSSE -- React hook managing SSE connection or mock engine for workspace events.
 * Depends on: WorkspaceAgent/WorkspaceEvent types, MockEventEngine, isMockMode
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { WorkspaceAgent, WorkspaceEvent } from "../types/workspace";
import { isMockMode, isDemoLab } from "../mock/useMockMode";
import { MockEventEngine } from "../mock/mockEventEngine";
import { API_BASE_URL } from "../api/client";

type WorkspaceEventCallback = (event: WorkspaceEvent) => void;

type BubbleCallback = (agentId: string, text: string) => void;

export interface WorkspaceSSEResult {
  agents: WorkspaceAgent[];
  connected: boolean;
  onBubble: (cb: BubbleCallback) => void;
  getMockEngine: () => MockEventEngine | null;
  onWorkspaceEvent: (cb: (event: WorkspaceEvent) => void) => void;
}

export function useWorkspaceSSE(slug: string): WorkspaceSSEResult {
  const [agents, setAgents] = useState<WorkspaceAgent[]>([]);
  const [connected, setConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const reconnectAttemptsRef = useRef(0);
  const mockEngineRef = useRef<MockEventEngine | null>(null);
  const bubbleCallbackRef = useRef<((agentId: string, text: string) => void) | null>(null);
  const eventCallbackRef = useRef<WorkspaceEventCallback | null>(null);

  const handleEvent = useCallback((data: WorkspaceEvent) => {
    // Notify workspace event subscribers
    if (eventCallbackRef.current) {
      eventCallbackRef.current(data);
    }

    setAgents((prev) => {
      const existing = prev.findIndex((a) => a.agent_id === data.agent_id);
      const updated: WorkspaceAgent = {
        agent_id: data.agent_id,
        zone: data.zone,
        position_x: data.position_x,
        position_y: data.position_y,
        status: data.status,
        last_action_at: data.timestamp,
      };
      if (existing >= 0) {
        const next = [...prev];
        next[existing] = updated;
        return next;
      }
      return [...prev, updated];
    });
  }, []);

  const connect = useCallback(() => {
    if (isMockMode() || isDemoLab(slug)) {
      const engine = new MockEventEngine(
        slug,
        handleEvent,
        (agentId: string, text: string) => {
          if (bubbleCallbackRef.current) {
            bubbleCallbackRef.current(agentId, text);
          }
        },
      );
      mockEngineRef.current = engine;
      engine.start();
      setConnected(true);
      return;
    }

    // Close existing connection before creating new one
    eventSourceRef.current?.close();

    const es = new EventSource(`${API_BASE_URL}/labs/${slug}/workspace/stream`);

    es.addEventListener("connected", () => {
      reconnectAttemptsRef.current = 0;
      setConnected(true);
    });

    es.addEventListener("workspace_update", (event) => {
      try {
        const data: WorkspaceEvent = JSON.parse(event.data);
        handleEvent(data);
      } catch {
        // Ignore malformed SSE messages
      }
    });

    es.onerror = () => {
      setConnected(false);
      es.close();
      // Exponential backoff: 1s, 2s, 4s, 8s, 16s, max 30s
      const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
      reconnectAttemptsRef.current += 1;
      reconnectTimeoutRef.current = setTimeout(connect, delay);
    };

    eventSourceRef.current = es;
  }, [slug, handleEvent]);

  useEffect(() => {
    connect();
    return () => {
      eventSourceRef.current?.close();
      mockEngineRef.current?.stop();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, [connect]);

  const getMockEngine = useCallback(() => mockEngineRef.current, []);

  const onWorkspaceEvent = useCallback((cb: WorkspaceEventCallback) => {
    eventCallbackRef.current = cb;
  }, []);

  const onBubble = useCallback((cb: BubbleCallback) => {
    bubbleCallbackRef.current = cb;
  }, []);

  return {
    agents,
    connected,
    onBubble,
    getMockEngine,
    onWorkspaceEvent,
  };
}
