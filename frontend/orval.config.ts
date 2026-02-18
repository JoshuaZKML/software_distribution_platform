import { defineConfig } from 'orval';

export default defineConfig({
  api: {
    input: './schema.yaml', // path to your OpenAPI spec
    output: {
      target: './src/lib/api/generated/api.ts',
      schemas: './src/lib/api/generated/model',
      client: 'react-query',
      httpClient: 'axios',   // explicitly set to axios; mutator returns raw data
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