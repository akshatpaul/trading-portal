import TopBar from './TopBar'
import ToastContainer from '../Toast'

export default function Layout({ children, onLogout }) {
  return (
    <div className="min-h-screen bg-page-bg text-text-primary">
      <TopBar onLogout={onLogout} />
      <main className="max-w-screen-2xl mx-auto px-4 py-5">
        {children}
      </main>
      <ToastContainer />
    </div>
  )
}
