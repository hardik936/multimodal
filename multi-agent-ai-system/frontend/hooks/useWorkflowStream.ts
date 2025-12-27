/**
 * WebSocket hook for real-time workflow execution streaming
 */

import { useState, useEffect, useRef, useCallback } from 'react';

export interface WorkflowEvent {
    timestamp: string;
    run_id: string;
    event_type: string;
    agent_name?: string;
    progress?: number;
    cost_so_far?: number;
    payload?: Record<string, any>;
}

export type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'error';

interface UseWorkflowStreamResult {
    events: WorkflowEvent[];
    connectionState: ConnectionState;
    latestEvent: WorkflowEvent | null;
    progress: number;
    currentAgent: string | null;
    reconnect: () => void;
}

export function useWorkflowStream(
    runId: string | null,
    enabled: boolean = true
): UseWorkflowStreamResult {
    const [events, setEvents] = useState<WorkflowEvent[]>([]);
    const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
    const [latestEvent, setLatestEvent] = useState<WorkflowEvent | null>(null);
    const [progress, setProgress] = useState<number>(0);
    const [currentAgent, setCurrentAgent] = useState<string | null>(null);

    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const reconnectAttemptsRef = useRef<number>(0);
    const maxReconnectAttempts = 3;

    const connect = useCallback(() => {
        if (!runId || !enabled) return;

        try {
            // WebSocket URL
            const wsUrl = `ws://localhost:8000/api/v1/ws/${runId}`;
            setConnectionState('connecting');
            const ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                console.log(`WebSocket connected for run ${runId}`);
                setConnectionState('connected');
                reconnectAttemptsRef.current = 0;
            };

            ws.onmessage = (event) => {
                try {
                    const data: WorkflowEvent = JSON.parse(event.data);

                    // Handle ping/keep-alive
                    if (data.event_type === 'ping') {
                        ws.send('pong');
                        return;
                    }

                    // Add to events array
                    setEvents(prev => [...prev, data]);
                    setLatestEvent(data);

                    // Update progress if available
                    if (typeof data.progress === 'number') {
                        setProgress(data.progress);
                    }

                    // Update current agent
                    if (data.agent_name) {
                        setCurrentAgent(data.agent_name);
                    }

                } catch (err) {
                    console.error('Error parsing WebSocket message:', err);
                }
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                setConnectionState('error');
            };

            ws.onclose = () => {
                console.log('WebSocket closed');
                setConnectionState('disconnected');

                // Attempt reconnection with exponential backoff
                if (reconnectAttemptsRef.current < maxReconnectAttempts) {
                    const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 10000);
                    reconnectAttemptsRef.current++;

                    console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})`);

                    reconnectTimeoutRef.current = setTimeout(() => {
                        connect();
                    }, delay);
                } else {
                    console.log('Max reconnection attempts reached');
                }
            };

            wsRef.current = ws;

        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            setConnectionState('error');
        }
    }, [runId, enabled]);

    const disconnect = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }

        if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
        }
    }, []);

    const reconnect = useCallback(() => {
        reconnectAttemptsRef.current = 0;
        disconnect();
        connect();
    }, [connect, disconnect]);

    // Connect on mount and when runId changes
    useEffect(() => {
        connect();
        return () => disconnect();
    }, [connect, disconnect]);

    return {
        events,
        connectionState,
        latestEvent,
        progress,
        currentAgent,
        reconnect,
    };
}
