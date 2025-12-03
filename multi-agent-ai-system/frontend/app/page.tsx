'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { workflowAPI } from '@/lib/api';
import { Workflow, WorkflowStatus } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Plus, Bot, AlertTriangle } from 'lucide-react';

export default function Home() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchWorkflows = async () => {
      try {
        setLoading(true);
        const response = await workflowAPI.list();
        setWorkflows(response.data);
        setError(null);
      } catch (err: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
        console.error('Failed to fetch workflows:', err);
        setError('Failed to load workflows. Please ensure the backend is running.');
      } finally {
        setLoading(false);
      }
    };

    fetchWorkflows();
  }, []);

  const getStatusBadgeVariant = (status: WorkflowStatus) => {
    switch (status) {
      case WorkflowStatus.PUBLISHED:
        return 'default';
      case WorkflowStatus.DRAFT:
        return 'secondary';
      default:
        return 'destructive';
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-200">
      <div className="container mx-auto px-4 py-8 md:py-12 max-w-7xl">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6 mb-12">
          <div className="space-y-1">
            <h1 className="text-3xl md:text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-violet-400">
              Multi-Agent AI Workflows
            </h1>
            <p className="text-slate-400 text-lg">
              Powered by LangGraph + Groq + FastAPI
            </p>
          </div>
          <Link href="/workflows/new">
            <Button className="w-full md:w-auto bg-blue-600 hover:bg-blue-500 text-white gap-2 shadow-lg shadow-blue-900/20">
              <Plus className="w-4 h-4" />
              Create Workflow
            </Button>
          </Link>
        </div>

        {/* Error State */}
        {error && (
          <div className="mb-8 p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 flex items-center gap-3 animate-in fade-in slide-in-from-top-2">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            <p className="font-medium">{error}</p>
            <Button
              variant="ghost"
              size="sm"
              className="ml-auto text-red-400 hover:text-red-300 hover:bg-red-500/10"
              onClick={() => setError(null)}
            >
              Dismiss
            </Button>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <Card key={i} className="border-slate-800 bg-slate-900/50">
                <CardHeader className="space-y-2">
                  <Skeleton className="h-4 w-1/3 bg-slate-800" />
                  <Skeleton className="h-6 w-2/3 bg-slate-800" />
                </CardHeader>
                <CardContent>
                  <Skeleton className="h-20 w-full bg-slate-800" />
                </CardContent>
                <CardFooter>
                  <Skeleton className="h-4 w-1/4 bg-slate-800" />
                </CardFooter>
              </Card>
            ))}
          </div>
        )}

        {/* Empty State */}
        {!loading && workflows.length === 0 && !error && (
          <div className="flex flex-col items-center justify-center py-20 text-center space-y-6 border border-dashed border-slate-800 rounded-xl bg-slate-900/30">
            <div className="w-20 h-20 rounded-full bg-slate-800/50 flex items-center justify-center">
              <Bot className="w-10 h-10 text-slate-400" />
            </div>
            <div className="space-y-2 max-w-md mx-auto">
              <h3 className="text-xl font-semibold text-slate-200">No workflows yet</h3>
              <p className="text-slate-400">
                Get started by creating your first multi-agent workflow to automate complex tasks.
              </p>
            </div>
            <Link href="/workflows/new">
              <Button size="lg" className="bg-blue-600 hover:bg-blue-500 text-white gap-2">
                <Plus className="w-5 h-5" />
                Create Your First Workflow
              </Button>
            </Link>
          </div>
        )}

        {/* Workflows Grid */}
        {!loading && workflows.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
            {workflows.map((workflow) => (
              <Link key={workflow.id} href={`/workflows/${workflow.id}`} className="group block h-full">
                <Card className="h-full border-slate-800 bg-slate-900/50 transition-all duration-200 hover:bg-slate-800/50 hover:border-slate-700 hover:shadow-xl hover:shadow-blue-900/5 group-hover:-translate-y-1">
                  <CardHeader>
                    <div className="flex items-start justify-between gap-4">
                      <CardTitle className="text-lg font-semibold text-slate-200 line-clamp-1 group-hover:text-blue-400 transition-colors">
                        {workflow.name}
                      </CardTitle>
                      <Badge variant={getStatusBadgeVariant(workflow.status)} className="shrink-0">
                        {workflow.status}
                      </Badge>
                    </div>
                    <CardDescription className="line-clamp-2 text-slate-400 min-h-[2.5rem]">
                      {workflow.description || "No description provided."}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-2">
                      {workflow.agents_config && Object.keys(workflow.agents_config).map((agentName) => (
                        <Badge key={agentName} variant="outline" className="text-xs border-slate-700 text-slate-400">
                          {agentName}
                        </Badge>
                      ))}
                    </div>
                  </CardContent>
                  <CardFooter className="mt-auto pt-4 border-t border-slate-800/50 flex items-center justify-between text-xs text-slate-500">
                    <span>{workflow.run_count || 0} runs</span>
                    {workflow.is_public && (
                      <span className="text-blue-400 font-medium flex items-center gap-1">
                        Public
                      </span>
                    )}
                  </CardFooter>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
