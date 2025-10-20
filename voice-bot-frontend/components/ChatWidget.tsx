// file: components/ChatWidget.tsx

"use client";

import React, { useState, useEffect, useRef } from "react";
import MicRecorder from "mic-recorder-to-mp3";
import { FiMic, FiSend, FiX, FiMessageSquare, FiGlobe } from "react-icons/fi";
import { FaUser, FaRobot } from "react-icons/fa";

// New changes
import ReactMarkdown from 'react-markdown';

// --- Types ---
type Message = {
  sender: "user" | "bot";
  text: string;
};

type Language = "en" | "hi";

// --- Constants ---
const CLIENT_ID = "client_demo";
const WEBSOCKET_URL = `ws://localhost:8000/ws/${CLIENT_ID}`;

// --- Child Components ---
const AutoPlayingAudioPlayer = ({ src }: { src: string }) => {
  const audioRef = useRef<HTMLAudioElement>(null);
  useEffect(() => {
    if (src && audioRef.current) {
      audioRef.current.play().catch(e => console.error("Audio autoplay failed:", e));
    }
  }, [src]);
  return <audio ref={audioRef} src={src} controls style={{ display: "none" }} />;
};

const TypingIndicator = () => (
  <div className="flex items-center space-x-2">
    <div className="w-2 h-2 rounded-full bg-gray-400 animate-pulse [animation-delay:-0.3s]"></div>
    <div className="w-2 h-2 rounded-full bg-gray-400 animate-pulse [animation-delay:-0.15s]"></div>
    <div className="w-2 h-2 rounded-full bg-gray-400 animate-pulse"></div>
  </div>
);

// --- Main Chat Component ---
export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [currentLanguage, setCurrentLanguage] = useState<Language>("en");
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [audioUrl, setAudioUrl] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(true); // NEW: Loading state for typing indicator

  const recorderRef = useRef<MicRecorder | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // --- WebSocket Connection ---
  useEffect(() => {
    const connectWebSocket = () => {
      const socket = new WebSocket(WEBSOCKET_URL);

      socket.onopen = () => {
        console.log("WebSocket connection established.");
        setWs(socket);
      };

      socket.onmessage = (event) => {
        setIsLoading(false); // Stop loading indicator on any message
        const data = JSON.parse(event.data);

        if (data.type === "response") {
          setMessages(prev => [...prev, { sender: "bot", text: data.text }]);
          //if (data.audio_base64) {
          //  setAudioUrl(`http://localhost:8000${data.audio_url}`);
          //}

          if (data.audio_base64){
            try{
              // Convert Base64 → binary
              const binary = atob(data.audio_base64);
              const bytes = new Uint8Array(binary.length);
              for (let i = 0; i < binary.length; i++) {
                bytes[i] = binary.charCodeAt(i);
            }
              // Create a Blob & object URL
              const blob = new Blob([bytes.buffer], { type: "audio/mp3" });
              const url = URL.createObjectURL(blob);

              // Set state to trigger AutoPlayingAudioPlayer
              setAudioUrl(url);

              // Cleanup old object URLs (avoid memory leaks)
              return () => URL.revokeObjectURL(url);
              } catch (err) {
              console.error("Failed to decode audio:", err);
              }
          }

        } else if (data.type === "user_message") {
          setMessages(prev => [...prev, { sender: "user", text: data.text }]);
        } else if (data.type === "error") {
            console.error("Server Error:", data.message);
            setMessages(prev => [...prev, { sender: "bot", text: `Error: ${data.message}` }]);
        }
      };

      socket.onclose = () => {
        console.log("WebSocket connection closed. Reconnecting...");
        setIsLoading(true);
        setTimeout(connectWebSocket, 3000);
      };
      
      socket.onerror = (error) => {
        console.error("WebSocket error:", error);
        setIsLoading(true);
        socket.close();
      };
    };

    connectWebSocket();
    recorderRef.current = new MicRecorder({ bitRate: 128 });

    return () => ws?.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- Helper Functions ---
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const sendMessage = () => {
    if (!inputValue.trim() || !ws || ws.readyState !== WebSocket.OPEN) return;
    setIsLoading(true);
    ws.send(JSON.stringify({ type: "text_query", text: inputValue }));
    setMessages(prev => [...prev, { sender: "user", text: inputValue }]);
    setInputValue("");
  };

  const handleMicClick = () => {
    if (isRecording) {
      recorderRef.current?.stop().getMp3().then(([buffer, blob]: [any,any]) => {
        setIsRecording(false);
        const reader = new FileReader();
        reader.readAsDataURL(blob);
        reader.onloadend = () => {
          const base64data = reader.result?.toString().split(',')[1];
          if (base64data && ws && ws.readyState === WebSocket.OPEN) {
            setIsLoading(true);
            ws.send(JSON.stringify({ type: "audio_query", audio_data: base64data }));
          }
        };
      });
    } else {
      navigator.mediaDevices.getUserMedia({ audio: true })
        .then(() => recorderRef.current?.start().then(() => setIsRecording(true)))
        .catch(error => console.error("Microphone access denied:", error));
    }
  };

  const toggleLanguage = () => {
    const newLang = currentLanguage === "en" ? "hi" : "en";
    setCurrentLanguage(newLang);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "language_switch", language: newLang }));
    }
  };

  return (
    <div className="fixed bottom-5 right-5 z-50">
      {isOpen ? (
        <div className="flex flex-col h-[70vh] max-h-[700px] w-[400px] bg-white rounded-2xl shadow-2xl border border-gray-200/80 overflow-hidden font-sans">
          {/* Header */}
          <header className="flex items-center justify-between p-4 bg-gray-50 border-b">
            <div className="flex items-center space-x-3">
              <div className="relative">
                <FaRobot className="w-10 h-10 text-white bg-gradient-to-br from-blue-500 to-indigo-600 p-2 rounded-full" />
                <span className="absolute bottom-0 right-0 w-3 h-3 bg-green-500 border-2 border-white rounded-full"></span>
              </div>
              <div>
                <h3 className="text-md font-bold text-gray-800">Voice Bot</h3>
                <p className="text-xs text-gray-500">Your AI Assistant</p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <button onClick={toggleLanguage} className="p-2 rounded-full text-gray-500 hover:bg-gray-200 transition-colors" title="Switch Language">
                <FiGlobe className="w-5 h-5" />
              </button>
              <button onClick={() => setIsOpen(false)} className="p-2 rounded-full text-gray-500 hover:bg-gray-200 transition-colors" title="Close">
                <FiX className="w-5 h-5" />
              </button>
            </div>
          </header>

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-6 bg-gray-100">
            {messages.map((msg, index) => (
              <div key={index} className={`flex items-end gap-2 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.sender === 'bot' && <FaRobot className="w-6 h-6 text-gray-400 mb-1" />}
                <div className={`max-w-[80%] rounded-xl px-4 py-2.5 shadow-sm text-sm ${
                  msg.sender === 'user' ? 'bg-blue-600 text-white rounded-br-none' : 'bg-white text-gray-800 rounded-bl-none'
                }`}>
                  <ReactMarkdown>{msg.text}</ReactMarkdown>
                </div>
                {msg.sender === 'user' && <FaUser className="w-6 h-6 text-gray-400 mb-1" />}
              </div>
            ))}
            {isLoading && (
              <div className="flex items-end gap-2 justify-start">
                <FaRobot className="w-6 h-6 text-gray-400 mb-1" />
                <div className="max-w-[80%] rounded-xl px-4 py-2.5 shadow-sm bg-white text-gray-800 rounded-bl-none">
                  <TypingIndicator />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <footer className="border-t p-3 bg-white">
            <div className="flex items-center space-x-2">
              <input
                type="text"
                value={inputValue}
                onChange={e => setInputValue(e.target.value)}
                onKeyPress={e => e.key === 'Enter' && sendMessage()}
                placeholder={isRecording ? "Listening..." : "Ask a question..."}
                className="flex-1 w-full px-4 py-2 text-sm bg-gray-100 border border-transparent rounded-full focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={isRecording}
              />
              <button onClick={handleMicClick} className={`p-3 rounded-full transition-colors focus:outline-none ${
                  isRecording ? 'bg-red-500 text-white animate-pulse' : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
              }`}>
                <FiMic className="w-5 h-5" />
              </button>
              <button onClick={sendMessage} disabled={!inputValue.trim() || isLoading} className="p-3 rounded-full bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors focus:outline-none">
                <FiSend className="w-5 h-5" />
              </button>
            </div>
          </footer>
        </div>
      ) : (
        <button onClick={() => setIsOpen(true)} className="p-4 bg-blue-600 rounded-full shadow-lg text-white hover:bg-blue-700 transition-transform hover:scale-105 animate-pulse">
          <FiMessageSquare className="w-8 h-8" />
        </button>
      )}
      {audioUrl && <AutoPlayingAudioPlayer src={audioUrl} key={audioUrl} />}
    </div>
  );
}