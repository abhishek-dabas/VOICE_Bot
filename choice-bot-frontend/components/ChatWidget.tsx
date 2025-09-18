// file: components/ChatWidget.tsx

"use client"; // This directive marks the component as a "Client Component" in a Next.js or React Server Components (RSC) application.
/* By default, Next.js renders components on the server for performance. However, features like state management (useState), event handling (onClick), and browser-specific APIs (like the microphone in this case) require JavaScript to run on the client side.
   The "use client"; directive tells the bundler to send this component to the user's browser, enabling interactive functionality.
*/

import React, { useState, useEffect, useRef } from "react"; // This line imports 3 React hooks from react library.
// useState - It helps to add state variables to functional component.
// useEffect - It helps to perform side effects in functional component like data fetching or manually interacting with DOM.
// useRef - It allows a component to persist(hold) a value between renders without causing a re-render when the value changes. It is used to store a reference to a DOM element or mutable value.
// These hooks helps us to build dynamic and interactive components in modern React.
import MicRecorder from "mic-recorder-to-mp3"; // It imports a 3rd party library that provides an easy way to record audio from user's microphone and convert it into an MP3 file.
import { FiMic, FiSend, FiX, FiVolume2, FiGlobe } from "react-icons/fi"; // It imports icon components from react-icons library which bundles popular icons like Feather icons(fi).
import { text } from "stream/consumers";
import { connect } from "http2";
import { constrainedMemory } from "process";
import { read } from "fs";
import { WiSandstorm } from "react-icons/wi";
// Instead of manually managing SVG files, this library provides a simple way to use a vector icons as React components, improving the visual design.

// --- Data Types ---
type Message = { // It defines a custom Typescript type called message. Message object has 2 properties -
  sender: "user" | "bot"; // A string which can only be either user or bot. It helps to distinguish that who sent the message.
  text: string; // It holds content of the message
}; // By using Typescript types it enforces structure and catches error if data is not passed around in expected format.

type Language = "en" | "hi"; // Another custom Typescript type. It enhances type safety for language-related functionality.

// -- Constants --
const CLIENT_ID = "client_demo"; // This should be dynamically set based on where the widget is embedded.
// CLIENT_ID used by backend server to recognize a specific user chat widget instance. it allows the server to manage different connections and retrieve session info or caht history for specific client.
// For production, CLIENT_ID shouldm't be hardcoded like "client_demo" as it will share the same identity. This means a conversation data could be mixed or exposed to the wrong user.
// For a real application, the CLIENT_ID should be generated dynamically and securely. For example, it could be a unique value passed into the component as a prop, fetched from an API, or retrieved from a cookie or local storage.
const WEBSOCKET_URL = 'ws://localhost:8000/ws/${CLIENT_ID}'; // It creates another constant, WEBSOCKET_URL. Chat application requires persistent, two way communication for sending and receiving messages instantly. Websocket is designed for this purpose only.
// The use of ...//localhost:8000.... shows that it is set up for local development. In production, this will be replaced by secure, public URL (Eg. wss://api.yourdomain.com/ws/${CLIENT_ID})

// -- Audio Player Component --
const AutoPlayingAudioPlayer = ({ src }:{ src: string}) => { // AudioPlayingAudioPlayer is a dedicated React component designed to handle and auto. play audio.
  // Its taking one argument/prop as src which is the URL of the audio file and return must be a string. This Typescript syntax makes this reusable & easy to understand.
  const audioRef = useRef<HTMLAudioElement>(null); // Here useRef hook is to create a persitent reference to a DOM element. <HTMLAudioElement> tells TypeScript that this ref. will be attached to <audio> HTML element.
  // It is initialised with null because the element doesn't exist until the component is rendered.

  useEffect(() => { // Here useEffect hook runs a side effect when src prop changes.
    if (audioRef.current) { // It checks and ensures that if audioRef is attached to <audio> HTML element and is not Null before trying to interact with it.
      audioRef.current.play().catch(e => console.error("Audio autoplay failed:", e)); // It calls built in JavaScript play() function on audio element which starts playback.
      // catch() handles potential errors cuz browsers often block audio autoplay unless user triggers it. If autoplay is blocked then it catches that error and prevent the application from crashing.
    }
  }, [src]); // It tells React to re run the effect only when src prop changes so that every time a new audio URL is provided, it attempts to play the new sound file.
  // This pattern responds auto. to changes in the audio source while handling browser autoplay restrictions. It is a reliable way to handle side effect of playing audio in React component.

  return <audio ref={audioRef} src={src} controls style={{ display: "none"}} />; // This returns JSX(Javascript XML - It is a syntax extension for JS that allows you to write HTML-like code directly within your JS files) for an HTML <audio> element.
  // ref={audioRef} - Attached audioRef to this element so that hook can access it
  // src={src} - Sets the sourc of the audio.
  // controls - Here visual controls are hidden by the 'style' attribute but in some browsers, this is neecessary for playback to function correctly.
  // style={{ display: "none" }} - This CSS style hides audio player from the user, so audio will run in background without showing audio player.
};

// -- Main Chat Component --
// The below code defines the ChatWidget functional component, using REact hooks to manage the state and access DOM elements for the chat application.
// useState hook allows a component to remember state. It returns a pair: the current state value & function to update it.
// When the state is updated, React re-renders the component to reflect the new value.
export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(true);  // Default open for demonstration
  // isOpen - A boolean variable which check whether chat widget is currently open or closed.
  // setIsOpen - The function used to change the value of isOpen. Eg - setIsOpen(false) would close the chat widget.
  // useState(true) - Initializes the chat widget to be open by default.
  const [messages, setMessages] = useState<Message[]>([]);
  // messages - An array state variable that stores all the chat messages. 
  // setMessages - The function to add new messages or update existing one in the chat history.
  // useState([]) - Initializes the chat message history as an empty array. The <Message[]> TS syntax specifies that it must be an array of Message object.
  const [inputValue, setInputValue] = useState("");
  // inputValue - A string state variable that holds the current text value of the user's input field.
  // setInputValue - The function to update the input field as the user types.
  // useState("") - Initializes the input value as an empty string.
  const [isRecording, setIsRecording] = useState(false);
  // isRecording - A boolean state variable which tracks that the user is recording audio or not.
  // setIsRecording - The function to toggle the recording status.
  // useState(false) - Initializes the recording status to false, since the user is not recording at the start.
  const [currentLanguage, setCurrentLanguage] = useState<Language>("en");
  // currentLanguage - A state variable which hold currently selected language, using custom Language type.
  // setCurrentLanguage - The function to change the language.
  // useState("en") - Initializes the chat language to English.
  const [ws, setWs] = useState<WebSocket | null>(null);
  // ws - A state variable which holds the WebSocket connection object.
  // setWs - The function to store the WebSocket connection object once it is established.
  // useState<WebSocket | null>(null) - Its initialized to null because the connection doesn't exist. The <WebSocket | null> annotation shows that it can either a WebSocket object or null.
  const [audioQueue, setAudioQueue] = useState<string[]>([]);
  // audioQueue - An array state variable that acts as a queue for audio files(stored as their URLs). It is used to handle situations where multiple bot responses arrive in quick succession.
  // setAudioQueue - The function to add or remove audio files from the queue.
  // useState([]) - Initializes the audio queue as an empty array. 

  // The useRef hook returns a mutable ref object whose .current property can be set to any value. Unlike state, updateing ref doesn't trigger a re-render.
  // This make it ideal for those values for storing things that are needed throughout the component's life.
  const recorderRef = useRef<MicRecorder | null>(null);
  // useRef<MicRecorder | null>(null) - Intializes the reference to null. It will hold the MicRecorder object once its created, so its method can be called(eg. to start/stop recording)
  const messagesEndRef = useRef<HTMLDivElement>(null);
  // useRef<HTMLDivElement>(null) - Intializes the ref. to null which will be attached to <div> in the JSX, allowing the componemt to programmatically scrool to the bottom of the message list whenever a new message is added.

// -- WebSocket Connection Handling --
// useEffect hook runs the contained function after 1st renders & subsequent renders, depending on its dependency array.
// In this case, the hook runs once when the component mounts becoz it is missing a dependency array & returns a cleanup function that handles component unmount.
// Side effects like establishing a WebSocket connection should be handled inside useEffect to avoid issues like memory leaks or re-connecting connections on every render.
useEffect(() => {
  const connectWebSocket = () => { // This function contains all the logic for creatibg & configuring the WebSocket connection.
    // Crerating a nested function makes it easier to call this login for both intial connection & for reconnecting after a disconnect.
    const socket = new WebSocket(WEBSOCKET_URL); // It creates a new WebSocket instance intiating the connection to the URL.

    socket.onopen = () => { // The onopen event is the right place to perform actions that depend on a successful connection.
      console.log("WebSocket connection established.");
      setWs(socket); // It stores the active 'socket' object ib the component's state using setWs().
    };

    socket.onmessage = event => { // It triggers whenever the client receives a message from the server.
      const data = JSON.parse(event.data); // This function parses the 'event.data'(string type) as JSON and then the update the component's state based on the message type.
      // Standard practice for transmitting structured data over WebSockets, allowing the client to easily access different properties like type and text.

      if (data.type === "response") { // This block handles standard text & audio response from the bot.
        setMessages(prev => [...prev, { sender: "bot", text: data.text}]); // It updates the chat messages state and appends the new bot message at the end of the existing messages.
        // prev is the previous state, ensuring message aren't lost in the update.
        if (data.audio_url) { // It checks if the message includes an audio URL.
          const fullAudioUrl = 'http://localhost:8000${data.audio_url}'; // It completes URL for the audio file by prepending the base URL.
          setAudioQueue(prev => [...prev, fullAudioUrl]); // adds the full audio URL to the audio queue state so the 'AutoPlayingAudioPlayer' component can play it.
        }
      } else if (data.type === "user_message") { // It handles the server's confirmation of a transcribed user message.
        // Display user's transcribed text. 
        setMessages(prev => [...prev, { sender: "user", text: data.text}]); // Its useful to display & final version of user's voice message before the bot's response comes in.
      } else if (data.type === "error") { // This handles error messages from the server, logging them and displaying an error message in the chat.
        console.error("Server Error:", data.message); // roper error handling provides feedback to the user and helps with debugging.
        setMessages(prev => [...prev, {sender: "bot", text: 'Error: ${data.message}' }]);
      }
    };

    socket.onclose = () => { // The onclose event fires when the connection is terminated.
      console.log("WebSocket connection closed. Reconnecting..."); // It is used to handle disconnections gracefully.
      setTimeout(connectWebSocket, 3000); // Reconnect logic
      // The setTimeout function implements a reconnection strategy, attempting to re-establish the connection after a 3-second delay, which makes the widget more resilient to network issues. 
    };

    socket.onerror = error => { // The onerror event fires if a connection error occurs.
      console.error("WebSockeet error:", error); // It provides a specific place to log and handle WebSocket errors.
      socket.close(); // Calling s 'socket.close()' within the handler ensures the clean shutdown after an error, which will then trigger the onclose logic to attempt a reconnect.
    };
  };

  connectWebSocket(); // The 'useEffect' hook immediately calls 'connectWebSocket' function, kicking off the process of establishing the connection as soon as the component mounts.
  
  //Intialize recorder instance
  // This block of code is very crucical part of 'useEffect' hook as these happen once: initializing audio recorder & defining cleanup functionto close the WebSocket connection when the component is unmounted.
  recorderRef.current = new MicRecorder({ bitRate: 128 }); // A new instance of 'MicRecorder' is created with recording quality to 128kbps.
  // By storing 'MicRecorder' instance inside 'useRef' hook instead of inside 'useState' is to ensure that the recorder object is created only once when the component is first mounted.
  // If it were in state, it might be re-created on every render, which is inefficient and also will disrupt our ongoing recording as well.

  return () => { // Cleanup function
    ws?.close(); // 'useEffect' hook return a function which React will run when the component unmmounts. It checks if WebSocket exists then calls close() method.
    // Failing to close WebSocket connection can cause memory leak. '?.' operator is used here to safely access close() method. It prevents TypeError if ws state is still null.
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  // The above line called linter rule is commented cuz we are sure that all the things mentioned in useEffect hook will be run once when its mounted.
}, []); // The eompty dependency tells React that this effect has no dependencies that would trigger it to re-run.

// -- Message Scroll --
// This block of code ensures that when a new message is added, the view scrolls down to show the most recent message at the bottom. 
useEffect(() => {
  messagesEndRef.current?.scrollIntoView({ behavior : "smooth"}); // messagesEndRef - This is the reference created earlier with useRef which is attached to empty <div>
  // .current - The way you can access the actual DOM element that the ref is pointing to.
  // ?. - It will help our code to not to throw error if messagesEndRef.current is null(which it will be on intial render).
  // scrollIntoView() - It is JS method which scrolls the page and its behavior tells the browser to animate the scroll.
}, [messages]); // It is a dependency array for this hook. By adding it as dependency array, it ensures that scrolling code is executed always whenever a new message is added.

// -- Core Actions --
const handleSendMessage = () => { // This function is responsible for processing abd sending a user's text input. It gets triggered when a user hits enter or click on send button.
  if (!inputValue.trim() || !ws || ws.readyState ! == WebSocket.OPEN) return; // Its a guard clause that performs the checks to ensure that message can be sent safely. The 'return' statement immediately exits if any condition is true.
  // !inputValue.trim() - Checks if the inputValue state variable is empty or contains only whitespace. The .trim() method removes leading and trailing whitespace.
  // !ws - Checks if the WebSocket connection object (ws) is null, meaning a connection has not been established yet.
  // ws.readyState !== WebSocket.OPEN: Checks if the WebSocket connection is in the OPEN state. It prevents sending messages while the connection is still connecting, closing, or already closed.

  ws.send(JSON.stringify({ type: "text_query", text: inputValue })); // It sends the message to WebSocket server.
  // JSON.stringify() converts JS object into JSON string
  setMessages(prev => [...prev, {sender: "user", text: inputValue }]); // It updates the local chat state with the user's message.
  // prev => [...] - This is a functional update. It uses the previous state (prev) to derive the next state, which is a best practice for avoiding race conditions with state updates.
  // ...prev - This spreads all the existing messages from the previous state into a new array.
  setInputValue(""); // This line resets the input field by setting the inputValue state back to an empty string. This clears the text box for the user's next message. 
};

const handleLanguageToggle = () => { // This function switches the conversation language.
  const newLang = currentLanguage === "en" ? "hi" : "en"; 
  // This line uses a ternary operator to toggle the language. It checks if the currentLanguage is "en" (English). If it is, newLang is set to "hi" (Hindi); otherwise, it's set to "en".
  setCurrentLanguage(newLang); // It updates the currentLanguage state with the newly selected language. This will cause the component to re-render. 
  if (ws && ws.readyState === WebSocket.OPEN) { // The if condition checks that the WebSocket connection(ws) is available and open before attempting to send the message
    ws.send(JSON.stringify({ type: "language_switch", language: newLang})); // t sends a JSON object with a type of "language_switch" and the newLang value.
    // This tells the server to start processing future user messages in the new language. 
  }
  console.log('Language switched to ${newLang}');
};

// -- Voice Input Handling --
const startRecording = () => { // This function initiates the audio recording process.
  navigator.mediaDevices.getUserMedia({ audio: true}) // It is a modern browser API call to request access to user's media devices. This is standard and secure way to ask user's permission(browser dialog box) to access microphone.
  // audio: true tells the browser that this application only needs access to microphone.
    .then(() =>  {
      recorderRef.current?.start().then(() => { // Calls the start() method on the recorder instance.
        // The ?. ensures that it doesn't fail if ref is not yet set.
        // The start() method returns a promise that resolves when the recording has started.
        // .then(() => { setIsRecording(true); });: When the recording successfully starts, this handler is executed, and it updates the isRecording state to true, which can be used to update the UI (e.g., change the microphone icon's appearance). 
        setIsRecording(true);
      });
    })
    .catch(error => console.error("Microphone access denied: ", error)); // It is the error handler for the getUserMedia promise.
    // It is executed the user denies the microphone access or if any other error.
};

const stopRecording = () => { // This function handles stopping the recording, processing the audio and sending it to the server.
    recorderRef.current?.stop().getMp3().then(([buffer, blob]) => { // It is a chained promise call to stop the recorder and get teh resulting mp3 audio.
      // recorderRef.current?.stop(): Calls the stop() method, which ends the recording.
      // .getMp3(): This method, provided by the mic-recorder-to-mp3 library, processes the recorded audio and returns a Promise.
      // .then(([buffer, blob]) => { is the success handler for the getmp3() promise. It receives the audio data as a buffer (ArrayBuffer) and a blob (Blob object).
      setIsRecording(false); // This immediately updates the state to reflect that the recording has stopped, which will update the UI.
      // Convert blob to base64 string to send via JSON/WebSocket
      const reader = new FileReader(); // It creates a new instance of the built -in FileReader object. 
      reader.readAsDataURL(blob); // It tells the FileReader to begin reading the contents of the audio blob. The result will be a data: URL, which includes the data encoded in Base64.
      reader.onloadend = () => { // This function executes after the FileReader has finished reading the data. It ensures that the rest of code is executed only after asynchronous reading operation is completed.
        const base64data = reader.result?.toString().split(',')[1]; // It extracts the raw Base64 string from the full data: URL.
        // reader.result - This property holds the completed data: URL string.
        // ?.toString() - Converts the result to a string (with optional chaining for safety).
        // .split(',')[1]: A data: URL is structured like data:audio/mp3;base64,LONG_BASE64_STRING. This command splits the string at the comma and takes the second part, which is the raw Base64 data.
        if (base64data && ws && ws.readyState === WebSocket.OPEN) { // A final safety check to ensure that Base64 data was extracted & it prevents from sending invalid data or over a closed connection.
          ws.send(JSON.stringify({ type: "audio_query", audio_data: base64data })); // It sends the encoded audio data to the server via WebSocket.
          // The server will liekly use the audio_data to perform speech-to-text transcription.
        }
      };
    });
  };

const handleMicClick = () => { // This function servers as a single event handler that orchestrates the starting and stopping of the voice recording feature.
  if (isRecording) { // isRecording state is a boolean that tracks whether the mic is currently active.
    // The button's behavior must change depending on the current state. If recording already in progress(isRecording is true) then after the button is clicked it should stop recording.
    stopRecording(); // It executes the logic for stopping the recorder, process the audio and sending it to the WebSocket server. 
  } else {
    startRecording(); // It executes the logic for requesting mic permission, starting the recorder and changing the isRecording state to true
  }
}; 

return ( // In a React component, return is what provides the markup that React will render to the DOM.
    // This block of JSX code renders the header section of the chat widget, which contains title, bot status and control buttons.
    // It uses conditional rendering to show the full chat interface only when the isOpen is true.
    <div className="fixed bottom-4 right-4 w-full max-w-md font-sans"> {/* Outermost container of entire chat widget */}
    {/* w-full max-w-md - Sets the width to 100% on small screens but caps it max. if md(448px), preventing it from becoming too large on desktop displays 
        fixed: Positions the element relative to the browser window.
        bottom-4 right-4: Places the widget 1rem (4 * 0.25rem) from the bottom and right edges of the viewport.*/}
      {isOpen ? ( // This is conditional rendering statement using a ternary operator. It checks if isOpen is true and if it is, it renders the JSX that follows.
        <div className="flex flex-col h-[600px] bg-white rounded-xl shadow-2xl border border-gray-200 overflow-hidden"> {/* This is the container for chat panel 
        flex flex-col - Uses Flexbox to arrange child elements(header, messages, footer) in a vertical column
        rounded-xl - Applies large, rounded corners to the container.
        shadow-2xl - Applies a strong drop shadow to make the widget stand out.
        overflow-hidden - Hides any content that might overflow the container, ensuring the rounded corners work correctly.*/}
          {/* Header */}
          <header className="flex items-center justify-between p-4 bg-gray-50 border-b border-gray-200"> {/* flex items-center justify-between - Uses Flexbox to align items vertically and place them on opposite ends of the header.
          p-4: Adds padding. border-b border-gray-200: Adds a bottom border to separate the header from the message area.*/}
            <div> {/* This div contains the bot's names and online status. */}
              <h3 className="text-lg font-bold text-gray-800">Choice Bot Assistant</h3> {/*text-lg font-bold text-gray-800 - Tailwind classes for styling the text.*/}
              <p className="text-xs text-green-600 font-medium">Online</p> 
            </div>
            <div className="flex items-center space-x-3"> {/* div groups the action buttons on the right side of the header */}
              <button
                onClick={handleLanguageToggle} // A button for toggling the language.
                className="p-2 rounded-full hover:bg-gray-200 text-gray-600 transition-colors" 
                title={`Switch to ${currentLanguage === "en" ? "Hindi" : "English"}`} // A dynamic title that provides a tooltip based on the current language state.
              >
                <FiGlobe className="w-5 h-5" /> {/* Renders the globe icon from the react-icons/fi library. */}
              </button>
              <button
                onClick={() => setIsOpen(false)} // Uses an inline arrow function to call setIsOpen state setter with false, hiding the chat panel.
                className="p-2 rounded-full hover:bg-gray-200 text-gray-600 transition-colors"
                title="Close chat" /* Provides a tooltip for the button. */
              >
                <FiX className="w-5 h-5" /> {/* Renders the "X" icon for closing the chat widget. */}
              </button>
            </div>
          </header>

          {/* Message Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-100/50"> {/* This div contains the list of messages. It uses several tailwind CSS classes for styling. 
          flex-1 - This utility takes up all available vertical space within its parent container(flex flex-col), pushing the input are to the bottom.
          overflow-y-auto - It enables vertical scrolling if the message exceeds the container's height
          space-y-4 - Adds vertical spcaing between each message element */}
            {messages.map((msg, index) => ( // Its JS map() function called on messages array. It loops through every msg obejct in the array adn runs the code for each one.
              <div key={index} className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}> {/* This is the container for a single message bubble. 
              key={index} - It is a special attribute that React uses to tack rach element in the list. It helps React to identify which items have been changed,added or deleted which optimizes performance.
              In production, instead of index use a unique ID for each message would be better taht supports deleting or reordering messages.
              ${msg.sender === "user" ? "justify-end" : "justify-start"}: This is a template literal with a ternary operator. It checks the sender property of the msg object.
              If sender is is "user", the justify-end class will be added and message bubble will be aligned to the right side of the container. 
              If sender is is "bot", the justify-start class will be added and message bubble will be aligned to the left side of the container.*/}
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-2 shadow-sm ${ // max-w-[80%] - It ensures the message bubble doesn't take up more than 80% of chat window's width.
                    // shadow-sun -  Applies a small drop shadow for a subtle visual effect.
                    msg.sender === "user" // Another ternary operator which will apply different background colors and text colors based on the sender.
                      ? "bg-blue-600 text-white" // User messages - A solid blue background with white text.
                      : "bg-white text-gray-800 border border-gray-100" // Bot messages - A white background with gray text and a light gray border. 
                  }`}
                >
                  <p className="text-sm">{msg.text}</p> {/* This p element displays the actual text content of the message. The {msg.text} part is a JSX expression that inserts the text property of the current msg object. */}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} /> {/* This is the empty div element. 
            This attaches the messagesEndRef created with useRef to this element. The useEffect hook that handles scrolling uses this ref to scroll the container to this element's position, ensuring the chat stays at the bottom.*/}
          </div>

          {/* Input Area */} {/* This code block renders the input area of chat widget, includingtext input field, mic button and send button. It also handles the conditional rendering of an open/close button for the entire widget. */}
          <footer className="border-t border-gray-200 p-3 bg-white"> {/* Defines bottom section of the chat panel. border-t border-gray-200 - It adds a top border to visually spearate it from message area. */}
            <div className="flex items-center space-x-2"> {/* This div acts as flex container for the input field and buttons. */}
              <input
                type="text"
                value={inputValue} // It sets the input's value to the inputValue state.
                onChange={e => setInputValue(e.target.value)} // Updates the inputValue state every time the user types. 
                // The e.target.value gets the current content of the input field.
                onKeyPress={e => e.key === "Enter" && handleSendMessage()} // Triggers the 'handleSendMessage()' function when user presses enter key inside the input field.
                placeholder={isRecording ? "Listening..." : "Type your message..."} // Dynamically changes the placeholder text based on the isRecording state.
                className="flex-1 px-4 py-2 border border-gray-300 rounded-full focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                disabled={isRecording} // Disables the input field when isRecording is True, preventing user from typing while a voice recording is in progress. 
              />
              <button
                onClick={handleMicClick} // Triggers the handleMicClick function, which toggles between starting and stopping the recording.
                className={`p-3 rounded-full transition-colors focus:outline-none ${
                  isRecording // Dynamically applies different styles based on the isRecording state using a template.
                    ? "bg-red-500 text-white animate-pulse" // If isRecording is true: The button turns red (bg-red-500), the text turns white (text-white), and it gets a pulsing animation (animate-pulse).
                    : "bg-gray-200 hover:bg-gray-300 text-gray-700" // If isRecording is false: It has a light gray background (bg-gray-200) and darker text (text-gray-700).
                }`}
              >
                <FiMic className="w-5 h-5" /> {/* Renders the microphone icon inside the microphone button. */}
              </button>
              <button
                onClick={handleSendMessage} // Calls the handleSendMessage function when clicked.
                disabled={!inputValue.trim()} // Disables the button if the inputValue is empty or contains only whitespaces. This prevents the user from sending an empty message.
                className="p-3 rounded-full bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors focus:outline-none"
              >
                <FiSend className="w-5 h-5" />
              </button>
            </div>
          </footer>
        </div>
      ) : ( // This is the else part of the conditional rendering. It is executed if isOpen is false.
        <button
          onClick={() => setIsOpen(true)} // When clicked, it sets the isOpen state to true, which causes the main chat panel to render.
          className="p-4 bg-blue-600 rounded-full shadow-lg text-white hover:bg-blue-700 transition-transform hover:scale-105"
        >
          <FiVolume2 className="w-8 h-8" /> {/* Renders a speaker icon for the closed chat button. */}
        </button>
      )}
      {/* Audio player logic */}
      {/* It implements a queuing system for audio messages from the bot, ensuring they are played one at a time in the order they were received. */}
      {audioQueue.length > 0 && ( // This is the conditional rendering statement and the expression on the left is evaluated first.
      // If the audioQueue array contains at least one item, the expression is true and React proceeds to evaluate and render the JSX on the right side.
      // If the audioQueue is empty (length is 0), the expression is false and React renders nothing so AutoPlayingAduioPlayer is not rendered.
        <AutoPlayingAudioPlayer // This renders the AutoPlayingAudioPlayer component defined earlier. 
            src={audioQueue[0]} // This is the first item in the audioQueue & it uses src prop to laod and play audio file.
            // By always passing the first item in the queue, we ensure a sequence of playback. THe useEffect hoook inside this function is configured to trigger playback whenever the src prop changes.
            key={audioQueue[0]} // Re-render component when src changes
            // When React renders the list of components, it uses the key prop to determine which items are new, changed or removed. Even though it's a list, using dynamic key force React to unmount and mount the AutoPlayingAudioPlayer whenever src changes.
            // By changing the key, it ensures that a new component is created which is reliable way to reset the component's internal state & force a fresh audio stream.
            // It helps to prevent issues with the audio player continuing to play an old stream or behaving unexpectedly.  
        />
      )}
    </div>
  );
}
