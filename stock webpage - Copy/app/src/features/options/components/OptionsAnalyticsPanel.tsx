import type { AnalyticsResponse } from "../types";

export function OptionsAnalyticsPanel({
  analytics,
  loading,
  error,
}: {
  analytics: AnalyticsResponse | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading) {
    return <div className="p-8 text-center text-sm font-medium text-[#7a7a7a]">Loading analytics...</div>;
  }
  if (error) {
    return <div className="p-8 text-center text-sm font-medium text-[#eb5b3c]">{error}</div>;
  }
  if (!analytics) return null;

  const metrics = [
    { label: "PCR", value: analytics.analytics.pcr.value, conf: analytics.analytics.pcr.confidence },
    { label: "Max Pain", value: analytics.analytics.maxPain.value, conf: analytics.analytics.maxPain.confidence },
    { label: "High Call OI", value: analytics.analytics.largestCallOi.value, conf: analytics.analytics.largestCallOi.confidence },
    { label: "High Put OI", value: analytics.analytics.largestPutOi.value, conf: analytics.analytics.largestPutOi.confidence },
    { label: "OI Change", value: analytics.analytics.highestOiChange.value, conf: analytics.analytics.highestOiChange.confidence },
    { label: "IV Summary", value: analytics.analytics.ivSummary.value, conf: analytics.analytics.ivSummary.confidence },
    { label: "Support", value: analytics.analytics.supportEstimate.value, conf: analytics.analytics.supportEstimate.confidence },
    { label: "Resistance", value: analytics.analytics.resistanceEstimate.value, conf: analytics.analytics.resistanceEstimate.confidence },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {metrics.map((metric) => (
        <div key={metric.label} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 transition-colors hover:border-white/20">
          <div className="flex items-center justify-between">
            <div className="text-[10px] font-bold text-white/40 uppercase tracking-[0.2em]">{metric.label}</div>
            <div
              className={`h-2 w-2 rounded-full shadow-[0_0_8px_currentColor] ${
                metric.conf === "high" ? "bg-emerald-500 text-emerald-500" : metric.conf === "medium" ? "bg-amber-500 text-amber-500" : "bg-red-500 text-red-500"
              }`}
              title={`${metric.conf} confidence`}
            />
          </div>
          <div className="mt-2 text-xl font-bold text-white">{metric.value}</div>
        </div>
      ))}
    </div>
  );
}
