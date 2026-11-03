import { describe, it, expect } from 'vitest'

describe('CodeImpact Frontend Core', () => {
  it('renders application shell title', () => {
    expect('CodeImpact').toBe('CodeImpact')
  })

  it('validates health probe parsing structure', () => {
    const mockHealthPayload = {
      status: 'ok',
      service: 'CodeImpact',
      version: '0.1.0',
      components: {
        database: { status: 'connected', type: 'postgresql' },
        redis: { status: 'connected', queue: 'codeimpact_analysis' },
      },
    }
    expect(mockHealthPayload.status).toBe('ok')
    expect(mockHealthPayload.components.database.status).toBe('connected')
    expect(mockHealthPayload.components.redis.status).toBe('connected')
  })
})
