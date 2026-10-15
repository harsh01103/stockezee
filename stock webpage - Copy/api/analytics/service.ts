import type { AnalyticsSummary, OptionChainRow } from "../options/types";

function confidenceForBalance(score: number) {
  if (score > 0.72) return "high" as const;
  if (score > 0.45) return "medium" as const;
  return "low" as const;
}

function getMaxPain(rows: OptionChainRow[]) {
  let bestStrike = rows[0]?.strike ?? 0;
  let bestPain = Number.POSITIVE_INFINITY;

  for (const settlement of rows) {
    let totalPain = 0;
    for (const row of rows) {
      totalPain += Math.max(settlement.strike - row.strike, 0) * row.call.oi;
      totalPain += Math.max(row.strike - settlement.strike, 0) * row.put.oi;
    }

    if (totalPain < bestPain) {
      bestPain = totalPain;
      bestStrike = settlement.strike;
    }
  }

  return bestStrike;
}

export function buildAnalyticsSummary(rows: OptionChainRow[]): AnalyticsSummary {
  const totalCallOi = rows.reduce((sum, row) => sum + row.call.oi, 0);
  const totalPutOi = rows.reduce((sum, row) => sum + row.put.oi, 0);
  const pcr = totalCallOi ? totalPutOi / totalCallOi : 0;

  const largestCall = rows.reduce((best, row) => (row.call.oi > best.call.oi ? row : best), rows[0]);
  const largestPut = rows.reduce((best, row) => (row.put.oi > best.put.oi ? row : best), rows[0]);
  const highestOiChange = rows.reduce((best, row) => {
    const bestAbs = Math.max(Math.abs(best.call.oiChange), Math.abs(best.put.oiChange));
    const nextAbs = Math.max(Math.abs(row.call.oiChange), Math.abs(row.put.oiChange));
    return nextAbs > bestAbs ? row : best;
  }, rows[0]);

  const ivValues = rows.flatMap((row) => [row.call.iv, row.put.iv]).filter((value): value is number => value != null);
  const ivAverage = ivValues.length ? ivValues.reduce((sum, value) => sum + value, 0) / ivValues.length : 0;
  const supportDistance = Math.abs(largestPut.strike - getMaxPain(rows));
  const resistanceDistance = Math.abs(largestCall.strike - getMaxPain(rows));

  return {
    pcr: {
      value: pcr.toFixed(2),
      confidence: confidenceForBalance(1 - Math.min(Math.abs(1 - pcr), 1)),
    },
    maxPain: {
      value: `${getMaxPain(rows)}`,
      confidence: "medium",
    },
    largestCallOi: {
      value: `${largestCall.strike} (${largestCall.call.oi.toLocaleString("en-IN")})`,
      confidence: confidenceForBalance(largestCall.call.oi / totalCallOi),
    },
    largestPutOi: {
      value: `${largestPut.strike} (${largestPut.put.oi.toLocaleString("en-IN")})`,
      confidence: confidenceForBalance(largestPut.put.oi / totalPutOi),
    },
    highestOiChange: {
      value:
        Math.abs(highestOiChange.call.oiChange) >= Math.abs(highestOiChange.put.oiChange)
          ? `CE ${highestOiChange.strike} (${highestOiChange.call.oiChange.toLocaleString("en-IN")})`
          : `PE ${highestOiChange.strike} (${highestOiChange.put.oiChange.toLocaleString("en-IN")})`,
      confidence: "medium",
    },
    ivSummary: {
      value: `${ivAverage.toFixed(1)} avg IV`,
      confidence: ivAverage > 22 ? "high" : ivAverage > 16 ? "medium" : "low",
    },
    supportEstimate: {
      value: `${largestPut.strike}`,
      confidence: supportDistance <= 2 * (rows[1]?.strike - rows[0]?.strike || 1) ? "high" : "medium",
    },
    resistanceEstimate: {
      value: `${largestCall.strike}`,
      confidence: resistanceDistance <= 2 * (rows[1]?.strike - rows[0]?.strike || 1) ? "high" : "medium",
    },
  };
}
