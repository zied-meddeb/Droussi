// Tiny pub/sub so the non-React API layer can push errors to the UI toast host
// without every call site having to wire up error handling itself.

type Handler = (message: string) => void;

const handlers = new Set<Handler>();

/** Subscribe to API errors. Returns an unsubscribe function. */
export function onApiError(handler: Handler): () => void {
  handlers.add(handler);
  return () => handlers.delete(handler);
}

/** Broadcast an API error message to every subscriber (the toast host). */
export function emitApiError(message: string): void {
  handlers.forEach((h) => {
    try {
      h(message);
    } catch {
      /* a broken listener must not break the API layer */
    }
  });
}
