'use client';

import { useState, useEffect, useRef } from 'react';
import { runAPI } from '@/lib/api';
import { RunStatus, WorkflowRun } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { AlertCircle, Loader2, CheckCircle2, XCircle, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';

interface WorkflowRunnerProps {
    workflowId: string;
}

export default function WorkflowRunner({ workflowId }: WorkflowRunnerProps) {
    const [inputData, setInputData] = useState<string>('');
    const [run, setRun] = useState<WorkflowRun | null>(null);
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

    // Cleanup polling on unmount
    useEffect(() => {
        return () => {
            if (pollIntervalRef.current) {
                clearInterval(pollIntervalRef.current);
            }
        };
    }, []);

    const pollRunStatus = (runId: string) => {
        // Clear existing interval if any
        if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
        }

        pollIntervalRef.current = setInterval(async () => {
            try {
                const response = await runAPI.get(runId);
                const updatedRun: WorkflowRun = response.data;
                setRun(updatedRun);

                if (
                    updatedRun.status === RunStatus.COMPLETED ||
                    updatedRun.status === RunStatus.FAILED ||
                    updatedRun.status === RunStatus.CANCELLED
                ) {
                    if (pollIntervalRef.current) {
                        clearInterval(pollIntervalRef.current);
                    }
                    setLoading(false);
                }
            } catch (err: unknown) {
                console.error("Error polling run status:", err);
                setError("Failed to fetch run status.");
                setLoading(false);
                if (pollIntervalRef.current) {
                    clearInterval(pollIntervalRef.current);
                }
            }
        }, 3000); // Poll every 3 seconds
    };

    const handleRun = async () => {
        setError(null);
        setLoading(true);
        setRun(null); // Clear previous run
        if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
        }

        try {
            // Convert plain text input to the format expected by the backend
            const payload = {
                input: inputData.trim(),
                language: 'python',
                mode: 'full'
            };

            const response = await runAPI.create({
                workflow_id: workflowId,
                input_data: payload
            });
            const newRun: WorkflowRun = response.data;
            setRun(newRun);
            pollRunStatus(newRun.id);
        } catch (err: unknown) {
            console.error("Error running workflow:", err);
            const errorMessage = err instanceof Error ? err.message : "An unexpected error occurred.";
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const detail = (err as any).response?.data?.detail;
            setError(detail || errorMessage);
            setLoading(false);
        }
    };

    const getStatusBadgeVariant = (status: RunStatus) => {
        switch (status) {
            case RunStatus.COMPLETED:
                return "default";
            case RunStatus.FAILED:
                return "destructive";
            case RunStatus.RUNNING:
                return "secondary";
            case RunStatus.PENDING:
                return "secondary";
            case RunStatus.CANCELLED:
                return "outline";
            default:
                return "outline";
        }
    };

    const getStatusIcon = (status: RunStatus) => {
        const iconClass = "w-3 h-3 mr-1";
        switch (status) {
            case RunStatus.COMPLETED:
                return <CheckCircle2 className={cn(iconClass, "text-green-400")} />;
            case RunStatus.FAILED:
                return <XCircle className={cn(iconClass, "text-red-400")} />;
            case RunStatus.RUNNING:
                return <Loader2 className={cn(iconClass, "animate-spin text-blue-400")} />;
            case RunStatus.PENDING:
                return <Clock className={cn(iconClass, "text-slate-400")} />;
            case RunStatus.CANCELLED:
                return <AlertCircle className={cn(iconClass, "text-yellow-400")} />;
            default:
                return null;
        }
    };

    return (
        <div className="space-y-6">
            <Card className="border-slate-800 bg-slate-900/50">
                <CardHeader>
                    <CardTitle className="text-xl font-semibold text-slate-100">Run Workflow</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-400">Your Request</label>
                        <Textarea
                            value={inputData}
                            onChange={(e) => setInputData(e.target.value)}
                            placeholder="Describe what you want the workflow to do... (e.g., 'find me 10 emails of companies that i can market my ai testing services')"
                            className="bg-slate-950 border-slate-800 min-h-[150px] text-slate-300 focus:ring-blue-500/20"
                            disabled={loading}
                        />
                    </div>

                    {error && (
                        <div className="p-3 rounded-md bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-start gap-2">
                            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                            <span>{error}</span>
                        </div>
                    )}

                    <Button
                        onClick={handleRun}
                        disabled={loading}
                        className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium transition-all"
                    >
                        {loading ? (
                            <>
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                Running...
                            </>
                        ) : (
                            'Run Workflow'
                        )}
                    </Button>
                </CardContent>
            </Card>

            {run && (
                <Card className="border-slate-800 bg-slate-900/50 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-lg font-medium text-slate-200">Run Status</CardTitle>
                        <Badge variant={getStatusBadgeVariant(run.status)} className="flex items-center">
                            {getStatusIcon(run.status)}
                            {run.status.toUpperCase()}
                        </Badge>
                    </CardHeader>
                    <CardContent className="space-y-4 pt-4">
                        <div className="grid grid-cols-2 gap-4 text-sm">
                            <div className="space-y-1">
                                <p className="text-slate-500">Run ID</p>
                                <p className="font-mono text-slate-300">{run.id.substring(0, 8)}...</p>
                            </div>
                            <div className="space-y-1">
                                <p className="text-slate-500">Duration</p>
                                <p className="font-mono text-slate-300">
                                    {run.duration_seconds > 0 ? `${run.duration_seconds.toFixed(2)}s` : 'Running...'}
                                </p>
                            </div>
                        </div>

                        {run.error_message && (
                            <div className="p-3 rounded-md bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                                <p className="font-semibold mb-1">Error:</p>
                                <p className="font-mono text-xs">{run.error_message}</p>
                            </div>
                        )}

                        {run.output_data && (
                            <div className="space-y-2">
                                <p className="text-sm font-medium text-slate-400">Output</p>
                                <div className="p-4 rounded-md bg-slate-950 border border-slate-800 overflow-x-auto">
                                    <pre className="text-xs font-mono text-green-400">
                                        {JSON.stringify(run.output_data, null, 2)}
                                    </pre>
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
