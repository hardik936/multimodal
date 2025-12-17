import axios from 'axios';

// Types
export interface Checkpoint {
    id: string;
    thread_id: string;
    parent_id?: string;
    metadata?: Record<string, any>;
    created_at?: string;
}

export interface ForkResponse {
    original_run_id: string;
    new_run_id: string;
    forked_from_checkpoint_id: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export const historyApi = {
    /**
     * Get the checkpoint history for a specific run.
     */
    getRunHistory: async (runId: string): Promise<Checkpoint[]> => {
        const response = await axios.get(`${API_URL}/runs/${runId}/history`);
        return response.data;
    },

    /**
     * Fork a run from a specific checkpoint.
     * Creates a new run starting from that state.
     */
    forkRun: async (runId: string, checkpointId: string): Promise<ForkResponse> => {
        const response = await axios.post(`${API_URL}/runs/${runId}/fork`, {
            checkpoint_id: checkpointId
        });
        return response.data;
    }
};
