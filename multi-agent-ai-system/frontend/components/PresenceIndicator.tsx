import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { User, Shield, Eye } from "lucide-react";

interface ConnectedUser {
    user_id: string;
    role: 'driver' | 'approver' | 'shadow';
}

interface PresenceIndicatorProps {
    users: ConnectedUser[];
}

export function PresenceIndicator({ users }: PresenceIndicatorProps) {
    if (!users || users.length === 0) return null;

    const getIcon = (role: string) => {
        switch (role) {
            case 'driver': return <User className="w-3 h-3" />;
            case 'approver': return <Shield className="w-3 h-3" />;
            case 'shadow': return <Eye className="w-3 h-3" />;
            default: return <User className="w-3 h-3" />;
        }
    };

    const getColor = (role: string) => {
        switch (role) {
            case 'driver': return 'bg-blue-500/20 text-blue-400 border-blue-500/50';
            case 'approver': return 'bg-purple-500/20 text-purple-400 border-purple-500/50';
            case 'shadow': return 'bg-slate-500/20 text-slate-400 border-slate-500/50';
            default: return 'bg-slate-500/20 text-slate-400';
        }
    };

    return (
        <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 font-medium mr-1">Online:</span>
            <div className="flex -space-x-2">
                <TooltipProvider>
                    {users.map((u, i) => (
                        <Tooltip key={`${u.user_id}-${i}`}>
                            <TooltipTrigger>
                                <div className={`flex items-center justify-center w-8 h-8 rounded-full border-2 border-slate-950 ${getColor(u.role)}`}>
                                    {getIcon(u.role)}
                                </div>
                            </TooltipTrigger>
                            <TooltipContent>
                                <p className="text-xs font-semibold">{u.user_id}</p>
                                <p className="text-[10px] capitalize text-slate-400">{u.role}</p>
                            </TooltipContent>
                        </Tooltip>
                    ))}
                </TooltipProvider>
            </div>
        </div>
    );
}
