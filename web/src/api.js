// Backend bilan aloqa. Barcha so'rovlar asinxron (fetch) — UI hech qachon bloklanmaydi.

const BASE = '/api'

export async function createJob(files) {
  const fd = new FormData()
  for (const f of files) fd.append('images', f)
  const res = await fetch(`${BASE}/jobs`, { method: 'POST', body: fd })
  if (!res.ok) {
    let detail = 'Yuklashda xatolik'
    try {
      detail = (await res.json()).detail || detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return res.json()
}

export async function getJob(id) {
  const res = await fetch(`${BASE}/jobs/${id}`)
  if (!res.ok) throw new Error('Holatni olishda xatolik')
  return res.json()
}

export function downloadUrl(id, format) {
  return `${BASE}/jobs/${id}/download?format=${format}`
}

export function annotatedUrl(id, index) {
  return `${BASE}/jobs/${id}/images/${index}`
}

export async function getHealth() {
  const res = await fetch(`${BASE}/health`)
  if (!res.ok) throw new Error('Server javob bermadi')
  return res.json()
}
