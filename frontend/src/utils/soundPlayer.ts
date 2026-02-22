/**
 * 音效类型
 */
export type SoundType = 'success' | 'error' | 'complete' | 'upload'

/**
 * 全局静音状态（可以从 localStorage 读取）
 */
let isMuted = false

/**
 * 音频上下文（懒加载）
 */
let audioContext: AudioContext | null = null

/**
 * 获取 AudioContext
 */
function getAudioContext(): AudioContext {
  if (!audioContext) {
    audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
  }
  return audioContext
}

/**
 * 使用 Web Audio API 生成简单的音效
 */
function playGeneratedSound(type: SoundType): void {
  if (isMuted) return

  try {
    const ctx = getAudioContext()
    const oscillator = ctx.createOscillator()
    const gainNode = ctx.createGain()

    oscillator.connect(gainNode)
    gainNode.connect(ctx.destination)

    const now = ctx.currentTime

    switch (type) {
      case 'success':
      {
        // 成功音：上升的愉悦音调
        oscillator.type = 'sine'
        oscillator.frequency.setValueAtTime(523.25, now) // C5
        oscillator.frequency.exponentialRampToValueAtTime(659.25, now + 0.1) // E5
        gainNode.gain.setValueAtTime(0.3, now)
        gainNode.gain.exponentialRampToValueAtTime(0.01, now + 0.3)
        oscillator.start(now)
        oscillator.stop(now + 0.3)
        break
      }

      case 'error':
      {
        // 错误音：低沉的音调
        oscillator.type = 'sawtooth'
        oscillator.frequency.setValueAtTime(200, now)
        oscillator.frequency.exponentialRampToValueAtTime(100, now + 0.2)
        gainNode.gain.setValueAtTime(0.3, now)
        gainNode.gain.exponentialRampToValueAtTime(0.01, now + 0.3)
        oscillator.start(now)
        oscillator.stop(now + 0.3)
        break
      }

      case 'complete':
      {
        // 完成音：欢快的和弦效果
        const osc1 = ctx.createOscillator()
        const osc2 = ctx.createOscillator()
        const gain1 = ctx.createGain()
        const gain2 = ctx.createGain()

        osc1.type = 'sine'
        osc2.type = 'sine'
        osc1.frequency.value = 523.25 // C5
        osc2.frequency.value = 659.25 // E5

        osc1.connect(gain1)
        osc2.connect(gain2)
        gain1.connect(ctx.destination)
        gain2.connect(ctx.destination)

        gain1.gain.setValueAtTime(0.2, now)
        gain2.gain.setValueAtTime(0.2, now)
        gain1.gain.exponentialRampToValueAtTime(0.01, now + 0.4)
        gain2.gain.exponentialRampToValueAtTime(0.01, now + 0.4)

        osc1.start(now)
        osc2.start(now)
        osc1.stop(now + 0.4)
        osc2.stop(now + 0.4)
        break
      }

      case 'upload':
      {
        // 上传音：短促的确认音
        oscillator.type = 'sine'
        oscillator.frequency.setValueAtTime(440, now) // A4
        gainNode.gain.setValueAtTime(0.2, now)
        gainNode.gain.exponentialRampToValueAtTime(0.01, now + 0.15)
        oscillator.start(now)
        oscillator.stop(now + 0.15)
        break
      }
    }
  } catch (error) {
    console.warn('Failed to play generated sound:', error)
  }
}

/**
 * 播放音效
 */
export function playSound(type: SoundType): void {
  // 检查是否静音
  if (isMuted) return

  // 尝试从 localStorage 读取静音状态
  try {
    const muted = localStorage.getItem('smartcut_sound_muted')
    if (muted === 'true') {
      isMuted = true
      return
    }
  } catch {
    // localStorage 可能不可用
  }

  // 使用生成的音效
  playGeneratedSound(type)
}

/**
 * 设置静音状态
 */
export function setMuted(muted: boolean): void {
  isMuted = muted
  try {
    localStorage.setItem('smartcut_sound_muted', String(muted))
  } catch {
    // localStorage 可能不可用
  }
}

/**
 * 获取静音状态
 */
export function getMuted(): boolean {
  try {
    const muted = localStorage.getItem('smartcut_sound_muted')
    return muted === 'true'
  } catch {
    return isMuted
  }
}

/**
 * 切换静音状态
 */
export function toggleMuted(): boolean {
  const newMuted = !getMuted()
  setMuted(newMuted)
  return newMuted
}
