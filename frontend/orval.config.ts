import { defineConfig } from 'orval';

export default defineConfig({
  api: {
    input: './schema.yaml',
    output: {
      target: './lib/api/generated.ts',
      client: 'react-query',
      baseUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
      mock: true, // generates MSW handlers
      override: {
        mutator: {
          path: './lib/api/client.ts',
          name: 'apiClient',
        },
      },
    },
  },
});