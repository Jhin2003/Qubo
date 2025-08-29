import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.scss'

import Container from './components/Container'
import Chatbot from './components/Chatbot'
import FileUploader from './components/FileUploader'

function App() {
  const [count, setCount] = useState(0)

  return (
    <>
    <Container>
      <FileUploader />
      <Chatbot />
    </Container>
    </>
  )
}

export default App
