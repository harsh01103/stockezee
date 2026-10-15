import { Button } from '@/components/ui/button';
import { useAuth } from '../context/AuthProvider';
import { LogOut } from 'lucide-react';

export function LogoutButton() {
    const { logout } = useAuth();

    return (
        <Button
            variant="outline"
            onClick={logout}
            className="border-[#333333] text-white hover:bg-white/5 hover:border-[#4a5568] flex items-center gap-2"
        >
            <LogOut className="w-4 h-4" />
            Logout
        </Button>
    );
}
