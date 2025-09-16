// file: app/page.tsx

import ChatWidget from "@/components/ChatWidget";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24 bg-gray-50">
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">Real Estate Website Demo</h1>
        <p className="text-lg text-gray-600">The "Choice Bot" widget is active in the bottom right corner.</p>
      </div>
      <ChatWidget />
    </main>
  );
}