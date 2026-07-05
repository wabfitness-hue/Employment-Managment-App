import { useEffect, useState } from 'react'
import api from '../../api/client'

interface Props {
  src: string
  alt: string
  className?: string
  fallback?: React.ReactNode
}

/**
 * <img> can't send Authorization headers, but our photo endpoint requires auth.
 * Fetch the bytes via axios (which attaches the token) and render as a blob URL.
 */
export function AuthImg({ src, alt, className, fallback }: Props) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let url: string | null = null
    let cancelled = false
    setFailed(false)
    setBlobUrl(null)

    api.get(src, { responseType: 'blob' })
      .then(res => {
        if (cancelled) return
        url = URL.createObjectURL(res.data)
        setBlobUrl(url)
      })
      .catch(() => { if (!cancelled) setFailed(true) })

    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [src])

  if (failed) return <>{fallback ?? null}</>
  if (!blobUrl) return <>{fallback ?? null}</>
  return <img src={blobUrl} alt={alt} className={className} />
}
