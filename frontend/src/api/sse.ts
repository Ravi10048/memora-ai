import { type AgentStep } from "./client";

/**
 * Connect to the SSE chat endpoint and stream agent steps.
 */
export function streamChat(
  message: string,
  conversationId: number | null,
  onStep: (step: AgentStep) => void,
  onDone: (fullResponse: string) => void,
  onError: (error: string) => void,
): () => void {
  const controller = new AbortController();

  const run = async () => {
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          conversation_id: conversationId,
          user_id: "default",
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        onError(`HTTP ${response.status}: ${response.statusText}`);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        onError("No response body");
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";
      let fullResponse = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse SSE events from buffer
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6).trim();
            if (!data) continue;

            try {
              const step: AgentStep = JSON.parse(data);
              onStep(step);

              if (step.type === "token") {
                fullResponse += step.content;
              }
              if (step.type === "done") {
                onDone(step.content || fullResponse);
                return;
              }
              if (step.type === "error") {
                onError(step.content);
                return;
              }
            } catch {
              // Skip malformed events
            }
          }
        }
      }

      if (fullResponse) {
        onDone(fullResponse);
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") return;
      onError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  run();

  return () => controller.abort();
}
