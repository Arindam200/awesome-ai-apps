import { MainContent } from './components/MainContent'
import { Sidebar } from './components/Sidebar'
import { Topbar } from './components/Topbar'

function App() {
  return (
    <div className="flex min-h-dvh bg-[#F5F0EA]">
      <Sidebar />
      <div className="ml-[220px] flex min-h-dvh min-w-0 flex-1 flex-col">
        <Topbar />
        <MainContent />
      </div>
    </div>
  )
}

export default App
