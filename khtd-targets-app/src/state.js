import { React } from './html.js'

const AppStateContext = React.createContext(null)

export function AppStateProvider({ children }) {
  const [period, setPeriod] = React.useState('2026-Q2')
  const [periods, setPeriods] = React.useState(['2026-Q2'])
  const [lastSync, setLastSync] = React.useState({ status: 'never', at: null })
  const [toast, setToast] = React.useState(null)

  const value = React.useMemo(
    () => ({ period, setPeriod, periods, setPeriods, lastSync, setLastSync, toast, setToast }),
    [period, periods, lastSync, toast]
  )

  return React.createElement(AppStateContext.Provider, { value }, children)
}

export function useAppState() {
  const ctx = React.useContext(AppStateContext)
  if (!ctx) throw new Error('Missing AppStateProvider')
  return ctx
}

