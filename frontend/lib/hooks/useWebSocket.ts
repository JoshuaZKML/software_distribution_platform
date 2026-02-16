import { useEffect, useRef, useState } from 'react';
import { useAuth } from './useAuth';

interface WebSocketMessage {
  type: string;
  data: any;
}

export function useWebSocket() {
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [readyState, setReadyState] = useState<number>(WebSocket.CONNECTING);
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<NodeJS.Timeout>();
  const { user } = useAuth();

  useEffect(() => {
    if (!user) return;

    const connect = () => {
      const url = process.env.NEXT_PUBLIC_WS_URL;
      if (!url) return;

      ws.current = new WebSocket(url);

      ws.current.onopen = () => {
        setReadyState(WebSocket.OPEN);
        ws.current?.send(JSON.stringify({ type: 'auth', token: localStorage.getItem('access_token') }));
      };

      ws.current.onclose = () => {
        setReadyState(WebSocket.CLOSED);
        reconnectTimeout.current = setTimeout(connect, 5000);
      };

      ws.current.onerror = (error) => {
        console.error('WebSocket error', error);
      };

      ws.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          setLastMessage(message);
        } catch (e) {
          console.error('Failed to parse WebSocket message', e);
        }
      };
    };

    connect();

    return () => {
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      if (ws.current) ws.current.close();
    };
  }, [user]);

  const sendMessage = (message: any) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
    }
  };

  return { lastMessage, readyState, sendMessage };
}
