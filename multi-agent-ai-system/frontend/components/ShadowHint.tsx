import { Lightbulb, X } from "lucide-react";
import { useState, useEffect } from "react";

export interface ShadowHint {
    message: string;
    suggestion_type: string;
    timestamp: string;
}

interface ShadowHintDisplayProps {
    hints: ShadowHint[];
}

export function ShadowHintDisplay({ hints }: ShadowHintDisplayProps) {
    const [latestHint, setLatestHint] = useState<ShadowHint | null>(null);
    const [dismissed, setDismissed] = useState(false);

    useEffect(() => {
        if (hints.length > 0) {
            setLatestHint(hints[hints.length - 1]);
            setDismissed(false);
        }
    }, [hints]);

    if (!latestHint || dismissed) return null;

    return (
        <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-right-10 fade-in duration-300">
            <div className="bg-slate-900 border border-violet-500/30 rounded-lg shadow-2xl shadow-violet-900/20 p-4 max-w-sm w-full backdrop-blur-sm relative">
                <button
                    onClick={() => setDismissed(true)}
                    className="absolute top-2 right-2 text-slate-500 hover:text-slate-300 transition-colors"
                >
                    <X className="w-4 h-4" />
                </button>

                <div className="flex gap-3">
                    <div className="w-8 h-8 rounded-lg bg-violet-500/20 flex items-center justify-center shrink-0">
                        <Lightbulb className="w-5 h-5 text-violet-400" />
                    </div>
                    <div>
                        <h4 className="text-sm font-semibold text-violet-300 mb-1">
                            Shadow Agent Suggestion
                        </h4>
                        <p className="text-sm text-slate-300 leading-relaxed">
                            {latestHint.message}
                        </p>
                        <span className="text-[10px] text-slate-500 mt-2 block">
                            {new Date(latestHint.timestamp).toLocaleTimeString()}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
}
