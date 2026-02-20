import { defineConfig } from 'orval';

export default defineConfig({
  api: {
    input: './schema.yaml', // your OpenAPI spec
    output: {
      target: './src/lib/api/generated/api.ts',
      schemas: './src/lib/api/generated/model',
      client: 'react-query',
      httpClient: 'axios',
      baseUrl: '', // ← forces relative paths
      mock: true,
      prettier: true,
      override: {
        mutator: {
          path: './src/lib/api/fetcher.ts',
          name: 'fetcher',
        },
      },
    },
  },
});