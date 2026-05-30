import { ChatContainer } from "@/components/chat/ChatContainer";

export default function Home() {
  return (
    <main className="relative flex flex-1 flex-col overflow-hidden px-3 py-3 sm:px-5 sm:py-5 lg:px-8 lg:py-7">
      <ChatContainer />
    </main>
  );
}
