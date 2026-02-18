// Compatibility layer for Orval-generated types
// This ensures DataTag works with 3 type parameters as used in generated code

import type { QueryKey } from '@tanstack/react-query';

// Create a DataTag type that accepts 3 parameters (for Orval compatibility)
// while being compatible with React Query's implementation
export type DataTag<T = any, K extends QueryKey = QueryKey, E = any> = any & {
  readonly __queryKey?: K;
  readonly __data?: T;
  readonly __error?: E;
};
