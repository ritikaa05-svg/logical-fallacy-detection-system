export interface FallacyColor {
  bg: string;
  border: string;
  text: string;
  hex: string;
}

export const FALLACY_COLORS: Record<string, FallacyColor> = {
  ad_hominem:           { bg: 'bg-red-100 dark:bg-red-900/30', border: 'border-red-500', text: 'text-red-700 dark:text-red-300', hex: '#EF4444' },
  straw_man:            { bg: 'bg-red-100 dark:bg-red-900/30', border: 'border-red-500', text: 'text-red-700 dark:text-red-300', hex: '#EF4444' },
  genetic_fallacy:      { bg: 'bg-red-100 dark:bg-red-900/30', border: 'border-red-500', text: 'text-red-700 dark:text-red-300', hex: '#EF4444' },
  moving_goalposts:     { bg: 'bg-red-100 dark:bg-red-900/30', border: 'border-red-500', text: 'text-red-700 dark:text-red-300', hex: '#EF4444' },
  affirming_consequent: { bg: 'bg-red-100 dark:bg-red-900/30', border: 'border-red-500', text: 'text-red-700 dark:text-red-300', hex: '#EF4444' },
  denying_antecedent:   { bg: 'bg-red-100 dark:bg-red-900/30', border: 'border-red-500', text: 'text-red-700 dark:text-red-300', hex: '#EF4444' },
  undistributed_middle: { bg: 'bg-red-100 dark:bg-red-900/30', border: 'border-red-500', text: 'text-red-700 dark:text-red-300', hex: '#EF4444' },
  illicit_major:        { bg: 'bg-red-100 dark:bg-red-900/30', border: 'border-red-500', text: 'text-red-700 dark:text-red-300', hex: '#EF4444' },
  illicit_minor:        { bg: 'bg-red-100 dark:bg-red-900/30', border: 'border-red-500', text: 'text-red-700 dark:text-red-300', hex: '#EF4444' },
  exclusive_premises:   { bg: 'bg-red-100 dark:bg-red-900/30', border: 'border-red-500', text: 'text-red-700 dark:text-red-300', hex: '#EF4444' },
  existential_fallacy:  { bg: 'bg-red-100 dark:bg-red-900/30', border: 'border-red-500', text: 'text-red-700 dark:text-red-300', hex: '#EF4444' },
  appeal_to_emotion:    { bg: 'bg-red-100 dark:bg-red-900/30', border: 'border-red-500', text: 'text-red-700 dark:text-red-300', hex: '#EF4444' },
  red_herring:          { bg: 'bg-amber-100 dark:bg-amber-900/30', border: 'border-amber-500', text: 'text-amber-700 dark:text-amber-300', hex: '#F59E0B' },
  tu_quoque:            { bg: 'bg-amber-100 dark:bg-amber-900/30', border: 'border-amber-500', text: 'text-amber-700 dark:text-amber-300', hex: '#F59E0B' },
  tu_quoque_contextual: { bg: 'bg-amber-100 dark:bg-amber-900/30', border: 'border-amber-500', text: 'text-amber-700 dark:text-amber-300', hex: '#F59E0B' },
  false_cause:          { bg: 'bg-amber-100 dark:bg-amber-900/30', border: 'border-amber-500', text: 'text-amber-700 dark:text-amber-300', hex: '#F59E0B' },
  hasty_generalization: { bg: 'bg-amber-100 dark:bg-amber-900/30', border: 'border-amber-500', text: 'text-amber-700 dark:text-amber-300', hex: '#F59E0B' },
  false_dilemma:        { bg: 'bg-amber-100 dark:bg-amber-900/30', border: 'border-amber-500', text: 'text-amber-700 dark:text-amber-300', hex: '#F59E0B' },
  slippery_slope:       { bg: 'bg-amber-100 dark:bg-amber-900/30', border: 'border-amber-500', text: 'text-amber-700 dark:text-amber-300', hex: '#F59E0B' },
  bandwagon:            { bg: 'bg-amber-100 dark:bg-amber-900/30', border: 'border-amber-500', text: 'text-amber-700 dark:text-amber-300', hex: '#F59E0B' },
  equivocation:         { bg: 'bg-emerald-100 dark:bg-emerald-900/30', border: 'border-emerald-500', text: 'text-emerald-700 dark:text-emerald-300', hex: '#10B981' },
  amphiboly:            { bg: 'bg-emerald-100 dark:bg-emerald-900/30', border: 'border-emerald-500', text: 'text-emerald-700 dark:text-emerald-300', hex: '#10B981' },
  accent:               { bg: 'bg-emerald-100 dark:bg-emerald-900/30', border: 'border-emerald-500', text: 'text-emerald-700 dark:text-emerald-300', hex: '#10B981' },
  appeal_to_nature:     { bg: 'bg-emerald-100 dark:bg-emerald-900/30', border: 'border-emerald-500', text: 'text-emerald-700 dark:text-emerald-300', hex: '#10B981' },
  appeal_to_tradition:  { bg: 'bg-emerald-100 dark:bg-emerald-900/30', border: 'border-emerald-500', text: 'text-emerald-700 dark:text-emerald-300', hex: '#10B981' },
  composition:          { bg: 'bg-emerald-100 dark:bg-emerald-900/30', border: 'border-emerald-500', text: 'text-emerald-700 dark:text-emerald-300', hex: '#10B981' },
  division:             { bg: 'bg-emerald-100 dark:bg-emerald-900/30', border: 'border-emerald-500', text: 'text-emerald-700 dark:text-emerald-300', hex: '#10B981' },
  no_true_scotsman:     { bg: 'bg-emerald-100 dark:bg-emerald-900/30', border: 'border-emerald-500', text: 'text-emerald-700 dark:text-emerald-300', hex: '#10B981' },
  begging_the_question: { bg: 'bg-emerald-100 dark:bg-emerald-900/30', border: 'border-emerald-500', text: 'text-emerald-700 dark:text-emerald-300', hex: '#10B981' },
  appeal_to_authority:  { bg: 'bg-emerald-100 dark:bg-emerald-900/30', border: 'border-emerald-500', text: 'text-emerald-700 dark:text-emerald-300', hex: '#10B981' },
  factual_statement:    { bg: 'bg-blue-100 dark:bg-blue-900/30', border: 'border-blue-500', text: 'text-blue-700 dark:text-blue-300', hex: '#3B82F6' },
  valid_reasoning:      { bg: 'bg-emerald-100 dark:bg-emerald-900/30', border: 'border-emerald-500', text: 'text-emerald-700 dark:text-emerald-300', hex: '#10B981' },
};
