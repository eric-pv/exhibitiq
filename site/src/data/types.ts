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
    companies: { companyId: string; name: string; country: string | null; verificationStatus: string }[];
    listedParticipations: number;
  }>;
  analyses: {
    analysisId: string; title: string; analysisType: string; inputDatasetId: string; generatedAt: string;
    reviewStatus: "draft" | "human_reviewed" | "approved" | "rejected"; dataOrigin: "synthetic" | "collected";
    analyzedCompanyIds: string[]; highPriorityRecommendations: number; claimCounts: Record<string, number>;
  }[];
  notices: { level: "info" | "warning" | "error"; message: string; occurredAt: string }[];
}
