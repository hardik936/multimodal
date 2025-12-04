'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { workflowAPI } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

export default function NewWorkflowPage() {
    const router = useRouter();
    const [loading, setLoading] = useState(false);
    const [formData, setFormData] = useState({
        name: '',
        description: '',
        is_public: false,
    });

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!formData.name.trim()) {
            toast.error('Workflow name is required');
            return;
        }

        setLoading(true);

        try {
            // Create workflow with default configuration
            const response = await workflowAPI.create({
                name: formData.name,
                description: formData.description || undefined,
                graph_definition: {
                    nodes: ['researcher', 'planner', 'executor', 'coder'],
                    edges: [
                        { from: 'researcher', to: 'planner' },
                        { from: 'planner', to: 'executor' },
                        { from: 'executor', to: 'coder' },
                    ],
                },
                agents_config: {
                    researcher: {
                        name: 'Researcher',
                        type: 'researcher',
                        temperature: 0.7,
                        max_tokens: 2000,
                    },
                    planner: {
                        name: 'Planner',
                        type: 'planner',
                        temperature: 0.5,
                        max_tokens: 2000,
                    },
                    executor: {
                        name: 'Executor',
                        type: 'executor',
                        temperature: 0.3,
                        max_tokens: 2000,
                    },
                    coder: {
                        name: 'Coder',
                        type: 'coder',
                        temperature: 0.2,
                        max_tokens: 3000,
                    },
                },
                is_public: formData.is_public,
            });

            toast.success('Workflow created successfully');

            // Redirect to the new workflow's page
            router.push(`/workflows/${response.data.id}`);
        } catch (error: unknown) {
            console.error('Failed to create workflow:', error);
            toast.error('Failed to create workflow. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <main className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-200">
            <div className="container mx-auto px-4 py-8 md:py-12 max-w-3xl">
                <Link href="/" className="inline-block mb-6">
                    <Button variant="ghost" className="text-slate-400 hover:text-slate-200 pl-0 hover:bg-transparent">
                        <ArrowLeft className="w-4 h-4 mr-2" />
                        Back to Workflows
                    </Button>
                </Link>

                <Card className="border-slate-800 bg-slate-900/50">
                    <CardHeader>
                        <CardTitle className="text-2xl font-bold text-slate-100">
                            Create New Workflow
                        </CardTitle>
                        <CardDescription className="text-slate-400">
                            Set up a new multi-agent workflow with default configuration
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <form onSubmit={handleSubmit} className="space-y-6">
                            <div className="space-y-2">
                                <Label htmlFor="name" className="text-slate-300">
                                    Workflow Name *
                                </Label>
                                <Input
                                    id="name"
                                    type="text"
                                    placeholder="e.g., Research Assistant"
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                    className="bg-slate-800 border-slate-700 text-slate-100 placeholder:text-slate-500"
                                    required
                                />
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="description" className="text-slate-300">
                                    Description
                                </Label>
                                <Textarea
                                    id="description"
                                    placeholder="Describe what this workflow does..."
                                    value={formData.description}
                                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                                    className="bg-slate-800 border-slate-700 text-slate-100 placeholder:text-slate-500 min-h-[100px]"
                                />
                            </div>

                            <div className="flex items-center space-x-2">
                                <input
                                    type="checkbox"
                                    id="is_public"
                                    checked={formData.is_public}
                                    onChange={(e) => setFormData({ ...formData, is_public: e.target.checked })}
                                    className="w-4 h-4 rounded border-slate-700 bg-slate-800 text-blue-600 focus:ring-blue-500 focus:ring-offset-slate-900"
                                />
                                <Label htmlFor="is_public" className="text-slate-300 cursor-pointer">
                                    Make this workflow public
                                </Label>
                            </div>

                            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 space-y-2">
                                <h3 className="text-sm font-semibold text-slate-300">Default Configuration</h3>
                                <p className="text-xs text-slate-400">
                                    This workflow will be created with 4 agents:
                                </p>
                                <ul className="text-xs text-slate-400 list-disc list-inside space-y-1">
                                    <li><span className="font-medium text-slate-300">Researcher</span> - Gathers information using web search</li>
                                    <li><span className="font-medium text-slate-300">Planner</span> - Creates execution plans</li>
                                    <li><span className="font-medium text-slate-300">Executor</span> - Executes the plan</li>
                                    <li><span className="font-medium text-slate-300">Coder</span> - Generates code</li>
                                </ul>
                                <p className="text-xs text-slate-500 mt-2">
                                    You can customize the configuration after creation.
                                </p>
                            </div>

                            <div className="flex gap-3 pt-4">
                                <Button
                                    type="submit"
                                    disabled={loading}
                                    className="flex-1 bg-blue-600 hover:bg-blue-500 text-white"
                                >
                                    {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                                    {loading ? 'Creating...' : 'Create Workflow'}
                                </Button>
                                <Link href="/" className="flex-1">
                                    <Button
                                        type="button"
                                        variant="outline"
                                        className="w-full border-slate-700 text-slate-300 hover:bg-slate-800"
                                        disabled={loading}
                                    >
                                        Cancel
                                    </Button>
                                </Link>
                            </div>
                        </form>
                    </CardContent>
                </Card>
            </div>
        </main>
    );
}
