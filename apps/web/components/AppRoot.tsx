"use client";
import { Loader2 } from "lucide-react";
import { AuthProvider, useAuth } from "@/lib/auth";
import AuthScreen from "./AuthScreen";
import Workspace from "./Workspace";

function Gate() {
  const { user, loading } = useAuth();
  if (loading) {
    return <div className="flex min-h-screen items-center justify-center"><Loader2 className="animate-spin text-brand-soft" /></div>;
  }
  return user ? <Workspace key={user.id} /> : <AuthScreen />;
}

export default function AppRoot() {
  return <AuthProvider><Gate /></AuthProvider>;
}
