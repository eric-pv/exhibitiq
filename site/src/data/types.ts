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
    website: string | null;
    acquisition: { method: string; status: PipelineStatus; notes: string | null; assessedAt: string | null; reportPath: string | null };
    editions: {
      editionId: string;
      year: number;
      latestDatasetId: string | null;
      lastAcquisition: { method: string; status: PipelineStatus; finishedAt: string; notes: string | null; crawlRunId: string | null; recordsExtracted: number | null; errorCount: number | null } | null;
      datasets: { datasetId: string; dataOrigin: "synthetic" | "collected"; validation: PipelineStatus; completeness: Completeness; createdAt: string; schemaVersion: string;
        validatedAt: string | null; validator: string | null; validationErrors: number | null; isLatest: boolean }[];
    }[];
  }[];
  datasets: Record<string, {
    datasetId: string; exhibitionId: string; editionId: string; dataOrigin: "synthetic" | "collected"; createdAt: string;
    completeness: Completeness;
    companies: { companyId: string; name: string; country: string | null; verificationStatus: string; aliases: string[]; listed: boolean; booths: string[]; detail: CompanyRecord }[];
    listedParticipations: number;
    sources: Record<string, SourceInfo>;
    /** profileId → term_id → matching companies (keyword candidates, W3-01) */
    keywordMatches: Record<string, Record<string, { companyIds: string[]; sourceIds: string[] }>>;
  }>;
  analyses: {
    analysisId: string; title: string; inputHash: string; schemaVersion: string; model: string | null; knowledgeVersion: string | null;
    cost: { recorded: boolean; input_tokens?: number; output_tokens?: number; amount?: number; currency?: string; measured_by?: string; notes?: string } | null;
    additionalInputs: { datasetId: string; contentHash: string }[]; evidenceSourceIds: string[]; analysisType: string; inputDatasetId: string; generatedAt: string;
    reviewStatus: "draft" | "human_reviewed" | "approved" | "rejected"; dataOrigin: "synthetic" | "collected";
    analyzedCompanyIds: string[]; highPriorityRecommendations: number; claimCounts: Record<string, number>;
    detail: AnalysisDetail;
    config: AnalysisConfigRef | null;
  }[];
  settings: { profiles: { profile: AnalysisProfile; hash: string }[];
    products: { productId: string; name: string; nameEn: string | null; summary: string; approvalStatus: string; approvedAt: string | null; terms: string[]; specCount: number }[];
    termLabels: Record<string, string>;
    scoreModels: { scoreModelId: string; approvalStatus: string; notes: string | null; factors: { factorId: string; label: string; defaultMax: number }[] }[];
    schemas: Record<string, object> };
  reportTemplates: { version: string; section_titles: Record<string, string>; types: Record<string, { label: string; sections: string[] }> };
  notices: { level: "info" | "warning" | "error"; message: string; occurredAt: string; exhibitionId: string | null; datasetId: string | null }[];
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

export type Level = "low" | "medium" | "high";
export interface EntityRef { entity_type: "exhibition" | "edition" | "company" | "participation"; entity_id: string }

/** analysis_result.schema.json as the Dashboard shows it (W2-04). Everything here is AI output unless claimType is "fact". */
export interface AnalysisDetail {
  summary: string | null; skillVersion: string | null;
  conclusions: {
    claimId: string; claimType: "fact" | "inference" | "unknown"; statement: string; subjects: EntityRef[]; sourceIds: string[];
    verificationStatus: string | null; confidence: Level | null; rationale: string | null; missingData: string | null; uncertaintyIds: string[];
  }[];
  uncertainties: { uncertaintyId: string; description: string; impact: Level }[];
  scores: {
    scoreId: string; modelId: string; subject: EntityRef; total: number; max: number; rank: number | null;
    factors: { factorId: string; label: string; status: "scored" | "insufficient_data"; points: number; max: number; sourceIds: string[]; claimIds: string[]; rationale: string | null }[];
  }[];
  relationships: { relationshipId: string; companyId: string; type: string; rationale: string | null; confidence: Level | null; sourceIds: string[]; claimIds: string[] }[];
  recommendations: {
    recommendationId: string; type: string; productIds: string[]; statement: string; rationale: string | null; priority: Level; subjects: EntityRef[];
    assumptions: string[]; sourceIds: string[]; claimIds: string[]; scoreIds: string[]; uncertaintyIds: string[];
  }[];
}

export type AnalysisMode = "bxr_opportunity" | "industry_research" | "competitor_research";
export const REL_TYPES = ["potential_customer", "competitor", "partner", "channel"] as const;
export type RelType = (typeof REL_TYPES)[number];
export interface Keyword { term_id: string; category: string; label: string; label_en?: string; synonyms?: string[]; enabled: boolean; notes?: string }

/** analysis_profile.schema.json (snake_case kept: this object is exported/imported as the contract file itself). */
export interface AnalysisProfile {
  schema_version: string; profile_id: string; version: number; name: string; description?: string; mode: AnalysisMode;
  keywords: Keyword[];
  relationship_signals?: Partial<Record<RelType, string[]>>;
  score_model?: { score_model_id: string; weights: Record<string, number> };
  targets?: { bxr_product_ids?: string[]; company_names?: string[]; focus_term_ids?: string[] };
  updated_at: string; updated_by?: string; notes?: string;
}

export interface AnalysisConfigRef {
  profileId: string; profileVersion: number; profileHash: string; mode: AnalysisMode; keywordCount: number; keywordLabels: string[];
  scoreModelId: string | null; bxrProductsStatus: string | null;
}
