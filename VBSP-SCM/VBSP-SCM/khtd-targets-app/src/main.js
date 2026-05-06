import { React, html } from './html.js'
import { createRoot } from 'https://esm.sh/react-dom@18.3.1/client'
import { BrowserRouter, Routes, Route } from 'https://esm.sh/react-router-dom@6.23.1'
import { AppStateProvider } from './state.js'
import { TopBar } from './components/TopBar.js'
import { ToastHost } from './components/Toast.js'
import { HomePage } from './pages/Home.js'
import { ImportSheetPage } from './pages/ImportSheet.js'
import { TargetsPage } from './pages/Targets.js'

function App() {
  return html`
    <${BrowserRouter}>
      <${AppStateProvider}>
        <${TopBar} />
        <${Routes}>
          <${Route} path=${'/'} element=${html`<${HomePage} />`} />
          <${Route} path=${'/google-sheet-import'} element=${html`<${ImportSheetPage} />`} />
          <${Route} path=${'/targets'} element=${html`<${TargetsPage} />`} />
          <${Route} path=${'*'} element=${html`<${HomePage} />`} />
        <//>
        <${ToastHost} />
      <//>
    <//>
  `
}

createRoot(document.getElementById('root')).render(React.createElement(App))

