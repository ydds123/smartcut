import { describe, expect, test } from 'bun:test'

import { resolveAssetUrl } from '../src/utils/assetUrl'

describe('assetUrl', () => {
  test('encodes question marks that are part of the filename', () => {
    expect(
      resolveAssetUrl('/data/uploads/你的一生，究竟为什么而活? - 001.mp4')
    ).toBe(
      'http://127.0.0.1:8000/data/uploads/%E4%BD%A0%E7%9A%84%E4%B8%80%E7%94%9F%EF%BC%8C%E7%A9%B6%E7%AB%9F%E4%B8%BA%E4%BB%80%E4%B9%88%E8%80%8C%E6%B4%BB%3F%20-%20001.mp4'
    )
  })

  test('preserves api_token query for protected direct asset urls', () => {
    expect(
      resolveAssetUrl('/data/uploads/demo.mp4?api_token=demo_token')
    ).toBe(
      'http://127.0.0.1:8000/data/uploads/demo.mp4?api_token=demo_token'
    )
  })

  test('preserves generic query params for api endpoints', () => {
    expect(
      resolveAssetUrl('/api/tasks/demo-task/frame?t=5666')
    ).toBe(
      'http://127.0.0.1:8000/api/tasks/demo-task/frame?t=5666'
    )
  })
})
