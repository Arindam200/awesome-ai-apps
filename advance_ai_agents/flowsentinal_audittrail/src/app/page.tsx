import Header from "@/components/Header";
import Dashboard from "@/components/Dashboard";

export default function Home() {
  return (
    <main className="h-screen flex flex-col overflow-hidden bg-bg">
      <Header />
      <Dashboard />
    </main>
  );
}
