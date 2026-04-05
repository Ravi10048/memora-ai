import { useState, useRef, useEffect } from "react";
import ChatMessage from "../components/ChatMessage";
import ChatInput from "../components/ChatInput";
import ThinkingPanel from "../components/ThinkingPanel";
import { streamChat } from "../api/sse";
import { type AgentStep } from "../api/client";

interface ChatMessage_ {
  role: "user" | "assistant";
  content: string;
}

interface ChatProps {
  conversationId: number | null;
  onConversationCreated: (id: number) => void;
}

export default function Chat({ conversationId, onConversationCreated }: ChatProps) {
  const [messages, setMessages] = useState<ChatMessage_[]>([]);
  const [streamingResponse, setStreamingResponse] = useState("");
  const [thinkingSteps, setThinkingSteps] = useState<AgentStep[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingResponse]);

  // Clear on new conversation
  useEffect(() => {
    setMessages([]);
    setStreamingResponse("");
    setThinkingSteps([]);
  }, [conversationId]);

  const handleSend = (message: string) => {
    // Add user message
    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setStreamingResponse("");
    setThinkingSteps([]);
    setIsProcessing(true);

    streamChat(
      message,
      conversationId,
      // onStep
      (step) => {
        if (step.type === "token") {
          setStreamingResponse((prev) => prev + step.content);
        } else {
          setThinkingSteps((prev) => [...prev, step]);
        }

        // Capture conversation_id from first response
        if (step.type === "done" && step.metadata?.conversation_id) {
          onConversationCreated(step.metadata.conversation_id as number);
        }
      },
      // onDone
      (fullResponse) => {
        setMessages((prev) => [...prev, { role: "assistant", content: fullResponse }]);
        setStreamingResponse("");
        setIsProcessing(false);
      },
      // onError
      (error) => {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `Error: ${error}` },
        ]);
        setStreamingResponse("");
        setIsProcessing(false);
      }
    );
  };

  return (
    <div className="flex h-[calc(100vh-2rem)] gap-4">
      {/* Chat Area */}
      <div className="flex-1 flex flex-col bg-slate-800/30 rounded-xl border border-slate-700 overflow-hidden">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 && !streamingResponse && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 rounded-full bg-purple-600/20 flex items-center justify-center mb-4">
                <span className="text-3xl">🧠</span>
              </div>
              <h2 className="text-xl font-semibold text-slate-200">Smart Memory Agent</h2>
              <p className="text-sm text-slate-400 mt-2 max-w-md">
                I remember everything across conversations. Tell me about yourself,
                ask me questions, or try: "What do you know about me?"
              </p>
            </div>
          )}

          {messages.map((msg, i) => (
            <ChatMessage key={i} role={msg.role} content={msg.content} />
          ))}

          {streamingResponse && (
            <ChatMessage role="assistant" content={streamingResponse} isStreaming />
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <ChatInput onSend={handleSend} disabled={isProcessing} />
      </div>

      {/* Thinking Panel (right side) */}
      <div className="w-80 flex-shrink-0">
        <ThinkingPanel steps={thinkingSteps} />
      </div>
    </div>
  );
}
