import { useNavigate } from 'react-router-dom'

interface LayoutProps {
  title: string
  children: React.ReactNode
  /** If provided, render a back button to this path. If undefined, use Telegram BackButton. */
  backTo?: string
}

export default function Layout({ title, children, backTo }: LayoutProps) {
  const navigate = useNavigate()

  const handleBack = () => {
    if (backTo) navigate(backTo)
    else navigate(-1)
  }

  return (
    <div className="min-h-screen w-full flex flex-col" style={{ background: 'var(--tg-theme-bg-color)' }}>
      {/* Header */}
      <header
        className="sticky top-0 z-10 flex items-center gap-3 px-4 py-3 border-b"
        style={{
          background: 'var(--tg-theme-secondary-bg-color)',
          borderColor: 'rgba(255,255,255,0.08)',
        }}
      >
        <button
          onClick={handleBack}
          className="p-1 rounded-lg active:opacity-60 transition-opacity"
          aria-label="Indietro"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M15.41 16.59L10.83 12l4.58-4.59L14 6l-6 6 6 6z" />
          </svg>
        </button>
        <h1 className="text-lg font-semibold truncate flex-1">{title}</h1>
      </header>

      {/* Content */}
      <main className="flex-1 min-w-0 p-4 space-y-3">{children}</main>
    </div>
  )
}
