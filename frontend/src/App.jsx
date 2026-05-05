import { useState } from 'react'
import Layout from './components/layout/Layout'
import LoginPage from './components/LoginPage'
import Dashboard from './pages/Dashboard'
import Chart from './pages/Chart'
import Trades from './pages/Trades'
import Performance from './pages/Performance'
import Settings from './pages/Settings'
import Strategies from './pages/Strategies'
import Activity from './pages/Activity'
import Journal from './pages/Journal'
import Kite from './pages/Kite'
import EmergencyStopModal from './components/modals/EmergencyStop'
import LiveModeConfirmModal from './components/modals/LiveModeConfirm'
import { useApp } from './context/AppContext'

function PageContent() {
  const { activeTab } = useApp()

  switch (activeTab) {
    case 'dashboard':   return <Dashboard />
    case 'chart':       return <Chart />
    case 'trades':      return <Trades />
    case 'performance': return <Performance />
    case 'strategies':  return <Strategies />
    case 'activity':    return <Activity />
    case 'journal':     return <Journal />
    case 'kite':        return <Kite />
    case 'settings':    return <Settings />
    default:            return <Dashboard />
  }
}

function Modals() {
  const { showEmergencyModal, showLiveModeModal } = useApp()
  return (
    <>
      {showEmergencyModal && <EmergencyStopModal />}
      {showLiveModeModal  && <LiveModeConfirmModal />}
    </>
  )
}

export default function App() {
  const [authed, setAuthed] = useState(!!localStorage.getItem('trading_token'))

  function handleLogout() {
    localStorage.removeItem('trading_token')
    setAuthed(false)
  }

  if (!authed) {
    return <LoginPage onLogin={() => setAuthed(true)} />
  }

  return (
    <Layout onLogout={handleLogout}>
      <PageContent />
      <Modals />
    </Layout>
  )
}
