export interface TokenContribution {
  token: string;
  score: number;
  start: number;
  end: number;
}

export interface FallacySpan {
  text: string;
  start: number;
  end: number;
  saliency: number;
}

export interface FallacyAnnotation {
  type: string;
  label: string;
  confidence: number;
  definition: string;
  explanation: string;
  sentence: string;
  sentence_start: number;
  sentence_end: number;
  spans: FallacySpan[];
}

export interface FallacyDetail {
  name: string;
  quote: string;
  explanation: string;
  confidence: number;
}

export interface ArgumentStructure {
  status: string;
  is_argument: boolean;
  premises: string[];
  conclusion: string;
  reasoning_type: string;
  fallacy: string | null;
  confidence: number;
  explanation: string;
  latency_ms: number;
}

export interface AnalysisResult {
  version: string;
  input_text: string;
  is_logical_claim: boolean;
  salience_score: number;
  coarse_category: string | null;
  fine_labels: string[];
  confidence_scores: number[];
  salient_tokens: TokenContribution[];
  fallacies: FallacyDetail[];
  argument_structure: ArgumentStructure | null;
  annotations: FallacyAnnotation[];
  z3_status: string | null;
  correction_strategy: string | null;
  logic_score: number;
  total_latency_ms: number;
  stage_latencies: Record<string, number>;
  cached: boolean;
  reranked: boolean;
  /** Active degradation tier: 0=full (GPU+LLM local+Z3), 1=ONNX-CPU+LLM 4-bit, 2=ONNX-CPU+API fallback, 3=ONNX-CPU+rule-based synthesis */
  degradation_tier: number;
  device_info: Record<string, unknown>;
  timestamp: string;
  /** Phase 9.4: ID for fetching the symbolic trace (/api/v1/traces/{id}) */
  analysis_id?: string;
  /** Phase 6: cross-segment contradiction analysis (null for single-segment) */
  cross_segment_contradictions: CrossSegmentContradictions | null;
}

export interface AnalysisRequest {
  text: string;
  skip_cache?: boolean;
  generate_correction?: boolean;
  include_explanations?: boolean;
  /** If True, force entirely local inference (skip HuggingFace API fallback) */
  localize?: boolean;
  fast_track?: boolean;
  document_id?: string;
}

export type PipelineStatus = 'idle' | 'loading' | 'success' | 'error';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  action?: string;
  logic_score?: number;
  fallacies?: string[];
  isStreaming?: boolean;
}

export interface DebateRequest {
  session_id?: string;
  user_input: string;
}

export interface DebateState {
  fallacy_density: number;
  argument_depth: number;
  user_sentiment: number;
  logic_score: number;
}

export interface DebateResponse {
  session_id: string;
  turn_number: number;
  agent_response: string;
  agent_action: string;
  detected_fallacies: string[];
  logic_score: number;
  debate_state: DebateState;
  total_turns: number;
  cumulative_reward: number;
  suggested_next_actions: string[];
}

export interface HealthHistoryEntry {
  timestamp: string;
  score: number;
}

export interface SystemHealth {
  status: string;
  version: string;
  classifier_mode: string;
  device: Record<string, unknown>;
  cache: Record<string, unknown>;
  timestamp: string;
}

// ────────────────────────────────────────────────
// Phase 6: Contradiction Detection
// ────────────────────────────────────────────────

export interface ContradictionMatch {
  segment_a_index: number;
  segment_b_index: number;
  segment_a_page: number | null;
  segment_b_page: number | null;
  type: 'lexical' | 'z3' | 'semantic';
  description: string;
  severity: 'minor' | 'moderate' | 'critical';
  confidence: number;
}

export interface CrossSegmentContradictions {
  contradictions: ContradictionMatch[];
  total_pairs_checked: number;
  latency_ms: number;
}

// ────────────────────────────────────────────────
// Phase 6: Document Ingestion
// ────────────────────────────────────────────────

export interface PageInfo {
  page_number: number;
  text_preview: string;
  start_offset: number;
  end_offset: number;
}

export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  mime_type: string;
  page_count: number;
  char_count: number;
  text_preview: string;
  pages: PageInfo[];
}

export interface DocumentAnalysisRequest {
  document_id: string;
  skip_cache?: boolean;
  fast_track?: boolean;
  include_explanations?: boolean;
}

export interface PerPageResult {
  page_number: number;
  result: AnalysisResult;
}

export interface DocumentAnalysisResult {
  document: DocumentUploadResponse;
  overall: AnalysisResult;
  per_page: PerPageResult[];
}

// ────────────────────────────────────────────────
// Phase 9.4: Trace / Dashboard
// ────────────────────────────────────────────────

export interface TraceNode {
  node_type: string;
  label: string;
  confidence?: number;
  saliency_tokens?: string[];
  children?: TraceNode[];
}

export interface TraceResponse {
  analysis_id: string;
  trace_tree: TraceNode;
}
