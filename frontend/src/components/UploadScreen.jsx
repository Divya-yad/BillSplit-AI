import React, { useState, useCallback, useRef } from 'react'
import { uploadBill } from '../api/client'
import useBillStore from '../store/billStore'

// Client-side image compression before upload
async function compressImage(file) {
  return new Promise((resolve) => {
    const img = new Image()
    const url = URL.createObjectURL(file)
    img.onload = () => {
      const MAX = 2000
      let { width, height } = img
      if (Math.max(width, height) > MAX) {
        const scale = MAX / Math.max(width, height)
        width = Math.round(width * scale)
        height = Math.round(height * scale)
      }
      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      const ctx = canvas.getContext('2d')
      ctx.drawImage(img, 0, 0, width, height)
      canvas.toBlob(
        (blob) => {
          URL.revokeObjectURL(url)
          resolve(new File([blob], file.name.replace(/\.[^.]+$/, '.jpg'), { type: 'image/jpeg' }))
        },
        'image/jpeg',
        0.85,
      )
    }
    img.src = url
  })
}

export default function UploadScreen() {
  const [files, setFiles] = useState([])   // { file, preview, id }[]
  const [dragging, setDragging] = useState(false)
  const { setLoading, loading, setBillData, setError, error } = useBillStore()
  const dragCounter = useRef(0)

  const addFiles = useCallback((newFiles) => {
    const accepted = Array.from(newFiles)
      .filter(f => f.type.startsWith('image/'))
      .slice(0, 3 - files.length)
    const withPreviews = accepted.map(f => ({
      file: f,
      preview: URL.createObjectURL(f),
      id: Math.random().toString(36).slice(2),
    }))
    setFiles(prev => [...prev, ...withPreviews].slice(0, 3))
  }, [files.length])

  const removeFile = (id) => {
    setFiles(prev => {
      const removed = prev.find(f => f.id === id)
      if (removed) URL.revokeObjectURL(removed.preview)
      return prev.filter(f => f.id !== id)
    })
  }

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    dragCounter.current = 0
    addFiles(e.dataTransfer.files)
  }, [addFiles])

  const handleDragEnter = (e) => {
    e.preventDefault()
    dragCounter.current++
    setDragging(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    dragCounter.current--
    if (dragCounter.current === 0) setDragging(false)
  }

  const handleSubmit = async () => {
    if (!files.length) return
    setLoading(true)
    setError(null)
    try {
      const compressed = await Promise.all(files.map(f => compressImage(f.file)))
      const result = await uploadBill(compressed)
      setBillData({ billId: result.bill_id, extracted: result.extracted })
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="screen animate-fade">
      {/* Header */}
      <header className="header">
        <span className="logo">⚡ BillSplit AI</span>
      </header>

      <div className="content" style={{ maxWidth: 600, margin: '0 auto', width: '100%' }}>
        {/* Hero */}
        <div style={{ textAlign: 'center', padding: '24px 0 8px' }}>
          <h1 style={{ fontSize: '2.2rem', marginBottom: 12 }}>
            <span className="text-gradient">Fair bills,</span>
            <br />zero arguments
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', maxWidth: 420, margin: '0 auto' }}>
            Snap your restaurant bill. BillSplit AI reads every line item, applies GST and service
            charges proportionally, and tells each person exactly what they owe.
          </p>
        </div>

        {/* Upload Zone */}
        <div
          className={`drop-zone ${dragging ? 'dragging' : ''}`}
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={e => e.preventDefault()}
          onDrop={handleDrop}
        >
          <input
            type="file"
            accept="image/*"
            multiple
            id="file-input"
            onChange={e => addFiles(e.target.files)}
          />
          <div style={{ pointerEvents: 'none' }}>
            <div style={{ fontSize: '3rem', marginBottom: 12 }}>📷</div>
            <p style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 8 }}>
              {dragging ? 'Drop your bill here' : 'Upload your bill'}
            </p>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
              Drag & drop or click to select · Up to 3 photos for long receipts
            </p>
          </div>
        </div>

        {/* Image Previews */}
        {files.length > 0 && (
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {files.map((f, idx) => (
              <div
                key={f.id}
                className="animate-pop"
                style={{
                  position: 'relative',
                  flex: '1 1 160px',
                  maxWidth: 200,
                  borderRadius: 'var(--radius-lg)',
                  overflow: 'hidden',
                  border: '1px solid var(--border)',
                }}
              >
                <img
                  src={f.preview}
                  alt={`Bill photo ${idx + 1}`}
                  style={{ width: '100%', height: 140, objectFit: 'cover', display: 'block' }}
                />
                <div style={{
                  position: 'absolute',
                  top: 0, left: 0, right: 0,
                  background: 'linear-gradient(to bottom, rgba(0,0,0,0.5), transparent)',
                  padding: '8px 10px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                }}>
                  <span style={{ fontSize: '0.7rem', fontWeight: 700, color: 'white' }}>
                    Photo {idx + 1}
                  </span>
                  <button
                    onClick={() => removeFile(f.id)}
                    style={{
                      background: 'rgba(0,0,0,0.5)',
                      border: 'none',
                      color: 'white',
                      width: 22,
                      height: 22,
                      borderRadius: '50%',
                      cursor: 'pointer',
                      fontSize: '0.75rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >✕</button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="alert alert-danger animate-fade">
            <span>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {/* Tips */}
        <div className="glass-card" style={{ padding: '16px 20px' }}>
          <p style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Tips for best results
          </p>
          <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {[
              '📱 Hold the camera steady and flat over the bill',
              '💡 Good lighting helps — use your phone torch if dim',
              '📄 Long receipts? Take 2 overlapping photos',
              '🔍 Make sure all text is in frame',
            ].map(tip => (
              <li key={tip} style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{tip}</li>
            ))}
          </ul>
        </div>

        {/* Submit */}
        <button
          className="btn btn-primary btn-lg"
          onClick={handleSubmit}
          disabled={files.length === 0 || loading}
          style={{ width: '100%' }}
          id="upload-submit-btn"
        >
          {loading ? (
            <>
              <div className="spinner" style={{ width: 20, height: 20, borderWidth: 2 }} />
              Reading your bill…
            </>
          ) : (
            `✨ Extract Bill${files.length > 0 ? ` (${files.length} photo${files.length > 1 ? 's' : ''})` : ''}`
          )}
        </button>

        {loading && (
          <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem', animation: 'pulse 2s infinite' }}>
            Sending to Gemini AI · This takes 5–15 seconds…
          </div>
        )}
      </div>
    </div>
  )
}
