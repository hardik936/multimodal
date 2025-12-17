import axios from 'axios';

const API_URL = 'http://localhost:8000/api/v1';

export interface User {
    id: string;
    email: string;
    full_name?: string;
    is_active: boolean;
    is_superuser: boolean;
}

export interface AuthResponse {
    access_token: string;
    token_type: string;
}

export const authApi = {
    login: async (email: string, password: string): Promise<AuthResponse> => {
        const formData = new FormData();
        formData.append('username', email);
        formData.append('password', password);
        const response = await axios.post<AuthResponse>(`${API_URL}/auth/token`, formData);
        return response.data;
    },
    register: async (email: string, password: string, fullName: string): Promise<User> => {
        const response = await axios.post<User>(`${API_URL}/auth/register`, {
            email,
            password,
            full_name: fullName
        });
        return response.data;
    },
    getMe: async (token: string): Promise<User> => {
        const response = await axios.get<User>(`${API_URL}/auth/users/me`, {
            headers: { Authorization: `Bearer ${token}` }
        });
        return response.data;
    }
};
