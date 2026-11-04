/**
 * View model produced by scripts/build-bundle.mjs from schema-validated files.
 * Pages never read raw packages; they go through repository.ts.
 */
import type { CompletenessStatus } from "../components/status/CompletenessIndicator";
import type { PipelineStatus } from "../components/status/StatusBadge";

export type DataOrigin = "synthetic" | "collected" | "none";
export interface Completeness { status: CompletenessStatus; official: number | null; collected: number }

export interface Bundle {
  schemaVersion: string;
  generatedFrom: { index: string; analyses: string };
  indexGeneratedAt: string;
  dataOrigin: DataOrigin;
  exhibitions: {
    exhibitionId: string;
    name: string;
    country: string | null;
    acquisition: { method: string; status: PipelineStatus; notes: string | null };
    editions: {
      editionId: string;
      year: number;
      latestDatasetId: string | null;
      lastAcquisition: { method: string; status: PipelineStatus; finishedAt: string; notes: string | null } | null;
      datasets: { datasetId: string; dataOrigin: "synthetic" | "collected"; validation: PipelineStatus; completeness: Completeness }[];
    }[];
  }[];
  datasets: Record<string, {
    datasetId: string; exhibitionId: string; editionId: string; dataOrigin: "synthetic" | "collected"; createdAt: string;
    completeness: Completeness;
    companies: { companyId: string; name: string; country: string | null; verificationStatus: string; aliases: string[]; listed: boolean; booths: string[]; detail: CompanyRecord }[];
    listedParticipations: number;
    sources: Record<string, SourceInfo>;
  }>;
  analyses: {
    analysisId: string; title: string; analysisType: string; inputDatasetId: string; generatedAt: string;
    reviewStatus: "draft" | "human_reviewed" | "approved" | "rejected"; dataOrigin: "synthetic" | "collected";
    analyzedCompanyIds: string[]; highPriorityRecommendations: number; claimCounts: Record<string, number>;
  }[];
  notices: { level: "info" | "warning" | "error"; message: string; occurredAt: string }[];
}

/** A source record (schemas/v1/source.schema.json) as the Dashboard shows it. */
export interface SourceInfo {
  sourceId: string; sourceType: string; url: string | null; title: string | null; publisher: string | null;
  retrievedAt: string; crawlRunId: string | null; contentSha256: string;
  snapshot: { storage: string; locator: string | null; retainedUntil: string | null };
  notes: string | null;
}

/** Field sources: keys are record field names; unlisted fields fall back to the record-level sourceIds. */
export type FieldSources = Record<string, string[]>;

export interface ParticipationRecord {
  participationId: string; editionId: string; nameAsListed: string; participationType: string; listingStatus: "listed" | "removed";
  booth: string | null; hall: string | null; countryAsListed: string | null; websiteAsListed: string | null;
  categories: string[]; products: string[]; firstSeenAt: string | null; lastSeenAt: string | null;
  verificationStatus: string; sourceIds: string[]; fieldSources: FieldSources; notes: string | null;
}

export interface CompanyRecord {
  nameEn: string | null; nameZhHant: string | null; website: string | null; domains: string[]; description: string | null;
  status: "active" | "merged"; mergedInto: string | null; firstSeenAt: string | null; notes: string | null;
  sourceIds: string[]; fieldSources: FieldSources;
  aliases: { name: string; lang: string | null; sourceIds: string[] }[];
  participations: ParticipationRecord[];
}
