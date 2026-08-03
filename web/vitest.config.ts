import { defineConfig } from 'vitest/config'

// Testes unitarios das libs PURAS do piloto (format/colors/coord/select-filter).
// Ambiente 'node': sao funcoes puras (Intl, regex, Math), sem DOM. Os componentes
// React e os fluxos ponta-a-ponta ficam para o E2E (Playwright), fora daqui.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
})
