import api from './client'

export interface UploadedFile {
  id: number
  filename: string
  file_type: string
  chunk_count: number
  created_at: string
}

export function uploadFile(file: File) {
  const form = new FormData()
  form.append('file', file)
  return api.post<UploadedFile>('/upload/file', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
}

export function getUploadedFiles() {
  return api.get<UploadedFile[]>('/upload/files')
}

export function deleteUploadedFile(fileId: number) {
  return api.delete(`/upload/files/${fileId}`)
}
