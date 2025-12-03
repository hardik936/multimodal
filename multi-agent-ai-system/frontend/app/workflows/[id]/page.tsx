'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { workflowAPI } from '@/lib/api';
import { Workflow } from '@/lib/types';
import WorkflowRunner from '@/components/WorkflowRunner';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowLeft, Calendar, User, Settings } from 'lucide-react';

export default function WorkflowPage() {
    const params = useParams();
    const id = params?.id as string;
    const [workflow, setWorkflow] = useState<Workflow | null>(null);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!id) return;

        const fetchWorkflow = async () => {
            try {
                setLoading(true);
                const response = await workflowAPI.get(id);
                setWorkflow(response.data);
                setError(null);
            } catch (err: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
                console.error('Failed to fetch workflow:', err);
                setError('Failed to load workflow details.');
            } finally {
                setLoading(false);
            }
        };

        fetchWorkflow();
    }, [id]);

    if (loading) {
        return (
            <main className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-200 p-8">
                <div className="max-w-5xl mx-auto space-y-6">
                    <Skeleton className="h-10 w-32 bg-slate-800" />
                    <Skeleton className="h-40 w-full bg-slate-800" />
                    <Skeleton className="h-96 w-full bg-slate-800" />
                </div>
            </main>
        );
    }

    if (error || !workflow) {
        return (
            <main className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-200 p-8 flex items-center justify-center">
                <div className="text-center space-y-4">
                    <h1 className="text-2xl font-bold text-red-400">Error</h1>
                    <p className="text-slate-400">{error || 'Workflow not found'}</p>
                    <Link href="/">
                        <Button variant="outline" className="mt-4">
                            <ArrowLeft className="w-4 h-4 mr-2" />
                            Back to Workflows
                        </Button>
                    </Link>
                </div>
            </main>
        );
    }

    return (
        <main className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-200">
            <div className="container mx-auto px-4 py-8 md:py-12 max-w-5xl">
                <Link href="/" className="inline-block mb-6">
                    <Button variant="ghost" className="text-slate-400 hover:text-slate-200 pl-0 hover:bg-transparent">
                        <ArrowLeft className="w-4 h-4 mr-2" />
                        Back to Workflows
                    </Button>
                </Link>

                <div className="grid gap-8">
                    {/* Workflow Header */}
                    <Card className="border-slate-800 bg-slate-900/50">
                        <CardHeader>
                            <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                                <div className="space-y-2">
                                    <div className="flex items-center gap-3">
                                        <CardTitle className="text-2xl font-bold text-slate-100">
                                            {workflow.name}
                                        </CardTitle>
                                        <Badge variant="outline" className="border-slate-700 text-slate-400">
                                            {workflow.status}
                                        </Badge>
                                    </div>
                                    <CardDescription className="text-slate-400 text-base">
                                        {workflow.description || "No description provided."}
                                    </CardDescription>
                                </div>
                                <div className="flex items-center gap-2 text-sm text-slate-500">
                                    <Calendar className="w-4 h-4" />
                                    <span>Created {new Date(workflow.created_at).toLocaleDateString()}</span>
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <div className="flex flex-wrap gap-6 text-sm text-slate-400">
                                <div className="flex items-center gap-2">
                                    <User className="w-4 h-4 text-slate-500" />
                                    <span>Owner: {workflow.user_id}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Settings className="w-4 h-4 text-slate-500" />
                                    <span>
                                        Agents: {workflow.agents_config ? Object.keys(workflow.agents_config).join(', ') : 'None'}
                                    </span>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Workflow Runner */}
                    <WorkflowRunner workflowId={workflow.id} />
                </div>
            </div>
        </main>
    );
}
