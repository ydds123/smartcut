export interface TaskThumbnailPresentation {
  alt: ''
  shouldRenderImage: boolean
}

export function getTaskThumbnailPresentation(
  previewUrl: string | null,
  loadFailed: boolean
): TaskThumbnailPresentation {
  return {
    alt: '',
    shouldRenderImage: Boolean(previewUrl) && !loadFailed,
  }
}
