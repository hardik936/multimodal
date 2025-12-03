import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
    baseURL: `${API_BASE_URL}/api/v1`,
    headers: {
        'Content-Type': 'application/json',
    },
    timeout: 30000, // 30 seconds
});

// Request interceptor to add auth token
api.interceptors.request.use(
    (config) => {
        // Only access localStorage in the browser
        if (typeof window !== 'undefined') {
            const token = localStorage.getItem('auth_token');
            if (token) {
                config.headers.Authorization = `Bearer ${token}`;
            }
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// Response interceptor for error handling
api.interceptors.response.use(
    (response) => response,
    (error) => {
        console.error('API Error:', error.response?.data || error.message);
        return Promise.reject(error);
    }
);

/* eslint-disable @typescript-eslint/no-explicit-any */
export const workflowAPI = {
    list: (params?: { skip?: number; limit?: number }) =>
        api.get('/workflows', { params }),
    get: (id: string) => api.get(`/workflows/${id}`),
    create: (data: any) => api.post('/workflows', data),
    update: (id: string, data: any) => api.put(`/workflows/${id}`, data),
    delete: (id: string) => api.delete(`/workflows/${id}`),
};

export const runAPI = {
    list: (params?: { workflow_id?: string }) => api.get('/runs', { params }),
    get: (id: string) => api.get(`/runs/${id}`),
    create: (data: { workflow_id: string; input_data: any }) =>
        api.post('/runs', data),
    logs: (id: string) => api.get(`/logs/${id}`),
};
/* eslint-enable @typescript-eslint/no-explicit-any */

export default api;
