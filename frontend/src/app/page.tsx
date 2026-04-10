"use client";

import { useEffect, useState } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";
import { LoginForm } from "@/components/LoginForm";
import * as api from "@/lib/api";

export default function Home() {
  const [user, setUser] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    api.checkSession()
      .then((data) => setUser(data?.username ?? null))
      .finally(() => setChecking(false));
  }, []);

  const handleLogout = async () => {
    await api.logout();
    setUser(null);
  };

  if (checking) return null;

  if (!user) return <LoginForm onLogin={setUser} />;

  return <KanbanBoard username={user} onLogout={handleLogout} />;
}
