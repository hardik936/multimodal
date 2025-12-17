'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import api from '@/lib/api'; // Import default axios instance
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Check, X, Clock, AlertTriangle, ArrowLeft, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

// --- Types ---
interface ReviewRequest {
    id: string;
    workflow_id: string;
    run_id: string;
    step_name: string;
    status: string;
    risk_level: string;
    created_at: string;
    expires_at?: string;
    proposed_action?: any;
    cost_estimate_usd: number;
}

// --- API Client (Inline) ---
const hitlAPI = {
    listReviews: async () => {
        const res = await api.get('/hitl/reviews');
        return res.data;
    },
    approve: async (id: string, reason: string) => {
        const res = await api.post(`/hitl/reviews/${id}/approve`, { reason, actor: 'admin_ui' });
        return res.data;
    },
    reject: async (id: string, reason: string) => {
        const res = await api.post(`/hitl/reviews/${id}/reject`, { reason, actor: 'admin_ui' });
        return res.data;
    }
};

export default function HITLAdminPage() {
    const router = useRouter();
    const [reviews, setReviews] = useState<ReviewRequest[]>([]);
    const [loading, setLoading] = useState<boolean>(true);
    const [processingId, setProcessingId] = useState<string | null>(null);

    const fetchReviews = async () => {
        try {
            setLoading(true);
            const data = await hitlAPI.listReviews();
            setReviews(data);
        } catch (err) {
            console.error("Failed to load reviews", err);
            toast.error("Failed to load pending reviews.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchReviews();
        // Poll every 10 seconds
        const interval = setInterval(fetchReviews, 10000);
        return () => clearInterval(interval);
    }, []);

    const handleDecision = async (id: string, decision: 'approve' | 'reject') => {
        try {
            setProcessingId(id);
            if (decision === 'approve') {
                await hitlAPI.approve(id, "Approved via Admin UI");
                toast.success(`Request ${id.slice(0, 8)} approved.`);
            } else {
                await hitlAPI.reject(id, "Rejected via Admin UI");
                toast.success(`Request ${id.slice(0, 8)} rejected.`);
            }
            // Remove from list immediately for better UX
            setReviews(prev => prev.filter(r => r.id !== id));
            // Refresh to be sure
            fetchReviews();
        } catch (err) {
            console.error(`Failed to ${decision} review`, err);
            toast.error(`Failed to ${decision} review.`);
        } finally {
            setProcessingId(null);
        }
    };

    const getRiskColor = (level: string) => {
        switch (level.toLowerCase()) {
            case 'high': return 'destructive'; // red
            case 'medium': return 'secondary'; // yellow-ish usually
            case 'low': return 'outline';
            default: return 'default';
        }
    };

    return (
        <main className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-200">
            <div className="container mx-auto px-4 py-8 md:py-12 max-w-5xl">

                {/* Header */}
                <div className="flex items-center justify-between mb-8">
                    <div className="flex items-center gap-4">
                        <Link href="/">
                            <Button variant="ghost" size="icon" className="text-slate-400 hover:text-white">
                                <ArrowLeft className="w-5 h-5" />
                            </Button>
                        </Link>
                        <div>
                            <h1 className="text-2xl font-bold text-white">Pending Reviews</h1>
                            <p className="text-slate-400 text-sm">Human-in-the-Loop Control Plane</p>
                        </div>
                    </div>
                    <Button variant="outline" size="sm" onClick={fetchReviews} disabled={loading} className="gap-2">
                        <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                </div>

                {/* Content */}
                {loading && reviews.length === 0 ? (
                    <div className="space-y-4">
                        {[1, 2, 3].map(i => <Skeleton key={i} className="h-40 w-full bg-slate-900/50" />)}
                    </div>
                ) : reviews.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-20 text-center space-y-4 border border-dashed border-slate-800 rounded-xl bg-slate-900/30">
                        <div className="w-16 h-16 rounded-full bg-slate-800/50 flex items-center justify-center">
                            <Check className="w-8 h-8 text-green-500" />
                        </div>
                        <div>
                            <h3 className="text-lg font-medium text-slate-200">All caught up!</h3>
                            <p className="text-slate-500">No pending reviews found.</p>
                        </div>
                    </div>
                ) : (
                    <div className="grid gap-6">
                        {reviews.map(review => (
                            <Card key={review.id} className="border-slate-800 bg-slate-900/40 overflow-hidden hover:border-slate-700 transition-colors">
                                <CardHeader className="bg-slate-900/60 pb-4 border-b border-slate-800/50">
                                    <div className="flex justify-between items-start">
                                        <div>
                                            <div className="flex items-center gap-2 mb-1">
                                                <Badge variant="outline" className="font-mono text-xs text-slate-400 border-slate-700">
                                                    {review.workflow_id}
                                                </Badge>
                                                <span className="text-slate-600">/</span>
                                                <span className="text-sm font-medium text-blue-400">{review.step_name}</span>
                                            </div>
                                            <CardTitle className="text-lg flex items-center gap-2">
                                                Approval Required
                                                <Badge variant={getRiskColor(review.risk_level) as any} className="ml-2 uppercase text-[10px]">
                                                    {review.risk_level} Risk
                                                </Badge>
                                            </CardTitle>
                                        </div>
                                        <div className="text-right text-xs text-slate-500 flex flex-col items-end gap-1">
                                            <span className="flex items-center gap-1">
                                                <Clock className="w-3 h-3" />
                                                {new Date(review.created_at).toLocaleString()}
                                            </span>
                                            {review.cost_estimate_usd > 0 && (
                                                <span className="text-emerald-400 font-mono">
                                                    Est. Cost: ${review.cost_estimate_usd.toFixed(4)}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                </CardHeader>
                                <CardContent className="pt-6">
                                    <div className="space-y-4">
                                        {review.proposed_action ? (
                                            <div className="bg-slate-950/50 rounded-lg p-4 border border-slate-800">
                                                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Proposed Action</h4>
                                                <pre className="text-sm text-slate-300 whitespace-pre-wrap font-mono overflow-auto max-h-40">
                                                    {JSON.stringify(review.proposed_action, null, 2)}
                                                </pre>
                                            </div>
                                        ) : (
                                            <p className="text-slate-400 italic">No detailed action context provided.</p>
                                        )}
                                    </div>
                                </CardContent>
                                <CardFooter className="bg-slate-900/30 border-t border-slate-800/50 flex justify-end gap-3 py-4">
                                    <Button
                                        variant="destructive"
                                        onClick={() => handleDecision(review.id, 'reject')}
                                        disabled={!!processingId}
                                        className="bg-red-900/20 hover:bg-red-900/40 text-red-400 border border-red-900/50"
                                    >
                                        <X className="w-4 h-4 mr-2" />
                                        Reject
                                    </Button>
                                    <Button
                                        variant="default"
                                        onClick={() => handleDecision(review.id, 'approve')}
                                        disabled={!!processingId}
                                        className="bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-900/20"
                                    >
                                        <Check className="w-4 h-4 mr-2" />
                                        Approve & Resume
                                    </Button>
                                </CardFooter>
                            </Card>
                        ))}
                    </div>
                )}
            </div>
        </main>
    );
}
