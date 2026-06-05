import { useCallback, useEffect, useRef, useState } from 'react'
import { annotatedUrl, createJob, downloadUrl, getJob } from './api.js'
import { LANGS, translations, getInitialLang, saveLang } from './i18n.js'

export default function App() {
  const [lang, setLang] = useState(getInitialLang)
  const [files, setFiles] = useState([])
  const [previews, setPreviews] = useState([])
  const [jobId, setJobId] = useState(null)
  const [job, setJob] = useState(null)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [editedText, setEditedText] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef(null)

  const t = translations[lang]

  // Til o'zgarsa: saqlaymiz, <html lang> va sahifa sarlavhasini yangilaymiz
  useEffect(() => {
    saveLang(lang)
    document.documentElement.lang = t.htmlLang
    document.title = t.title
  }, [lang, t])

  const status = job?.status
  const isBusy = submitting || status === 'pending' || status === 'processing'

  const statusLabel =
    { pending: t.statusPending, processing: t.statusProcessing, done: t.statusDone, error: t.statusError }[status] ||
    t.sending

  // --- Rasm tanlash ---
  const addFiles = useCallback((fileList) => {
    const imgs = Array.from(fileList).filter((f) => f.type.startsWith('image/'))
    if (imgs.length === 0) return
    setFiles((prev) => [...prev, ...imgs])
    setPreviews((prev) => [
      ...prev,
      ...imgs.map((f) => ({ name: f.name, url: URL.createObjectURL(f) })),
    ])
  }, [])

  const onInputChange = (e) => addFiles(e.target.files)

  const onDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files) addFiles(e.dataTransfer.files)
  }

  const removeFile = (idx) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx))
    setPreviews((prev) => {
      URL.revokeObjectURL(prev[idx]?.url)
      return prev.filter((_, i) => i !== idx)
    })
  }

  // --- Yuborish ---
  const onSubmit = async () => {
    if (files.length === 0) return
    setError(null)
    setJob(null)
    setEditedText('')
    setSubmitting(true)
    try {
      const { job_id } = await createJob(files)
      setJobId(job_id)
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  // --- Polling (bloklanmaydigan): holat tayyor/xato bo'lguncha so'rab turamiz ---
  useEffect(() => {
    if (!jobId) return
    let active = true

    const tick = async () => {
      try {
        const j = await getJob(jobId)
        if (!active) return
        setJob(j)
        if (j.status === 'done') {
          setEditedText(j.result?.text || '')
        }
        if (j.status === 'done' || j.status === 'error') {
          clearInterval(timer)
        }
      } catch {
        /* vaqtinchalik xato — keyingi urinishda davom etadi */
      }
    }

    const timer = setInterval(tick, 1500)
    tick()
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [jobId])

  const reset = () => {
    previews.forEach((p) => URL.revokeObjectURL(p.url))
    setFiles([])
    setPreviews([])
    setJobId(null)
    setJob(null)
    setError(null)
    setEditedText('')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const copyText = async () => {
    try {
      await navigator.clipboard.writeText(editedText)
    } catch {
      /* clipboard mavjud emas */
    }
  }

  const progress = job?.progress

  return (
    <div className="app">
      <header className="header">
        <div className="lang-switch" role="group" aria-label="Til / Language">
          {LANGS.map((l) => (
            <button
              key={l}
              type="button"
              className={lang === l ? 'active' : ''}
              onClick={() => setLang(l)}
              title={translations[l].langTitle}
              aria-pressed={lang === l}
            >
              {translations[l].langLabel}
            </button>
          ))}
        </div>
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">📖</span>
          <div className="brand-text">
            <h1 className="brand-name">EUY<span className="brand-accent">·HTR</span></h1>
            <p className="brand-tagline">{t.tagline}</p>
          </div>
        </div>
      </header>

      {/* --- Yuklash bo'limi --- */}
      {!jobId && (
        <section className="card">
          <div
            className={`dropzone ${dragOver ? 'dragover' : ''}`}
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              hidden
              onChange={onInputChange}
            />
            <div className="dropzone-inner">
              <span className="dz-icon">⬆️</span>
              <p>{t.dropTitle}</p>
              <small>{t.dropHint}</small>
            </div>
          </div>

          {previews.length > 0 && (
            <div className="thumbs">
              {previews.map((p, i) => (
                <div className="thumb" key={i}>
                  <img src={p.url} alt={p.name} />
                  <button className="thumb-x" onClick={() => removeFile(i)} title={t.remove}>
                    ×
                  </button>
                  <span className="thumb-name">{p.name}</span>
                </div>
              ))}
            </div>
          )}

          <div className="actions">
            <button className="btn primary" onClick={onSubmit} disabled={files.length === 0 || submitting}>
              {submitting ? t.sending : `${t.recognize} (${files.length})`}
            </button>
            {files.length > 0 && (
              <button className="btn ghost" onClick={reset}>
                {t.clear}
              </button>
            )}
          </div>
        </section>
      )}

      {error && <div className="alert error">⚠️ {error}</div>}

      {/* --- Holat / progress --- */}
      {jobId && isBusy && (
        <section className="card status-card">
          <div className="spinner" />
          <div className="status-text">
            <strong>{statusLabel}</strong>
            {progress && progress.line_total > 0 && (
              <span>
                {t.image} {progress.image}/{progress.image_total} — {t.line} {progress.line}/{progress.line_total}
              </span>
            )}
            <small>{t.processingNote}</small>
          </div>
        </section>
      )}

      {/* --- Xato holati --- */}
      {status === 'error' && (
        <section className="card">
          <div className="alert error">⚠️ {t.errorPrefix} {job?.error}</div>
          <button className="btn" onClick={reset}>
            {t.retry}
          </button>
        </section>
      )}

      {/* --- Natija --- */}
      {status === 'done' && job?.result && (
        <section className="result">
          <div className="card">
            <div className="result-head">
              <h2>{t.resultTitle}</h2>
              <span className="badge">
                {job.result.num_images} {t.imagesUnit} · {job.result.total_lines} {t.linesUnit}
              </span>
            </div>
            <textarea
              className="result-text"
              dir="rtl"
              value={editedText}
              onChange={(e) => setEditedText(e.target.value)}
              rows={Math.min(24, Math.max(8, editedText.split('\n').length + 1))}
            />
            <div className="actions">
              <button className="btn" onClick={copyText}>
                📋 {t.copy}
              </button>
              <a className="btn" href={downloadUrl(jobId, 'txt')}>
                ⬇️ TXT
              </a>
              <a className="btn" href={downloadUrl(jobId, 'docx')}>
                ⬇️ DOCX
              </a>
              <a className="btn" href={downloadUrl(jobId, 'pdf')}>
                ⬇️ PDF
              </a>
              <button className="btn ghost" onClick={reset}>
                {t.newDoc}
              </button>
            </div>
            <p className="hint">{t.hint}</p>
          </div>

          {/* Annotatsiyalangan rasmlar */}
          <div className="card">
            <h2>{t.detectedLines}</h2>
            <div className="annotated-list">
              {job.result.images.map((img) => (
                <figure className="annotated" key={img.index}>
                  <img src={annotatedUrl(jobId, img.index)} alt={`${t.imageAlt} ${img.index}`} />
                  <figcaption>
                    {img.original_filename} — {img.num_lines} {t.linesUnit}
                  </figcaption>
                </figure>
              ))}
            </div>
          </div>
        </section>
      )}

      <footer className="footer">
        <span><strong className="footer-brand">EUY·HTR</strong> · {t.footer}</span>
      </footer>
    </div>
  )
}
