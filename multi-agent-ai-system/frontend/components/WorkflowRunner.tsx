'use client';

import { useState, useEffect, useRef } from 'react';
import { runAPI } from '@/lib/api';
import { RunStatus, WorkflowRun } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { AlertCircle, Loader2, CheckCircle2, XCircle, Clock, Wifi, WifiOff } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkflowStream } from '@/hooks/useWorkflowStream';

import { PresenceIndicator } from './PresenceIndicator';
import { ShadowHintDisplay } from './ShadowHint';

interface WorkflowRunnerProps {
    workflowId: string;
}

export default function WorkflowRunner({ workflowId }: WorkflowRunnerProps) {
    const [inputData, setInputData] = useState<string>('');
    const [mode, setMode] = useState<string>('full');
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [run, setRun] = useState<WorkflowRun | null>(null);
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    // Use WebSocket for real-time updates
    // Simulating "Driver" role for this user
    const { progress, currentAgent, connectionState, events, onlineUsers, hints } = useWorkflowStream(
        run?.id || null,
        !!run,
        "driver",
        "user-" + Math.floor(Math.random() * 1000) // Random ID for demo
    );

    // Auto-stop loading when workflow completes
    // React to events to update local state
    useEffect(() => {
        if (!events.length) return;

        const latestEvent = events[events.length - 1];
        if (!latestEvent) return;

        // Auto-update status based on events
        if (latestEvent.event_type === 'workflow.completed') {
            setLoading(false);
            if (run) {
                setRun(prev => prev ? ({
                    ...prev,
                    status: RunStatus.COMPLETED,
                    output_data: latestEvent.payload?.output ? { final_output: latestEvent.payload.output } : prev.output_data,
                    // If payload has output, use it as result
                    result: (latestEvent.payload?.output as string) || prev.result
                }) : null);
            }
        } else if (latestEvent.event_type === 'workflow.failed') {
            setLoading(false);
            if (run) {
                setRun(prev => prev ? ({
                    ...prev,
                    status: RunStatus.FAILED,
                    error_message: (latestEvent.payload?.error as string) || "Unknown error"
                }) : null);
            }
        } else if (latestEvent.event_type === 'workflow.started') {
            if (run && run.status === RunStatus.PENDING) {
                setRun(prev => prev ? ({
                    ...prev,
                    status: RunStatus.RUNNING
                }) : null);
            }
        }
    }, [events, run]);

    const handleRun = async () => {
        setError(null);
        setLoading(true);
        setRun(null); // Clear previous run

        try {
            let currentInput = inputData.trim();
            // If in OCR mode and file is selected, upload it first
            if (mode === 'invoice_ocr' && selectedFile) {
                const formData = new FormData();
                formData.append('file', selectedFile);

                try {
                    // Upload file (inline fetch since we don't have a helper yet)
                    // In a real app, add this to api.ts but for speed we do it here
                    // assuming backend is on correct port relative to this
                    // NOTE: Hardcoded localhost:8000 might fail if deployed. 
                    // Better to use relative path if proxying, or generic API client.
                    // For local dev this is fine.
                    const uploadRes = await fetch('http://localhost:8000/api/v1/uploads', {
                        method: 'POST',
                        body: formData,
                    });

                    if (!uploadRes.ok) {
                        throw new Error('File upload failed');
                    }

                    const uploadData = await uploadRes.json();

                    // Pass a JSON string as input if using file.
                    currentInput = JSON.stringify({
                        file_path: uploadData.file_path,
                        text: currentInput
                    });

                } catch (uploadErr) {
                    console.error("Upload failed", uploadErr);
                    throw new Error("Failed to upload file. Please try again.");
                }
            }

            // Convert plain text input to the format expected by the backend
            const payload = {
                input: currentInput,
                language: 'python',
                mode: mode
            };

            const response = await runAPI.create({
                workflow_id: workflowId,
                input_data: payload
            });
            const newRun: WorkflowRun = response.data;
            setRun(newRun);
            // WebSocket will now handle real-time updates automatically
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
                        <label className="text-sm font-medium text-slate-400">Workflow Mode</label>
                        <select
                            value={mode}
                            onChange={(e) => setMode(e.target.value)}
                            className="w-full bg-slate-950 border border-slate-800 rounded-md p-2 text-slate-300 focus:ring-blue-500/20"
                            disabled={loading}
                        >
                            <option value="full">Standard Research</option>
                            <option value="invoice_ocr">Invoice OCR</option>
                        </select>
                    </div>

                    {mode === 'invoice_ocr' && (
                        <div className="space-y-2 animate-in fade-in slide-in-from-top-2">
                            <label className="text-sm font-medium text-slate-400">Upload Invoice (PDF/Image)</label>
                            <input
                                type="file"
                                onChange={(e) => setSelectedFile(e.target.files ? e.target.files[0] : null)}
                                accept=".pdf,.txt,.png,.jpg,.jpeg"
                                className="w-full bg-slate-950 border border-slate-800 rounded-md p-2 text-slate-300 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-500"
                                disabled={loading}
                            />
                            <p className="text-xs text-slate-500">
                                Upload a file OR paste text below.
                            </p>
                        </div>
                    )}

                    <div className="space-y-2">
                        <label className="text-sm font-medium text-slate-400">Your Request</label>
                        <Textarea
                            value={inputData}
                            onChange={(e) => setInputData(e.target.value)}
                            placeholder={mode === 'invoice_ocr' ? "Optional: Add any extra instructions..." : "Describe what you want the workflow to do..."}
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
                        <div className="flex items-center gap-4">
                            <CardTitle className="text-lg font-medium text-slate-200">Run Status</CardTitle>
                            <PresenceIndicator users={onlineUsers} />
                        </div>
                        <Badge variant={getStatusBadgeVariant(run.status)} className="flex items-center">
                            {getStatusIcon(run.status)}
                            {run.status.toUpperCase()}
                        </Badge>
                    </CardHeader>
                    <CardContent className="space-y-4 pt-4">
                        <ShadowHintDisplay hints={hints} />
                        {/* WebSocket Connection Status */}
                        <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2 text-xs">
                                {connectionState === 'connected' ? (
                                    <>
                                        <Wifi className="w-3 h-3 text-green-400" />
                                        <span className="text-green-400">Live</span>
                                    </>
                                ) : connectionState === 'connecting' ? (
                                    <>
                                        <Loader2 className="w-3 h-3 animate-spin text-blue-400" />
                                        <span className="text-blue-400">Connecting...</span>
                                    </>
                                ) : (
                                    <>
                                        <WifiOff className="w-3 h-3 text-slate-500" />
                                        <span className="text-slate-500">Offline</span>
                                    </>
                                )}
                            </div>
                        </div>

                        {/* Live Progress Bar */}
                        {(loading || progress > 0) && (
                            <div className="space-y-2">
                                <div className="flex items-center justify-between text-xs">
                                    <span className="text-slate-400">
                                        {currentAgent ? `${currentAgent}...` : 'Initializing...'}
                                    </span>
                                    <span className="text-slate-400 font-medium">{progress}%</span>
                                </div>
                                <div className="relative h-2 bg-slate-800 rounded-full overflow-hidden">
                                    <div
                                        className="absolute top-0 left-0 h-full bg-gradient-to-r from-blue-500 to-violet-500 transition-all duration-500 ease-out"
                                        style={{ width: `${progress}%` }}
                                    >
                                        <div className="absolute inset-0 bg-white/20 animate-pulse" />
                                    </div>
                                </div>
                            </div>
                        )}

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
                                {/* Display clean result if available */}
                                {(run as any).result && (
                                    <div className="space-y-2">
                                        <p className="text-sm font-medium text-slate-400">Result</p>
                                        <div className="p-4 rounded-md bg-slate-950 border border-slate-800 overflow-x-auto">
                                            <div className="prose prose-invert prose-sm max-w-none">
                                                <pre className="text-sm text-slate-300 whitespace-pre-wrap font-sans">
                                                    {(run as any).result}
                                                </pre>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* Show raw output in a collapsible section for debugging */}
                                <details className="group">
                                    <summary className="text-sm font-medium text-slate-500 cursor-pointer hover:text-slate-400 transition-colors">
                                        Raw Output (Debug)
                                    </summary>
                                    <div className="mt-2 p-4 rounded-md bg-slate-950 border border-slate-800 overflow-x-auto">
                                        <pre className="text-xs font-mono text-green-400">
                                            {JSON.stringify(run.output_data, null, 2)}
                                        </pre>
                                    </div>
                                </details>
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
