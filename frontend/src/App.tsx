import {
  useCallback,
  useState,
} from "react";

import SplashScreen from
  "./components/splash/SplashScreen";

import Dashboard from
  "./components/dashboard/Dashboard";

import LandingPage from
  "./pages/LandingPage";

type Screen =
  | "landing"
  | "console";

export default function App() {
  const [
    showSplash,
    setShowSplash,
  ] = useState(true);

  const [
    screen,
    setScreen,
  ] = useState<Screen>(
    "landing",
  );

  const finishSplash =
    useCallback(() => {
      setShowSplash(false);
    }, []);

  if (showSplash) {
    return (
      <SplashScreen
        onComplete={
          finishSplash
        }
      />
    );
  }

  if (screen === "console") {
    return (
      <Dashboard
        onBack={() =>
          setScreen("landing")
        }
      />
    );
  }

  return (
    <LandingPage
      onOpenConsole={() =>
        setScreen("console")
      }
    />
  );
}