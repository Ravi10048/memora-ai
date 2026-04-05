import { useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Chat from "./pages/Chat";
import MemoryBank from "./pages/MemoryBank";
import ConversationHistory from "./pages/ConversationHistory";
import Settings from "./pages/Settings";

export default function App() {
  const [conversationId, setConversationId] = useState<number | null>(null);

  const handleNewChat = () => {
    setConversationId(null); // Reset triggers new conversation
  };

  return (
    <BrowserRouter>
      <div className="flex min-h-screen bg-slate-950">
        <Sidebar onNewChat={handleNewChat} />
        <main className="flex-1 p-4 overflow-auto">
          <Routes>
            <Route
              path="/"
              element={
                <Chat
                  conversationId={conversationId}
                  onConversationCreated={setConversationId}
                />
              }
            />
            <Route path="/memory" element={<MemoryBank />} />
            <Route path="/history" element={<ConversationHistory />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
