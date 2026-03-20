import type {
  FrameReceiptPayload,
  SourceAdapter,
  SourceAdapterResult,
  SourceQuery,
  SourceRecord,
} from "@frame/types";

function nowIso(): string {
  return new Date().toISOString();
}

export async function fetchFecContext(
  query: SourceQuery,
): Promise<SourceAdapterResult> {
  const candidateId = String(query.params.candidateId ?? "");
  if (!candidateId) {
    return { sources: [], errors: ["fec: candidateId is required"] };
  }

  const apiKey = (query.params.apiKey as string | undefined) ?? "DEMO_KEY";
  const baseUrl = "https://api.open.fec.gov/v1";
  const sources: SourceRecord[] = [];
  const errors: string[] = [];
  let candidateName = candidateId;
  let allCycleTotals: Array<{
    cycle: number;
    receipts: number;
    pacContributions: number;
    individualContributions: number;
    electionYear: number;
  }> = [];

  try {
    const searchUrl = `${baseUrl}/candidates/?candidate_id=${candidateId}&api_key=${apiKey}`;
    const searchRes = await fetch(searchUrl);
    const searchData = await searchRes.json() as {
      results?: Array<{
        name?: string;
        office_full?: string;
        state?: string;
        party_full?: string;
        election_years?: number[];
      }>;
    };
    if (searchData.results?.[0]) {
      const c = searchData.results[0];
      candidateName = c.name ?? candidateId;
      sources.push({
        id: `fec-candidate-${candidateId}`,
        adapter: "fec",
        url: searchUrl,
        title: `FEC candidate profile: ${candidateName}`,
        retrievedAt: nowIso(),
        externalRef: candidateId,
        metadata: {
          candidateId,
          candidateName,
          office: c.office_full,
          state: c.state,
          party: c.party_full,
          electionYears: c.election_years,
        },
      });
    }
  } catch (e) {
    errors.push(`fec candidate search failed: ${String(e)}`);
  }

  try {
    const totalsUrl = `${baseUrl}/candidates/totals/?candidate_id=${candidateId}&api_key=${apiKey}&per_page=20&sort=-election_year`;
    const totalsRes = await fetch(totalsUrl);
    const totalsData = await totalsRes.json() as {
      results?: Array<{
        cycle?: number;
        receipts?: number;
        other_political_committee_contributions?: number;
        individual_itemized_contributions?: number;
        election_year?: number;
      }>;
    };
    allCycleTotals = (totalsData.results ?? [])
      .map((r) => ({
        cycle: r.cycle ?? 0,
        receipts: r.receipts ?? 0,
        pacContributions: r.other_political_committee_contributions ?? 0,
        individualContributions: r.individual_itemized_contributions ?? 0,
        electionYear: r.election_year ?? r.cycle ?? 0,
      }))
      .filter((r) => r.receipts > 0);

    sources.push({
      id: `fec-totals-${candidateId}`,
      adapter: "fec",
      url: totalsUrl,
      title: `FEC fundraising totals by cycle: ${candidateName}`,
      retrievedAt: nowIso(),
      externalRef: candidateId,
      metadata: { candidateId, allCycleTotals },
    });
  } catch (e) {
    errors.push(`fec totals lookup failed: ${String(e)}`);
  }

  return {
    sources,
    errors: errors.length ? errors : undefined,
    metadata: { candidateName, allCycleTotals },
  };
}

export async function buildLiveFecReceipt(
  candidateId: string,
  apiKey: string = "DEMO_KEY",
): Promise<FrameReceiptPayload> {
  const result = await fetchFecContext({
    kind: "fec",
    params: { candidateId, apiKey },
  });

  const { candidateName = candidateId, allCycleTotals = [] } = (result.metadata ?? {}) as {
    candidateName?: string;
    allCycleTotals?: Array<{
      cycle: number;
      receipts: number;
      pacContributions: number;
      individualContributions: number;
      electionYear: number;
    }>;
  };

  const sources = result.sources;
  const narrative: Array<{ text: string; sourceId: string }> = [];
  const totalsSourceId = `fec-totals-${candidateId}`;

  if (!sources.find((s) => s.id === totalsSourceId)) {
    sources.push({
      id: totalsSourceId,
      adapter: "fec",
      url: `https://api.open.fec.gov/v1/candidates/totals/?candidate_id=${candidateId}`,
      title: `FEC fundraising totals: ${candidateName}`,
      retrievedAt: nowIso(),
      externalRef: candidateId,
      metadata: { note: "API unavailable at signing time" },
    });
  }

  if (allCycleTotals.length === 0) {
    narrative.push({
      text: `FEC records were queried for candidate ${candidateName} (ID: ${candidateId}) at signing time. No fundraising totals were returned.`,
      sourceId: totalsSourceId,
    });
  } else {
    const careerTotal = allCycleTotals.reduce((sum, c) => sum + c.receipts, 0);
    const careerPac = allCycleTotals.reduce((sum, c) => sum + c.pacContributions, 0);
    const pacPct = careerTotal > 0 ? ((careerPac / careerTotal) * 100).toFixed(1) : "0";

    narrative.push({
      text: `According to FEC records, ${candidateName} (ID: ${candidateId}) raised a total of $${careerTotal.toLocaleString()} across ${allCycleTotals.length} election cycle(s) on record.`,
      sourceId: totalsSourceId,
    });

    narrative.push({
      text: `Of that total, $${careerPac.toLocaleString()} (${pacPct}%) came from PACs and other political committees, with $${(careerTotal - careerPac).toLocaleString()} from individual contributors.`,
      sourceId: totalsSourceId,
    });

    const electionCycles = allCycleTotals.filter((c) => c.electionYear === c.cycle);
    for (const c of electionCycles.slice(0, 3)) {
      narrative.push({
        text: `In the ${c.cycle} election cycle, ${candidateName} raised $${c.receipts.toLocaleString()} total, including $${c.pacContributions.toLocaleString()} from PACs.`,
        sourceId: totalsSourceId,
      });
    }
  }

  return {
    schemaVersion: "1.0.0",
    receiptId: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
    claims: [
      {
        id: "claim-1",
        statement: `Live FEC fundraising record for ${candidateName} (${candidateId})`,
        assertedAt: new Date().toISOString(),
      },
    ],
    sources,
    narrative,
    contentHash: "",
  };
}

/** OpenSecrets — money-in-politics summaries (illustrative stub). */
export async function fetchOpenSecretsSummary(
  query: SourceQuery,
): Promise<SourceAdapterResult> {
  const cid = String(query.params.candidateId ?? "");
  if (!cid) {
    return { sources: [], errors: ["opensecrets: candidateId is required"] };
  }
  const sources: SourceRecord[] = [
    {
      id: `os-cand-${cid}`,
      adapter: "opensecrets",
      url: `https://www.opensecrets.org/members-of-congress/summary?cid=${encodeURIComponent(cid)}`,
      title: `OpenSecrets summary ${cid}`,
      retrievedAt: nowIso(),
      externalRef: cid,
      metadata: { candidateId: cid },
    },
  ];
  return { sources };
}

/** ProPublica Congress API — member & votes (illustrative stub). */
export async function fetchProPublicaMember(
  query: SourceQuery,
): Promise<SourceAdapterResult> {
  const bioguide = String(query.params.bioguideId ?? "");
  if (!bioguide) {
    return { sources: [], errors: ["propublica: bioguideId is required"] };
  }
  const sources: SourceRecord[] = [
    {
      id: `pp-member-${bioguide}`,
      adapter: "propublica",
      url: `https://projects.propublica.org/api-docs/congress-api/members`,
      title: `ProPublica Congress API member ${bioguide}`,
      retrievedAt: nowIso(),
      externalRef: bioguide,
      metadata: { bioguideId: bioguide },
    },
  ];
  return { sources };
}

/** Senate LDA / House disclosures — lobbying registrations (illustrative stub). */
export async function fetchLobbyingFiling(
  query: SourceQuery,
): Promise<SourceAdapterResult> {
  const reg = String(query.params.registrationId ?? "");
  if (!reg) {
    return {
      sources: [],
      errors: ["lobbying: registrationId is required"],
    };
  }
  const sources: SourceRecord[] = [
    {
      id: `lda-${reg}`,
      adapter: "lobbying",
      url: `https://lda.senate.gov/filings/public/filing/${encodeURIComponent(reg)}/`,
      title: `Lobbying disclosure ${reg}`,
      retrievedAt: nowIso(),
      externalRef: reg,
      metadata: { registrationId: reg },
    },
  ];
  return { sources };
}

/** SEC EDGAR — issuer filings (illustrative stub). */
export async function fetchEdgarCompany(
  query: SourceQuery,
): Promise<SourceAdapterResult> {
  const cik = String(query.params.cik ?? "");
  if (!cik) {
    return { sources: [], errors: ["edgar: cik is required"] };
  }
  const padded = cik.padStart(10, "0");
  const sources: SourceRecord[] = [
    {
      id: `edgar-${padded}`,
      adapter: "edgar",
      url: `https://www.sec.gov/cgi-bin/browse-edgar?CIK=${padded}&owner=exclude`,
      title: `EDGAR browse CIK ${padded}`,
      retrievedAt: nowIso(),
      externalRef: padded,
      metadata: { cik: padded },
    },
  ];
  return { sources };
}

const registry: Record<string, SourceAdapter> = {
  fec: fetchFecContext,
  opensecrets: fetchOpenSecretsSummary,
  propublica: fetchProPublicaMember,
  lobbying: fetchLobbyingFiling,
  edgar: fetchEdgarCompany,
  manual: async (q) => ({
    sources: (q.params.sources as SourceRecord[] | undefined) ?? [],
  }),
};

/**
 * Dispatches a normalized `SourceQuery` to the matching adapter.
 */
export async function runAdapter(query: SourceQuery): Promise<SourceAdapterResult> {
  const fn = registry[query.kind];
  if (!fn) {
    return { sources: [], errors: [`Unknown adapter: ${query.kind}`] };
  }
  return fn(query);
}

export { registry as sourceAdapterRegistry };
