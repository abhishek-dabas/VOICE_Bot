// file: app/page.tsx

import ChatWidget from "@/components/ChatWidget"; // The @/ is a path alias configured in the tsconfig.json file.
// It's a shorthand for the project's root directory, making imports cleaner and more robust then relative paths.

export default function Home() { // It defines functional React component named Home and exports it as the default export.
  // In Next.js, a page file must export a default React component. It uses this exported component to render the page. 
  return ( // It indicates that Home will return the JSX that defines the user interface.
    <main className="flex min-h-screen flex-col items-center justify-center p-24 bg-gray-50"> {/* In React, className is used instaed of class 
    This styling centers the page content, including chat widget and title. */}
      <div className="text-center"> {/* A div that acts as a container for the page's centered text */}
        <h1 className="text-4xl font-bold mb-4">Website Demo</h1>
        <p className="text-lg text-gray-600">The "Voice Bot" widget is active in the bottom right corner.</p>
      </div>
      <ChatWidget /> {/* This is the core of the page, it renders the ChatWidget. In this way, a custom React component within your JSX. 
      By simply including the component tag, all the logic and UI defined in ChatWidget.tsx are rendered at this position on the page. */}
    </main>
  );
}