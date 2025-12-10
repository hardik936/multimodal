/* eslint-disable @typescript-eslint/no-explicit-any */
export enum WorkflowStatus {
    DRAFT = 'draft',
    PUBLISHED = 'published',
    ARCHIVED = 'archived',
}

export enum RunStatus {
    PENDING = 'pending',
    RUNNING = 'running',
    COMPLETED = 'completed',
    FAILED = 'failed',
    CANCELLED = 'cancelled',
}

export interface AgentConfig {
    name: string;
    type: 'researcher' | 'planner' | 'executor' | 'coder';
    temperature: number;
    max_tokens: number;
}

export interface Workflow {
    id: string;
    user_id: string;
    name: string;
    description?: string;
    status: WorkflowStatus;
    is_public: boolean;
    created_at: string;
    updated_at: string;
    graph_definition?: any;
    agents_config?: Record<string, AgentConfig>;
    run_count?: number;
}

export interface WorkflowRun {
    id: string;
    workflow_id: string;
    status: RunStatus;
    input_data: any;
    output_data?: any;
    error_message?: string;
    created_at: string;
    started_at?: string;
    completed_at?: string;
    duration_seconds: number;
}

export interface Message {
    id: string;
    run_id: string;
    role: 'user' | 'agent' | 'system';
    agent_name?: string;
    content: string;
    metadata?: any;
    timestamp: string;
}
/* eslint-enable @typescript-eslint/no-explicit-any */
