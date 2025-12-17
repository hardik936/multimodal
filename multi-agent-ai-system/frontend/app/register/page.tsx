'use client';

import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import Link from 'next/link';
import { authApi } from '../../services/auth';
import { useRouter } from 'next/navigation';

export default function RegisterPage() {
    const { login } = useAuth();
    const router = useRouter();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [fullName, setFullName] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError('');
        try {
            await authApi.register(email, password, fullName);
            // Auto login after register
            const response = await authApi.login(email, password);
            login(response.access_token);
        } catch (err: any) {
            console.error(err);
            if (err.response?.data?.detail) {
                setError(err.response.data.detail);
            } else {
                setError('Registration failed');
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-900 px-4">
            <div className="w-full max-w-md space-y-8 rounded-xl bg-white dark:bg-slate-800 p-8 shadow-lg border border-slate-200 dark:border-slate-700">
                <div className="text-center">
                    <h2 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Create Account</h2>
                    <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">Get started with Multi-Agent AI</p>
                </div>

                {error && (
                    <div className="p-3 bg-red-100 border border-red-400 text-red-700 rounded text-sm text-center">
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-6">
                    <div className="space-y-2">
                        <Label htmlFor="fullname">Full Name</Label>
                        <Input
                            id="fullname"
                            placeholder="John Doe"
                            value={fullName}
                            onChange={e => setFullName(e.target.value)}
                            className="bg-slate-50 dark:bg-slate-900"
                        />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="email">Email</Label>
                        <Input
                            id="email"
                            type="email"
                            placeholder="name@example.com"
                            value={email}
                            onChange={e => setEmail(e.target.value)}
                            required
                            className="bg-slate-50 dark:bg-slate-900"
                        />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="password">Password</Label>
                        <Input
                            id="password"
                            type="password"
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            required
                            className="bg-slate-50 dark:bg-slate-900"
                        />
                    </div>
                    <Button type="submit" className="w-full" disabled={loading}>
                        {loading ? 'Create Account' : 'Register'}
                    </Button>
                </form>
                <div className="text-center text-sm">
                    <p className="text-slate-600 dark:text-slate-400">
                        Already have an account? <Link href="/login" className="text-blue-600 hover:text-blue-500 font-medium">Sign In</Link>
                    </p>
                </div>
            </div>
        </div>
    );
}
