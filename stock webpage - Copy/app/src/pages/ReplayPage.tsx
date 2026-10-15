import { ReplayMode } from '../features/replay/components/ReplayMode';

export function ReplayPage() {
    return (
        <div className="min-h-screen bg-[#050505] pt-8 px-4 pb-20">
            <div className="max-w-[1200px] mx-auto">
                <ReplayMode />
            </div>
        </div>
    );
}
