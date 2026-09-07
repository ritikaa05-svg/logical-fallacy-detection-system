export class ApiResponseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ApiResponseError';
  }
}

export function validateAnalysisResult(data: any): void {
  if (!data || typeof data !== 'object') {
    throw new ApiResponseError('Invalid response: expected an object');
  }
  const requiredFields = ['fallacies', 'fine_labels', 'coarse_category', 'is_logical_claim'] as const;
  for (const field of requiredFields) {
    if (!(field in data)) {
      throw new ApiResponseError(`Invalid response: missing required field "${field}"`);
    }
  }
  if (!Array.isArray(data.fallacies)) {
    throw new ApiResponseError('Invalid response: "fallacies" must be an array');
  }
  if (!Array.isArray(data.fine_labels)) {
    throw new ApiResponseError('Invalid response: "fine_labels" must be an array');
  }
}
