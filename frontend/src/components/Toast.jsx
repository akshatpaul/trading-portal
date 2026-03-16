import { useApp } from '../context/AppContext'

const TYPE_STYLES = {
  success: 'bg-emerald-900/90 border-emerald-600 text-emerald-100',
  error:   'bg-red-900/90 border-red-600 text-red-100',
  warning: 'bg-amber-900/90 border-amber-600 text-amber-100',
  info:    'bg-slate-800/90 border-slate-600 text-slate-100',
}

const TYPE_ICONS = {
  success: '✅',
  error:   '❌',
  warning: '⚠️',
  info:    'ℹ️',
}

function ToastItem({ toast, onRemove }) {
  return (
    <div
      className={`flex items-start gap-3 px-4 py-3 rounded-xl border backdrop-blur-sm
                  shadow-xl text-sm max-w-sm w-full cursor-pointer
                  ${TYPE_STYLES[toast.type] || TYPE_STYLES.info}
                  ${toast.exiting ? 'toast-exit' : 'toast-enter'}`}
      onClick={() => onRemove(toast.id)}
    >
      <span className="text-base flex-shrink-0">{TYPE_ICONS[toast.type]}</span>
      <span className="leading-snug">{toast.message}</span>
    </div>
  )
}

export default function ToastContainer() {
  const { toasts, removeToast } = useApp()
  if (!toasts.length) return null

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 items-end">
      {toasts.map(t => (
        <ToastItem key={t.id} toast={t} onRemove={removeToast} />
      ))}
    </div>
  )
}
